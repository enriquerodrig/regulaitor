# tests/unit/test_explicit_config_wired.py
"""H15.2 keystone proof — the explicit-corpus retrieval path must:
(a) under env-unset, use DEFAULT_CONFIG.top_k=5 and DEFAULT_CONFIG.pre_rerank=50
    (production byte-identical to v0.1.6-h15.1);
(b) under env-set (monkeypatched DEFAULT_CONFIG), use the override values
    (closes the §22.22 design-defect disclosed POST-SPEND in H15.1-T10/T11);
(c) WHERE-CLAUSE construction stays byte-identical character-for-character under
    BOTH env states (the no-leakage carry; T6 §22.18/H14 invariant scope).

Property (c) is the central proof: the §22.18/H14 no-leakage guarantee is
about cross-corpus contamination (the where-clause), NOT about specific
top_k/pre_rerank values — H15.2 corrects the H15.1 implementation's
conservative interpretation of T6 at the architecturally-correct narrower scope.
"""
from __future__ import annotations

from regulaitor.rag import retrieval


class _SearchStub:
    """Captures the `.limit(N)` argument and the where-clause."""

    def __init__(self, captured: dict) -> None:
        self._captured = captured

    def where(self, c: str):
        self._captured["where_clause"] = c
        return self

    def limit(self, n: int):
        self._captured["pre_rerank"] = n
        return self

    def to_list(self):
        # empty -> short-circuit (see test_explicit_path_unchanged.py; no _enrich path needed)
        return []


class _TableStub:
    def __init__(self, captured: dict) -> None:
        self._captured = captured

    def search(self, _v):
        return _SearchStub(self._captured)


def _install_stubs(monkeypatch, captured: dict) -> None:
    monkeypatch.setattr(retrieval.embeddings, "embed", lambda _q: [[0.0]])
    monkeypatch.setattr(retrieval.store, "connect", lambda _p: _TableStub(captured))

    def _rerank_stub(_q, _passages, top_n: int):
        captured["top_n"] = top_n
        return []  # empty -> run() returns [] without entering _enrich

    monkeypatch.setattr(retrieval.reranker, "rerank", _rerank_stub)


def test_env_unset_uses_default_config_defaults(monkeypatch) -> None:
    """Production-byte-identical: DEFAULT_CONFIG() defaults → top_k=5, pre_rerank=50."""
    monkeypatch.setattr(retrieval, "DEFAULT_CONFIG", retrieval.RetrievalConfig())
    captured: dict = {}
    _install_stubs(monkeypatch, captured)

    out = retrieval.run("q", "ai_act", "es")

    assert out == []
    assert captured["pre_rerank"] == 50  # DEFAULT_CONFIG.pre_rerank
    assert captured["top_n"] == 5  # DEFAULT_CONFIG.top_k
    assert captured["where_clause"] == "norma = 'ai_act' AND language = 'es'"


def test_env_set_overrides_default_config(monkeypatch) -> None:
    """Override flows through: DEFAULT_CONFIG(pre_rerank=80, top_k=3) → run() uses those."""
    monkeypatch.setattr(
        retrieval,
        "DEFAULT_CONFIG",
        retrieval.RetrievalConfig(pre_rerank=80, top_k=3),
    )
    captured: dict = {}
    _install_stubs(monkeypatch, captured)

    out = retrieval.run("q", "gdpr", "en")

    assert out == []
    assert captured["pre_rerank"] == 80
    assert captured["top_n"] == 3
    assert captured["where_clause"] == "norma = 'gdpr' AND language = 'en'"


def test_explicit_top_k_overrides_default_config(monkeypatch) -> None:
    """Backward-compat: callers passing explicit top_k still win (per-call override
    survives the wiring change; eval harness + existing tests rely on this)."""
    monkeypatch.setattr(
        retrieval,
        "DEFAULT_CONFIG",
        retrieval.RetrievalConfig(pre_rerank=80, top_k=3),
    )
    captured: dict = {}
    _install_stubs(monkeypatch, captured)

    out = retrieval.run("q", "nis2", "es", top_k=10)

    assert out == []
    assert captured["pre_rerank"] == 80  # DEFAULT_CONFIG (no explicit pre_rerank)
    assert captured["top_n"] == 10  # explicit top_k wins
    assert captured["where_clause"] == "norma = 'nis2' AND language = 'es'"


def test_where_clause_byte_identical_under_both_env_states(monkeypatch) -> None:
    """The central H15.2 proof: WHERE-CLAUSE construction is byte-identical
    under env-unset (DEFAULT_CONFIG()) AND env-set (DEFAULT_CONFIG(80,3)).
    This is the §22.18/H14 no-leakage invariant at its actual narrow scope.
    T6 (tests/unit/test_explicit_path_unchanged.py) asserts this for env-unset;
    this test extends the assertion to env-set, proving the wiring change does
    not touch the no-leakage-critical line."""
    captured_unset: dict = {}
    captured_set: dict = {}

    monkeypatch.setattr(retrieval, "DEFAULT_CONFIG", retrieval.RetrievalConfig())
    _install_stubs(monkeypatch, captured_unset)
    retrieval.run("q", "dora", "es")

    monkeypatch.setattr(
        retrieval,
        "DEFAULT_CONFIG",
        retrieval.RetrievalConfig(pre_rerank=80, top_k=3),
    )
    # First run already captured into captured_unset; re-patch stubs with the
    # captured_set closure so the second run() populates that dict.
    _install_stubs(monkeypatch, captured_set)
    retrieval.run("q", "dora", "es")

    # Same query, same corpus, same language → WHERE-CLAUSE must be byte-identical
    assert captured_unset["where_clause"] == captured_set["where_clause"]
    assert captured_unset["where_clause"] == "norma = 'dora' AND language = 'es'"
