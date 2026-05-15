"""H9 — Red team runner orchestration.

Loads attacks from attacks.jsonl, dispatches each to its pipeline, captures
outcome, aggregates, renders report. Pure Python; no HTTP. Wraps H4 chat graph
and H5 document pipeline read-only per spec §H9 (no backend modification).
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from redteam.report import render_report
from redteam.schemas import (
    LAYERS_WITH_NONE,
    Attack,
    AttackAggregate,
    AttackOutcome,
    RedTeamRunMeta,
    ScenarioAggregate,
)
from regulaitor.citation.schemas import DocumentBlockedError
from regulaitor.corpus import loader as corpus_loader
from regulaitor.document import extractor as _extractor_mod
from regulaitor.document import sanitizer as _sanitizer_mod
from regulaitor.orchestration.document_graph import run_document
from regulaitor.orchestration.graph import run as run_chat
from regulaitor.security.injection import is_injection

_ATTACKS_PATH = Path("redteam/attacks.jsonl")
_DOC_DIR = Path("redteam/documents")
_REPORT_PATH = Path("redteam/reports/latest.md")

_CHAT_TIMEOUT_S = int(os.environ.get("REGULAITOR_REDTEAM_TIMEOUT_CHAT", "300"))
_DOC_TIMEOUT_S = int(os.environ.get("REGULAITOR_REDTEAM_TIMEOUT_DOC", "900"))


def extractor_extract(file_bytes: bytes, mime_type: str, language: str) -> Any:
    """Wrapper around regulaitor.document.extractor.extract for monkeypatch-friendly injection.

    The real extract() does not use language; the wrapper accepts it so the
    runner interface is uniform and tests can patch this symbol directly.
    """
    return _extractor_mod.extract(file_bytes=file_bytes, mime_type=mime_type)


def sanitizer_sanitize(raw: Any) -> Any:
    """Wrapper around regulaitor.document.sanitizer.sanitize for monkeypatch-friendly injection."""
    return _sanitizer_mod.sanitize(raw)


def _git_sha_short() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL
        )
        return out.strip()[:7]
    except Exception:  # noqa: BLE001
        return "unknown"


def load_attacks(path: Path = _ATTACKS_PATH) -> list[Attack]:
    """Parse attacks.jsonl. Enforces uniqueness of IDs and chat/requires_e2e invariants."""
    attacks: list[Attack] = []
    if not path.exists():
        return attacks
    seen_ids: set[str] = set()
    with path.open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            a = Attack.model_validate_json(stripped)
            if a.id in seen_ids:
                raise ValueError(f"duplicate attack id: {a.id}")
            if a.mode == "chat" and a.requires_e2e:
                raise ValueError(
                    f"attack {a.id}: requires_e2e=True is invalid on mode=chat "
                    "(chat is always E2E; flag is doc-mode only)"
                )
            seen_ids.add(a.id)
            attacks.append(a)
    return attacks


def _matches_expected(attack: Attack, *, blocked: bool, actual_layer: str) -> bool:
    """Per spec §3.2: 'any' matches any non-none block; specific layer must match exactly."""
    if not blocked:
        return False
    if attack.expected_block_layer == "any":
        return True
    return actual_layer == attack.expected_block_layer


def run_chat_attack(attack: Attack) -> AttackOutcome:
    """Execute a chat-mode attack via H4 graph (always E2E). ~$0.019 per attack."""
    t0 = time.monotonic()
    error: str | None = None
    actual_verdict = "pass"
    blocked = False
    actual_layer: str = "none"

    try:
        state = run_chat(
            query=attack.payload,
            corpus="ai_act",
            language="es",
            case_id=f"redteam-{attack.id}",
        )
        audited = state.audited_answer
        if audited is not None:
            actual_verdict = audited.verdict.value
            blocked = audited.verdict.value in {"block", "requires_human_review"}
            actual_layer = "auditor" if blocked else "none"
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"[:500]
        blocked = False
        actual_layer = "none"
        actual_verdict = "error"

    latency_ms = int((time.monotonic() - t0) * 1000)
    return AttackOutcome(
        attack_id=attack.id,
        blocked=blocked,
        actual_block_layer=actual_layer,  # type: ignore[arg-type]
        actual_verdict=actual_verdict,
        matches_expected=_matches_expected(attack, blocked=blocked, actual_layer=actual_layer),
        latency_ms=latency_ms,
        cost_eur=0.019 if error is None else 0.0,
        error=error,
    )


def run_doc_attack(attack: Attack) -> AttackOutcome:
    """Execute a document-mode attack with layered defense.

    1. Sanitizer (raises DocumentBlockedError → layer=sanitizer).
    2. Injection regex (returns True → layer=injection).
    3. If requires_e2e: run full H5 pipeline → layer=auditor or none.
       Otherwise: layer=none (escaped deterministic defenses).
    """
    pdf_path = _DOC_DIR / attack.payload
    t0 = time.monotonic()
    error: str | None = None

    try:
        file_bytes = pdf_path.read_bytes()
    except OSError as exc:
        latency_ms = int((time.monotonic() - t0) * 1000)
        return AttackOutcome(
            attack_id=attack.id,
            blocked=False,
            actual_block_layer="none",
            actual_verdict="missing_file",
            matches_expected=_matches_expected(attack, blocked=False, actual_layer="none"),
            latency_ms=latency_ms,
            cost_eur=0.0,
            error=f"{type(exc).__name__}: {exc}"[:500],
        )

    try:
        raw = extractor_extract(file_bytes=file_bytes, mime_type="application/pdf", language="es")
    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.monotonic() - t0) * 1000)
        return AttackOutcome(
            attack_id=attack.id,
            blocked=False,
            actual_block_layer="none",
            actual_verdict="extractor_error",
            matches_expected=_matches_expected(attack, blocked=False, actual_layer="none"),
            latency_ms=latency_ms,
            cost_eur=0.0,
            error=f"{type(exc).__name__}: {exc}"[:500],
        )

    try:
        sanitized = sanitizer_sanitize(raw)
    except DocumentBlockedError:
        latency_ms = int((time.monotonic() - t0) * 1000)
        return AttackOutcome(
            attack_id=attack.id,
            blocked=True,
            actual_block_layer="sanitizer",
            actual_verdict="block",
            matches_expected=_matches_expected(attack, blocked=True, actual_layer="sanitizer"),
            latency_ms=latency_ms,
            cost_eur=0.0,
            error=None,
        )

    inj_hit, pattern = is_injection(sanitized.clean_text, mode="document")
    if inj_hit:
        latency_ms = int((time.monotonic() - t0) * 1000)
        return AttackOutcome(
            attack_id=attack.id,
            blocked=True,
            actual_block_layer="injection",
            actual_verdict="block",
            matches_expected=_matches_expected(attack, blocked=True, actual_layer="injection"),
            latency_ms=latency_ms,
            cost_eur=0.0,
            error=None,
        )

    if not attack.requires_e2e:
        latency_ms = int((time.monotonic() - t0) * 1000)
        return AttackOutcome(
            attack_id=attack.id,
            blocked=False,
            actual_block_layer="none",
            actual_verdict="pass",
            matches_expected=_matches_expected(attack, blocked=False, actual_layer="none"),
            latency_ms=latency_ms,
            cost_eur=0.0,
            error=None,
        )

    # requires_e2e: run full H5 pipeline
    try:
        report = run_document(
            file_bytes=file_bytes,
            mime_type="application/pdf",
            language="es",
            corpus=["ai_act"],
            case_id=f"redteam-{attack.id}",
        )
        verdict = report.document_verdict.value
        blocked = verdict in {"block", "requires_human_review"}
        actual_layer = "auditor" if blocked else "none"
        cost_eur = 0.193
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"[:500]
        blocked = False
        actual_layer = "none"
        verdict = "error"
        cost_eur = 0.0

    latency_ms = int((time.monotonic() - t0) * 1000)
    return AttackOutcome(
        attack_id=attack.id,
        blocked=blocked,
        actual_block_layer=actual_layer,  # type: ignore[arg-type]
        actual_verdict=verdict,
        matches_expected=_matches_expected(attack, blocked=blocked, actual_layer=actual_layer),
        latency_ms=latency_ms,
        cost_eur=cost_eur,
        error=error,
    )


def _run_with_timeout(
    fn: Callable[[Attack], AttackOutcome], attack: Attack, timeout_s: int
) -> AttackOutcome:
    """Run fn(attack) in a worker thread; if it exceeds timeout_s, return a
    timeout AttackOutcome instead of hanging the whole run (H9 lesson:
    Anthropic API can hang silently with no traceback). The orphaned thread
    is abandoned (consumes at most one in-flight API call ~$0.02-0.19)."""
    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn, attack)
        try:
            return fut.result(timeout=timeout_s)
        except FuturesTimeout:
            return AttackOutcome(
                attack_id=attack.id,
                blocked=False,
                actual_block_layer="none",
                actual_verdict="timeout",
                matches_expected=False,
                latency_ms=timeout_s * 1000,
                cost_eur=0.0,
                error=f"timeout: attack exceeded {timeout_s}s (likely Anthropic hang)",
            )


def aggregate(
    outcomes: list[AttackOutcome],
    attacks: list[Attack],
    *,
    baseline: float | None,
) -> AttackAggregate:
    """Compute global + per-scenario + per-layer aggregates."""
    by_id = {a.id: a for a in attacks}
    n_total = len(outcomes)
    n_blocked = sum(1 for o in outcomes if o.blocked)
    block_rate = n_blocked / n_total if n_total > 0 else 0.0
    n_matches = sum(1 for o in outcomes if o.matches_expected)
    cost_total = sum(o.cost_eur for o in outcomes)
    n_e2e = sum(1 for o in outcomes if o.cost_eur > 0)

    per_layer: dict[str, int] = {layer: 0 for layer in LAYERS_WITH_NONE}
    for o in outcomes:
        per_layer[o.actual_block_layer] = per_layer.get(o.actual_block_layer, 0) + 1

    scenario_to_outcomes: dict[int, list[AttackOutcome]] = {}
    for o in outcomes:
        a = by_id[o.attack_id]
        scenario_to_outcomes.setdefault(a.scenario, []).append(o)

    per_scenario: list[ScenarioAggregate] = []
    for scenario_id in sorted(scenario_to_outcomes.keys()):
        scen_outcomes = scenario_to_outcomes[scenario_id]
        scen_n = len(scen_outcomes)
        scen_blocked = sum(1 for o in scen_outcomes if o.blocked)
        scen_rate = scen_blocked / scen_n if scen_n > 0 else 0.0
        escaped = [o.attack_id for o in scen_outcomes if not o.blocked]
        scen_name = by_id[scen_outcomes[0].attack_id].scenario_name
        per_scenario.append(
            ScenarioAggregate(
                scenario=scenario_id,  # type: ignore[arg-type]
                scenario_name=scen_name,
                n_total=scen_n,
                n_blocked=scen_blocked,
                block_rate=scen_rate,
                escaped_ids=escaped,
            )
        )

    return AttackAggregate(
        n_total=n_total,
        n_blocked=n_blocked,
        block_rate=block_rate,
        block_rate_baseline=baseline,
        block_rate_final=block_rate,
        per_scenario=per_scenario,
        per_layer=per_layer,  # type: ignore[arg-type]
        n_e2e_attacks=n_e2e,
        n_matches_expected=n_matches,
        cost_total_eur=cost_total,
    )


def main(
    *,
    attacks_path: Path = _ATTACKS_PATH,
    smoke: bool = False,
    baseline: float | None = None,
) -> None:
    """Entry point. Loads, dispatches, aggregates, writes report."""
    attacks = load_attacks(attacks_path)

    if smoke:
        attacks = [a for a in attacks if a.mode == "document" and not a.requires_e2e]

    # Corpus warmup is only needed for chat-mode (H4 retriever) or for doc-mode
    # requires_e2e=True (H5 pipeline). Smoke runs only the deterministic doc layers
    # (sanitizer + injection regex), so we skip warmup — this also lets CI run the
    # smoke gate without pulling LFS corpus files.
    needs_corpus = any(
        a.mode == "chat" or (a.mode == "document" and a.requires_e2e) for a in attacks
    )
    if needs_corpus:
        corpus_loader.warmup()

    outcomes: list[AttackOutcome] = []
    for attack in attacks:
        if attack.mode == "chat":
            outcomes.append(_run_with_timeout(run_chat_attack, attack, _CHAT_TIMEOUT_S))
        else:
            outcomes.append(_run_with_timeout(run_doc_attack, attack, _DOC_TIMEOUT_S))

    agg = aggregate(outcomes, attacks, baseline=baseline)
    meta = RedTeamRunMeta(
        run_date=datetime.now(UTC).isoformat(),
        commit_sha=_git_sha_short(),
        mode="smoke" if smoke else "full",
        corpus_languages=["es"],
    )

    try:
        from regulaitor.observability.langfuse_client import is_enabled

        if is_enabled():
            from langfuse import Langfuse  # lazy

            _lf = Langfuse()
            _lf.score(
                name="block_rate",
                value=agg.block_rate,
                comment=f"redteam {meta.mode} run, n={agg.n_total}",
            )
            _lf.flush()
    except Exception as exc:  # noqa: BLE001 — observability never breaks the run
        import logging

        logging.getLogger("regulaitor.observability").warning(
            "langfuse block_rate score emit failed: %s", exc
        )

    markdown = render_report(meta, agg, outcomes, attacks)
    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_PATH.write_text(markdown, encoding="utf-8")
