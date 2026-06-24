"""Unit tests for security/tenancy.py (Fase 4 — multi-tenant registry, ADR-0039)."""

from __future__ import annotations

import json

import pytest

from regulaitor.security import tenancy

_T = "tok_" + "a" * 20  # a >=16-char token
_T2 = "tok_" + "b" * 20


@pytest.fixture(autouse=True)
def _reset_registry():
    tenancy._reset()
    yield
    tenancy._reset()


def _clear_env(monkeypatch):
    for k in ("REGULAITOR_TENANTS_JSON", "REGULAITOR_TENANTS_FILE", "REGULAITOR_API_TOKEN"):
        monkeypatch.delenv(k, raising=False)


def test_inline_json_loads_multiple_tenants(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv(
        "REGULAITOR_TENANTS_JSON",
        json.dumps(
            [
                {
                    "token": _T,
                    "tenant_id": "acme",
                    "name": "Acme SL",
                    "rate_limit_ask": "60/minute",
                },
                {"token": _T2, "tenant_id": "globex", "name": "Globex"},
            ]
        ),
    )
    tenancy.load_tenants_or_raise()
    acme = tenancy.resolve_tenant(_T)
    assert acme is not None and acme.tenant_id == "acme"
    assert acme.rate_limit_ask == "60/minute"
    assert acme.rate_limit_analyze == "5/minute"  # default
    assert tenancy.resolve_tenant(_T2).name == "Globex"
    assert tenancy.tenant_by_id("globex").tenant_id == "globex"


def test_file_source(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    p = tmp_path / "tenants.json"
    p.write_text(json.dumps([{"token": _T, "tenant_id": "acme", "name": "Acme"}]), encoding="utf-8")
    monkeypatch.setenv("REGULAITOR_TENANTS_FILE", str(p))
    tenancy.load_tenants_or_raise()
    assert tenancy.resolve_tenant(_T).tenant_id == "acme"


def test_backward_compat_single_api_token(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("REGULAITOR_API_TOKEN", _T)
    tenancy.load_tenants_or_raise()
    t = tenancy.resolve_tenant(_T)
    assert t is not None and t.tenant_id == "default"
    assert tenancy.resolve_tenant("wrong_token_xxxxxxx") is None


def test_no_config_raises(monkeypatch):
    _clear_env(monkeypatch)
    with pytest.raises(RuntimeError, match="No tenants configured"):
        tenancy.load_tenants_or_raise()


def test_short_token_rejected(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv(
        "REGULAITOR_TENANTS_JSON", json.dumps([{"token": "short", "tenant_id": "a", "name": "A"}])
    )
    with pytest.raises(RuntimeError, match="at least 16 characters"):
        tenancy.load_tenants_or_raise()


def test_short_api_token_rejected(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("REGULAITOR_API_TOKEN", "short")
    with pytest.raises(RuntimeError, match="at least 16 characters"):
        tenancy.load_tenants_or_raise()


def test_duplicate_tenant_id_rejected(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv(
        "REGULAITOR_TENANTS_JSON",
        json.dumps(
            [
                {"token": _T, "tenant_id": "dup", "name": "A"},
                {"token": _T2, "tenant_id": "dup", "name": "B"},
            ]
        ),
    )
    with pytest.raises(RuntimeError, match="duplicate tenant_id"):
        tenancy.load_tenants_or_raise()


def test_extra_field_rejected(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv(
        "REGULAITOR_TENANTS_JSON",
        json.dumps([{"token": _T, "tenant_id": "a", "name": "A", "bogus": 1}]),
    )
    with pytest.raises(Exception):  # noqa: B017 — Pydantic ValidationError (extra=forbid)
        tenancy.load_tenants_or_raise()


def test_resolve_unknown_token_returns_none(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("REGULAITOR_API_TOKEN", _T)
    tenancy.load_tenants_or_raise()
    assert tenancy.resolve_tenant("nope_xxxxxxxxxxxxxxx") is None


def test_non_ascii_token_resolves_none_without_crash(monkeypatch):
    """Review AUTH-1/TSC-1: a non-ASCII presented token (attacker-controlled, latin-1
    from the raw header) must resolve to None — NOT raise TypeError (which became a 500)."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("REGULAITOR_API_TOKEN", _T)
    tenancy.load_tenants_or_raise()
    # contains codepoints > 127 — str hmac.compare_digest would raise TypeError here
    assert tenancy.resolve_tenant("ñoño_tøken_with_nonascii_ééé") is None


def test_malformed_rate_limit_rejected_at_load(monkeypatch):
    """Review RL-1: a bad limit string must fail CLOSED at load, not fail-open at runtime."""
    _clear_env(monkeypatch)
    monkeypatch.setenv(
        "REGULAITOR_TENANTS_JSON",
        json.dumps([{"token": _T, "tenant_id": "a", "name": "A", "rate_limit_ask": "banana"}]),
    )
    with pytest.raises(Exception, match="invalid rate limit"):
        tenancy.load_tenants_or_raise()


def test_zero_rate_limit_rejected(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv(
        "REGULAITOR_TENANTS_JSON",
        json.dumps([{"token": _T, "tenant_id": "a", "name": "A", "rate_limit_ask": "0/minute"}]),
    )
    with pytest.raises(Exception, match="positive amount"):
        tenancy.load_tenants_or_raise()


def test_malformed_json_raises_named_error_and_stays_unloaded(monkeypatch):
    """Review TEN-LOAD-01/02: invalid JSON fails fast with a source-named error + fail-closed."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("REGULAITOR_TENANTS_JSON", "{not valid json")
    with pytest.raises(RuntimeError, match="REGULAITOR_TENANTS_JSON is not valid JSON"):
        tenancy.load_tenants_or_raise()
    assert tenancy.is_loaded() is False


def test_missing_file_raises_named_error_and_stays_unloaded(monkeypatch, tmp_path):
    _clear_env(monkeypatch)
    monkeypatch.setenv("REGULAITOR_TENANTS_FILE", str(tmp_path / "does_not_exist.json"))
    with pytest.raises(RuntimeError, match="REGULAITOR_TENANTS_FILE not found"):
        tenancy.load_tenants_or_raise()
    assert tenancy.is_loaded() is False


# --- Fase 6B (ADR-0042): per-tenant model_choice + corpus allowlist ---------


def _load_one(monkeypatch, **extra):
    _clear_env(monkeypatch)
    entry = {"token": _T, "tenant_id": "acme", "name": "Acme", **extra}
    monkeypatch.setenv("REGULAITOR_TENANTS_JSON", json.dumps([entry]))
    tenancy.load_tenants_or_raise()
    return tenancy.resolve_tenant(_T)


def test_defaults_unset_backward_compat(monkeypatch):
    t = _load_one(monkeypatch)
    assert t is not None and t.model_choice is None and t.allowed_corpora is None


def test_valid_model_choice_accepted(monkeypatch):
    t = _load_one(monkeypatch, model_choice="self_hosted")
    assert t.model_choice == "self_hosted"


def test_invalid_model_choice_rejected_at_load(monkeypatch):
    with pytest.raises(Exception, match="invalid model_choice"):
        _load_one(monkeypatch, model_choice="bogus-mode")


def test_valid_allowed_corpora_accepted(monkeypatch):
    t = _load_one(monkeypatch, allowed_corpora=["ai_act", "gdpr"])
    assert t.allowed_corpora == ["ai_act", "gdpr"]


def test_invalid_corpus_in_allowlist_rejected(monkeypatch):
    with pytest.raises(Exception, match="invalid corpus"):
        _load_one(monkeypatch, allowed_corpora=["ai_act", "not_a_corpus"])


def test_empty_allowed_corpora_rejected(monkeypatch):
    with pytest.raises(Exception, match="cannot be empty"):
        _load_one(monkeypatch, allowed_corpora=[])
