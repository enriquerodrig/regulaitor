"""H9 — Red team Pydantic v2 schemas.

Attack: declarative test case (commit en redteam/attacks.jsonl).
AttackOutcome: computed result per Attack execution.
ScenarioAggregate, AttackAggregate: aggregation outputs.
RedTeamRunMeta: header for report.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_ScenarioId = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
_LayerWithNone = Literal["sanitizer", "injection", "validator", "auditor", "none"]
_LayerOrAny = Literal["sanitizer", "injection", "validator", "auditor", "any"]
_Mode = Literal["chat", "document"]
_ExpectedVerdict = Literal["block", "requires_human_review"]

# Public tuple constants — single source of truth shared with runner + report.
# Typed as tuples of the corresponding Literal alias so mypy treats each entry
# as a valid key for dict[Literal, ...] lookups (used in per_layer aggregation).
LAYERS_WITH_NONE: tuple[_LayerWithNone, ...] = (
    "sanitizer",
    "injection",
    "validator",
    "auditor",
    "none",
)
LAYERS_OR_ANY: tuple[_LayerOrAny, ...] = (
    "sanitizer",
    "injection",
    "validator",
    "auditor",
    "any",
)


class Attack(BaseModel):
    """One adversarial test case. Immutable, declared in attacks.jsonl."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    scenario: _ScenarioId
    scenario_name: str
    mode: _Mode
    payload: str
    expected_block_layer: _LayerOrAny
    expected_verdict: _ExpectedVerdict
    requires_e2e: bool = False
    description: str
    rationale: str


class AttackOutcome(BaseModel):
    """Result of executing one Attack. Computed by runner."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attack_id: str
    blocked: bool
    actual_block_layer: _LayerWithNone
    actual_verdict: str
    matches_expected: bool
    latency_ms: int = Field(ge=0)
    cost_eur: float = Field(ge=0.0)
    error: str | None


class ScenarioAggregate(BaseModel):
    """Per-scenario aggregation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario: _ScenarioId
    scenario_name: str
    n_total: int = Field(ge=0)
    n_blocked: int = Field(ge=0)
    block_rate: float = Field(ge=0.0, le=1.0)
    escaped_ids: list[str]


class AttackAggregate(BaseModel):
    """Run-level aggregation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    n_total: int = Field(ge=0)
    n_blocked: int = Field(ge=0)
    block_rate: float = Field(ge=0.0, le=1.0)
    block_rate_baseline: float | None
    block_rate_final: float = Field(ge=0.0, le=1.0)
    per_scenario: list[ScenarioAggregate]
    per_layer: dict[_LayerWithNone, int]
    n_e2e_attacks: int = Field(ge=0)
    n_matches_expected: int = Field(ge=0)
    cost_total_eur: float = Field(ge=0.0)


class RedTeamRunMeta(BaseModel):
    """Run metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_date: str
    commit_sha: str
    mode: Literal["full", "smoke"]
    corpus_languages: list[str]
