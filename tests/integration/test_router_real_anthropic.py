"""Slow integration: direct router call to real Anthropic API."""

from __future__ import annotations

import os

import pytest

from regulaitor.models import router
from regulaitor.models.config import ANTHROPIC_SONNET_4_6

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module", autouse=True)
def _require_api_key() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set; slow LLM tests skipped")


def test_router_simple_text_completion() -> None:
    result = router.complete(
        messages=[{"role": "user", "content": "Reply with the single word PASS"}],
        system="You are a test fixture. Reply exactly as instructed.",
        max_tokens=20,
    )
    assert result.text is not None
    assert "PASS" in result.text.upper()
    assert result.tool_use_input is None
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0
    assert result.cost_eur > 0
    assert result.latency_ms > 0
    assert result.model_id == ANTHROPIC_SONNET_4_6
