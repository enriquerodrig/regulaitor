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

from evals.cache import cache_call
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
from regulaitor.corpus import loader as corpus_loader
from regulaitor.models import router as _router
from regulaitor.orchestration.document_graph import run_document
from regulaitor.orchestration.graph import run as run_chat
from regulaitor.orchestration.state import ChatState

_GOLD_PATH = Path("evals/gold_set.jsonl")
_DOC_DIR = Path("evals/document_cases")
_REPORT_PATH = Path("evals/reports/latest.md")
# report metadata label only; actual model is set by the router mode
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
    *,
    gold_path: Path = _GOLD_PATH,
    doc_dir: Path = _DOC_DIR,
    case_ids: set[str] | None = None,
) -> tuple[list[GoldCaseChat], list[GoldCaseDoc]]:
    """Load chat cases from gold_set.jsonl + doc cases from document_cases/*.expected.json.

    When case_ids is given, only cases whose .id is in the set are returned
    (applied to BOTH chat and doc cases). None = all (unchanged behavior).
    """
    chat_cases: list[GoldCaseChat] = []
    if gold_path.exists():
        with gold_path.open(encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                gc = GoldCaseChat.model_validate_json(stripped)
                if case_ids is None or gc.id in case_ids:
                    chat_cases.append(gc)

    doc_cases: list[GoldCaseDoc] = []
    if doc_dir.exists():
        for manifest in sorted(doc_dir.glob("*.expected.json")):
            dc = GoldCaseDoc.model_validate_json(manifest.read_text(encoding="utf-8"))
            if case_ids is None or dc.id in case_ids:
                doc_cases.append(dc)

    return chat_cases, doc_cases


def _anthropic_client_factory() -> object:
    """Return a live anthropic.Anthropic() client.

    Defined as a module-level function so tests can monkeypatch it
    (``monkeypatch.setattr(harness, "_anthropic_client_factory", ...)``)
    without needing a real ANTHROPIC_API_KEY at import time.
    The lazy ``import anthropic`` keeps the module importable without the SDK
    installed or the key set (mirrors the existing lazy-import intent).
    """
    import anthropic

    return anthropic.Anthropic()


def _real_anthropic_invoke(
    *, model: str, system: str, user: str, temperature: float, max_tokens: int
) -> tuple[str, int, int]:
    """Live Anthropic invocation with bounded tenacity retry on transient errors.

    Imports lazily so unit tests don't require API key at import time.
    Retries on OverloadedError (529), RateLimitError, APITimeoutError,
    APIConnectionError, and InternalServerError — mirroring the router.py
    tenacity config (stop_after_attempt(3), wait_exponential(multiplier=1,
    min=1, max=10)) and adding OverloadedError which was the specific 529
    that crashed the H15 holdout run. Bounded: re-raises after exhausting
    attempts so sustained Anthropic degradation surfaces cleanly.
    H9/H11/H15 resilience lesson — mirrors router tenacity, adds OverloadedError.
    """
    # Lazy imports: keep ``import evals.harness`` API-key-safe and avoid
    # pulling in tenacity / anthropic exceptions at module load time.
    from anthropic._exceptions import (
        APIConnectionError,
        APITimeoutError,
        InternalServerError,
        OverloadedError,
        RateLimitError,
    )
    from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

    _transient = (
        OverloadedError,
        RateLimitError,
        APITimeoutError,
        APIConnectionError,
        InternalServerError,
    )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(_transient),
        reraise=True,
    )
    def _invoke() -> tuple[str, int, int]:
        client = _anthropic_client_factory()
        response = client.messages.create(
            model=model,
            system=system,
            messages=[{"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = "".join(b.text for b in response.content if b.type == "text")
        return text, response.usage.input_tokens, response.usage.output_tokens

    return _invoke()


def _error_doc_report(case_id: str, error_msg: str, corpus: list[str]) -> DocumentReport:
    """Build a sentinel DocumentReport for cases where the H5 pipeline raised."""
    from regulaitor.citation.schemas import AuditVerdict

    return DocumentReport(
        case_id=case_id,
        document_hash="0" * 64,
        language="es",
        corpus=corpus,
        sanitizer_log=[],
        segments=[],
        document_verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
        document_reason=f"harness_backend_error: {error_msg[:200]}",
        n_segments_total=0,
        n_segments_blocked_by_injection=0,
        n_segments_pass=0,
        n_segments_block=0,
        n_segments_review=0,
        latency_ms_total=0,
        cost_eur_total=0.0,
    )


def _error_chat_state(case_id: str, error_msg: str) -> ChatState:
    """Build a sentinel ChatState for cases where the backend raised.

    metrics.compute_chat_metrics handles audited_answer=None by mapping
    actual_verdict to requires_human_review (more honest than 'block'
    for backend errors). The errors list is preserved for the report.
    """
    return ChatState(
        case_id=case_id,
        query="(backend error)",
        corpus="ai_act",
        language="es",
        errors=[error_msg[:500]],  # truncate to keep logs hygienic
    )


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
    _router.reset_cost_accumulator()
    t0 = time.monotonic()
    try:
        state = run_chat(
            query=case.entrada,
            corpus=case.corpus_esperado,
            language="es",
            case_id=case_id,
        )
    except Exception as exc:  # noqa: BLE001 — per-case backend errors must not crash full run
        state = _error_chat_state(case_id, f"{type(exc).__name__}: {exc}")
    latency_ms = int((time.monotonic() - t0) * 1000)

    # H15 / ADR 0016 — real measured spend from router.complete() (closes the
    # H12/H13 estimate gap; the old fixed heuristic is removed).
    # 0.0 here means no complete() call occurred (e.g. backend raised pre-LLM);
    # that is a correct measured "no spend", not a missing measurement.
    measured_cost_eur = _router.get_accumulated_cost_eur()
    return state, latency_ms, measured_cost_eur, False


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
    _router.reset_cost_accumulator()
    t0 = time.monotonic()
    try:
        report = run_document(
            file_bytes=file_bytes,
            mime_type="application/pdf",
            language="es",
            corpus=list(case.corpus_esperado),
            case_id=case_id,
        )
    except Exception as exc:  # noqa: BLE001 — per-case backend errors must not crash full run
        report = _error_doc_report(
            case_id, f"{type(exc).__name__}: {exc}", list(case.corpus_esperado)
        )
    latency_ms_total = int((time.monotonic() - t0) * 1000)
    # H15 / ADR 0016 — real measured spend from router.complete() (closes the
    # H12/H13 estimate gap; the old fixed heuristic is removed).
    # 0.0 here means no complete() call occurred (e.g. backend raised pre-LLM);
    # that is a correct measured "no spend", not a missing measurement.
    measured_cost_eur = _router.get_accumulated_cost_eur()
    return report, latency_ms_total, measured_cost_eur, False


def main(
    *,
    gold_set_path: Path = _GOLD_PATH,
    subset: int | None = None,
    cache_only: bool = False,
    case_ids: set[str] | None = None,
) -> None:
    """Entry point. Loads gold, runs all cases, writes the report."""
    # Corpus loader must be populated before the retriever calls get_manifest_meta.
    # H4 chat graph and H5 document graph both depend on this. mcp_server does it
    # at startup; for the eval harness we do it here.
    corpus_loader.warmup()

    chat_cases, doc_cases = load_gold_set(gold_path=gold_set_path, case_ids=case_ids)

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
    for doc_case in doc_cases:
        report, latency_ms, cost_eur, cache_hit = run_doc_case(doc_case, cache_only=cache_only)
        doc_result = compute_doc_metrics(
            doc_case,
            report,
            judge_call=judge_call,
            judge_score_fn=judge_score_fn,
            latency_ms_total=latency_ms,
            cost_eur_total=cost_eur,
            cache_hit=cache_hit,
        )
        doc_results.append(doc_result)

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
