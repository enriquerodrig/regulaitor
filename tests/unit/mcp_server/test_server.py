"""Unit tests for mcp_server/server.py — bootstrap orchestration.

Server stdio loop is exercised by the integration test in Task 11; this
module verifies the warmup sequence and tool registration logic in isolation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest

from regulaitor.mcp_server import server


def test_warmup_calls_loader_then_reranker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loader integrity check must run before the reranker downloads."""
    parent = MagicMock()
    parent.loader_warmup = MagicMock()
    parent.reranker_warmup = MagicMock()

    monkeypatch.setattr(server.loader, "warmup", parent.loader_warmup)
    monkeypatch.setattr(server.reranker, "warmup", parent.reranker_warmup)

    server._warmup_dependencies()

    assert parent.mock_calls == [call.loader_warmup(), call.reranker_warmup()]


def test_loader_failure_aborts_warmup(monkeypatch: pytest.MonkeyPatch) -> None:
    """If loader fails, reranker must NOT be called (fail-closed)."""
    loader_mock = MagicMock(side_effect=RuntimeError("hash drift"))
    reranker_mock = MagicMock()

    monkeypatch.setattr(server.loader, "warmup", loader_mock)
    monkeypatch.setattr(server.reranker, "warmup", reranker_mock)

    with pytest.raises(RuntimeError, match="hash drift"):
        server._warmup_dependencies()

    reranker_mock.assert_not_called()
