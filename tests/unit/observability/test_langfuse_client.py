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


class _FakeTrace:
    def __init__(self) -> None:
        self.updated: list[dict] = []
        self.spans: list[tuple[str, dict]] = []

    def update(self, **kw: object) -> None:
        self.updated.append(kw.get("metadata", {}))  # type: ignore[arg-type]

    def span(self, **kw: object) -> None:
        self.spans.append((kw.get("name", ""), kw.get("metadata", {})))  # type: ignore[arg-type]


class _FakeLangfuse:
    last_instance: _FakeLangfuse | None = None

    def __init__(self, *a: object, **kw: object) -> None:
        self.traces: list[_FakeTrace] = []
        self.flushed = False
        _FakeLangfuse.last_instance = self

    def trace(self, **kw: object) -> _FakeTrace:
        t = _FakeTrace()
        self.traces.append(t)
        return t

    def flush(self) -> None:
        self.flushed = True


@pytest.fixture
def _enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "https://x")
    import sys
    import types

    fake_mod = types.ModuleType("langfuse")
    fake_mod.Langfuse = _FakeLangfuse  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langfuse", fake_mod)
    return _FakeLangfuse


def test_trace_turn_enabled_emits_root_and_spans(_enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    with lc.trace_turn(kind="chat", case_id="c1", corpus="ai_act", language="es") as tt:
        tt.set_root(verdict="pass", cost_eur_total=0.02, query_sha256_12="abc123")
        tt.span("retriever", n_chunks=5, latency_ms=12)
        tt.span("analyst", latency_ms=3000, cost_eur=0.018)
    inst = _enabled.last_instance
    assert inst is not None
    assert inst.flushed is True
    assert inst.traces[0].updated[-1]["verdict"] == "pass"
    span_names = {n for n, _ in inst.traces[0].spans}
    assert {"retriever", "analyst"} <= span_names


def test_trace_turn_swallows_langfuse_init_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk")
    monkeypatch.setenv("LANGFUSE_HOST", "https://x")
    import sys
    import types

    fake_mod = types.ModuleType("langfuse")

    class _Boom:
        def __init__(self, *a: object, **k: object) -> None:
            raise RuntimeError("langfuse down")

    fake_mod.Langfuse = _Boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "langfuse", fake_mod)
    # Must NOT raise — pipeline continues.
    with lc.trace_turn(kind="chat", case_id="c", corpus="ai_act", language="es") as tt:
        tt.set_root(verdict="pass")
    assert tt._root_meta["verdict"] == "pass"


def test_trace_turn_swallows_flush_failure(_enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom_flush(self: object) -> None:
        raise RuntimeError("flush failed")

    monkeypatch.setattr(_enabled, "flush", _boom_flush)
    # Must NOT raise.
    with lc.trace_turn(kind="document", case_id="d", corpus="gdpr", language="es") as tt:
        tt.set_root(document_verdict="block")


def test_redaction_hard_no_raw_text_in_payload(_enabled, monkeypatch: pytest.MonkeyPatch) -> None:
    """SSDLC: a sentinel resembling raw query/doc/citation text must never
    appear in anything sent to LangFuse. Caller is responsible for hashing;
    this test asserts the client does not stringify the accumulator naively
    AND documents the contract."""
    sentinel = "CONFIDENTIAL_CLIENT_POLICY_TEXT_SENTINEL"
    with lc.trace_turn(kind="document", case_id="d", corpus="gdpr", language="es") as tt:
        # Correct usage: only hashes/metadata. We deliberately pass a hash.
        tt.set_root(document_sha256_12=lc.hash12(sentinel))
        tt.span("sanitizer", n_events=3, blocked_category=None)
    inst = _enabled.last_instance
    serialized = repr(inst.traces[0].updated) + repr(inst.traces[0].spans)
    assert sentinel not in serialized
    assert lc.hash12(sentinel) in serialized
