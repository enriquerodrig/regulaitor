"""Unit tests for evals.judge — Haiku 4.5 wrapper + prompt loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from evals import judge


def test_load_judge_prompt_returns_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_prompt_path = tmp_path / "faithfulness.v1.0.md"
    fake_prompt_path.write_text("# Judge prompt\nTest content.\n", encoding="utf-8")
    monkeypatch.setattr(judge, "_PROMPT_PATH", fake_prompt_path)
    text = judge._load_judge_prompt()
    assert "Judge prompt" in text
    assert "Test content" in text


def test_load_judge_prompt_real_file_present() -> None:
    """The real prompt file must exist after Task 5."""
    assert judge._PROMPT_PATH.exists()
    content = judge._load_judge_prompt()
    assert "evaluador" in content.lower() or "evaluator" in content.lower()


def test_score_criteria_parses_json_response() -> None:
    fake_response = json.dumps(
        {
            "scores": [
                {"criterion": "Cita art. 6.1", "passed": True, "reason": "literal"},
                {"criterion": "No afirma X", "passed": False, "reason": "afirma X"},
            ]
        }
    )

    def fake_cache_call(**kwargs: Any) -> tuple[str, float]:
        return fake_response, 0.001

    scores = judge.score_criteria(
        criteria=["Cita art. 6.1", "No afirma X"],
        query="q",
        actual_answer="a",
        expected_answer="ea",
        cited_articles=["6.1"],
        expected_articles=["6.1"],
        cache_call=fake_cache_call,
    )
    assert len(scores) == 2
    assert scores[0].passed is True
    assert scores[1].passed is False
    assert scores[1].reason == "afirma X"


def test_score_criteria_raises_on_malformed_json() -> None:
    def fake_cache_call(**kwargs: Any) -> tuple[str, float]:
        return "not json{{", 0.001

    with pytest.raises(json.JSONDecodeError):
        judge.score_criteria(
            criteria=["c"],
            query="q",
            actual_answer="a",
            expected_answer=None,
            cited_articles=[],
            expected_articles=[],
            cache_call=fake_cache_call,
        )


def test_score_criteria_passes_correct_args_to_cache_call() -> None:
    captured: dict[str, Any] = {}

    def fake_cache_call(**kwargs: Any) -> tuple[str, float]:
        captured.update(kwargs)
        return json.dumps({"scores": []}), 0.0

    judge.score_criteria(
        criteria=["c"],
        query="q",
        actual_answer="a",
        expected_answer="ea",
        cited_articles=["6.1"],
        expected_articles=["6.1"],
        cache_call=fake_cache_call,
    )
    assert captured["model"] == "claude-haiku-4-5-20251001"
    assert captured["temperature"] == 0.0
    # The user payload should contain the JSON the prompt expects
    assert '"query":' in captured["user"]
    assert '"criteria":' in captured["user"]
