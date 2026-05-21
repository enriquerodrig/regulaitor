"""v0.1.16 — Dual-layer threshold rendering in evals/report.py.

Pins the v0.1.16 architecture from spec §2 D1-D4:

1. `_THRESHOLDS` is a 4-tuple `(metric, v0120_bar, aspirational, gated)`.
2. All 8 quality metrics from CLAUDE.md §17 are covered.
3. v0.1.20-bar values match the spec §2 D2 table exactly.
4. Aspirational values match the CLAUDE.md §17 long-term targets.
5. `_render_aggregate_table(agg)` emits 4 column headers (`Métrica | Valor |
   v0.1.20-bar | Aspiracional`) and renders both threshold columns per metric.
6. `_render_caveats_block()` emits the 4 caveat anchor strings from spec §2 D2.
7. For every gated metric, `v0120_bar < aspirational` (sanity check: catches
   accidental inversion of the dual layer).

Source of truth: docs/superpowers/specs/
2026-05-21-v0.1.16-section17-thresholds-judge-family-design.md §2 D2.
"""

from __future__ import annotations

from evals.report import _THRESHOLDS, _render_aggregate_table, _render_caveats_block
from evals.schemas import AggregateMetrics

_EXPECTED_BAR_VALUES = {
    "faithfulness_mean": 0.65,
    "answer_relevancy_mean": 0.55,
    "context_precision_mean": 0.55,
    "context_recall_mean": 0.0,  # info-only, bar irrelevant (gated=False)
    "citation_precision_mean": 0.25,
    "citation_recall_mean": 0.60,
    "verdict_match_rate": 0.35,
    "severity_match_rate": 0.35,
}

_EXPECTED_ASPIRATIONAL_VALUES = {
    "faithfulness_mean": 0.85,
    "answer_relevancy_mean": 0.85,
    "context_precision_mean": 0.80,
    "context_recall_mean": 0.80,
    "citation_precision_mean": 0.90,
    "citation_recall_mean": 0.80,
    "verdict_match_rate": 0.85,
    "severity_match_rate": 0.80,
}


def _make_agg(value: float = 0.5) -> AggregateMetrics:
    """Synthesize an AggregateMetrics with all quality metrics at `value`."""
    return AggregateMetrics(
        n_chat_cases=10,
        n_doc_cases=5,
        faithfulness_mean=value,
        answer_relevancy_mean=value,
        context_precision_mean=value,
        context_recall_mean=value,
        citation_precision_mean=value,
        citation_recall_mean=value,
        verdict_match_rate=value,
        severity_match_rate=value,
        chat_latency_p95_ms=8000,
        doc_latency_p95_ms=8000,
        latency_p95_ms=8000,
        cost_per_chat_eur=0.02,
        cost_per_doc_eur=0.2,
        cost_total_eur=1.0,
        cache_hit_rate=0.0,
    )


def test_thresholds_table_covers_8_quality_metrics() -> None:
    """_THRESHOLDS must list all 8 quality metrics from CLAUDE.md §17."""
    metric_names = [row[0] for row in _THRESHOLDS]
    assert set(metric_names) == set(_EXPECTED_BAR_VALUES.keys()), (
        f"_THRESHOLDS metrics drift; expected={sorted(_EXPECTED_BAR_VALUES.keys())}, "
        f"got={sorted(metric_names)}"
    )


def test_v0120_bar_values_pinned() -> None:
    """v0.1.20-bar values are derived from H10 + H15 v1.2 measured baselines (spec §2 D2).
    Pin them so a refactor cannot silently soften the bar."""
    for metric_name, v0120_bar, _, _gated in _THRESHOLDS:
        expected = _EXPECTED_BAR_VALUES[metric_name]
        assert (
            v0120_bar == expected
        ), f"v0.1.20-bar drift for {metric_name}: expected {expected}, got {v0120_bar}"


def test_aspirational_values_pinned() -> None:
    """Aspirational values are CLAUDE.md §17 long-term targets — verbatim.
    Pin them to catch any drift from §17."""
    for metric_name, _, aspirational, _gated in _THRESHOLDS:
        expected = _EXPECTED_ASPIRATIONAL_VALUES[metric_name]
        assert (
            aspirational == expected
        ), f"Aspirational drift for {metric_name}: expected {expected}, got {aspirational}"


def test_v0120_bar_below_aspirational_for_gated_metrics() -> None:
    """Sanity check: for every gated metric, bar < aspirational. Catches accidental
    inversion of the dual layer (e.g. typo swapping the two values in a row)."""
    for metric_name, v0120_bar, aspirational, gated in _THRESHOLDS:
        if not gated:
            continue
        assert v0120_bar < aspirational, (
            f"{metric_name}: v0120_bar {v0120_bar} should be < aspirational "
            f"{aspirational} (gated metric)"
        )


def test_render_aggregate_table_emits_4_column_headers_and_dual_marks() -> None:
    """The aggregate table must render the 4-column header AND for a metric with
    value below both bar and aspirational, both badges should show ❌."""
    agg = _make_agg(value=0.5)
    table = _render_aggregate_table(agg)
    assert (
        "| Métrica | Valor | v0.1.20-bar | Aspiracional |" in table
    ), f"4-column header not found in table:\n{table}"
    # Faithfulness at 0.5: below both bar (0.65) and aspirational (0.85). Two ❌ should appear.
    faithfulness_row = next((r for r in table.split("\n") if "faithfulness_mean" in r), None)
    assert faithfulness_row is not None, f"no faithfulness row in:\n{table}"
    assert faithfulness_row.count("❌") == 2, (
        f"faithfulness row should show ❌ for both bar and aspirational columns at "
        f"value=0.5: {faithfulness_row!r}"
    )
    # verdict_match at 0.5: above bar (0.35) but below aspirational (0.85). One ✅ and one ❌.
    verdict_row = next((r for r in table.split("\n") if "verdict_match_rate" in r), None)
    assert verdict_row is not None
    assert verdict_row.count("✅") == 1 and verdict_row.count("❌") == 1, (
        f"verdict_match at value=0.5 should show 1 ✅ (bar) + 1 ❌ (aspirational): "
        f"{verdict_row!r}"
    )


def test_render_caveats_block_emits_all_4_anchors() -> None:
    """The new Caveats — v0.1.20-bar reading subsection must contain all 4 anchor strings
    from spec §2 D2."""
    caveats = _render_caveats_block()
    assert "## Caveats — v0.1.20-bar reading" in caveats
    # Anchor 1: aspirational column framing.
    assert "Aspirational column" in caveats
    assert "CLAUDE.md §17" in caveats
    # Anchor 2: bar derivation lineage.
    assert "v0.1.20-bar column" in caveats
    assert "H10" in caveats
    assert "H15 v1.2" in caveats
    # Anchor 3: judge family stays Haiku 4.5.
    assert "Haiku 4.5" in caveats
    assert "ADR-0010 D1" in caveats
    assert "HX" in caveats
    # Anchor 4: latency p95 contamination.
    assert "Latency p95" in caveats
    assert "H17" in caveats
    assert "LangFuse" in caveats
