"""AnalystAgent — produces a structured Answer via Anthropic tool use (H4).

Reuses the H3 RetrieverAgent pattern: thin class wrapping a stateless call.
The system prompt is versioned per the prompt-versioning skill (H3 drafted).
Decisions log 2026-05-05 entries "Anthropic Claude Sonnet 4.6 primary" + "tool use".
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from regulaitor.citation.schemas import Answer, Context
from regulaitor.models import router

PROMPTS_DIR = Path(__file__).parent / "prompts" / "analyst"


def _strip_unsupported_schema_fields(schema: dict[str, Any]) -> dict[str, Any]:
    """Pydantic v2 -> JSON Schema may include fields Anthropic SDK rejects.

    Specifically: top-level `additionalProperties` and `$defs` references that
    Anthropic does accept, but `additionalProperties: false` should be set
    explicitly at the root for tool schemas.
    """
    cleaned = dict(schema)
    cleaned.setdefault("additionalProperties", False)
    return cleaned


def _render_user_message(query: str, context: Context) -> str:
    """Format the retrieved context into a prompt-friendly text block."""
    lines = [f"User query: {query}", "", f"Retrieved context ({len(context.chunks)} chunks):"]
    for i, chunk in enumerate(context.chunks, start=1):
        location = f"{chunk.norma} art. {chunk.articulo}"
        if chunk.apartado is not None:
            location += f".{chunk.apartado}"
        location += f" ({chunk.language})"
        lines.append(f"\n[Chunk {i}] {location}\n{chunk.text}")
    return "\n".join(lines)


class AnalystAgent:
    """Stateless Analyst: load versioned prompt, call router, parse Answer."""

    def __init__(self, prompt_version: str = "v1.0") -> None:
        self.prompt_version = prompt_version
        prompt_path = PROMPTS_DIR / f"system.{prompt_version}.md"
        self._system_prompt = prompt_path.read_text(encoding="utf-8")

    def analyze(self, query: str, context: Context) -> Answer:
        """Produce a validated Answer via Anthropic tool use."""
        result = router.complete(
            messages=[{"role": "user", "content": _render_user_message(query, context)}],
            system=self._system_prompt,
            tools=[
                {
                    "name": "emit_answer",
                    "description": "Emit the final Answer with findings + citations.",
                    "input_schema": _strip_unsupported_schema_fields(Answer.model_json_schema()),
                }
            ],
            tool_choice={"type": "tool", "name": "emit_answer"},
            model_choice="default",
            max_tokens=2000,
        )
        if result.tool_use_input is None:
            raise RuntimeError("Analyst LLM did not emit emit_answer tool call; received text only")
        return Answer.model_validate(result.tool_use_input)
