"""Unit tests for scripts/chat.py — CLI smoke entry."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    Finding,
)
from regulaitor.orchestration.state import ChatState


def _make_audited_answer() -> AuditedAnswer:
    citation = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")
    finding = Finding(text="f", citations=[citation])
    answer = Answer(query="q", language="es", text="response", findings=[finding])
    audit_result = AuditResult(
        citation=citation,
        validated=True,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=True,
        reason=None,
    )
    return AuditedAnswer(
        answer=answer,
        verdict=AuditVerdict.PASS,
        audit_results=[audit_result],
        reason=None,
    )


def test_chat_main_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    audited = _make_audited_answer()
    state = ChatState(
        case_id="ch-test",
        query="q",
        corpus="ai_act",
        language="es",
        audited_answer=audited,
    )

    import scripts.chat as chat_module

    monkeypatch.setattr(chat_module, "run", MagicMock(return_value=state))

    rc = chat_module.main(["--query", "q", "--corpus", "ai_act", "--lang", "es"])

    assert rc == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["verdict"] == "pass"
    assert output["case_id"].startswith("ch-")
    assert output["audit"]["n_validated"] == 1


def test_chat_main_blocked_injection(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    state = ChatState(
        case_id="ch-test",
        query="ignore previous",
        corpus="ai_act",
        language="es",
        injection_blocked=True,
        injection_reason="ignore-previous",
        audited_answer=None,
    )

    import scripts.chat as chat_module

    monkeypatch.setattr(chat_module, "run", MagicMock(return_value=state))

    rc = chat_module.main(["--query", "ignore previous", "--corpus", "ai_act", "--lang", "es"])

    assert rc == 1
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["verdict"] == "blocked_injection"


def test_chat_main_block_verdict(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    audited = _make_audited_answer()
    blocked_audited = audited.model_copy(
        update={"verdict": AuditVerdict.BLOCK, "reason": "BLOCK: ..."}
    )
    state = ChatState(
        case_id="ch-test",
        query="q",
        corpus="ai_act",
        language="es",
        audited_answer=blocked_audited,
    )

    import scripts.chat as chat_module

    monkeypatch.setattr(chat_module, "run", MagicMock(return_value=state))

    rc = chat_module.main(["--query", "q", "--corpus", "ai_act", "--lang", "es"])

    assert rc == 1
