"""H11 — chat graph tracing regression: behaviour identical without keys,
metadata emitted with keys. Backend graph is mocked (no LLM)."""

from __future__ import annotations

import pytest

from regulaitor.orchestration import graph as g


def _fake_final_dict() -> dict:
    return {
        "case_id": "c1",
        "query": "test query",
        "corpus": "ai_act",
        "language": "es",
        "errors": [],
        "injection_blocked": False,
        "audited_answer": None,
    }


def test_run_without_keys_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        monkeypatch.delenv(k, raising=False)

    class _Compiled:
        def invoke(self, _initial: object) -> dict:
            return _fake_final_dict()

    monkeypatch.setattr(g, "_compiled_graph", lambda: _Compiled())
    state = g.run(query="test query", corpus="ai_act", language="es", case_id="c1")
    assert state.case_id == "c1"
    assert state.corpus == "ai_act"


def test_run_emits_trace_metadata_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    class _TT:
        def set_root(self, **kw: object) -> None:
            captured.update(kw)

        def span(self, name: str, **kw: object) -> None:
            captured[f"span:{name}"] = kw

    import contextlib

    @contextlib.contextmanager
    def _fake_trace_turn(**_kw: object):
        yield _TT()

    monkeypatch.setattr(g, "trace_turn", _fake_trace_turn)

    class _Compiled:
        def invoke(self, _initial: object) -> dict:
            return _fake_final_dict()

    monkeypatch.setattr(g, "_compiled_graph", lambda: _Compiled())
    g.run(query="test query", corpus="ai_act", language="es", case_id="c1")
    assert "verdict" in captured
    assert "latency_ms_total" in captured
    assert "query_sha256_12" in captured
    # Redaction: raw query never in the captured metadata values.
    assert "test query" not in repr(captured)
