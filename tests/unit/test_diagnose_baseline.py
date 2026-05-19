# tests/unit/test_diagnose_baseline.py
# ruff: noqa: E501  -- _SAMPLE contains realistic report lines that exceed 100 chars by design
from __future__ import annotations

from scripts.diagnose_baseline import classify_case, parse_report

_SAMPLE = """\
### chat-001

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Citations**: emitted=['105', '2.2', '25.3', '6.1'] expected=['6.1'] precision=0.25 recall=1.00
- **RAG metrics**: faithfulness=0.67 answer_relevancy=0.79 context_precision=1.00 context_recall=0.33

### chat-003

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Citations**: emitted=[] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.00 answer_relevancy=0.00 context_precision=0.00 context_recall=0.00

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Citations**: emitted=['6.2', '6.3'] expected=['6.2', '6.3'] precision=1.00 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.88 context_precision=0.83 context_recall=1.00
"""


def test_parse_report_extracts_cases() -> None:
    cases = parse_report(_SAMPLE)
    ids = [c["id"] for c in cases]
    assert ids == ["chat-001", "chat-003", "chat-002"]
    assert cases[0]["actual"] == "requires_human_review"
    assert cases[0]["expected"] == "pass"
    assert cases[0]["emitted"] == ["105", "2.2", "25.3", "6.1"]
    assert cases[1]["emitted"] == []


def test_classify_over_citation() -> None:
    assert (
        classify_case(
            {
                "actual": "requires_human_review",
                "expected": "pass",
                "emitted": ["105", "2.2", "25.3", "6.1"],
                "recall": 1.0,
            }
        )
        == "over_citation"
    )


def test_classify_no_answer() -> None:
    assert (
        classify_case(
            {"actual": "requires_human_review", "expected": "pass", "emitted": [], "recall": 0.0}
        )
        == "no_answer"
    )


def test_classify_other_when_verdict_matches() -> None:
    assert (
        classify_case({"actual": "pass", "expected": "pass", "emitted": ["6.2"], "recall": 1.0})
        == "other"
    )


def test_classify_wrong_article_when_mismatch_emitted_recall_zero() -> None:
    # Analyst active (emitted non-empty) but cited entirely wrong articles
    # (recall==0) on a verdict mismatch -> distinct third Analyst failure mode.
    assert (
        classify_case(
            {
                "actual": "requires_human_review",
                "expected": "block",
                "emitted": ["113.7", "63", "63.2"],
                "recall": 0.0,
            }
        )
        == "wrong_article"
    )
