# ADR 0005 — MCP server architecture

- **Status:** Accepted
- **Date:** 2026-05-05 (H3 closure)
- **Deciders:** Project owner.
- **Companion ADRs:** 0004 (RAG architecture), 0002 (skills/MCPs roadmap).

## Context

H3 introduces the project's first **trust boundary surface**: an MCP server
exposing 3 tools (`search_articles`, `fetch_article`, `validate_citation`) over
stdio JSON-RPC. The server is the single point of access for both internal
agents (H4 LangGraph nodes) and external clients (Claude Desktop, evaluation
harness, future API). This ADR captures the architecture that emerged after
the H3 brainstorming + implementation.

## Decision

Six new modules + one helper in existing layers, organized in 4 trust-boundary tiers:

| Tier | Modules | Trust |
|---|---|---|
| Public surface | `mcp_server/server.py`, `tools.py`, `errors.py`, `__main__.py` | Validates all input via Pydantic |
| Agent adapter | `agents/retriever.py` | In-process, trusted Pydantic |
| Schemas + validator | `citation/schemas.py`, `citation/validator.py` | Pure logic, no I/O |
| Domain helpers | `corpus/loader.py`, `rag/retrieval.py` | Read-only after warmup |

The MCP server fails closed at startup if the corpus loader detects hash drift
(decisions log "Corpus loader: lazy singleton + integrity check fail-closed").
The retrieval helper is the single source of truth shared by both the MCP tool
adapter and the LangGraph agent (no internal RPC; same Python function).

The validator runs 3 strict checks (article exists, apartado exists, normalized
text match) reusing the `_normalize` function from `rag/chunking.py`. Fuzzy
matching is explicitly deferred to H15 calibration.

## Alternatives considered

- **5 tools shipped in H3 (with stubs for document tools):** rejected; doubles
  test surface for code that will be rewritten in H5.
- **Streamable HTTP transport in MVP:** rejected; stdio is simpler and matches
  Claude Desktop's default.
- **Agent-talks-MCP via in-process loopback:** rejected; helper-shared
  architecture avoids RPC overhead inside the same process.
- **Fuzzy citation matching by default:** rejected; vulnerable to adversarial
  near-paraphrase attacks; H15 may add as fallback only.
- **Hash drift as warning instead of fail-closed:** rejected; SSDLC fail-closed
  posture for tampered corpus.
- **Low-level `mcp.server.Server` (per the brainstorming pseudocode):**
  rejected during implementation; the SDK 1.x `Server` class lacks a `.tool()`
  method. Switched to `mcp.server.FastMCP` which provides idiomatic
  `add_tool(fn)` registration plus `run_stdio_async()`. Functional intent
  preserved (3 tools registered, stdio loop, fail-closed warmup); the code
  ended up cleaner.

## Consequences

### Positive

- Trust boundary is a single physical surface (the MCP server) — easier to
  audit, log, and threat-model than scattered tool implementations.
- LangGraph nodes (H4) and external clients see exactly the same retrieval
  logic — no behavioural drift between development and demo.
- Hash drift detection gives the project a concrete defensive control to point
  at in the TFM defense.
- The 3-tool MCP contract is a small, stable surface that downstream
  integrations (LangFuse in H11, FastAPI in H7) can consume without coupling.
- Smoke-validated server boot time: ~3 s with HF cache warm (loader ~190 ms,
  reranker ~3 s, integrity check imperceptible).

### Negative

- New runtime dependency: `mcp` Python SDK (still <1.0; pinned `>=1.0,<2.0`).
- Loader integrity check adds ~50–100 ms to MCP server startup (acceptable per
  Q12 of brainstorming).
- The validator's 3-check fail-fast structure is rigid; adding a 4th check
  requires a careful re-ordering decision documented per the
  `citation-validator` skill.
- The `run()` body in `mcp_server/server.py` is marked `# pragma: no cover`
  because the asyncio stdio loop is exercised only by the slow integration
  test. Two code-review observations were noted as future improvements:
  extract `_build_server() -> FastMCP` for unit-testable bootstrap; add an
  assertion test that exactly 3 tools register. Captured in the H3 closure
  log entry as deferred polish.

## References

- `docs/superpowers/specs/2026-05-05-h3-mcp-server-design.md` — H3 spec.
- `docs/superpowers/plans/2026-05-05-h3-mcp-server.md` — H3 plan.
- `docs/technical_decisions_log.md` H3 section.
- `docs/adr/0004-rag-architecture.md` — predecessor; RAG layer that H3 consumes.
- `src/regulaitor/mcp_server/`, `src/regulaitor/citation/`, `src/regulaitor/agents/retriever.py`, `src/regulaitor/corpus/loader.py`, `src/regulaitor/rag/retrieval.py` — concrete output.
