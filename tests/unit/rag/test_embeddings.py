"""Unit tests for rag.embeddings. Mocks the FlagEmbedding model to avoid
loading 2.3 GB during unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from regulaitor.rag import embeddings


@pytest.fixture(autouse=True)
def reset_singletons(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset module-level singletons before each test."""
    monkeypatch.setattr(embeddings, "_MODEL", None)
    monkeypatch.setattr(embeddings, "_TOKENIZER", None)


@pytest.fixture
def mock_model(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace BGEM3FlagModel constructor with a mock that returns a MagicMock."""
    mock_class = MagicMock()
    fake_instance = MagicMock()
    fake_instance.tokenizer = MagicMock()
    fake_instance.tokenizer.encode = MagicMock(
        side_effect=lambda text, **_: list(range(len(text.split())))
    )
    mock_class.return_value = fake_instance
    monkeypatch.setattr(embeddings, "BGEM3FlagModel", mock_class)
    return mock_class


def test_embed_returns_one_vector_per_input(mock_model: MagicMock) -> None:
    fake_instance = mock_model.return_value
    fake_instance.encode.return_value = {"dense_vecs": [[0.1] * 1024, [0.2] * 1024]}
    out = embeddings.embed(["hello", "world"])
    assert len(out) == 2
    assert len(out[0]) == 1024
    fake_instance.encode.assert_called_once()


def test_embed_uses_batch_size_argument(mock_model: MagicMock) -> None:
    fake_instance = mock_model.return_value
    fake_instance.encode.return_value = {"dense_vecs": [[0.1] * 1024]}
    embeddings.embed(["x"], batch_size=8)
    _, kwargs = fake_instance.encode.call_args
    assert kwargs["batch_size"] == 8


def test_token_count_uses_tokenizer(mock_model: MagicMock) -> None:
    n = embeddings.token_count("hello world this is text")
    assert n == 5  # 5 whitespace-split words in our mock tokenizer


def test_singleton_loads_only_once(mock_model: MagicMock) -> None:
    fake_instance = mock_model.return_value
    fake_instance.encode.return_value = {"dense_vecs": [[0.0] * 1024]}
    embeddings.embed(["a"])
    embeddings.embed(["b"])
    # BGEM3FlagModel constructor should only have been called once
    assert mock_model.call_count == 1


def test_model_identifier_returns_pinned_format(mock_model: MagicMock) -> None:
    """model_identifier should return 'BAAI/bge-m3@<something>' for the loaded model."""
    fake_instance = mock_model.return_value
    fake_instance.model = MagicMock()
    fake_instance.model.config = MagicMock()
    fake_instance.model.config._commit_hash = "abc123def456"
    embeddings._ensure_loaded()  # force load
    ident = embeddings.model_identifier()
    assert ident.startswith("BAAI/bge-m3@")
    assert "abc123def456" in ident or "v1.0" in ident  # accept either real hash or fallback tag


def test_embed_empty_list_returns_empty_no_load(mock_model: MagicMock) -> None:
    """embed([]) should return [] without triggering model load."""
    out = embeddings.embed([])
    assert out == []
    mock_model.assert_not_called()
