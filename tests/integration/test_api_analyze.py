"""Integration tests for POST /analyze."""

from __future__ import annotations

import pytest

from regulaitor.citation.schemas import (
    AuditVerdict,
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


def _multipart(file_name: str, file_bytes: bytes, corpus: str, language: str) -> list:
    """Build multipart fields list compatible with httpx 0.28+.

    httpx 0.28 deprecated passing io.BytesIO objects in the files tuple and no
    longer merges ``data=`` with ``files=`` into a single multipart body.
    Sending all fields as entries in the ``files`` list (using ``(None, value)``
    for plain text parts) is the supported approach across all versions.
    """
    mime = "application/pdf" if file_name.endswith(".pdf") else "text/plain"
    return [
        ("file", (file_name, file_bytes, mime)),
        ("corpus", (None, corpus)),
        ("language", (None, language)),
    ]


def test_analyze_happy_path(client, auth_headers, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "regulaitor.api.routes_analyze.run_document",
        lambda **_kw: _ok_report(),
    )
    response = client.post(
        "/analyze",
        headers=auth_headers,
        files=_multipart("policy.pdf", _MINIMAL_PDF_BYTES, "ai_act", "es"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["document_verdict"] == "pass"
    assert body["case_id"].startswith("api-doc-")


def test_analyze_no_auth_returns_401(client) -> None:
    response = client.post(
        "/analyze",
        files=_multipart("policy.pdf", _MINIMAL_PDF_BYTES, "ai_act", "es"),
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error_code"] == "http_401"
    assert "case_id" in body


def test_analyze_oversize_returns_413(
    client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("REGULAITOR_MAX_UPLOAD_BYTES", "100")
    big = b"%PDF-1.4\n" + (b"x" * 200)
    response = client.post(
        "/analyze",
        headers=auth_headers,
        files=_multipart("big.pdf", big, "ai_act", "es"),
    )
    assert response.status_code == 413


def test_analyze_empty_returns_415(client, auth_headers) -> None:
    response = client.post(
        "/analyze",
        headers=auth_headers,
        files=_multipart("empty.pdf", b"", "ai_act", "es"),
    )
    assert response.status_code == 415


def test_analyze_unsupported_mime_returns_415(client, auth_headers) -> None:
    # Pass a non-PDF, non-Markdown filename so _detect_mime raises UnsupportedMediaType
    response = client.post(
        "/analyze",
        headers=auth_headers,
        files=[
            ("file", ("bad.txt", b"plain text", "text/plain")),
            ("corpus", (None, "ai_act")),
            ("language", (None, "es")),
        ],
    )
    assert response.status_code == 415


def test_analyze_invalid_language_returns_415(client, auth_headers) -> None:
    response = client.post(
        "/analyze",
        headers=auth_headers,
        files=_multipart("policy.pdf", _MINIMAL_PDF_BYTES, "ai_act", "fr"),
    )
    assert response.status_code == 415


def test_analyze_invalid_corpus_returns_415(client, auth_headers) -> None:
    response = client.post(
        "/analyze",
        headers=auth_headers,
        files=_multipart("policy.pdf", _MINIMAL_PDF_BYTES, "nis2", "es"),
    )
    assert response.status_code == 415


def test_analyze_sanitizer_critical_returns_200_review(
    client, auth_headers, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When run_document detects sanitizer-critical content it returns a partial DocumentReport
    with verdict=requires_human_review (NOT a raised exception). The API surfaces this as HTTP 200.
    """

    def _critical_report(**_kw) -> DocumentReport:
        return DocumentReport(
            case_id="api-doc-x",
            document_hash="d" * 64,
            language="es",
            corpus=["ai_act"],
            sanitizer_log=[],
            segments=[],
            document_verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
            document_reason="sanitizer_critical:javascript_blocked",
            n_segments_total=0,
            n_segments_blocked_by_injection=0,
            n_segments_pass=0,
            n_segments_block=0,
            n_segments_review=0,
            latency_ms_total=120,
            cost_eur_total=0.0,
        )

    monkeypatch.setattr("regulaitor.api.routes_analyze.run_document", _critical_report)
    response = client.post(
        "/analyze",
        headers=auth_headers,
        files=_multipart("policy.pdf", _MINIMAL_PDF_BYTES, "ai_act", "es"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["document_verdict"] == "requires_human_review"
    assert body["document_reason"] == "sanitizer_critical:javascript_blocked"
