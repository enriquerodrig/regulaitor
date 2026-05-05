# ADR 0006 — Chat E2E architecture (Analyst + Auditor + LangGraph)

- **Status:** Accepted
- **Date:** 2026-05-05 (H4 closure)
- **Deciders:** Project owner.
- **Companion ADRs:** 0005 (MCP server architecture), 0004 (RAG architecture).

## Context

H4 introduces the first chat E2E flow that materializes the "no citation, no
answer" rule. Wires the H3 retriever + validator into a 3-agent LangGraph
pipeline (Retriever → Analyst → Auditor), with the first real LLM provider
integration (Claude Sonnet 4.6) behind a routable seam, anti-injection gate,
and structured logging.

## Decision

Seven new modules + one extended (`citation/schemas.py`), organized in 4
trust-boundary tiers:

| Tier | Modules |
|---|---|
| Public surface | `scripts/chat.py` (CLI smoke) |
| Orchestration | `orchestration/graph.py`, `orchestration/state.py` |
| Agents | `agents/analyst.py`, `agents/auditor.py` (+ H3 retriever) |
| Helpers | `models/router.py`, `models/config.py`, `security/injection.py` |

Anti-injection gate short-circuits to END before LLM call. Auditor is
pure-Python (no LLM in lean H4); Analyst calls LLM via thin router with
single Anthropic Sonnet 4.6 backend. Verdict aggregation is **Lenient-strict**
(Finding passes if ≥1 cita valid; Answer fails if ANY Finding fully blocked;
partial → REQUIRES_HUMAN_REVIEW).

Schemas extended in `citation/schemas.py`: `Finding`, `Answer`, `AuditVerdict`,
`AuditedAnswer`. Frozen Answer + AuditedAnswer wrapper (Auditor never mutates
the Analyst output).

LangGraph state is Pydantic v2 BaseModel with `extra='forbid'` (added during
code review). Module-level agents are lazy-init via `functools.lru_cache` to
avoid import-time I/O. Compiled graph is cached at module level (recompilation
per request was an early bug found by code review).

Per-turn structured JSON log emitted from `graph.run()`: `case_id`,
`query_hash` (SHA256[:12], no raw query — PII discipline), `corpus`, `language`,
`verdict`, finding/citation counts, `latency_ms_total`, `reason_code`, `errors`.
Per-LLM-call cost + latency logged from `models/router.py`.

## Alternatives considered

- **Strict-strict aggregation** (any failed citation → BLOCK whole Answer):
  rejected as too aggressive; produces high false-negative rate; bad UX.
- **GPT-4o or Llama 70B Groq as primary** in H4: rejected for H4 baseline
  (Claude minimizes "is the LLM being good" variable while debugging the
  pipeline); H12 router will add them as cost/evaluation modes.
- **JSON mode for Analyst output** instead of tool use: rejected; tool use
  produces SDK-validated structured output, eliminating prose-parser fragility.
- **TypedDict for LangGraph state**: rejected for inconsistency with
  Pydantic-everywhere convention; BaseModel gives validation + serialization.
- **Strategy pattern for router** (ABC + multiple implementations): rejected
  as premature polymorphism with one provider; thin router is the right
  abstraction now; H12 expansion is non-breaking.
- **LLM-as-judge for Auditor in H4** (CLAUDE.md §6 check 4 implementation):
  deferred to H13 (Council of Judges) and H15 (calibration); H4 ships
  mechanical defenses + structural validator wrap.
- **Module-level agent constants** (`_RETRIEVER = RetrieverAgent()`):
  rejected during code review; replaced with `lru_cache`-wrapped lazy helpers
  to avoid import-time I/O failures cascading.

## Consequences

### Positive

- First real chat E2E ships; the "no citation, no answer" rule is now
  operational against the live AI Act + GDPR corpus.
- LangGraph state is Pydantic-typed with `extra='forbid'`; serializable for
  logs/observability/H11 LangFuse integration.
- Anti-injection gate cheap by construction (no LLM cost on attack queries).
- Auditor verdict aggregation is testable, deterministic, and pure-Python.
- Per-turn JSON logs include cost + latency for H17 cost analysis defensibility.
- Code review surfaced and fixed several hardenings: retry policy filters
  transient errors only (no 3-attempt waste on permanent 4xx); fail-fast on
  missing API key; path-traversal validation on `prompt_version`; Pydantic
  ValidationError wrapped for debuggability; `_aggregate_reason` uses ` | `
  separator (validator reason format would have collided with `;`); compiled
  graph cached; agent singletons lazy-init.
- Smoke-validated: 284 fast tests pass; 5 slow tests skip cleanly without
  `ANTHROPIC_API_KEY`. Coverage 93.87% global (gate 90%).

### Negative

- Anthropic SDK pinned `<1.0`; future major-version upgrade is a refactor.
- LangGraph 0.x is moving fast; pinned `>=0.2,<1.0` for breaking-change
  protection.
- Anti-injection regex list is heuristic; H9 redteam will expand it.
- LLM-as-judge for "cita apoya afirmación" is deferred; structural validator
  alone may produce false positives on semantically wrong-but-valid citations.
  Mitigated by gold set evaluation in H8 + Council of Judges in H13.
- First Analyst prompt v1.0 is unvalidated against gold set; H8 will measure
  and v2.0+ will iterate per the prompt-versioning skill.
- The `_render_user_message` formatter does not delimit user query vs chunks
  with structured markers (e.g. `<user_query>`, `<chunk>`). Code reviewer
  flagged as Suggestion; load-bearing in H5 (document mode) and H9 (red team).
  Deferred polish.

## References

- `docs/superpowers/specs/2026-05-05-h4-chat-e2e-design.md` — H4 spec.
- `docs/superpowers/plans/2026-05-05-h4-chat-e2e.md` — H4 plan.
- `docs/technical_decisions_log.md` H4 section.
- `docs/adr/0005-mcp-server-architecture.md` — predecessor; H3 trust boundary.
- `.claude/skills/prompt-versioning/SKILL.md` — activated by H4 with
  `agents/prompts/analyst/system.v1.0.md`.
- `src/regulaitor/{agents,models,orchestration,security}/` — concrete output.
