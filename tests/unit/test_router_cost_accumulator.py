# tests/unit/test_router_cost_accumulator.py
from __future__ import annotations

from regulaitor.models import router


def test_accumulator_starts_zero_after_reset() -> None:
    router.reset_cost_accumulator()
    assert router.get_accumulated_cost_eur() == 0.0


def test_record_cost_accumulates() -> None:
    router.reset_cost_accumulator()
    router._record_cost_eur(0.01)
    router._record_cost_eur(0.02)
    assert abs(router.get_accumulated_cost_eur() - 0.03) < 1e-9


def test_reset_clears() -> None:
    router._record_cost_eur(0.05)
    router.reset_cost_accumulator()
    assert router.get_accumulated_cost_eur() == 0.0
