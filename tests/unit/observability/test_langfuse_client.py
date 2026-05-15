"""Unit tests for observability/langfuse_client.py."""

from __future__ import annotations

import pytest

from regulaitor.observability import langfuse_client as lc


def test_is_enabled_false_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)
    assert lc.is_enabled() is False


def test_is_enabled_false_with_partial_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.setenv("LANGFUSE_HOST", "https://x")
    assert lc.is_enabled() is False


def test_is_enabled_true_with_all_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "https://x")
    assert lc.is_enabled() is True


def test_trace_turn_noop_yields_inert_accumulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)
    with lc.trace_turn(kind="chat", case_id="c1", corpus="ai_act", language="es") as tt:
        tt.set_root(verdict="pass", cost_eur_total=0.02)
        tt.span("retriever", n_chunks=5, latency_ms=12)
    # No exception; accumulator captured data but nothing was sent.
    assert tt.kind == "chat"
    assert tt._root_meta["verdict"] == "pass"
    assert tt._spans["retriever"]["n_chunks"] == 5


def test_trace_turn_noop_does_not_import_langfuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without keys, the langfuse SDK must NOT be imported (zero overhead)."""
    import sys

    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delitem(sys.modules, "langfuse", raising=False)
    with lc.trace_turn(kind="chat", case_id="c", corpus="ai_act", language="es"):
        pass
    assert "langfuse" not in sys.modules
