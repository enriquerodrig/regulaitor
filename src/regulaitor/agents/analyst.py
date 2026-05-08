"""AnalystAgent — produces a structured Answer via Anthropic tool use (H4).

Reuses the H3 RetrieverAgent pattern: thin class wrapping a stateless call.
The system prompt is versioned per the prompt-versioning skill (H3 drafted).
Decisions log 2026-05-05 entries "Anthropic Claude Sonnet 4.6 primary" + "tool use".
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from regulaitor.citation.schemas import Answer, Context
from regulaitor.models import router

# H5: prompts now live in subdirectories per role.
PROMPTS_ROOT = Path(__file__).parent / "prompts"
PROMPTS_DIR = PROMPTS_ROOT / "analyst"  # backcompat alias for tests + H4 callers

_PROMPT_VERSION_PATTERN = re.compile(r"^v\d+\.\d+$")
_PROMPT_ROLE_PATTERN = re.compile(r"^(analyst|document_analyst)$")


def _strip_unsupported_schema_fields(schema: dict[str, Any]) -> dict[str, Any]:
    """Pydantic v2 -> JSON Schema may include fields Anthropic SDK rejects.

    Hard-sets additionalProperties=False at root regardless of input value
    (defense against future Pydantic schema generation changes that might
    emit additionalProperties=True under extra="allow").
    """
    cleaned = dict(schema)
    cleaned["additionalProperties"] = False  # hard set, not setdefault
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

    def __init__(
        self,
        prompt_role: Literal["analyst", "document_analyst"] = "analyst",
        prompt_version: str = "v1.0",
    ) -> None:
        if not _PROMPT_ROLE_PATTERN.match(prompt_role):
            raise ValueError(
                f"prompt_role must match {_PROMPT_ROLE_PATTERN.pattern}; " f"got {prompt_role!r}"
            )
        if not _PROMPT_VERSION_PATTERN.match(prompt_version):
            raise ValueError(
                f"prompt_version must match {_PROMPT_VERSION_PATTERN.pattern}; "
                f"got {prompt_version!r}"
            )
        self.prompt_role = prompt_role
        self.prompt_version = prompt_version
        prompt_path = PROMPTS_ROOT / prompt_role / f"system.{prompt_version}.md"
        # Defense in depth.
        resolved = prompt_path.resolve()
        if not resolved.is_relative_to(PROMPTS_ROOT.resolve()):
            raise ValueError(
                f"prompt_role/version {prompt_role}/{prompt_version} resolves outside prompts dir"
            )
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
        try:
            return Answer.model_validate(result.tool_use_input)
        except ValidationError as e:
            raise RuntimeError(
                f"Analyst emitted malformed Answer: {e.error_count()} validation errors. "
                f"Errors: {e.errors()}"
            ) from e
