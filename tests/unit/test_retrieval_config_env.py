"""Unit tests for the REGULAITOR_RETRIEVAL_CONFIG eval-only env-override seam.

Tests call _config_from_env() directly (no module reload needed) so they are
deterministic and $0 (no LLM / network).  monkeypatch is used to set / clear
the env var around each call.

TDD Step 1: these tests are written BEFORE the implementation exists and are
expected to FAIL until _config_from_env is added to retrieval.py (Step 3).
"""

from __future__ import annotations

import logging

import pytest

from regulaitor.rag.retrieval import RetrievalConfig, _config_from_env

ENV_VAR = "REGULAITOR_RETRIEVAL_CONFIG"


# ---------------------------------------------------------------------------
# 1. Unset → frozen defaults (production-byte-identical guarantee)
# ---------------------------------------------------------------------------


def test_unset_env_yields_frozen_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)
    cfg = _config_from_env()
    assert cfg == RetrievalConfig()
    assert cfg.pre_rerank == 50
    assert cfg.top_k == 5
    assert cfg.purity_threshold == 0.6
    assert cfg.query_normalize is False


# ---------------------------------------------------------------------------
# 2. Empty string → defaults
# ---------------------------------------------------------------------------


def test_empty_env_yields_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VAR, "")
    cfg = _config_from_env()
    assert cfg == RetrievalConfig()


# ---------------------------------------------------------------------------
# 3. Valid JSON subset → overrides specified fields, keeps defaults for rest
# ---------------------------------------------------------------------------


def test_valid_json_overrides_subset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_VAR, '{"pre_rerank":80,"purity_threshold":0.55}')
    cfg = _config_from_env()
    assert cfg.pre_rerank == 80
    assert cfg.purity_threshold == 0.55
    assert cfg.top_k == 5  # default kept
    assert cfg.query_normalize is False  # default kept


# ---------------------------------------------------------------------------
# 4. Malformed JSON → WARNING + defaults, no crash
# ---------------------------------------------------------------------------


def test_invalid_json_warns_and_falls_back(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(ENV_VAR, "not json{")
    with caplog.at_level(logging.WARNING, logger="regulaitor.rag.retrieval"):
        cfg = _config_from_env()
    assert cfg == RetrievalConfig()
    assert any(
        "REGULAITOR_RETRIEVAL_CONFIG" in r.message and r.levelno == logging.WARNING
        for r in caplog.records
    ), "Expected a WARNING log mentioning REGULAITOR_RETRIEVAL_CONFIG"


# ---------------------------------------------------------------------------
# 5. Unknown key in JSON → WARNING + defaults
# ---------------------------------------------------------------------------


def test_unknown_key_warns_and_falls_back(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(ENV_VAR, '{"bogus":1}')
    with caplog.at_level(logging.WARNING, logger="regulaitor.rag.retrieval"):
        cfg = _config_from_env()
    assert cfg == RetrievalConfig()
    assert any(
        "REGULAITOR_RETRIEVAL_CONFIG" in r.message and r.levelno == logging.WARNING
        for r in caplog.records
    ), "Expected a WARNING log mentioning REGULAITOR_RETRIEVAL_CONFIG"


# ---------------------------------------------------------------------------
# 6. __post_init__ violation (top_k=0) → WARNING + defaults, no propagation
# ---------------------------------------------------------------------------


def test_post_init_violation_warns_and_falls_back(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(ENV_VAR, '{"top_k":0}')
    with caplog.at_level(logging.WARNING, logger="regulaitor.rag.retrieval"):
        cfg = _config_from_env()
    assert cfg == RetrievalConfig()
    assert any(
        "REGULAITOR_RETRIEVAL_CONFIG" in r.message and r.levelno == logging.WARNING
        for r in caplog.records
    ), "Expected a WARNING log mentioning REGULAITOR_RETRIEVAL_CONFIG"


# ---------------------------------------------------------------------------
# 7. Return type is always a frozen RetrievalConfig instance
# ---------------------------------------------------------------------------


def test_returns_frozen_retrievalconfig(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENV_VAR, raising=False)
    cfg = _config_from_env()
    assert isinstance(cfg, RetrievalConfig)
    # Verify it is truly frozen (dataclass frozen=True raises FrozenInstanceError
    # which is a subclass of AttributeError on direct assignment)
    with pytest.raises(AttributeError):
        cfg.top_k = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 8. Non-dict JSON (e.g. array) → WARNING + defaults, no crash
# ---------------------------------------------------------------------------


def test_non_dict_json_warns_and_falls_back(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv(ENV_VAR, "[1,2,3]")
    with caplog.at_level(logging.WARNING, logger="regulaitor.rag.retrieval"):
        cfg = _config_from_env()
    assert cfg == RetrievalConfig()
    assert any(
        "REGULAITOR_RETRIEVAL_CONFIG" in r.message and r.levelno == logging.WARNING
        for r in caplog.records
    )


# ---------------------------------------------------------------------------
# 9. Wrong-type field value → WARNING + defaults, DEFAULT_CONFIG NOT corrupted
# ---------------------------------------------------------------------------


def test_wrong_type_value_warns_and_falls_back(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # realistic typo: string instead of float — must NOT corrupt DEFAULT_CONFIG
    monkeypatch.setenv(ENV_VAR, '{"purity_threshold":"0.7"}')
    with caplog.at_level(logging.WARNING, logger="regulaitor.rag.retrieval"):
        cfg = _config_from_env()
    assert cfg == RetrievalConfig()
    assert cfg.purity_threshold == 0.6  # frozen default, NOT the corrupt "0.7"
    assert any(
        "REGULAITOR_RETRIEVAL_CONFIG" in r.message and r.levelno == logging.WARNING
        for r in caplog.records
    )
