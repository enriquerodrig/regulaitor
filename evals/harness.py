"""H8 — Evaluation harness orchestration.

Loads the gold set, runs each case through the H4 chat graph or H5 document
graph (with cache), computes metrics + judge scores, and writes the
markdown report.
"""

from __future__ import annotations

import subprocess
import time
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from evals.cache import cache_call, estimate_cost_eur
from evals.judge import score_criteria
from evals.metrics import aggregate, compute_chat_metrics, compute_doc_metrics
from evals.report import render_report
from evals.schemas import (
    ChatCaseResult,
    DocCaseResult,
    EvalRunMeta,
    GoldCaseChat,
    GoldCaseDoc,
)
from regulaitor.citation.schemas import DocumentReport
from regulaitor.orchestration.document_graph import run_document
from regulaitor.orchestration.graph import run as run_chat
from regulaitor.orchestration.state import ChatState

_GOLD_PATH = Path("evals/gold_set.jsonl")
_DOC_DIR = Path("evals/document_cases")
_REPORT_PATH = Path("evals/reports/latest.md")
_PRODUCTION_MODEL = "claude-sonnet-4-6"
_JUDGE_MODEL = "claude-haiku-4-5-20251001"


def _git_sha_short() -> str:
    """Returns the first 7 chars of HEAD; falls back to 'unknown' on failure."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        )
        return out.strip()[:7]
    except Exception:  # noqa: BLE001 — best-effort metadata, never block harness
        return "unknown"


def load_gold_set(
    *, gold_path: Path = _GOLD_PATH, doc_dir: Path = _DOC_DIR
) -> tuple[list[GoldCaseChat], list[GoldCaseDoc]]:
    """Load chat cases from gold_set.jsonl + doc cases from document_cases/*.expected.json."""
    chat_cases: list[GoldCaseChat] = []
    if gold_path.exists():
        with gold_path.open(encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                chat_cases.append(GoldCaseChat.model_validate_json(stripped))

    doc_cases: list[GoldCaseDoc] = []
    if doc_dir.exists():
        for manifest in sorted(doc_dir.glob("*.expected.json")):
            doc_cases.append(GoldCaseDoc.model_validate_json(manifest.read_text(encoding="utf-8")))

    return chat_cases, doc_cases


def _real_anthropic_invoke(
    *, model: str, system: str, user: str, temperature: float, max_tokens: int
) -> tuple[str, int, int]:
    """Live Anthropic invocation. Imports lazily so unit tests don't require API key."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        system=system,
        messages=[{"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    return text, response.usage.input_tokens, response.usage.output_tokens


def run_chat_case(
    case: GoldCaseChat,
    *,
    cache_only: bool,
) -> tuple[ChatState, int, float, bool]:
    """Run one chat case through the H4 graph. Returns (state, latency_ms, cost_eur, cache_hit).

    NOTE: H4 graph.run does its own LLM invocation through anthropic SDK,
    without going through evals.cache. For H8 MVP we accept that the cache
    is at the JUDGE layer only (judge calls go via cache_call), and the
    production calls always hit the API. cache_hit reflects judge-layer only.
    Spec §6.4 documents this.
    """
    case_id = f"eval-{case.id}"
    t0 = time.monotonic()
    state = run_chat(
        query=case.entrada,
        corpus=case.corpus_esperado,
        language="es",
        case_id=case_id,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)

    # Cost estimation: extract tokens from state if available; fallback to heuristic.
    # H4's _log_turn doesn't surface tokens; ~3000 input + 800 output per chat case
    # on Sonnet is the tested approximation.
    estimated_cost_eur = estimate_cost_eur(model=_PRODUCTION_MODEL, tokens_in=3000, tokens_out=800)
    return state, latency_ms, estimated_cost_eur, False


def run_doc_case(
    case: GoldCaseDoc,
    *,
    cache_only: bool,
) -> tuple[DocumentReport, int, float, bool]:
    """Run one doc case through H5 pipeline.

    Returns (report, latency_ms_total, cost_eur, cache_hit).
    """
    pdf_path = _DOC_DIR / case.pdf_path
    file_bytes = pdf_path.read_bytes()
    case_id = f"eval-{case.id}"
    t0 = time.monotonic()
    report = run_document(
        file_bytes=file_bytes,
        mime_type="application/pdf",
        language="es",
        corpus=list(case.corpus_esperado),
        case_id=case_id,
    )
    latency_ms_total = int((time.monotonic() - t0) * 1000)
    # Estimate ~30k input + 8k output per doc on Sonnet
    estimated_cost_eur = estimate_cost_eur(
        model=_PRODUCTION_MODEL, tokens_in=30_000, tokens_out=8_000
    )
    return report, latency_ms_total, estimated_cost_eur, False


def main(
    *,
    gold_set_path: Path = _GOLD_PATH,
    subset: int | None = None,
    cache_only: bool = False,
) -> None:
    """Entry point. Loads gold, runs all cases, writes the report."""
    chat_cases, doc_cases = load_gold_set(gold_path=gold_set_path)

    if subset is not None:
        chat_cases = chat_cases[: max(0, subset)]
        doc_cases = doc_cases[: max(0, subset // 3)]  # 30:10 ratio in gold set

    # Bound cache_call to cache_only mode for the judge invocations
    judge_call = partial(cache_call, invoke=_real_anthropic_invoke, cache_only=cache_only)
    judge_score_fn = partial(score_criteria, cache_call=judge_call)

    chat_results: list[ChatCaseResult] = []
    for case in chat_cases:
        state, latency_ms, cost_eur, cache_hit = run_chat_case(case, cache_only=cache_only)
        result = compute_chat_metrics(
            case,
            state,
            judge_call=judge_call,
            judge_score_fn=judge_score_fn,
            latency_ms=latency_ms,
            cost_eur=cost_eur,
            cache_hit=cache_hit,
        )
        chat_results.append(result)

    doc_results: list[DocCaseResult] = []
    for case in doc_cases:
        report, latency_ms, cost_eur, cache_hit = run_doc_case(case, cache_only=cache_only)
        result = compute_doc_metrics(
            case,
            report,
            judge_call=judge_call,
            judge_score_fn=judge_score_fn,
            latency_ms_total=latency_ms,
            cost_eur_total=cost_eur,
            cache_hit=cache_hit,
        )
        doc_results.append(result)

    agg = aggregate(chat_results, doc_results)
    meta = EvalRunMeta(
        run_date=datetime.now(UTC).isoformat(),
        commit_sha=_git_sha_short(),
        production_model=_PRODUCTION_MODEL,
        judge_model=_JUDGE_MODEL,
        temperature=0.0,
        subset=subset,
        cache_only=cache_only,
    )
    markdown = render_report(meta, agg, chat_results, doc_results)
    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_PATH.write_text(markdown, encoding="utf-8")
