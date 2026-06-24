"""AnalystAgent — produces a structured Answer via Anthropic tool use (H4).

Reuses the H3 RetrieverAgent pattern: thin class wrapping a stateless call.
The system prompt is versioned per the prompt-versioning skill (H3 drafted).
Decisions log 2026-05-05 entries "Anthropic Claude Sonnet 4.6 primary" + "tool use".
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import ValidationError

from regulaitor.citation.schemas import Answer, Context
from regulaitor.models import router

# H5: prompts now live in subdirectories per role.
PROMPTS_ROOT = Path(__file__).parent / "prompts"
PROMPTS_DIR = PROMPTS_ROOT / "analyst"  # backcompat alias for tests + H4 callers

_PROMPT_VERSION_PATTERN = re.compile(r"^v\d+\.\d+$")
_PROMPT_ROLE_PATTERN = re.compile(r"^(analyst|document_analyst)$")

logger = logging.getLogger("regulaitor.agents.analyst")


def _set_additional_properties_false_recursive(node: Any) -> Any:
    """Walk a JSON Schema and set ``additionalProperties: False`` on every
    object-typed subschema (root + nested + $defs).

    v0.1.22 (ADR-0029): the original root-only setter ([analyst.py:45] pre-fix)
    left ``$defs`` entries (Finding, Citation) and nested object properties
    untouched. Anthropic strict mode (Capa A; ``"strict": True``) rejects such
    schemas with ``400 invalid_request_error: tools.0.custom: For 'object'
    type, 'additionalProperties' must be explicitly set to false``. The bug
    shipped silently in v0.1.21 because the T0 strict-mode probe used a
    trivial schema (no nested objects, no $defs). v0.1.22 paid probe
    discovered it on 5/5 chat cases → 100% RHR rate (broken-fail-safe per
    §6 invariant preservation; documented honestly in ADR-0029 §22.22).

    Returns a deep-copy with the patch applied; original schema not mutated.
    """
    if isinstance(node, dict):
        new = {k: _set_additional_properties_false_recursive(v) for k, v in node.items()}
        if new.get("type") == "object":
            new["additionalProperties"] = False
        return new
    if isinstance(node, list):
        return [_set_additional_properties_false_recursive(item) for item in node]
    return node


def _strip_unsupported_schema_fields(schema: dict[str, Any]) -> dict[str, Any]:
    """Pydantic v2 -> JSON Schema may include fields Anthropic SDK rejects.

    Recursively sets ``additionalProperties: False`` on every object-typed
    subschema (v0.1.22 fix; pre-fix root-only setter shipped silently broken
    in v0.1.21 — see ``_set_additional_properties_false_recursive`` docstring
    for the full §22.22 disclosure).

    v0.1.21 (ADR-0027 D2, Capa A): also injects `minItems: 1` on the
    `findings` array property at the root level. Defense-in-depth with
    Pydantic Capa B; the Anthropic API rejects tool_use responses where
    `findings` is empty at the model-output stage (closer to the source
    than Capa B), feeding the failure into Capa C retry loop.
    """
    cleaned = _set_additional_properties_false_recursive(schema)
    # Capa A: inject minItems=1 on findings if the property exists.
    props = cleaned.get("properties")
    if isinstance(props, dict) and "findings" in props and isinstance(props["findings"], dict):
        # Copy-on-write so the original Pydantic schema dict is not mutated.
        props = dict(props)
        findings_schema = dict(props["findings"])
        findings_schema["minItems"] = 1
        props["findings"] = findings_schema
        cleaned["properties"] = props
    return cleaned


def _analyst_model_choice() -> router.ModelChoice:
    """Probe/eval seam: override ONLY the Analyst's router mode.

    The global REGULAITOR_ROUTER_MODE (ADR-0013) overrides EVERY router call,
    including the Auditor/Council judge — useless for an A/B that must keep the
    judge constant while swapping the Analyst's model. This Analyst-scoped seam
    (mirrors REGULAITOR_ANALYST_PROMPT_VERSION) does exactly that. Env unset =>
    'default' (Sonnet, prod byte-identical); invalid value => 'default' +
    WARNING (never crashes on a bad env). Set REGULAITOR_ANALYST_MODEL_CHOICE=
    self_hosted for the open-model probe R1.
    """
    v = os.environ.get("REGULAITOR_ANALYST_MODEL_CHOICE")
    if v is None:
        return "default"
    if v in router._VALID_MODES:
        return cast("router.ModelChoice", v)
    logger.warning(
        "REGULAITOR_ANALYST_MODEL_CHOICE=%r invalid (valid: %s); using 'default'",
        v,
        sorted(router._VALID_MODES),
    )
    return "default"


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
        prompt_version: str | None = None,
    ) -> None:
        if prompt_version is None:
            # Eval-only env seam (ADR 0016 + ADR-0026), analogous to ADR-0013
            # REGULAITOR_ROUTER_MODE. v0.1.20 flipped the env-unset default
            # for the chat `analyst` role from v1.0 to v1.4 per ADR-0026
            # (T6 bar 6/7 PASS + T7 safety floor PASS). v0.1.21 further
            # flipped the chat default v1.4 -> v1.5 per ADR-0027 final-review
            # C4 (v1.4's `findings: []` refusal pattern is incompatible with
            # v0.1.21 Tier 2 Capa A+B hard constraints on findings non-empty;
            # v1.5 ships Finding-based refusal that satisfies the schema
            # while preserving §6 "no citation, no answer" via corpus-grounded
            # refusal). v0.1.28 flipped the `document_analyst` role default
            # v1.0 -> v1.6 per ADR-0033 (v0.1.27 probe revealed v1.0 doc_analyst
            # emits placeholder citation strings <UNKNOWN>/N/A/... when context
            # insufficient → all-blocked → 3/3 BLOCK verdicts; v1.6 = v1.5
            # doc-mode adaptation with Finding-based refusal pattern citing
            # corpus scope article when segment cannot be analyzed).
            # Invalid env still falls back to v1.0 (known-safe baseline;
            # never crashes on a bad env value). Opt-in to v1.0 for either
            # role via REGULAITOR_ANALYST_PROMPT_VERSION=v1.0; v1.4 still
            # loadable via the same env (for retrospective comparison with
            # the v0.1.20 paid A/B).
            default_version = "v1.5" if prompt_role == "analyst" else "v1.6"
            env_v = os.environ.get("REGULAITOR_ANALYST_PROMPT_VERSION")
            if env_v is None:
                prompt_version = default_version
            elif _PROMPT_VERSION_PATTERN.match(env_v):
                prompt_version = env_v
            else:
                logger.warning(
                    "REGULAITOR_ANALYST_PROMPT_VERSION=%r invalid (expected vN.M); using v1.0",
                    env_v,
                )
                prompt_version = "v1.0"
        if not _PROMPT_ROLE_PATTERN.match(prompt_role):
            raise ValueError(
                f"prompt_role must match {_PROMPT_ROLE_PATTERN.pattern}; got {prompt_role!r}"
            )
        if not _PROMPT_VERSION_PATTERN.match(prompt_version):
            raise ValueError(
                f"prompt_version must match {_PROMPT_VERSION_PATTERN.pattern}; "
                f"got {prompt_version!r}"
            )
        self.prompt_role = prompt_role
        self.prompt_version = prompt_version
        prompt_path = PROMPTS_ROOT / prompt_role / f"system.{prompt_version}.md"
        resolved = prompt_path.resolve()
        if not resolved.is_relative_to(PROMPTS_ROOT.resolve()):
            raise ValueError(
                f"prompt_role/version {prompt_role}/{prompt_version} resolves outside prompts dir"
            )
        self._system_prompt = prompt_path.read_text(encoding="utf-8")

    def analyze(self, query: str, context: Context, *, model_choice: str | None = None) -> Answer:
        """Produce a validated Answer via Anthropic tool use.

        v0.1.21 (ADR-0027 D4, Capa C): aggressive retry with
        failure-specific feedback. Up to 3 attempts total. On each Pydantic
        ValidationError (Capa B `findings=[]` rejection, or any other
        format failure), the next attempt's tool_result message includes:
        - the failure category ("findings empty" vs other validation),
        - a quoted excerpt of the offending `text` field (first 200 chars),
        - an actionable instruction to map claims to Findings or remove
          unsupported claims from `text`.

        Spec §6 "no citation, no answer" stays intact — if all 3 attempts
        fail, RuntimeError surfaces (preserves H8 behavior); the Auditor
        still acts on the eventual valid response if attempts 1 or 2 succeed.
        """
        tools_spec = [
            {
                "name": "emit_answer",
                "description": "Emit the final Answer with findings + citations.",
                # v0.1.21 (ADR-0027 D2, Capa A): strict mode enforces the
                # `minItems: 1` on `findings` at the Anthropic API layer
                # (T0 verified strict support on Sonnet 4.6). Capa B
                # (Pydantic min_length=1) is the post-API defense; Capa C
                # (this retry loop) is the recovery layer.
                "strict": True,
                "input_schema": _strip_unsupported_schema_fields(Answer.model_json_schema()),
            }
        ]
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": _render_user_message(query, context)}
        ]
        last_error: ValidationError | None = None
        n_retries = 0
        max_attempts = 3
        # Fase 6B (ADR-0042): a per-tenant model_choice (threaded from the route)
        # overrides the env seam; an unset/invalid value falls back to it.
        chosen_model: router.ModelChoice = (
            cast("router.ModelChoice", model_choice)
            if model_choice in router._VALID_MODES
            else _analyst_model_choice()
        )
        for attempt in range(1, max_attempts + 1):
            result = router.complete(
                messages=messages,
                system=self._system_prompt,
                tools=tools_spec,
                tool_choice={"type": "tool", "name": "emit_answer"},
                model_choice=chosen_model,
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
                if attempt == max_attempts:
                    break
                # Capa C: build failure-specific feedback and retry (deep-review
                # I2 fix: branch on actual error shape vs hardcoded empty-findings
                # variant; honors ADR-0027 D4 "failure-specific feedback" mandate).
                offending_text = ""
                if isinstance(result.tool_use_input, dict):
                    raw_text = result.tool_use_input.get("text")
                    if isinstance(raw_text, str):
                        offending_text = raw_text[:200]
                feedback = _build_retry_feedback(e, offending_text)
                tool_use_id = f"retry_v0121_attempt{attempt}"
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
                                "content": feedback,
                                "is_error": True,
                            }
                        ],
                    },
                ]
                n_retries += 1
        suffix = f" after {n_retries} retries" if n_retries else ""
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


def _build_retry_feedback(e: ValidationError, offending_text: str) -> str:
    """Map a ValidationError to a failure-specific retry feedback string.

    Per ADR-0027 D4: feedback should describe WHICH field failed and HOW to
    fix it, not a generic "fix your response" message. Deep-review I2 fix:
    previously hardcoded to the empty-findings variant; now branches on the
    actual error shape (findings missing/empty, findings citations malformed,
    text empty/missing, language invalid, severity invalid, or generic fallback).
    """
    errors = e.errors()
    if not errors:
        return "Your response had no validation errors but Answer.model_validate failed. Retry."

    # Categorize: empty/missing findings (most common path; Capa B min_length=1).
    if _is_findings_missing(e) or all(
        err.get("loc") in (("findings",), ("findings", 0)) for err in errors
    ):
        return (
            "Your previous response had `findings=[]` or `findings` missing. "
            f"Your text claimed: '{offending_text}'. Map each substantive claim "
            "to a Finding with citations. If you cannot find a citation in the "
            "retrieved context to support a claim, remove that claim from text."
        )

    # Categorize: malformed citations inside findings (e.g. invalid norma,
    # missing apartado, whitespace-only text per v0.1.32-post).
    if any(
        isinstance(err.get("loc"), tuple)
        and len(err["loc"]) >= 3
        and err["loc"][0] == "findings"
        and err["loc"][2] == "citations"
        for err in errors
    ):
        first = errors[0]
        return (
            f"Your previous response had malformed citations: {first.get('msg', '')}. "
            "Every Finding must have ≥1 valid Citation with non-empty norma, "
            "articulo, language, and non-whitespace text quoted literally from "
            "the retrieved context. Re-emit emit_answer with valid citations."
        )

    # Categorize: text field empty or missing.
    if any(err.get("loc") == ("text",) for err in errors):
        return (
            "Your previous response had an empty or missing `text` field. "
            "Emit a non-empty `text` summarizing the answer (≥1 char)."
        )

    # Generic fallback: cite the first error verbatim so Sonnet can self-correct.
    first = errors[0]
    return (
        f"Your previous response had {len(errors)} validation error(s). First: "
        f"location={first.get('loc')} type={first.get('type')} msg={first.get('msg', '')}. "
        "Re-emit emit_answer with a valid Answer schema."
    )
