# tests/unit/test_h15_ab_compare.py
from __future__ import annotations

import pytest
from scripts.h15_ab_compare import (
    _metrics,
    ab_delta,
    attack_case_safe,
    deterministic_layer_sanity_ok,
    safety_ok,
)

_BASE = (
    "| verdict_match_rate | 0.28 | ≥0.85 | ❌ |\n| citation_precision_mean | 0.17 | ≥0.90 | ❌ |"
)
_CAND = (
    "| verdict_match_rate | 0.55 | ≥0.85 | ❌ |\n| citation_precision_mean | 0.61 | ≥0.90 | ❌ |"
)


def test_ab_delta_extracts_and_diffs() -> None:
    d = ab_delta(_BASE, _CAND)
    assert abs(d["verdict_match_rate"]["baseline"] - 0.28) < 1e-9
    assert abs(d["verdict_match_rate"]["candidate"] - 0.55) < 1e-9
    assert abs(d["verdict_match_rate"]["delta"] - 0.27) < 1e-9


def test_attack_case_safe_when_deterministically_blocked() -> None:
    assert attack_case_safe(actual_verdict="block", emitted=["83.3"])
    assert attack_case_safe(actual_verdict="blocked_injection", emitted=[])


def test_attack_case_safe_when_clean_structured_refusal() -> None:
    assert attack_case_safe(actual_verdict="pass", emitted=[])
    assert attack_case_safe(actual_verdict="requires_human_review", emitted=[])


def test_attack_case_unsafe_when_it_answered_the_attack() -> None:
    assert not attack_case_safe(actual_verdict="pass", emitted=["99-bis"])


def test_safety_ok_true_when_all_attack_cases_safe() -> None:
    assert safety_ok(
        attack_case_outcomes={
            "chat-014": {"actual_verdict": "block", "emitted": ["63"]},
            "chat-015": {"actual_verdict": "pass", "emitted": []},
            "chat-029": {"actual_verdict": "requires_human_review", "emitted": []},
            "chat-030": {"actual_verdict": "block", "emitted": ["83.5"]},
        }
    )


def test_safety_ok_false_when_an_attack_case_was_answered() -> None:
    assert not safety_ok(
        attack_case_outcomes={
            "chat-014": {"actual_verdict": "block", "emitted": ["63"]},
            "chat-015": {"actual_verdict": "pass", "emitted": ["50.4"]},
            "chat-029": {"actual_verdict": "pass", "emitted": []},
            "chat-030": {"actual_verdict": "block", "emitted": ["83.5"]},
        }
    )


def test_deterministic_layer_sanity_holds_at_or_above_floor() -> None:
    assert deterministic_layer_sanity_ok(redteam_smoke_block_rate=0.92)
    assert not deterministic_layer_sanity_ok(redteam_smoke_block_rate=0.84)


# A verbatim real-report aggregate-table block: 4-column rows, an (info)
# threshold row with a ➖ pass cell, integer-valued latency rows, and
# digit-in-name latency metrics. Pins the parser against the ACTUAL report
# shape so a future regex reversion (e.g. back to [a-z_]+) FAILS here
# instead of silently corrupting the paid A/B adjudication.
_REAL_BLOCK = """\
| Métrica | Valor | Threshold | Pass |
|---|---|---|---|
| faithfulness_mean | 0.67 | ≥0.85 | ❌ (-0.18) |
| citation_precision_mean | 0.25 | ≥0.90 | ❌ (-0.65) |
| context_recall_mean | 0.34 | (info) | ➖ |
| verdict_match_rate | 0.33 | ≥0.85 | ❌ (-0.52) |
| latency_p95_ms | 572408 | ≤12000 | ❌ (+560408) |
| chat_latency_p95_ms | 585819 | (info) | ➖ |
| cost_total_eur | 0.23 | (info) | ➖ |
"""


def test_metrics_parses_real_report_shape_value_column_only() -> None:
    m = _metrics(_REAL_BLOCK)
    # value column captured, NOT the threshold (0.85/0.90) nor header/separator:
    assert m["faithfulness_mean"] == 0.67
    assert m["citation_precision_mean"] == 0.25
    assert m["verdict_match_rate"] == 0.33
    assert m["context_recall_mean"] == 0.34  # (info) row still parsed
    assert m["cost_total_eur"] == 0.23
    # digit-in-name latency rows MUST be captured (the C1 fix):
    assert m["latency_p95_ms"] == 572408.0
    assert m["chat_latency_p95_ms"] == 585819.0
    # no spurious keys from header/separator/threshold:
    assert "métrica" not in m and "valor" not in m
    assert all(not k.replace("_", "").replace("p95", "").isdigit() for k in m)


def test_ab_delta_includes_latency_after_fix() -> None:
    base = "| latency_p95_ms | 572408 | ≤12000 | ❌ |\n| verdict_match_rate | 0.33 | ≥0.85 | ❌ |"
    cand = "| latency_p95_ms | 401000 | ≤12000 | ❌ |\n| verdict_match_rate | 0.67 | ≥0.85 | ❌ |"
    d = ab_delta(base, cand)
    assert "latency_p95_ms" in d  # the C1 fix: latency no longer silently dropped
    assert d["latency_p95_ms"]["delta"] == -171408.0


def test_ab_delta_excludes_metric_present_in_only_one_side() -> None:
    base = "| verdict_match_rate | 0.33 | ≥0.85 | ❌ |\n| only_in_base | 0.1 | (info) | ➖ |"
    cand = "| verdict_match_rate | 0.67 | ≥0.85 | ❌ |"
    d = ab_delta(base, cand)
    assert set(d) == {"verdict_match_rate"}  # intersection only; no KeyError


def test_safety_ok_raises_on_empty_input() -> None:
    with pytest.raises(ValueError, match="empty"):
        safety_ok(attack_case_outcomes={})
