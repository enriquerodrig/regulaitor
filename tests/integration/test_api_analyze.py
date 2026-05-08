"""Integration tests for POST /analyze."""

from __future__ import annotations

import io

import pytest

from regulaitor.citation.schemas import (
    AuditVerdict,
    DocumentBlockedError,
    DocumentReport,
)


def _ok_report(case_id: str = "api-doc-fake-1") -> DocumentReport:
    return DocumentReport(
        case_id=case_id,
        document_hash="d" * 64,
        language="es",
        corpus=["ai_act"],
        sanitizer_log=[],
        segments=[],
        document_verdict=AuditVerdict.PASS,
        document_reason=None,
        n_segments_total=0,
        n_segments_blocked_by_injection=0,
        n_segments_pass=0,
        n_segments_block=0,
        n_segments_review=0,
        latency_ms_total=120,
        cost_eur_total=0.0,
    )


_MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\n"
    b"0000000000 65535 f \ntrailer\n<<>>\nstartxref\n9\n%%EOF\n"
)


def test_analyze_happy_path(client, auth_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "regulaitor.api.routes_analyze.run_document",
        lambda **_kw: _ok_report(),
    )
    files = {"file": ("policy.pdf", io.BytesIO(_MINIMAL_PDF_BYTES), "application/pdf")}
    data = [("corpus", "ai_act"), ("language", "es")]
    response = client.post("/analyze", headers=auth_headers, files=files, data=data)
    assert response.status_code == 200
    body = response.json()
    assert body["document_verdict"] == "pass"
    assert body["case_id"].startswith("api-doc-")


def test_analyze_no_auth_returns_401(client) -> None:
    files = {"file": ("policy.pdf", io.BytesIO(_MINIMAL_PDF_BYTES), "application/pdf")}
    response = client.post("/analyze", files=files, data=[("corpus", "ai_act"), ("language", "es")])
    assert response.status_code == 401


def test_analyze_oversize_returns_413(
    client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REGULAITOR_MAX_UPLOAD_BYTES", "100")
    big = b"%PDF-1.4\n" + (b"x" * 200)
    files = {"file": ("big.pdf", io.BytesIO(big), "application/pdf")}
    response = client.post(
        "/analyze",
        headers=auth_headers,
        files=files,
        data=[("corpus", "ai_act"), ("language", "es")],
    )
    assert response.status_code == 413


def test_analyze_empty_returns_415(client, auth_headers) -> None:
    files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}
    response = client.post(
        "/analyze",
        headers=auth_headers,
        files=files,
        data=[("corpus", "ai_act"), ("language", "es")],
    )
    assert response.status_code == 415


def test_analyze_unsupported_mime_returns_415(client, auth_headers) -> None:
    files = {"file": ("bad.txt", io.BytesIO(b"plain text"), "text/plain")}
    response = client.post(
        "/analyze",
        headers=auth_headers,
        files=files,
        data=[("corpus", "ai_act"), ("language", "es")],
    )
    assert response.status_code == 415


def test_analyze_invalid_language_returns_415(client, auth_headers) -> None:
    files = {"file": ("policy.pdf", io.BytesIO(_MINIMAL_PDF_BYTES), "application/pdf")}
    response = client.post(
        "/analyze",
        headers=auth_headers,
        files=files,
        data=[("corpus", "ai_act"), ("language", "fr")],
    )
    assert response.status_code == 415


def test_analyze_invalid_corpus_returns_415(client, auth_headers) -> None:
    files = {"file": ("policy.pdf", io.BytesIO(_MINIMAL_PDF_BYTES), "application/pdf")}
    response = client.post(
        "/analyze",
        headers=auth_headers,
        files=files,
        data=[("corpus", "nis2"), ("language", "es")],
    )
    assert response.status_code == 415


def test_analyze_document_blocked_returns_422(
    client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise(**_kw):
        raise DocumentBlockedError(reason="javascript detected", sanitizer_log=[])

    monkeypatch.setattr("regulaitor.api.routes_analyze.run_document", _raise)
    files = {"file": ("policy.pdf", io.BytesIO(_MINIMAL_PDF_BYTES), "application/pdf")}
    response = client.post(
        "/analyze",
        headers=auth_headers,
        files=files,
        data=[("corpus", "ai_act"), ("language", "es")],
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error_code"] == "document_blocked"
