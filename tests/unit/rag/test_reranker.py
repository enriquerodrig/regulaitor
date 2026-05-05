"""Unit tests for rag.reranker. Mocks FlagReranker to avoid loading 600 MB."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from regulaitor.rag import reranker


@pytest.fixture(autouse=True)
def reset_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(reranker, "_RERANKER", None)


@pytest.fixture
def mock_reranker(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock_class = MagicMock()
    fake_instance = MagicMock()
    mock_class.return_value = fake_instance
    monkeypatch.setattr(reranker, "FlagReranker", mock_class)
    return mock_class


def test_rerank_empty_passages_returns_empty(mock_reranker: MagicMock) -> None:
    out = reranker.rerank("query", [])
    assert out == []
    mock_reranker.assert_not_called()  # model not even loaded for empty input


def test_rerank_returns_indices_sorted_by_score_desc(mock_reranker: MagicMock) -> None:
    fake_instance = mock_reranker.return_value
    fake_instance.compute_score.return_value = [0.3, 0.9, 0.1]
    out = reranker.rerank("q", ["p0", "p1", "p2"])
    assert out == [(1, 0.9), (0, 0.3), (2, 0.1)]


def test_rerank_top_n_truncates(mock_reranker: MagicMock) -> None:
    fake_instance = mock_reranker.return_value
    fake_instance.compute_score.return_value = [0.3, 0.9, 0.1, 0.5]
    out = reranker.rerank("q", ["p0", "p1", "p2", "p3"], top_n=2)
    assert len(out) == 2
    assert out == [(1, 0.9), (3, 0.5)]


def test_rerank_passes_normalize_true_to_compute_score(mock_reranker: MagicMock) -> None:
    fake_instance = mock_reranker.return_value
    fake_instance.compute_score.return_value = [0.5]
    reranker.rerank("q", ["p"])
    _, kwargs = fake_instance.compute_score.call_args
    assert kwargs.get("normalize") is True


def test_warmup_loads_model_and_runs_dummy_query(mock_reranker: MagicMock) -> None:
    fake_instance = mock_reranker.return_value
    fake_instance.compute_score.return_value = [0.0]
    reranker.warmup()
    mock_reranker.assert_called_once()
    fake_instance.compute_score.assert_called_once()
