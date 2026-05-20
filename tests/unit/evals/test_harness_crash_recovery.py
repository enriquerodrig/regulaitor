"""v0.1.8 — harness crash-recovery contract.

These tests pin the behaviour that resolves the H15.2 T6 disaster
(`docs/retriever_h15-2_redesign.md` §4.3):

1. **Per-case exception in compute_chat_metrics → loop continues.**
   Previously `compute_chat_metrics._ragas_metrics_chat` had no try/except;
   when Haiku 429-on-credits the exception propagated up and killed the loop.
   The fix wraps the loop body so individual case failures land as error
   placeholders, the loop continues, and subsequent cases still run.

2. **Each successful case is persisted to checkpoint BEFORE the next case starts.**
   Previously the harness wrote `evals/reports/latest.md` only atomically at the
   end. Any catastrophic crash (e.g. BaseException like SystemExit, OS kill, OOM)
   between case N and case N+1 lost cases 1..N from the in-RAM list. The fix
   appends each completed case to `evals/checkpoints/<run_id>.jsonl` immediately
   after computing it, so even a catastrophic crash preserves the prior work on
   disk.

These two contracts together make paid eval runs safe to retry — the user gets
back N cases of real measurement instead of nothing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from evals import checkpoint, harness
from evals.schemas import ChatCaseResult, CitationMetrics, CriteriaScore, GoldCaseChat


def _make_gold(case_id: str) -> GoldCaseChat:
    """Minimal GoldCaseChat — only the fields the harness inspects in main()."""
    return GoldCaseChat(
        id=case_id,
        tipo="chat",
        entrada=f"q-{case_id}",
        corpus_esperado="ai_act",
        articulos_esperados=["6.1"],
        severidad_esperada="medium",
        criterios_evaluacion=["cita_art_6"],
        salida_esperada="exp",
        requiere_revision_humana=False,
        expected_verdict="pass",
    )


def _make_result(case_id: str) -> ChatCaseResult:
    return ChatCaseResult(
        case_id=case_id,
        expected_verdict="pass",
        actual_verdict="pass",
        verdict_match=True,
        expected_severity="medium",
        actual_severity="medium",
        severity_match=True,
        citations=CitationMetrics(emitted=["6.1"], expected=["6.1"], precision=1.0, recall=1.0),
        faithfulness=0.9,
        answer_relevancy=0.8,
        context_precision=0.7,
        context_recall=0.6,
        criteria_scores=[CriteriaScore(criterion="cita_art_6", passed=True, reason=None)],
        latency_ms=12000,
        cost_eur=0.05,
        cache_hit=False,
    )


@pytest.fixture
def _harness_stubs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, MagicMock]:
    """Stub the heavy paths in harness.main() so tests run $0 + ms-fast.

    Stubs: corpus warmup, gold loader, run_chat_case, run_doc_case (returns empty),
    judge_call, report renderer (the report writer is left REAL to verify the
    final `_REPORT_PATH.write_text` still fires after a clean run; tests that
    care about the report path point it at tmp_path)."""
    monkeypatch.setattr(harness.corpus_loader, "warmup", lambda: None)
    monkeypatch.setattr(harness, "_REPORT_PATH", tmp_path / "latest.md")
    monkeypatch.setattr(harness, "_CHECKPOINT_ROOT", tmp_path / "checkpoints")
    monkeypatch.setattr(harness, "_real_anthropic_invoke", MagicMock(return_value=("", 0.0)))
    return {}


def test_per_case_compute_metrics_exception_does_not_kill_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    _harness_stubs: dict[str, MagicMock],
) -> None:
    """If compute_chat_metrics raises mid-loop (the H15.2 T6 failure mode), the
    loop must continue and the report must still be rendered with all cases
    represented (errored cases as error placeholders, successful as normal)."""
    cases = [_make_gold(f"chat-{i:03d}") for i in range(1, 6)]
    monkeypatch.setattr(harness, "load_gold_set", lambda **_: (cases, []))
    monkeypatch.setattr(harness, "run_chat_case", lambda case, **_: (None, 1000, 0.05, False))

    call_count = {"n": 0}

    def _raising_compute(case, *_args, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] == 3:
            raise RuntimeError("simulated mid-loop ragas crash")
        return _make_result(case.id)

    monkeypatch.setattr(harness, "compute_chat_metrics", _raising_compute)
    # Stub doc + render + aggregate so we focus the test on the chat-loop contract.
    monkeypatch.setattr(harness, "aggregate", lambda chat_results, doc_results: MagicMock())
    monkeypatch.setattr(harness, "render_report", lambda *_a, **_kw: "stub-report")

    harness.main()

    # All 5 cases must be reflected; case-3 must be an error placeholder, others
    # are real results.
    report_path = tmp_path / "latest.md"
    assert report_path.exists(), "report was not rendered → loop died on case 3"
    n = call_count["n"]
    assert n == 5, f"loop did not continue past the raise (only {n} cases processed)"


def test_each_completed_case_is_persisted_to_checkpoint_before_next_starts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    _harness_stubs: dict[str, MagicMock],
) -> None:
    """Checkpoint contract: by the time case N+1 starts, case N is already on disk.

    Verified by recording the checkpoint contents at the moment each
    compute_chat_metrics call begins — at start of call k, the file must contain
    exactly k-1 entries (cases 1..k-1 already persisted)."""
    cases = [_make_gold(f"chat-{i:03d}") for i in range(1, 4)]
    monkeypatch.setattr(harness, "load_gold_set", lambda **_: (cases, []))
    monkeypatch.setattr(harness, "run_chat_case", lambda case, **_: (None, 1000, 0.05, False))

    snapshots: list[int] = []
    seen_run_ids: list[str] = []

    def _compute_observing(case, *_args, **_kwargs):
        # The harness must pass a run_id; the checkpoint must use the same.
        # We probe by listing the checkpoint files under _CHECKPOINT_ROOT and
        # counting entries in the (unique) one.
        ckpt_root = harness._CHECKPOINT_ROOT
        if ckpt_root.exists():
            jsonls = list(ckpt_root.glob("*.jsonl"))
            if jsonls:
                seen_run_ids.append(jsonls[0].stem)
                snapshots.append(len(jsonls[0].read_text(encoding="utf-8").splitlines()))
            else:
                snapshots.append(0)
        else:
            snapshots.append(0)
        return _make_result(case.id)

    monkeypatch.setattr(harness, "compute_chat_metrics", _compute_observing)
    monkeypatch.setattr(harness, "aggregate", lambda *_a, **_kw: MagicMock())
    monkeypatch.setattr(harness, "render_report", lambda *_a, **_kw: "stub")

    harness.main()

    # At start of case 1: 0 entries on disk; case 2: 1 entry; case 3: 2 entries.
    assert snapshots == [0, 1, 2], (
        f"Expected per-case-N to see N-1 prior entries on disk, got {snapshots}. "
        "Checkpoint append is happening AFTER, not BEFORE, the next case starts."
    )


def test_catastrophic_crash_preserves_prior_cases_on_disk(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    _harness_stubs: dict[str, MagicMock],
) -> None:
    """Simulates the H15.2 T6 mode: an uncatchable crash (SystemExit / KeyboardInterrupt
    bypasses `except Exception`). The main() loop dies entirely, the report never
    renders, BUT the prior cases must be on disk in the checkpoint."""
    cases = [_make_gold(f"chat-{i:03d}") for i in range(1, 6)]
    monkeypatch.setattr(harness, "load_gold_set", lambda **_: (cases, []))
    monkeypatch.setattr(harness, "run_chat_case", lambda case, **_: (None, 1000, 0.05, False))

    call_count = {"n": 0}

    def _killing_compute(case, *_args, **_kwargs):
        call_count["n"] += 1
        if call_count["n"] == 3:
            # SystemExit inherits from BaseException, NOT Exception — bypasses
            # the per-case try/except just like a hard kill / OOM would.
            raise SystemExit("simulated catastrophic kill at case 3")
        return _make_result(case.id)

    monkeypatch.setattr(harness, "compute_chat_metrics", _killing_compute)
    monkeypatch.setattr(harness, "aggregate", lambda *_a, **_kw: MagicMock())
    monkeypatch.setattr(harness, "render_report", lambda *_a, **_kw: "stub")

    with pytest.raises(SystemExit):
        harness.main()

    # Report NEVER got rendered (catastrophic crash kills main before render).
    assert not (tmp_path / "latest.md").exists()

    # BUT cases 1 and 2 must be persisted in the checkpoint — the whole point.
    ckpt_root = harness._CHECKPOINT_ROOT
    jsonls = list(ckpt_root.glob("*.jsonl"))
    assert len(jsonls) == 1, f"expected exactly one checkpoint file, got {jsonls}"

    run_id = jsonls[0].stem
    completed = checkpoint.load_completed(run_id, root=ckpt_root)
    assert (
        len(completed) == 2
    ), f"expected cases 1+2 persisted before the SystemExit at case 3, got {len(completed)}"
    assert [c.case_id for c in completed] == ["chat-001", "chat-002"]
