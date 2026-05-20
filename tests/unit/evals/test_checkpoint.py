"""v0.1.8 — checkpoint module unit tests.

The checkpoint module preserves per-case results to disk as JSONL ANTES de avanzar
al siguiente case, so that a mid-loop crash (Anthropic credit_balance_too_low,
network failure, OOM) does not lose the work already completed in RAM.

This was the structural cause of the H15.2 T6 disaster — see
`docs/retriever_h15-2_redesign.md` §4.3 (three converging causes).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evals import checkpoint
from evals.schemas import (
    ChatCaseResult,
    CitationMetrics,
    CriteriaScore,
    DocCaseResult,
)


def _make_chat_result(case_id: str = "chat-001") -> ChatCaseResult:
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
        criteria_scores=[CriteriaScore(criterion="cita_art_6", passed=True, reason="ok")],
        latency_ms=12000,
        cost_eur=0.05,
        cache_hit=False,
    )


def _make_doc_result(case_id: str = "doc-001") -> DocCaseResult:
    return DocCaseResult(
        case_id=case_id,
        expected_document_verdict="pass",
        actual_document_verdict="pass",
        verdict_match=True,
        expected_n_segments=5,
        actual_n_segments=5,
        n_segments_within_tolerance=True,
        findings_citations=CitationMetrics(emitted=[], expected=[], precision=1.0, recall=1.0),
        faithfulness=0.85,
        criteria_scores=[],
        latency_ms_total=45000,
        cost_eur_total=0.15,
        cache_hit=False,
    )


def test_checkpoint_path_is_deterministic_given_run_id(tmp_path: Path) -> None:
    """checkpoint_path(run_id) must be stable + reside under the configured root."""
    p1 = checkpoint.checkpoint_path("run-abc", root=tmp_path)
    p2 = checkpoint.checkpoint_path("run-abc", root=tmp_path)
    assert p1 == p2
    assert p1.parent == tmp_path
    assert p1.name == "run-abc.jsonl"


def test_append_then_load_chat_case_round_trip(tmp_path: Path) -> None:
    """A ChatCaseResult written via append_case is recoverable via load_completed
    with byte-equality on the deserialized fields."""
    case = _make_chat_result()
    checkpoint.append_case("run-1", case, root=tmp_path)

    loaded = checkpoint.load_completed("run-1", root=tmp_path)

    assert len(loaded) == 1
    assert isinstance(loaded[0], ChatCaseResult)
    assert loaded[0].case_id == case.case_id
    assert loaded[0].faithfulness == case.faithfulness
    assert loaded[0].citations.emitted == case.citations.emitted


def test_append_then_load_doc_case_round_trip(tmp_path: Path) -> None:
    """Same round-trip for DocCaseResult (the JSONL must discriminate)."""
    case = _make_doc_result()
    checkpoint.append_case("run-1", case, root=tmp_path)

    loaded = checkpoint.load_completed("run-1", root=tmp_path)

    assert len(loaded) == 1
    assert isinstance(loaded[0], DocCaseResult)
    assert loaded[0].case_id == case.case_id


def test_multiple_appends_preserve_order(tmp_path: Path) -> None:
    """Appending N cases yields N entries in append order."""
    cases = [_make_chat_result(f"chat-{i:03d}") for i in range(1, 6)]
    for c in cases:
        checkpoint.append_case("run-multi", c, root=tmp_path)

    loaded = checkpoint.load_completed("run-multi", root=tmp_path)
    assert [c.case_id for c in loaded] == [c.case_id for c in cases]


def test_mixed_chat_and_doc_cases_load_with_correct_types(tmp_path: Path) -> None:
    """A run with both chat and doc cases discriminates each line correctly on load."""
    checkpoint.append_case("run-mixed", _make_chat_result("chat-001"), root=tmp_path)
    checkpoint.append_case("run-mixed", _make_doc_result("doc-001"), root=tmp_path)
    checkpoint.append_case("run-mixed", _make_chat_result("chat-002"), root=tmp_path)

    loaded = checkpoint.load_completed("run-mixed", root=tmp_path)
    assert len(loaded) == 3
    assert isinstance(loaded[0], ChatCaseResult) and loaded[0].case_id == "chat-001"
    assert isinstance(loaded[1], DocCaseResult) and loaded[1].case_id == "doc-001"
    assert isinstance(loaded[2], ChatCaseResult) and loaded[2].case_id == "chat-002"


def test_load_completed_missing_file_returns_empty_list(tmp_path: Path) -> None:
    """First run before any append: no file on disk → empty list, not raise."""
    assert checkpoint.load_completed("run-fresh", root=tmp_path) == []


def test_append_creates_parent_directory(tmp_path: Path) -> None:
    """The checkpoint root may not exist on first call — append_case creates it."""
    nested = tmp_path / "deeply" / "nested" / "checkpoints"
    assert not nested.exists()

    checkpoint.append_case("run-create-dir", _make_chat_result(), root=nested)

    assert nested.exists()
    assert (nested / "run-create-dir.jsonl").exists()


def test_append_jsonl_format_is_one_line_per_case(tmp_path: Path) -> None:
    """Each appended case occupies exactly one line — the file must be valid JSONL
    so partial reads (e.g. tail during a long run) yield parseable per-line records."""
    for i in range(3):
        checkpoint.append_case("run-format", _make_chat_result(f"chat-{i:03d}"), root=tmp_path)

    path = checkpoint.checkpoint_path("run-format", root=tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    for line in lines:
        parsed = json.loads(line)
        assert "kind" in parsed
        assert "data" in parsed
        assert parsed["kind"] in ("chat", "doc")


def test_unknown_kind_in_existing_jsonl_raises_on_load(tmp_path: Path) -> None:
    """Defensive: if a future-incompatible kind appears in an existing checkpoint
    (e.g. someone hand-edited the file or a newer harness wrote it), load_completed
    raises ValueError naming the unknown kind — fail loud, do not silently skip."""
    path = checkpoint.checkpoint_path("run-bad", root=tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"kind": "future-mystery-type", "data": {}}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="future-mystery-type"):
        checkpoint.load_completed("run-bad", root=tmp_path)
