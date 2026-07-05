"""Unit tests for the P3.1 metrics floor (observability/metrics.py)."""

from __future__ import annotations

import pytest

from regulaitor.observability import metrics


def test_record_turns_and_render() -> None:
    metrics.reset()
    metrics.record_turn("chat", "pass")
    metrics.record_turn("chat", "pass")
    metrics.record_turn("chat", "block")
    metrics.record_turn("document", "requires_human_review")
    metrics.record_pii_query()
    out = metrics.render_prometheus()
    assert 'regulaitor_turns_total{mode="chat",verdict="pass"} 2' in out
    assert 'regulaitor_turns_total{mode="chat",verdict="block"} 1' in out
    assert 'regulaitor_turns_total{mode="document",verdict="requires_human_review"} 1' in out
    assert "regulaitor_pii_queries_total 1" in out
    assert out.startswith("# HELP")
    metrics.reset()


def test_reset_clears_counters() -> None:
    metrics.record_turn("chat", "pass")
    metrics.record_pii_query()
    metrics.reset()
    out = metrics.render_prometheus()
    assert "regulaitor_turns_total{" not in out  # no per-verdict rows
    assert "regulaitor_pii_queries_total 0" in out


def test_is_enabled_is_fail_secure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REGULAITOR_ENABLE_METRICS", raising=False)
    assert metrics.is_enabled() is False
    monkeypatch.setenv("REGULAITOR_ENABLE_METRICS", "0")
    assert metrics.is_enabled() is False
    monkeypatch.setenv("REGULAITOR_ENABLE_METRICS", "1")
    assert metrics.is_enabled() is True
