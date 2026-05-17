"""H12 — pure Anthropic<->OpenAI tool/message translation.

The Analyst (H4, read-only) speaks Anthropic's tool schema. OpenAI and Groq
(OpenAI-compatible) need the function-calling schema. These helpers are pure
and exhaustively unit-tested ($0) because cross-provider tool-calling parity
is the highest H12 risk (spec §5/§9).
"""

from __future__ import annotations

import json
from typing import Any


def tools_to_openai(
    tools: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    """Anthropic [{name,description,input_schema}] -> OpenAI function tools."""
    if tools is None:
        return None
    return [
        {
            "type": "function",
            "function": {
                "name": tspec["name"],
                "description": tspec.get("description", ""),
                "parameters": tspec["input_schema"],
            },
        }
        for tspec in tools
    ]


def tool_choice_to_openai(
    tool_choice: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Anthropic {"type":"tool","name":N} -> OpenAI {"type":"function",...}."""
    if tool_choice is None:
        return None
    if tool_choice.get("type") == "tool" and "name" in tool_choice:
        return {"type": "function", "function": {"name": tool_choice["name"]}}
    # "any"/"auto" pass through unchanged (OpenAI accepts "auto"/"required").
    return tool_choice


def messages_to_openai(messages: list[dict[str, Any]], *, system: str) -> list[dict[str, Any]]:
    """Translate Anthropic messages (+system) to OpenAI chat messages.

    Handles: plain string content; the H8 retry assistant `tool_use` block ->
    assistant `tool_calls`; the H8 retry user `tool_result` block -> a
    `{"role":"tool",...}` message.
    """
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        # content is a list of Anthropic blocks
        for block in content:
            btype = block.get("type")
            if btype == "tool_use":
                out.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": block["id"],
                                "type": "function",
                                "function": {
                                    "name": block["name"],
                                    "arguments": json.dumps(block["input"], ensure_ascii=False),
                                },
                            }
                        ],
                    }
                )
            elif btype == "tool_result":
                out.append(
                    {
                        "role": "tool",
                        "tool_call_id": block["tool_use_id"],
                        "content": block["content"],
                    }
                )
            elif btype == "text":
                out.append({"role": role, "content": block["text"]})
            else:
                # Security-critical translator: never silently drop a message
                # block. The Analyst (sole producer) emits only the 3 types
                # above; an unknown type means the producer changed and a
                # message would be lost — surface it loudly instead.
                raise ValueError(f"unrecognized Anthropic block type: {btype!r}")
    return out


def extract_openai_tool_use(response: Any) -> tuple[str | None, dict[str, Any] | None]:
    """OpenAI/Groq response -> (text, tool_use_input) matching CompletionResult.

    tool_use_input is the parsed JSON arguments of the first tool call, or None
    if the model returned plain content instead.
    """
    message = response.choices[0].message
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        args = tool_calls[0].function.arguments
        return None, json.loads(args)
    text = message.content
    return (text if text else None), None
