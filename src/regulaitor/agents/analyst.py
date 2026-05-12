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
        """Produce a validated Answer via Anthropic tool use.

        H8 finding: Sonnet occasionally drops the `findings` field despite the
        tool_use input_schema marking it required. One retry with a `tool_result`
        error message recovers the case without contaminating downstream with
        sentinel fallbacks. Spec §6 "no citation, no answer" stays intact —
        if the second attempt also fails, RuntimeError surfaces as before.
        """
        tools_spec = [
            {
                "name": "emit_answer",
                "description": "Emit the final Answer with findings + citations.",
                "input_schema": _strip_unsupported_schema_fields(Answer.model_json_schema()),
            }
        ]
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": _render_user_message(query, context)}
        ]
        last_error: ValidationError | None = None
        retried = False
        for attempt in (1, 2):
            result = router.complete(
                messages=messages,
                system=self._system_prompt,
                tools=tools_spec,
                tool_choice={"type": "tool", "name": "emit_answer"},
                model_choice="default",
                max_tokens=2000,
            )
            if result.tool_use_input is None:
                raise RuntimeError(
                    f"Analyst LLM did not emit emit_answer tool call (attempt {attempt})"
                )
            try:
                return Answer.model_validate(result.tool_use_input)
            except ValidationError as e:
                last_error = e
                if attempt == 2 or not _is_findings_missing(e):
                    break
                # H8 retry: feed back the malformed tool_use with a tool_result error
                tool_use_id = "retry_h4_findings"
                messages = messages + [
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": tool_use_id,
                                "name": "emit_answer",
                                "input": result.tool_use_input,
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_use_id,
                                "content": (
                                    "Your emit_answer call was missing the required "
                                    "`findings` field. Re-emit the Answer with all "
                                    "required fields. If the corpus does not support "
                                    "specific findings, emit `findings: []` as your "
                                    "system instructions describe."
                                ),
                                "is_error": True,
                            }
                        ],
                    },
                ]
                retried = True
        suffix = " after retry" if retried else ""
        raise RuntimeError(
            f"Analyst emitted malformed Answer{suffix}: "
            f"{last_error.error_count() if last_error else 0} validation errors. "
            f"Errors: {last_error.errors() if last_error else []}"
        ) from last_error


def _is_findings_missing(e: ValidationError) -> bool:
    """True if validation errors are EXCLUSIVELY about `findings` being absent.

    Conservative: returns False if there are any other validation errors so
    we don't waste a retry when the model's response is broken in multiple ways.
    """
    errors = e.errors()
    if not errors:
        return False
    return all(err.get("loc") == ("findings",) and err.get("type") == "missing" for err in errors)
