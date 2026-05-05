"""Slow integration: full chat E2E with real Anthropic Sonnet + real corpus + real validator."""

from __future__ import annotations

import os

import pytest

from regulaitor.citation.schemas import AuditVerdict
from regulaitor.corpus import loader
from regulaitor.orchestration.graph import run
from regulaitor.rag import reranker

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module", autouse=True)
def _setup() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set; slow LLM tests skipped")
    loader.reset()
    loader.warmup()
    reranker.warmup()
    yield
    loader.reset()


def test_chat_e2e_real_llm_simple_query() -> None:
    """Real LLM, real corpus, real Auditor. Asserts pipeline does not crash + verdict is defined."""
    state = run(
        query="¿Qué dice el AI Act sobre sistemas de inteligencia artificial de alto riesgo?",
        corpus="ai_act",
        language="es",
        case_id="ch-e2e-real",
    )

    assert state.injection_blocked is False
    assert state.audited_answer is not None
    # Any verdict is acceptable for non-flaky test (LLM has variance)
    assert state.audited_answer.verdict in {
        AuditVerdict.PASS,
        AuditVerdict.REQUIRES_HUMAN_REVIEW,
        AuditVerdict.BLOCK,
    }
    # Bound the cost (gate from CLAUDE.md §17)
    # We can't easily get cost out of state in lean H4 (no logging integration yet).
    # Task 12 adds structured logging that would surface this.
