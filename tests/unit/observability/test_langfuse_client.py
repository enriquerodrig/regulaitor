"""Unit tests for observability/langfuse_client.py."""

from __future__ import annotations

import pytest

from regulaitor.observability import langfuse_client as lc

# ---------------------------------------------------------------------------
# Helper: reset the module-level cached client before each test that exercises
# the enabled path so tests are independent (the fixture does this).
# ---------------------------------------------------------------------------


def _reset_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset the module-level _client to None so each test starts clean."""
    monkeypatch.setattr(lc, "_client", None)


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
    """Fake Langfuse client. Tracks construction count to detect thread leak."""

    last_instance: _FakeLangfuse | None = None
    instance_count: int = 0

    def __init__(self, *a: object, **kw: object) -> None:
        self.traces: list[_FakeTrace] = []
        self.flushed = False
        _FakeLangfuse.last_instance = self
        _FakeLangfuse.instance_count += 1

    def trace(self, **kw: object) -> _FakeTrace:
        t = _FakeTrace()
        self.traces.append(t)
        return t

    def flush(self) -> None:
        self.flushed = True

    def shutdown(self) -> None:
        """Called by atexit; must exist so atexit.register does not fail."""


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
    # Reset module-level cached client so tests are independent.
    _reset_client(monkeypatch)
    # Reset construction counter.
    _FakeLangfuse.instance_count = 0
    _FakeLangfuse.last_instance = None
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
    _reset_client(monkeypatch)
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


# ---------------------------------------------------------------------------
# Issue 1: cached client — assert constructed once across two turns
# ---------------------------------------------------------------------------


def test_client_constructed_once_across_multiple_turns(
    _enabled, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_get_client() must return the same instance across calls — no thread
    accumulation under load (spec §2 enfoque A: async batching, ~0 latency)."""
    assert _FakeLangfuse.instance_count == 0  # clean slate from fixture

    with lc.trace_turn(kind="chat", case_id="t1", corpus="ai_act", language="es") as tt:
        tt.set_root(verdict="pass", latency_ms_total=10)

    with lc.trace_turn(kind="chat", case_id="t2", corpus="ai_act", language="es") as tt:
        tt.set_root(verdict="pass", latency_ms_total=20)

    # Only one Langfuse() construction, regardless of how many turns ran.
    assert _FakeLangfuse.instance_count == 1


# ---------------------------------------------------------------------------
# Issue 2: runtime allowlist guard
# ---------------------------------------------------------------------------


def test_set_root_rejects_raw_text_key() -> None:
    """A key not in the allowlist (e.g. raw query text) must raise ValueError."""
    tt = lc.TurnTrace(kind="chat", case_id="c", corpus="ai_act", language="es")
    with pytest.raises(ValueError, match="not in redaction allowlist"):
        tt.set_root(query_text="raw user query")


def test_span_rejects_raw_text_key() -> None:
    """span() must enforce the same allowlist as set_root()."""
    tt = lc.TurnTrace(kind="chat", case_id="c", corpus="ai_act", language="es")
    with pytest.raises(ValueError, match="not in redaction allowlist"):
        tt.span("retriever", raw_document="some policy text here")


def test_allowlist_accepts_all_task4_and_task5_keys() -> None:
    """Every key emitted by the Task 4 (chat) and Task 5 (document) plan
    instrumentation must pass the allowlist without raising.  If this test
    fails after adding new instrumentation keys, extend _SAFE_META_KEYS or
    _SAFE_KEY_SUFFIXES in langfuse_client.py."""
    tt = lc.TurnTrace(kind="chat", case_id="c", corpus="ai_act", language="es")

    # Task 4 — chat graph tt.set_root() keys (plan lines 626-634)
    tt.set_root(
        verdict="pass",
        query_sha256_12="abc123def456",
        n_findings=2,
        n_citations=4,
        n_validated=3,
        n_blocked=1,
        latency_ms_total=420,
    )

    # Task 5 — document graph tt.set_root() keys (plan lines 748-760)
    tt_doc = lc.TurnTrace(kind="document", case_id="d", corpus="ai_act", language="es")
    tt_doc.set_root(
        case_id="d1",
        document_sha256_12="aabbccdd1122",
        corpus="ai_act",
        language="es",
        document_verdict="requires_human_review",
        n_segments_total=5,
        n_segments_pass=3,
        n_segments_block=1,
        n_segments_review=1,
        n_segments_blocked_by_injection=0,
        latency_ms_total=800,
        cost_eur_total=0.05,
    )

    # Span keys used in existing tests + plan (retriever, analyst, sanitizer spans)
    tt.span("retriever", n_chunks=5, latency_ms=12, embedding_model="bge-m3", cost_eur=0.001)
    tt.span("analyst", latency_ms=3000, cost_eur=0.018, tokens_in=512, tokens_out=256)
    tt.span("auditor", n_validated=3, n_blocked=1, latency_ms=200)
    tt.span("sanitizer", n_events=3, blocked_category="hidden_text", pattern_name="zero_width")
    tt.span("injection_guard", hit=True, blocked_category="prompt_injection", n_events=1)
    tt.span("reranker", n_chunks=5, latency_ms=80, retry_triggered=False)

    # If we reach here without ValueError, the allowlist is correct.
    assert True


def test_assert_safe_keys_accepts_h13_council_keys() -> None:
    """SSDLC egress-survival test: all four H13 council summary keys must pass
    the redaction boundary (_assert_safe_keys) without raising ValueError.
    This guards against a future council-key rename silently dropping from
    LangFuse (spec §3/§5 — council summary required in JSON log AND LangFuse
    trace)."""
    tt = lc.TurnTrace(kind="chat", case_id="c", corpus="ai_act", language="es")

    # Exercise the same egress boundary that tt.set_root() enforces,
    # passing exactly the four H13 keys forwarded by run() via tt.set_root().
    tt.set_root(
        verdict="requires_human_review",
        query_sha256_12="abc123def456",
        n_findings=1,
        n_citations=2,
        n_validated=1,
        n_blocked=1,
        council_triggered=True,
        council_verdict="block",
        council_diverges=False,
        n_judges_ok=2,
        latency_ms_total=500,
        errors=[],
    )

    # All four council keys must survive without ValueError.
    assert tt._root_meta["council_triggered"] is True
    assert tt._root_meta["council_verdict"] == "block"
    assert tt._root_meta["council_diverges"] is False
    assert tt._root_meta["n_judges_ok"] == 2
