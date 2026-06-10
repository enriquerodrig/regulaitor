"""Fase 3 review NEC-1: the doc-analysis CLI corpus gate must accept every
canonical norma (it derives _VALID_CORPUS from ALL_NORMAS). Guards against a
future norma addition silently regressing this site again."""

from __future__ import annotations

from scripts.analyze import _VALID_CORPUS

from regulaitor.corpus._targets import ALL_NORMAS


def test_analyze_gate_accepts_every_canonical_norma() -> None:
    assert set(ALL_NORMAS) <= _VALID_CORPUS


def test_analyze_gate_accepts_new_rts_normas() -> None:
    assert "dora_rts_incident" in _VALID_CORPUS
    assert "dora_rts_class" in _VALID_CORPUS
