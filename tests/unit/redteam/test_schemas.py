"""Unit tests for redteam/schemas.py."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from redteam.schemas import (
    Attack,
    AttackAggregate,
    AttackOutcome,
    RedTeamRunMeta,
    ScenarioAggregate,
)


def _make_attack(**overrides) -> dict:
    base = {
        "id": "attack-001",
        "scenario": 1,
        "scenario_name": "Doc ordena ignorar instrucciones",
        "mode": "document",
        "payload": "attack_001.pdf",
        "expected_block_layer": "sanitizer",
        "expected_verdict": "block",
        "requires_e2e": False,
        "description": "PDF que ordena ignorar instrucciones del Analyst.",
        "rationale": "Caso canónico §18.1; sanitizer + injection deben cazarlo.",
    }
    base.update(overrides)
    return base


def test_attack_valid_minimal() -> None:
    a = Attack.model_validate(_make_attack())
    assert a.id == "attack-001"
    assert a.scenario == 1
    assert a.mode == "document"
    assert a.requires_e2e is False


def test_attack_rejects_scenario_out_of_range() -> None:
    with pytest.raises(ValidationError):
        Attack.model_validate(_make_attack(scenario=11))


def test_attack_rejects_invalid_mode() -> None:
    with pytest.raises(ValidationError):
        Attack.model_validate(_make_attack(mode="audio"))


def test_attack_rejects_invalid_expected_layer() -> None:
    with pytest.raises(ValidationError):
        Attack.model_validate(_make_attack(expected_block_layer="firewall"))


def test_attack_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Attack.model_validate(_make_attack(extra_field="oops"))


def test_attack_frozen() -> None:
    a = Attack.model_validate(_make_attack())
    with pytest.raises(ValidationError):
        a.id = "attack-002"  # type: ignore[misc]


def test_attack_outcome_basic() -> None:
    o = AttackOutcome(
        attack_id="attack-001",
        blocked=True,
        actual_block_layer="sanitizer",
        actual_verdict="block",
        matches_expected=True,
        latency_ms=45,
        cost_eur=0.0,
        error=None,
    )
    assert o.matches_expected is True
    assert o.cost_eur == 0.0


def test_attack_outcome_rejects_negative_latency() -> None:
    with pytest.raises(ValidationError):
        AttackOutcome(
            attack_id="x",
            blocked=False,
            actual_block_layer="none",
            actual_verdict="pass",
            matches_expected=False,
            latency_ms=-1,
            cost_eur=0.0,
            error=None,
        )


def test_scenario_aggregate() -> None:
    sa = ScenarioAggregate(
        scenario=1,
        scenario_name="Doc ordena ignorar",
        n_total=5,
        n_blocked=5,
        block_rate=1.0,
        escaped_ids=[],
    )
    assert sa.block_rate == 1.0


def test_scenario_aggregate_rejects_invalid_rate() -> None:
    with pytest.raises(ValidationError):
        ScenarioAggregate(
            scenario=1,
            scenario_name="x",
            n_total=5,
            n_blocked=3,
            block_rate=1.5,  # >1.0
            escaped_ids=[],
        )


def test_attack_aggregate_basic() -> None:
    agg = AttackAggregate(
        n_total=50,
        n_blocked=46,
        block_rate=0.92,
        block_rate_baseline=0.86,
        block_rate_final=0.92,
        per_scenario=[],
        per_layer={"sanitizer": 14, "injection": 12, "validator": 1, "auditor": 19, "none": 4},
        n_e2e_attacks=10,
        n_matches_expected=42,
        cost_total_eur=2.35,
    )
    assert agg.block_rate == 0.92
    assert agg.per_layer["sanitizer"] == 14


def test_run_meta_full_mode() -> None:
    m = RedTeamRunMeta(
        run_date="2026-05-12T20:00:00Z",
        commit_sha="abcdef1",
        mode="full",
        corpus_languages=["es"],
    )
    assert m.mode == "full"
