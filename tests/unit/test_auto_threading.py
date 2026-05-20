# tests/unit/test_auto_threading.py
from __future__ import annotations

from regulaitor.agents.retriever import RetrieverAgent
from regulaitor.rag import retrieval


def test_retriever_explicit_corpus_calls_run_not_auto(monkeypatch) -> None:
    called = {}
    monkeypatch.setattr(retrieval, "run", lambda *a, **k: (called.setdefault("run", a), [])[1])
    monkeypatch.setattr(
        retrieval, "run_auto", lambda *a, **k: called.setdefault("auto", a) or ([], [])
    )
    monkeypatch.setattr(retrieval.embeddings, "model_identifier", lambda: "m")
    ctx = RetrieverAgent().retrieve("q", "gdpr", "es")
    assert "run" in called and "auto" not in called
    assert ctx.corpus == "gdpr"
    assert ctx.resolved_normas == ["gdpr"]


def test_retriever_auto_calls_run_auto_and_sets_resolved(monkeypatch) -> None:
    monkeypatch.setattr(retrieval, "run_auto", lambda q, lang, cfg: ([], ["nis2", "dora"]))
    monkeypatch.setattr(retrieval.embeddings, "model_identifier", lambda: "m")
    ctx = RetrieverAgent().retrieve("q", "auto", "es")
    assert ctx.corpus == "auto"
    assert ctx.resolved_normas == ["nis2", "dora"]
