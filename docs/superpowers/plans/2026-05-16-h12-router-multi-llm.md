# H12 — Router multi-LLM + cost analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `models/router.py` + `models/config.py` to 3 real providers (Anthropic/OpenAI/Groq) with mode-based routing, an eval-only env override, and controlled one-hop fallback; run a user-gated paid A/B; produce `docs/cost_analysis.md` with measured cost-vs-quality numbers — H1–H5 backend untouched.

**Architecture:** Approach 1 (spec §D4): `complete()` reads optional env `REGULAITOR_ROUTER_MODE` (overrides caller's `model_choice`, eval-only; unset = prod unchanged), resolves `mode → (provider, model_id)`, dispatches to `_call_anthropic`/`_call_openai`/`_call_groq` (each returns the existing provider-agnostic `CompletionResult`, each its own tenacity retry). Pure translation helpers convert the Analyst's Anthropic-shaped `tools`/`tool_choice`/`messages` (incl. the H8 retry `tool_use`/`tool_result` blocks) to/from the OpenAI schema (Groq is OpenAI-compatible). Real per-call `cost_eur` from `config.PRICING`. A thin `scripts/ab_eval.py` reuses `evals/harness.py` to run the GPT-4o + Llama arms; the Sonnet arm reuses the frozen H10/H11 baseline.

**Tech Stack:** Python 3.11 · `anthropic` (have) · `openai` SDK (new) · `groq` SDK (new) · `tenacity` · pytest. Spec: [docs/superpowers/specs/2026-05-16-h12-router-cost-design.md](../specs/2026-05-16-h12-router-cost-design.md) (commit `3a0e331`).

---

## File structure (lock-in)

```
Modified:
src/regulaitor/models/config.py    # Task 1 — new model-id consts + PRICING + PRICING_SNAPSHOT_DATE
src/regulaitor/models/router.py    # Tasks 2-7 — ModelChoice, _MODE_MAP, env resolve,
                                   #             translators, _call_openai/_call_groq, fallback
pyproject.toml                     # Task 1 — +openai +groq deps + mypy overrides

New:
src/regulaitor/models/_translate.py             # Task 4 — pure Anthropic<->OpenAI tool/msg translators
scripts/ab_eval.py                              # Task 8 — thin A/B wrapper over evals.harness
docs/cost_analysis.md                           # Task 10 — measured 3-way table
docs/adr/0013-router-multi-llm.md               # Task 11
tests/unit/models/test_config.py               # Task 1 (extend if exists; else create)
tests/unit/models/test_translate.py            # Task 4
tests/unit/models/test_router.py               # Tasks 2-7 (extend existing)
tests/unit/scripts/test_ab_eval.py             # Task 8

Read-only (DO NOT MODIFY): src/regulaitor/agents/*, orchestration/*, api/*,
ui_streamlit/*, citation/*, evals/harness.py (reuse, do not edit), prompts.
```

Boundary: only the files listed under "Modified"/"New" change. `evals/harness.py` is **reused** by `scripts/ab_eval.py`, not edited.

---

## Task 1: Scaffolding — SDK deps + config.py model IDs/pricing

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/regulaitor/models/config.py`
- Test: `tests/unit/models/test_config.py`

- [ ] **Step 1: Write failing test for new pricing + snapshot**

Create/extend `tests/unit/models/test_config.py`:
```python
"""Unit tests for models/config.py (H12 multi-provider pricing)."""

from __future__ import annotations

from regulaitor.models import config


def test_pricing_snapshot_date_present() -> None:
    assert isinstance(config.PRICING_SNAPSHOT_DATE, str)
    assert config.PRICING_SNAPSHOT_DATE  # non-empty


def test_cost_eur_known_for_all_h12_models() -> None:
    for mid in (
        config.ANTHROPIC_SONNET_4_6,
        config.OPENAI_GPT_4O,
        config.OPENAI_GPT_4O_MINI,
        config.GROQ_LLAMA_70B,
    ):
        c = config.cost_eur(model_id=mid, input_tokens=1000, output_tokens=500)
        assert c > 0.0


def test_cost_eur_gpt_4o_value() -> None:
    # 1M in @2.50 + 1M out @10.00 = 12.50 USD * 0.93 = 11.625 EUR
    c = config.cost_eur(
        model_id=config.OPENAI_GPT_4O,
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert abs(c - 11.625) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest --no-cov tests/unit/models/test_config.py -v`
Expected: FAIL — `AttributeError: module 'regulaitor.models.config' has no attribute 'PRICING_SNAPSHOT_DATE'`.

- [ ] **Step 3: Add model IDs + pricing to config.py**

In `src/regulaitor/models/config.py`, replace the model-id + PRICING block (lines ~17-25) with:
```python
# Model IDs
ANTHROPIC_SONNET_4_6 = "claude-sonnet-4-6"
OPENAI_GPT_4O = "gpt-4o"
OPENAI_GPT_4O_MINI = "gpt-4o-mini"
# Groq's exact 70B id is verified against the live catalog in Task 6 (3.1-70B
# may be served as llama-3.3-70b-versatile); update this constant + PRICING key
# together if it differs, and record the verified id in decisions log §H12.
GROQ_LLAMA_70B = "llama-3.3-70b-versatile"

# Published list prices, USD per 1M tokens. VERIFY against each provider's
# pricing page at implementation time and pin PRICING_SNAPSHOT_DATE; if a
# number differs, use the verified value and note it in decisions log §H12.
PRICING: dict[str, ModelPricing] = {
    ANTHROPIC_SONNET_4_6: ModelPricing(input_per_million=3.0, output_per_million=15.0),
    OPENAI_GPT_4O: ModelPricing(input_per_million=2.50, output_per_million=10.0),
    OPENAI_GPT_4O_MINI: ModelPricing(input_per_million=0.15, output_per_million=0.60),
    GROQ_LLAMA_70B: ModelPricing(input_per_million=0.59, output_per_million=0.79),
}

PRICING_SNAPSHOT_DATE = "2026-05-16"

# Rough USD->EUR rate; cost_analysis.md pins exact rate per snapshot date.
USD_TO_EUR = 0.93
```
(Leave `ModelPricing`, `cost_eur` and the existing `USD_TO_EUR` semantics unchanged — only move/extend constants. Delete the old standalone `USD_TO_EUR = 0.93` line if duplicated.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest --no-cov tests/unit/models/test_config.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Add SDK deps + mypy overrides to pyproject.toml**

In `pyproject.toml` `[project.optional-dependencies] dev = [...]`, after the `anthropic>=0.40,<1.0` line add:
```
    "openai>=1.40,<2.0",
    "groq>=0.11,<1.0",
```
After the existing `module = "anthropic.*"` mypy override block add:
```toml
[[tool.mypy.overrides]]
module = "openai"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "openai.*"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "groq"
ignore_missing_imports = true

[[tool.mypy.overrides]]
module = "groq.*"
ignore_missing_imports = true
```

- [ ] **Step 6: Sync deps + verify pip-audit**

Run: `uv sync --extra dev && uv run pip-audit --skip-editable --ignore-vuln CVE-2026-1839 --ignore-vuln CVE-2025-69872 --ignore-vuln CVE-2026-6587 2>&1 | tail -3`
Expected: deps install; no new high/critical CVEs. If new CVEs from openai/groq transitive deps: document in this commit message + add `--ignore-vuln` with rationale to `.github/workflows/ci.yml` (follow the H8 pattern; do not silently ignore).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock src/regulaitor/models/config.py tests/unit/models/test_config.py
SKIP=gitleaks git commit -m "chore(h12): add openai+groq deps + multi-provider pricing/snapshot"
```
(Local Windows commits skip ONLY the un-runnable gitleaks hook via `SKIP=gitleaks` — never `--no-verify`; gitleaks is CI-enforced. If a pre-commit cache `InvalidManifestError` occurs, run `pre-commit clean` once then retry the same command.)

---

## Task 2: ModelChoice expansion + env-override resolution

**Files:**
- Modify: `src/regulaitor/models/router.py`
- Test: `tests/unit/models/test_router.py`

- [ ] **Step 1: Write failing tests for mode resolution**

Append to `tests/unit/models/test_router.py`:
```python
def test_resolve_mode_passthrough_when_env_unset(monkeypatch) -> None:
    from regulaitor.models import router as r

    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    assert r._resolve_mode("default") == "default"
    assert r._resolve_mode("quality") == "quality"


def test_resolve_mode_env_override(monkeypatch) -> None:
    from regulaitor.models import router as r

    monkeypatch.setenv("REGULAITOR_ROUTER_MODE", "evaluation")
    assert r._resolve_mode("default") == "evaluation"


def test_resolve_mode_invalid_env_ignored_with_warning(monkeypatch, caplog) -> None:
    import logging

    from regulaitor.models import router as r

    monkeypatch.setenv("REGULAITOR_ROUTER_MODE", "bogus")
    with caplog.at_level(logging.WARNING, logger="regulaitor.models.router"):
        assert r._resolve_mode("default") == "default"
    assert "REGULAITOR_ROUTER_MODE" in caplog.text
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest --no-cov tests/unit/models/test_router.py -v -k resolve_mode`
Expected: FAIL — `AttributeError: ... has no attribute '_resolve_mode'`.

- [ ] **Step 3: Implement ModelChoice + _MODE_MAP + _resolve_mode**

In `src/regulaitor/models/router.py`:

Replace the `ModelChoice` line (line ~29):
```python
ModelChoice = Literal["default", "quality", "cost", "evaluation", "fallback"]
_VALID_MODES: frozenset[str] = frozenset(
    ("default", "quality", "cost", "evaluation", "fallback")
)
```

Add `import` for the new config symbols at the top (extend the existing `from regulaitor.models.config import ...` line):
```python
from regulaitor.models.config import (
    ANTHROPIC_SONNET_4_6,
    GROQ_LLAMA_70B,
    OPENAI_GPT_4O,
    OPENAI_GPT_4O_MINI,
    cost_eur,
)
```

Add after `logger = logging.getLogger(...)`:
```python
# mode -> (provider, model_id). "fallback" is also the controlled-fallback target.
_MODE_MAP: dict[str, tuple[str, str]] = {
    "default": ("anthropic", ANTHROPIC_SONNET_4_6),
    "quality": ("anthropic", ANTHROPIC_SONNET_4_6),
    "cost": ("groq", GROQ_LLAMA_70B),
    "evaluation": ("openai", OPENAI_GPT_4O),
    "fallback": ("openai", OPENAI_GPT_4O_MINI),
}


def _resolve_mode(model_choice: ModelChoice) -> str:
    """Apply the optional eval-only env override.

    REGULAITOR_ROUTER_MODE, when set to a valid mode, overrides the caller's
    model_choice (used by the A/B harness). An invalid value is ignored with a
    WARNING so a bad env never breaks production. Unset => caller's choice.
    """
    override = os.environ.get("REGULAITOR_ROUTER_MODE")
    if override is None:
        return model_choice
    if override in _VALID_MODES:
        return override
    logger.warning(
        "REGULAITOR_ROUTER_MODE=%r is not a valid mode %s; ignoring (using %r)",
        override,
        sorted(_VALID_MODES),
        model_choice,
    )
    return model_choice
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest --no-cov tests/unit/models/test_router.py -v -k resolve_mode`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/models/router.py tests/unit/models/test_router.py
SKIP=gitleaks git commit -m "feat(h12): ModelChoice 5 modes + _MODE_MAP + env-override resolution"
```

---

## Task 3: Refactor `_call_anthropic` to be model-id-parametric (regression-zero)

**Files:**
- Modify: `src/regulaitor/models/router.py`
- Test: `tests/unit/models/test_router.py`

- [ ] **Step 1: Write regression-zero test**

Append to `tests/unit/models/test_router.py`:
```python
def test_default_still_routes_to_anthropic_sonnet(monkeypatch) -> None:
    """Regression-zero: env unset + default => Anthropic Sonnet, unchanged."""
    from regulaitor.models import router as r
    from regulaitor.models.config import ANTHROPIC_SONNET_4_6

    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    captured: dict = {}

    def _fake_anthropic(*, model_id, messages, system, tools, tool_choice, max_tokens):
        captured["model_id"] = model_id
        return r.CompletionResult(
            text="ok", tool_use_input=None,
            usage=r.Usage(input_tokens=1, output_tokens=1),
            model_id=model_id, latency_ms=1, cost_eur=0.0,
        )

    monkeypatch.setattr(r, "_call_anthropic", _fake_anthropic)
    out = r.complete(messages=[{"role": "user", "content": "x"}], system="s")
    assert captured["model_id"] == ANTHROPIC_SONNET_4_6
    assert out.text == "ok"
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest --no-cov tests/unit/models/test_router.py -v -k default_still_routes`
Expected: FAIL — `_call_anthropic` does not exist (current name is `_call_anthropic_sonnet`).

- [ ] **Step 3: Refactor `_call_anthropic_sonnet` → `_call_anthropic(model_id, ...)`**

In `router.py`, rename `_call_anthropic_sonnet` to `_call_anthropic`, add a leading keyword-only `model_id: str` param, and replace the two hardcoded `ANTHROPIC_SONNET_4_6` uses inside it with `model_id`. Keep the `@retry(...)` decorator unchanged. The signature becomes:
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError)
    ),
    reraise=True,
)
def _call_anthropic(
    *,
    model_id: str,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None,
    tool_choice: dict[str, Any] | None,
    max_tokens: int,
) -> CompletionResult:
```
Inside: `kwargs["model"] = model_id` (was `ANTHROPIC_SONNET_4_6`), and `cost = cost_eur(model_id=model_id, ...)`, `model_id=model_id` in the `CompletionResult(...)` and the log line.

Rewrite `complete()` body to resolve + dispatch (anthropic only for now; others raise until Tasks 5-7):
```python
def complete(
    *,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
    model_choice: ModelChoice = "default",
    max_tokens: int = 2000,
) -> CompletionResult:
    """Single entry. Resolves env override -> (provider, model_id) -> dispatch."""
    mode = _resolve_mode(model_choice)
    provider, model_id = _MODE_MAP[mode]
    if provider == "anthropic":
        return _call_anthropic(
            model_id=model_id, messages=messages, system=system,
            tools=tools, tool_choice=tool_choice, max_tokens=max_tokens,
        )
    raise NotImplementedError(f"provider {provider!r} wired in Tasks 5-7")
```

- [ ] **Step 4: Run regression + existing router tests**

Run: `uv run pytest --no-cov tests/unit/models/test_router.py -v 2>&1 | tail -15`
Expected: the regression-zero test PASSES; all pre-existing router tests still PASS (if any referenced `_call_anthropic_sonnet` by name, update them to `_call_anthropic` with the `model_id=` kwarg — this is a permitted test-only rename, note it in the commit).

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/models/router.py tests/unit/models/test_router.py
SKIP=gitleaks git commit -m "refactor(h12): _call_anthropic model-id-parametric + dispatch skeleton (regression-zero)"
```

---

## Task 4: Anthropic↔OpenAI translation helpers (the crux — pure, $0 unit-tested)

**Files:**
- Create: `src/regulaitor/models/_translate.py`
- Test: `tests/unit/models/test_translate.py`

Context: the Analyst passes Anthropic-shaped `tools` (`[{"name","description","input_schema"}]`), `tool_choice` (`{"type":"tool","name":N}`), and `messages` where the H8 retry path injects `{"type":"tool_use","id","name","input"}` (assistant) and `{"type":"tool_result","tool_use_id","content","is_error"}` (user) content blocks. OpenAI/Groq need the OpenAI function-calling schema.

- [ ] **Step 1: Write failing tests (all shapes incl. H8 retry blocks)**

Create `tests/unit/models/test_translate.py`:
```python
"""Unit tests for models/_translate.py (Anthropic<->OpenAI tool/msg)."""

from __future__ import annotations

import json

from regulaitor.models import _translate as t


def test_tools_anthropic_to_openai() -> None:
    anthropic = [{"name": "emit_answer", "description": "d", "input_schema": {"type": "object"}}]
    out = t.tools_to_openai(anthropic)
    assert out == [
        {
            "type": "function",
            "function": {
                "name": "emit_answer",
                "description": "d",
                "parameters": {"type": "object"},
            },
        }
    ]


def test_tool_choice_anthropic_to_openai() -> None:
    assert t.tool_choice_to_openai({"type": "tool", "name": "emit_answer"}) == {
        "type": "function",
        "function": {"name": "emit_answer"},
    }
    assert t.tool_choice_to_openai(None) is None


def test_messages_plain_text() -> None:
    msgs = [{"role": "user", "content": "hello"}]
    assert t.messages_to_openai(msgs, system="sys") == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
    ]


def test_messages_h8_retry_blocks_round_trip() -> None:
    msgs = [
        {"role": "user", "content": "q"},
        {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "tid", "name": "emit_answer", "input": {"a": 1}}
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tid",
                    "content": "missing findings",
                    "is_error": True,
                }
            ],
        },
    ]
    out = t.messages_to_openai(msgs, system="sys")
    assert out[0] == {"role": "system", "content": "sys"}
    assert out[1] == {"role": "user", "content": "q"}
    assert out[2]["role"] == "assistant"
    assert out[2]["tool_calls"][0]["id"] == "tid"
    assert out[2]["tool_calls"][0]["type"] == "function"
    assert out[2]["tool_calls"][0]["function"]["name"] == "emit_answer"
    assert json.loads(out[2]["tool_calls"][0]["function"]["arguments"]) == {"a": 1}
    assert out[3] == {"role": "tool", "tool_call_id": "tid", "content": "missing findings"}


def test_extract_tool_use_input_from_openai_response() -> None:
    class _Fn:
        name = "emit_answer"
        arguments = '{"findings": []}'

    class _TC:
        id = "tid"
        function = _Fn()

    class _Msg:
        content = None
        tool_calls = [_TC()]

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    text, tui = t.extract_openai_tool_use(_Resp())
    assert text is None
    assert tui == {"findings": []}


def test_extract_text_when_no_tool_call() -> None:
    class _Msg:
        content = "plain answer"
        tool_calls = None

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]

    text, tui = t.extract_openai_tool_use(_Resp())
    assert text == "plain answer"
    assert tui is None
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest --no-cov tests/unit/models/test_translate.py -v`
Expected: FAIL — module `regulaitor.models._translate` not found.

- [ ] **Step 3: Implement `_translate.py`**

Create `src/regulaitor/models/_translate.py`:
```python
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


def messages_to_openai(
    messages: list[dict[str, Any]], *, system: str
) -> list[dict[str, Any]]:
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
                                    "arguments": json.dumps(
                                        block["input"], ensure_ascii=False
                                    ),
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
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest --no-cov tests/unit/models/test_translate.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/models/_translate.py tests/unit/models/test_translate.py
SKIP=gitleaks git commit -m "feat(h12): pure Anthropic<->OpenAI tool/message translators (crux, $0-tested)"
```

---

## Task 5: `_call_openai` (GPT-4o / GPT-4o-mini)

**Files:**
- Modify: `src/regulaitor/models/router.py`
- Test: `tests/unit/models/test_router.py`

- [ ] **Step 1: Write failing test (mocked openai client)**

Append to `tests/unit/models/test_router.py`:
```python
def test_call_openai_returns_completion_result(monkeypatch) -> None:
    from regulaitor.models import router as r
    from regulaitor.models.config import OPENAI_GPT_4O

    class _Fn:
        name = "emit_answer"
        arguments = '{"findings": []}'

    class _TC:
        id = "t1"
        function = _Fn()

    class _Msg:
        content = None
        tool_calls = [_TC()]

    class _Choice:
        message = _Msg()

    class _Usage:
        prompt_tokens = 10
        completion_tokens = 4

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    class _Client:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                def create(**kwargs):
                    return _Resp()

    monkeypatch.setattr(r, "_openai_client", lambda: _Client())
    out = r._call_openai(
        model_id=OPENAI_GPT_4O,
        messages=[{"role": "user", "content": "q"}],
        system="s",
        tools=[{"name": "emit_answer", "description": "d", "input_schema": {"type": "object"}}],
        tool_choice={"type": "tool", "name": "emit_answer"},
        max_tokens=100,
    )
    assert out.model_id == OPENAI_GPT_4O
    assert out.tool_use_input == {"findings": []}
    assert out.usage.input_tokens == 10
    assert out.usage.output_tokens == 4
    assert out.cost_eur > 0.0


def test_openai_client_missing_key_fails_fast(monkeypatch) -> None:
    from regulaitor.models import router as r

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import pytest

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        r._openai_client()
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest --no-cov tests/unit/models/test_router.py -v -k call_openai`
Expected: FAIL — `_call_openai` / `_openai_client` not defined.

- [ ] **Step 3: Implement `_openai_client` + `_call_openai`**

In `router.py` add imports (top):
```python
import openai
from openai import (
    APIConnectionError as OpenAIConnErr,
    APITimeoutError as OpenAITimeoutErr,
    InternalServerError as OpenAIServerErr,
    RateLimitError as OpenAIRateErr,
)

from regulaitor.models import _translate
```
Add:
```python
def _openai_client() -> "openai.OpenAI":
    """OpenAI client. Fail-fast if OPENAI_API_KEY missing (only constructed
    when an openai-backed mode is actually used; prod default never calls it)."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY not set; required for router 'evaluation'/'fallback' "
            "modes. Add it to .env or use a mocked router in tests."
        )
    return openai.OpenAI(api_key=key)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (OpenAIRateErr, OpenAIConnErr, OpenAITimeoutErr, OpenAIServerErr)
    ),
    reraise=True,
)
def _call_openai(
    *,
    model_id: str,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None,
    tool_choice: dict[str, Any] | None,
    max_tokens: int,
) -> CompletionResult:
    """OpenAI chat.completions with Anthropic-shaped inputs translated in."""
    client = _openai_client()
    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": _translate.messages_to_openai(messages, system=system),
        "max_tokens": max_tokens,
    }
    otools = _translate.tools_to_openai(tools)
    if otools is not None:
        kwargs["tools"] = otools
    otc = _translate.tool_choice_to_openai(tool_choice)
    if otc is not None:
        kwargs["tool_choice"] = otc

    t0 = time.monotonic()
    response = client.chat.completions.create(**kwargs)
    latency_ms = int((time.monotonic() - t0) * 1000)

    text, tool_use_input = _translate.extract_openai_tool_use(response)
    usage = Usage(
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )
    cost = cost_eur(
        model_id=model_id,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )
    logger.info(
        "openai completion: model=%s tokens=%d/%d cost_eur=%.4f latency_ms=%d",
        model_id, usage.input_tokens, usage.output_tokens, cost, latency_ms,
    )
    return CompletionResult(
        text=text, tool_use_input=tool_use_input, usage=usage,
        model_id=model_id, latency_ms=latency_ms, cost_eur=cost,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest --no-cov tests/unit/models/test_router.py -v -k call_openai`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/models/router.py tests/unit/models/test_router.py
SKIP=gitleaks git commit -m "feat(h12): _call_openai (GPT-4o/4o-mini) via translators + tenacity"
```

---

## Task 6: `_call_groq` (Llama-70B, OpenAI-compatible)

**Files:**
- Modify: `src/regulaitor/models/router.py`
- Test: `tests/unit/models/test_router.py`

- [ ] **Step 1: Verify the live Groq model id**

Run: `uv run python -c "import os, groq; c=groq.Groq(api_key=os.environ['GROQ_API_KEY']); print([m.id for m in c.models.list().data if 'llama' in m.id and '70' in m.id])"`
(Requires `GROQ_API_KEY` in env — gated; if unavailable, defer this step to Task 10's pre-flight and keep `GROQ_LLAMA_70B="llama-3.3-70b-versatile"`.) If the printed id differs from `config.GROQ_LLAMA_70B`, update the constant **and** its `PRICING` key together, and record the verified id + date in decisions log §H12.

- [ ] **Step 2: Write failing test (mocked groq client)**

Append to `tests/unit/models/test_router.py`:
```python
def test_call_groq_returns_completion_result(monkeypatch) -> None:
    from regulaitor.models import router as r
    from regulaitor.models.config import GROQ_LLAMA_70B

    class _Fn:
        name = "emit_answer"
        arguments = '{"findings": []}'

    class _TC:
        id = "g1"
        function = _Fn()

    class _Msg:
        content = None
        tool_calls = [_TC()]

    class _Choice:
        message = _Msg()

    class _Usage:
        prompt_tokens = 7
        completion_tokens = 3

    class _Resp:
        choices = [_Choice()]
        usage = _Usage()

    class _Client:
        class chat:  # noqa: N801
            class completions:  # noqa: N801
                @staticmethod
                def create(**kwargs):
                    return _Resp()

    monkeypatch.setattr(r, "_groq_client", lambda: _Client())
    out = r._call_groq(
        model_id=GROQ_LLAMA_70B,
        messages=[{"role": "user", "content": "q"}],
        system="s",
        tools=[{"name": "emit_answer", "description": "d", "input_schema": {"type": "object"}}],
        tool_choice={"type": "tool", "name": "emit_answer"},
        max_tokens=100,
    )
    assert out.model_id == GROQ_LLAMA_70B
    assert out.tool_use_input == {"findings": []}
    assert out.cost_eur > 0.0


def test_groq_client_missing_key_fails_fast(monkeypatch) -> None:
    from regulaitor.models import router as r
    import pytest

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        r._groq_client()
```

- [ ] **Step 3: Run to verify fail**

Run: `uv run pytest --no-cov tests/unit/models/test_router.py -v -k call_groq`
Expected: FAIL — `_call_groq` / `_groq_client` not defined.

- [ ] **Step 4: Implement `_groq_client` + `_call_groq`**

In `router.py` add imports:
```python
import groq
from groq import (
    APIConnectionError as GroqConnErr,
    APITimeoutError as GroqTimeoutErr,
    InternalServerError as GroqServerErr,
    RateLimitError as GroqRateErr,
)
```
Add (Groq's SDK is OpenAI-compatible; reuse the `_translate` helpers verbatim):
```python
def _groq_client() -> "groq.Groq":
    """Groq client. Fail-fast if GROQ_API_KEY missing (only constructed when
    the 'cost' mode is actually used)."""
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY not set; required for router 'cost' mode. "
            "Add it to .env or use a mocked router in tests."
        )
    return groq.Groq(api_key=key)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(
        (GroqRateErr, GroqConnErr, GroqTimeoutErr, GroqServerErr)
    ),
    reraise=True,
)
def _call_groq(
    *,
    model_id: str,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None,
    tool_choice: dict[str, Any] | None,
    max_tokens: int,
) -> CompletionResult:
    """Groq chat.completions (OpenAI-compatible) with translated inputs."""
    client = _groq_client()
    kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": _translate.messages_to_openai(messages, system=system),
        "max_tokens": max_tokens,
    }
    gtools = _translate.tools_to_openai(tools)
    if gtools is not None:
        kwargs["tools"] = gtools
    gtc = _translate.tool_choice_to_openai(tool_choice)
    if gtc is not None:
        kwargs["tool_choice"] = gtc

    t0 = time.monotonic()
    response = client.chat.completions.create(**kwargs)
    latency_ms = int((time.monotonic() - t0) * 1000)

    text, tool_use_input = _translate.extract_openai_tool_use(response)
    usage = Usage(
        input_tokens=response.usage.prompt_tokens,
        output_tokens=response.usage.completion_tokens,
    )
    cost = cost_eur(
        model_id=model_id,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
    )
    logger.info(
        "groq completion: model=%s tokens=%d/%d cost_eur=%.4f latency_ms=%d",
        model_id, usage.input_tokens, usage.output_tokens, cost, latency_ms,
    )
    return CompletionResult(
        text=text, tool_use_input=tool_use_input, usage=usage,
        model_id=model_id, latency_ms=latency_ms, cost_eur=cost,
    )
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest --no-cov tests/unit/models/test_router.py -v -k call_groq`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add src/regulaitor/models/router.py tests/unit/models/test_router.py
SKIP=gitleaks git commit -m "feat(h12): _call_groq (Llama-70B, OpenAI-compatible) via translators"
```

---

## Task 7: Wire all 5 modes + controlled one-hop fallback

**Files:**
- Modify: `src/regulaitor/models/router.py`
- Test: `tests/unit/models/test_router.py`

- [ ] **Step 1: Write failing tests (dispatch + fallback)**

Append to `tests/unit/models/test_router.py`:
```python
def _stub_result(r, model_id):
    return r.CompletionResult(
        text="ok", tool_use_input=None,
        usage=r.Usage(input_tokens=1, output_tokens=1),
        model_id=model_id, latency_ms=1, cost_eur=0.0,
    )


def test_each_mode_dispatches_to_right_provider(monkeypatch) -> None:
    from regulaitor.models import router as r

    seen: list[str] = []
    monkeypatch.setattr(r, "_call_anthropic", lambda **k: (seen.append("anthropic"), _stub_result(r, k["model_id"]))[1])
    monkeypatch.setattr(r, "_call_openai", lambda **k: (seen.append("openai"), _stub_result(r, k["model_id"]))[1])
    monkeypatch.setattr(r, "_call_groq", lambda **k: (seen.append("groq"), _stub_result(r, k["model_id"]))[1])
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    for mc, prov in [
        ("default", "anthropic"), ("quality", "anthropic"),
        ("cost", "groq"), ("evaluation", "openai"), ("fallback", "openai"),
    ]:
        seen.clear()
        r.complete(messages=[{"role": "user", "content": "x"}], system="s", model_choice=mc)
        assert seen == [prov], mc


def test_controlled_fallback_one_hop(monkeypatch) -> None:
    from regulaitor.models import router as r
    from regulaitor.models.config import OPENAI_GPT_4O_MINI

    calls: list[str] = []

    def _boom(**k):
        calls.append("primary")
        raise RuntimeError("provider down")

    def _fallback(**k):
        calls.append("fallback")
        return _stub_result(r, k["model_id"])

    monkeypatch.setattr(r, "_call_groq", _boom)        # 'cost' primary
    monkeypatch.setattr(r, "_call_openai", _fallback)  # 'fallback' target
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    out = r.complete(messages=[{"role": "user", "content": "x"}], system="s", model_choice="cost")
    assert calls == ["primary", "fallback"]
    assert out.model_id == OPENAI_GPT_4O_MINI


def test_fallback_also_fails_raises_original(monkeypatch) -> None:
    from regulaitor.models import router as r

    def _boom(**k):
        raise RuntimeError("primary down")

    def _boom2(**k):
        raise RuntimeError("fallback down too")

    monkeypatch.setattr(r, "_call_groq", _boom)
    monkeypatch.setattr(r, "_call_openai", _boom2)
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    import pytest

    with pytest.raises(RuntimeError, match="primary down"):
        r.complete(messages=[{"role": "user", "content": "x"}], system="s", model_choice="cost")
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest --no-cov tests/unit/models/test_router.py -v -k "dispatches or fallback"`
Expected: FAIL — `complete()` still raises NotImplementedError for non-anthropic / no fallback logic.

- [ ] **Step 3: Implement full dispatch + controlled fallback**

In `router.py`, replace `complete()` body:
```python
def complete(
    *,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
    model_choice: ModelChoice = "default",
    max_tokens: int = 2000,
) -> CompletionResult:
    """Resolve env override -> (provider, model_id) -> dispatch.

    Controlled fallback: if the active provider fails terminally (after its
    own tenacity retries) AND we are not already on the fallback model, retry
    exactly once on the 'fallback' model. If that also fails, the ORIGINAL
    exception propagates (bounded — no loop).
    """
    mode = _resolve_mode(model_choice)
    try:
        return _dispatch(
            mode, messages=messages, system=system,
            tools=tools, tool_choice=tool_choice, max_tokens=max_tokens,
        )
    except Exception as primary_exc:  # noqa: BLE001 — bounded controlled fallback
        if mode == "fallback":
            raise
        logger.warning(
            "router primary mode=%r failed (%s); one-hop fallback -> 'fallback'",
            mode, primary_exc,
        )
        try:
            result = _dispatch(
                "fallback", messages=messages, system=system,
                tools=tools, tool_choice=tool_choice, max_tokens=max_tokens,
            )
        except Exception:  # noqa: BLE001 — surface the ORIGINAL failure
            raise primary_exc from None
        logger.info("router fallback_used=true (primary mode=%r)", mode)
        return result


def _dispatch(
    mode: str,
    *,
    messages: list[dict[str, Any]],
    system: str,
    tools: list[dict[str, Any]] | None,
    tool_choice: dict[str, Any] | None,
    max_tokens: int,
) -> CompletionResult:
    provider, model_id = _MODE_MAP[mode]
    fn = {
        "anthropic": _call_anthropic,
        "openai": _call_openai,
        "groq": _call_groq,
    }[provider]
    return fn(
        model_id=model_id, messages=messages, system=system,
        tools=tools, tool_choice=tool_choice, max_tokens=max_tokens,
    )
```

- [ ] **Step 4: Run to verify pass + full router suite**

Run: `uv run pytest --no-cov tests/unit/models/ -v 2>&1 | tail -20`
Expected: all model tests PASS (dispatch ×5, fallback ×3, translators, config, regression-zero).

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/models/router.py tests/unit/models/test_router.py
SKIP=gitleaks git commit -m "feat(h12): wire 5-mode dispatch + controlled one-hop fallback"
```

---

## Task 8: `scripts/ab_eval.py` — thin A/B wrapper (no paid run yet)

**Files:**
- Create: `scripts/ab_eval.py`
- Test: `tests/unit/scripts/test_ab_eval.py`

Context: `evals/harness.py` exposes `main(...)` (the H8 CLI entry; see `scripts/evaluate.py`). `ab_eval` runs the harness once per non-Sonnet arm with `REGULAITOR_ROUTER_MODE` set, writing each arm's report to a distinct path; it does NOT re-run Sonnet (reuse frozen baseline).

- [ ] **Step 1: Write failing test (arms + env wiring, harness mocked)**

Create `tests/unit/scripts/test_ab_eval.py`:
```python
"""Unit tests for scripts/ab_eval.py (no real LLM)."""

from __future__ import annotations

import os

import scripts.ab_eval as ab


def test_arms_are_evaluation_and_cost_only() -> None:
    assert ab.AB_ARMS == [("evaluation", "gpt-4o"), ("cost", "llama-groq")]
    # Sonnet is intentionally NOT an arm (frozen baseline reused).
    assert all(arm[0] != "default" for arm in ab.AB_ARMS)


def test_run_arm_sets_and_clears_env(monkeypatch) -> None:
    seen: dict[str, str | None] = {}

    def _fake_harness_main(**kwargs):
        seen["mode"] = os.environ.get("REGULAITOR_ROUTER_MODE")
        return None

    monkeypatch.setattr(ab, "_harness_main", _fake_harness_main)
    monkeypatch.delenv("REGULAITOR_ROUTER_MODE", raising=False)
    ab.run_arm("evaluation", gold_set="evals/gold_set.jsonl", subset=2)
    assert seen["mode"] == "evaluation"
    # env restored after the arm
    assert os.environ.get("REGULAITOR_ROUTER_MODE") is None
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest --no-cov tests/unit/scripts/test_ab_eval.py -v`
Expected: FAIL — module `scripts.ab_eval` not found (and ensure `tests/unit/scripts/__init__.py` exists; create empty if missing).

- [ ] **Step 3: Implement `scripts/ab_eval.py`**

Create `scripts/ab_eval.py`:
```python
"""H12 — A/B cost-vs-quality eval wrapper.

Runs the H8 harness once per non-Sonnet arm with REGULAITOR_ROUTER_MODE set so
the (read-only) Analyst's router resolves to that arm's model. The Sonnet arm
is NOT run here — its frozen H10/H11 baseline is reused in cost_analysis.md.
USER-GATED: real arms cost Anthropic/OpenAI/Groq credit; run only on explicit OK.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from evals.harness import main as _harness_main

# (router mode, human label) — Sonnet excluded by design (frozen baseline).
AB_ARMS: list[tuple[str, str]] = [("evaluation", "gpt-4o"), ("cost", "llama-groq")]


def run_arm(mode: str, *, gold_set: str, subset: int | None) -> None:
    """Run the full harness for one arm with the router env override set,
    restoring the prior env afterwards."""
    prev = os.environ.get("REGULAITOR_ROUTER_MODE")
    os.environ["REGULAITOR_ROUTER_MODE"] = mode
    try:
        _harness_main(gold_set=Path(gold_set), subset=subset, report_suffix=mode)
    finally:
        if prev is None:
            os.environ.pop("REGULAITOR_ROUTER_MODE", None)
        else:
            os.environ["REGULAITOR_ROUTER_MODE"] = prev


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="H12 A/B cost-vs-quality eval")
    p.add_argument("--gold-set", default="evals/gold_set.jsonl")
    p.add_argument("--subset", type=int, default=None,
                   help="First N chat cases (proportional docs). None = full 40.")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    for mode, label in AB_ARMS:
        print(f"=== A/B arm: {label} (REGULAITOR_ROUTER_MODE={mode}) ===", flush=True)
        run_arm(mode, gold_set=args.gold_set, subset=args.subset)
```
> **Implementation note:** `evals.harness.main` must accept a `report_suffix`
> kwarg so each arm writes a distinct report (e.g.
> `evals/reports/latest.<suffix>.md`) instead of overwriting
> `evals/reports/latest.md`. **`evals/harness.py` is read-only in this plan.**
> If `main` does not already support `report_suffix`, do NOT edit harness.py;
> instead, in `run_arm`, after `_harness_main(...)` returns, copy
> `evals/reports/latest.md` to `evals/reports/latest.<mode>.md` and restore the
> original from git (`git show HEAD:evals/reports/latest.md`) so the canonical
> baseline file is never clobbered. Implement whichever path matches the real
> `harness.main` signature you observe; state which in the commit message.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest --no-cov tests/unit/scripts/test_ab_eval.py -v`
Expected: PASS (2 tests). If `_harness_main` signature differs, adjust the stub + the `run_arm` call together (keep the test asserting env set/restore).

- [ ] **Step 5: Commit**

```bash
git add scripts/ab_eval.py tests/unit/scripts/__init__.py tests/unit/scripts/test_ab_eval.py
SKIP=gitleaks git commit -m "feat(h12): thin A/B eval wrapper (env-driven arms, harness reused)"
```

---

## Task 9: Full gate — regression-zero + lint + types + CI-relevant

**Files:** none (verification only)

- [ ] **Step 1: Full not-slow suite + coverage gate**

Run: `uv run pytest -m "not slow" -q 2>&1 | tail -6`
Expected: all pass; `Required test coverage of 90% reached`. The prod path (env unset, `model_choice="default"`) is unchanged → all pre-existing agent/orchestration/api tests green untouched.

- [ ] **Step 2: Lint + types**

Run: `uv run ruff check . 2>&1 | tail -1 && uv run black --check src tests scripts 2>&1 | tail -1 && uv run mypy 2>&1 | tail -1`
Expected: ruff "All checks passed!"; black OK; mypy "Success".

- [ ] **Step 3: Confirm prod regression-zero explicitly**

Run: `uv run pytest --no-cov tests/unit/orchestration tests/unit/agents -q 2>&1 | tail -3`
Expected: unchanged pass (Analyst still calls `model_choice="default"` → Sonnet; no behavior change).

- [ ] **Step 4: Commit (if any lint/format autofix touched files)**

```bash
git add -A
SKIP=gitleaks git commit -m "chore(h12): lint/format/type gate green (regression-zero verified)" || echo "nothing to commit"
```

---

## Task 10: GATED paid A/B run + `docs/cost_analysis.md`

**Files:**
- Create: `docs/cost_analysis.md`
- (Generates: `evals/reports/latest.evaluation.md`, `evals/reports/latest.cost.md`)

**⚠️ Cost ~$3–5 (OpenAI GPT-4o is the driver; Groq cheap/fast). USER-GATED. Confirm before running. Requires `OPENAI_API_KEY` + `GROQ_API_KEY` in `.env`.**

- [ ] **Step 1: Confirm with user + pre-flight keys**

State: "About to run the H12 A/B: GPT-4o + Llama-Groq over the 40-case gold set (~$3–5, Anthropic credit ~$5 — H15 needs a separate recharge). Proceed?" Wait for explicit OK. Then verify keys (booleans only, never print values):
```bash
uv run python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('OPENAI', bool(os.environ.get('OPENAI_API_KEY'))); print('GROQ', bool(os.environ.get('GROQ_API_KEY')))"
```
Expected: both `True`. If false → ask the user to add them to `.env` (never `.env.example`).

- [ ] **Step 2: Verify the live Groq model id (Task 6 Step 1, now that the key exists)**

Run the Groq `models.list()` command from Task 6 Step 1. If the id differs from `config.GROQ_LLAMA_70B`, update the constant + its `PRICING` key, commit `fix(h12): pin verified Groq model id <id>`, and note it in decisions §H12.

- [ ] **Step 3: Back up the canonical baseline report**

```bash
cp evals/reports/latest.md /tmp/eval_baseline_pre_h12.md
```

- [ ] **Step 4: Run the two A/B arms in background (timeout-protected by harness)**

Run (background): `uv run python -m scripts.ab_eval --gold-set evals/gold_set.jsonl`
Wait for completion (notify on done; do not poll). Expect ~1–3 h wall under rate-limit. On completion, restore the canonical baseline if the harness clobbered it: `git checkout HEAD -- evals/reports/latest.md`.

- [ ] **Step 5: Assemble `docs/cost_analysis.md`**

Read the Sonnet baseline numbers from `docs/technical_decisions_log.md §H10` (frozen) and the two arm reports (`evals/reports/latest.evaluation.md`, `evals/reports/latest.cost.md`). Create `docs/cost_analysis.md`:
```markdown
# RegulAItor — Cost vs Quality Analysis (H12)

**Date:** <YYYY-MM-DD> · **Pricing snapshot:** <config.PRICING_SNAPSHOT_DATE> · **USD→EUR:** 0.93
**Gold set:** 30 chat + 10 doc (40 cases) · **Judge:** Haiku 4.5 (unchanged, cross-arm comparable)
**Method:** Sonnet column = frozen H10/H11 baseline (reused, NOT re-measured this run);
GPT-4o + Llama-Groq measured via `scripts/ab_eval.py` with `REGULAITOR_ROUTER_MODE`.

| Metric | Sonnet 4.6 (baseline) | GPT-4o | Llama-3.x-70B (Groq) |
|---|---|---|---|
| faithfulness | 0.54 | <m> | <m> |
| citation_precision | 0.17 | <m> | <m> |
| citation_recall | 0.44 | <m> | <m> |
| answer_relevancy | 0.53 | <m> | <m> |
| context_precision | 0.48 | <m> | <m> |
| verdict_match_rate | 0.28 | <m> | <m> |
| severity_match_rate | 0.23 | <m> | <m> |
| **€ / chat query (measured)** | <baseline €> | <m> | <m> |
| **€ / doc (10p, measured)** | <baseline €> | <m> | <m> |
| latency p50 / p95 (s) | <baseline> | <m> | <m> |

## Reading
<2-4 sentences: cost-vs-quality trade-off; if Llama structured-output is
weaker that is an honest finding, not hidden (spec §5/§7, §22.22).>

## Caveats
Sonnet numbers are the frozen baseline reused for comparability (not re-run
this milestone); the known H15 calibration gap applies to all arms; N=40 per
arm; single run per arm (no variance estimate — documented limitation).
```
Fill every `<m>` with the measured value; no placeholders left.

- [ ] **Step 6: Commit**

```bash
git add docs/cost_analysis.md evals/reports/latest.evaluation.md evals/reports/latest.cost.md
SKIP=gitleaks git commit -m "docs(h12): measured A/B cost-vs-quality 3-way table (gold set N=40)"
```
(If `evals/reports/latest.*.md` are gitignored by the `evals/reports/*` rule, add `!evals/reports/latest.*.md` to `.gitignore` in this commit, mirroring the existing `!evals/reports/latest.md` exception, so the arm reports are tracked as evidence.)

---

## Task 11: H12 closure — ADR + decisions log + evidence_matrix + CLAUDE.md + memory + tag

**Files:**
- Create: `docs/adr/0013-router-multi-llm.md`
- Modify: `docs/technical_decisions_log.md` (append §H12), `docs/evidence_matrix.md`, `CLAUDE.md` §27
- Memory: rename `h11_closed_h12_starting.md` → `h12_closed_h13_starting.md`, rewrite; update `MEMORY.md`

- [ ] **Step 1: Write ADR 0013** mirroring ADR 0012 structure: Status/Date, Context (single-backend router H4 → multi-LLM; §10.4 modes; §24 Módulo 1 deliverable), Decision (D1–D4 from spec §2 summarized), Consequences (positive: real router artifact + measured cost_analysis; negative: 2 new SDK deps + provider keys; cross-provider tool-calling parity caveat), Alternatives (graph-threading rejected, litellm rejected), References (spec, decisions §H12).

- [ ] **Step 2: Append decisions log §H12** — header `## H12 — Router multi-LLM + cost (cerrado <YYYY-MM-DD>, squash \`<squash-sha>\`, tag \`v0.1.2-h12\`)`; the 4 brainstorming decisions; any amendments during implementation (esp. the verified Groq model id + any pricing corrections); the measured A/B headline (best cost-vs-quality arm); skills activated (none — `cost-accounting` stays H17); artefacts.

- [ ] **Step 3: Update evidence_matrix.md** — Módulo 1 row: router multi-LLM `models/router.py` → ✅ H12; `docs/cost_analysis.md` → ✅ H12 (measured, N=40); follow-ups table: "Multi-LLM router + cost_analysis" → ✅ done H12; keep latency-opt → H15.

- [ ] **Step 4: Update CLAUDE.md §27** — add H12 closed entry after the H11 line; change "Hito siguiente" to H13 (Council of Judges).

- [ ] **Step 5: Full verification**

Run: `uv run pytest -m "not slow" -q 2>&1 | tail -3 && uv run ruff check . 2>&1 | tail -1 && uv run mypy 2>&1 | tail -1`
Expected: green, coverage ≥90%.

- [ ] **Step 6: Commit closure docs**

```bash
git add docs/adr/0013-router-multi-llm.md docs/technical_decisions_log.md docs/evidence_matrix.md CLAUDE.md
SKIP=gitleaks git commit -m "docs(h12): close milestone — ADR 0013 + decisions §H12 + evidence_matrix + CLAUDE.md"
```

- [ ] **Step 7: Push + PR**

```bash
git push -u origin feat/h12-router-multi-llm
gh pr create --title "feat(h12): router multi-LLM + measured cost analysis" --body "<summary from spec §1-2 + measured A/B headline + the cross-provider tool-calling note + non-goals>"
```

- [ ] **Step 8: After user OK + CI green: squash-merge + tag + memory**

- Squash-merge subject `feat(h12): router multi-LLM + cost analysis`.
- Tag `v0.1.2-h12` (confirm scheme with user; consistent with `v0.1.1-h11`).
- Post-merge: populate `<squash-sha>`/date in ADR 0013, decisions §H12, CLAUDE.md §27 via a `docs(h12): populate post-merge SHA` commit on main + tag it (the H10/H11 pattern); push main + tag.
- `mv h11_closed_h12_starting.md h12_closed_h13_starting.md`, rewrite for MVP+H11+H12 state + H13 boundary; update `MEMORY.md` index line.

---

## Closure gate checklist (Task 11 wrap-up)

- [ ] Router serves all 5 modes with real provider calls; `_resolve_mode` env-override; controlled one-hop fallback (tests green).
- [ ] Regression-zero proven: env unset + `default` → Sonnet, prod behavior unchanged; agents/graph/api untouched.
- [ ] Translators unit-tested incl. the H8 retry `tool_use`/`tool_result` blocks.
- [ ] Gated A/B executed (explicit user OK); `docs/cost_analysis.md` with measured 3-way N=40 table, no `<m>` placeholders.
- [ ] Verified Groq model id pinned + recorded; pricing verified against live pages + snapshot date.
- [ ] ADR 0013 + decisions §H12 + evidence_matrix + CLAUDE.md §27 committed.
- [ ] CI 5 jobs green; coverage `models/` ≥90%.
- [ ] Tag `v0.1.2-h12` + memory rename + MEMORY.md updated.

---

## Anti-patterns to avoid

- Do NOT edit agents/graph/api/Streamlit/prompts/`evals/harness.py` — router+config+new script+docs only (spec §10).
- Do NOT thread `model_choice` through `graph.run()` (rejected Approach 2 — breaks backend-read-only).
- Do NOT add litellm/langchain router (rejected Approach 3 — undercuts the Module-1 hand-built-router artifact).
- Do NOT re-run the Sonnet arm (frozen H10/H11 baseline is reused — saves spend).
- Do NOT run the paid A/B without explicit user confirmation (Task 10 Step 1).
- Do NOT add `.env.example` (single `.env`). Do NOT `--no-verify`; `SKIP=gitleaks` is the sanctioned local-only skip.
- Do NOT present an unmeasured metric as measured; if Llama underperforms, document honestly (§22.22 + H11 precedent).
- Do NOT let a bad `REGULAITOR_ROUTER_MODE` break prod — invalid → WARN + ignore.
