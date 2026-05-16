"""Unit tests for redteam/report.py."""

from __future__ import annotations

from redteam.report import render_report
from redteam.schemas import (
    Attack,
    AttackAggregate,
    AttackOutcome,
    RedTeamRunMeta,
    ScenarioAggregate,
)


def _make_meta(mode: str = "full") -> RedTeamRunMeta:
    return RedTeamRunMeta(
        run_date="2026-05-12T20:00:00+00:00",
        commit_sha="abcdef1",
        mode=mode,  # type: ignore[arg-type]
        corpus_languages=["es"],
    )


def _make_attack(idx: int, scenario: int = 1) -> Attack:
    return Attack(
        id=f"attack-{idx:03d}",
        scenario=scenario,  # type: ignore[arg-type]
        scenario_name="Doc ordena ignorar instrucciones",
        mode="document",
        payload=f"attack_{idx:03d}.pdf",
        expected_block_layer="sanitizer",
        expected_verdict="block",
        requires_e2e=False,
        description=f"Caso {idx}",
        rationale=f"Test {idx}",
    )


def _make_outcome(idx: int, blocked: bool = True, layer: str = "sanitizer") -> AttackOutcome:
    return AttackOutcome(
        attack_id=f"attack-{idx:03d}",
        blocked=blocked,
        actual_block_layer=layer,  # type: ignore[arg-type]
        actual_verdict="block" if blocked else "pass",
        matches_expected=blocked and layer == "sanitizer",
        latency_ms=45,
        cost_eur=0.0,
        error=None,
    )


def _make_agg(n_total: int = 50, n_blocked: int = 46) -> AttackAggregate:
    return AttackAggregate(
        n_total=n_total,
        n_blocked=n_blocked,
        block_rate=n_blocked / n_total,
        block_rate_baseline=0.86,
        block_rate_final=n_blocked / n_total,
        per_scenario=[
            ScenarioAggregate(
                scenario=1,  # type: ignore[arg-type]
                scenario_name="Doc ordena ignorar",
                n_total=5,
                n_blocked=5,
                block_rate=1.0,
                escaped_ids=[],
            )
        ],
        per_layer={"sanitizer": 14, "injection": 12, "validator": 1, "auditor": 19, "none": 4},
        n_e2e_attacks=10,
        n_matches_expected=42,
        cost_total_eur=2.35,
    )


def test_render_report_header_includes_run_date_and_commit() -> None:
    meta = _make_meta()
    agg = _make_agg()
    attacks = [_make_attack(1)]
    outcomes = [_make_outcome(1)]
    md = render_report(meta, agg, outcomes, attacks)
    assert "2026-05-12T20:00:00+00:00" in md
    assert "abcdef1" in md


def test_render_report_includes_gate_status_pass() -> None:
    meta = _make_meta()
    agg = _make_agg(n_total=50, n_blocked=46)  # 0.92, above 0.90
    md = render_report(meta, agg, [_make_outcome(1)], [_make_attack(1)])
    assert "0.92" in md
    assert "≥0.90" in md
    assert "✅" in md


def test_render_report_includes_gate_status_fail() -> None:
    meta = _make_meta()
    agg = _make_agg(n_total=50, n_blocked=40)  # 0.80, below 0.90
    md = render_report(meta, agg, [_make_outcome(1)], [_make_attack(1)])
    assert "0.80" in md
    assert "❌" in md


def test_render_report_includes_per_scenario_table() -> None:
    md = render_report(_make_meta(), _make_agg(), [_make_outcome(1)], [_make_attack(1)])
    assert "Per-scenario block rate" in md
    assert "Doc ordena ignorar" in md


def test_render_report_includes_per_layer_attribution() -> None:
    md = render_report(_make_meta(), _make_agg(), [_make_outcome(1)], [_make_attack(1)])
    assert "Per-layer attribution" in md
    assert "sanitizer" in md
    assert "14" in md


def _make_timeout_outcome(idx: int) -> AttackOutcome:
    return AttackOutcome(
        attack_id=f"attack-{idx:03d}",
        blocked=False,
        actual_block_layer="none",  # type: ignore[arg-type]
        actual_verdict="timeout",
        matches_expected=False,
        latency_ms=300000,
        cost_eur=0.0,
        error="timeout: attack exceeded 300s (likely Anthropic hang)",
    )


def test_render_report_emits_timeout_contamination_banner() -> None:
    """When attacks time out (API degradation), the report must surface the
    contamination honestly in both the Gate banner and Caveats (C1 fix)."""
    meta = _make_meta()
    agg = _make_agg(n_total=3, n_blocked=1)
    attacks = [_make_attack(1), _make_attack(2), _make_attack(3)]
    outcomes = [
        _make_outcome(1, blocked=True, layer="sanitizer"),
        _make_timeout_outcome(2),
        _make_outcome(3, blocked=False, layer="none"),
    ]
    md = render_report(meta, agg, outcomes, attacks)
    assert "Timeout contamination" in md
    assert "1/3 attacks timed out" in md
    assert "0.50" in md  # 1 blocked / 2 completed (3 - 1 timeout - 0 error)
    assert "smoke 0.92" in md
    assert "not an H9 re-open" in md
    assert "Contaminación por timeout" in md  # also in Caveats


def test_render_report_no_banner_when_no_timeouts() -> None:
    """Clean / smoke runs (zero timeouts) must NOT carry the banner."""
    meta = _make_meta()
    agg = _make_agg(n_total=2, n_blocked=2)
    attacks = [_make_attack(1), _make_attack(2)]
    outcomes = [_make_outcome(1), _make_outcome(2)]
    md = render_report(meta, agg, outcomes, attacks)
    assert "Timeout contamination" not in md
    assert "Contaminación por timeout" not in md


def test_render_report_per_attack_appendix_marks_escaped() -> None:
    meta = _make_meta()
    agg = _make_agg(n_total=2, n_blocked=1)
    attacks = [_make_attack(1), _make_attack(2)]
    outcomes = [
        _make_outcome(1, blocked=True, layer="sanitizer"),
        _make_outcome(2, blocked=False, layer="none"),
    ]
    md = render_report(meta, agg, outcomes, attacks)
    assert "attack-001" in md
    assert "attack-002" in md
    # Escaped attack must be flagged with ❌
    assert "ESCAPED" in md or "❌" in md
