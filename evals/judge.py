"""H8 — Haiku 4.5 LLM-as-judge wrapper.

Loads the versioned judge prompt from src/regulaitor/agents/prompts/judge/
(per H4 prompt-versioning skill) and exposes `score_criteria` that the
metrics module calls per case to grade `criterios_evaluacion`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from evals.schemas import CriteriaScore

_JUDGE_MODEL = "claude-haiku-4-5-20251001"
_PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "regulaitor"
    / "agents"
    / "prompts"
    / "judge"
    / "faithfulness.v1.0.md"
)
_MAX_TOKENS = 2000


def _load_judge_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def score_criteria(
    *,
    criteria: list[str],
    query: str,
    actual_answer: str,
    expected_answer: str | None,
    cited_articles: list[str],
    expected_articles: list[str],
    cache_call: Callable[..., tuple[str, float]],
) -> list[CriteriaScore]:
    """Ask Haiku 4.5 to judge each criterion. Returns one CriteriaScore per item.

    `cache_call` is the cache-aware LLM invoke function; the harness pre-binds
    `invoke` and `cache_only` via functools.partial. This function calls it with
    keyword args (model, system, user, temperature, max_tokens) and expects
    (response_text, cost_eur).
    """
    system_prompt = _load_judge_prompt()
    user_payload: dict[str, Any] = {
        "query": query,
        "actual_answer": actual_answer,
        "expected_answer": expected_answer,
        "cited_articles": cited_articles,
        "expected_articles": expected_articles,
        "criteria": criteria,
    }
    user_message = json.dumps(user_payload, ensure_ascii=False, indent=2)

    response_text, _cost = cache_call(
        model=_JUDGE_MODEL,
        system=system_prompt,
        user=user_message,
        temperature=0.0,
        max_tokens=_MAX_TOKENS,
    )
    parsed = json.loads(response_text)
    return [CriteriaScore(**s) for s in parsed["scores"]]
