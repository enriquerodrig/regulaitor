# ADR 0012 — Observability architecture (H11)

- **Status:** Accepted
- **Date:** 2026-05-15 (decision); 2026-05-16 (implemented; squash `<squash-sha>`, tag `v0.1.1-h11` — finalized post-merge)
- **Deciders:** Project owner.
- **Companion ADRs:** 0001 (project scope), 0006 (chat graph), 0007 (document pipeline),
  0011 (redteam runner — this ADR closes its H9-deferred full run).

## Context

CLAUDE.md §16.3 lists H11 as the first advanced-track milestone: LangFuse
observability across the agents plus a dashboard of real cost/latency. §10.5
requires "LangFuse en todos los agentes + dashboard (citation accuracy, latencia
p95, coste, tasa de bloqueo)". Two debts from earlier milestones are folded in:
the H9-deferred full 50-attack redteam run (H9 amendment 5 — first attempt hung
on a silent Anthropic API timeout because the runner had no per-attack timeout),
and the §17 #7 latency caveat (the eval `latency_p95_ms` ≈ 572 s is a
batch-under-rate-limit artifact, not the product SLA — a clean per-span
measurement was deferred to H11).

Two hard constraints frame every decision: (a) §18.8 / §22.15 — citations and
user content are validated against the corpus, never leaked; traces go to a
**third party** (LangFuse Cloud), so raw query/document/citation text must never
leave the process; (b) the H1–H5 backend (agents, prompts, schemas, router) is
read-only from H6 onward — observability is an orchestration-layer concern, not
an agent change. The system entering H11 (main `b8dbf10`, tag `v0.1.0-mvp`) had
no `observability/` module beyond the structured JSON `_log_turn` /
`_log_document_turn` lines.

## Decision

Six design decisions (brainstorming closed 2026-05-15). Full rationale per Q in
`docs/technical_decisions_log.md §H11`. Executive summary:

### D1 — Scope: bundle all three pieces in H11

LangFuse instrumentation, the redteam per-attack timeout, and the full 50-attack
run ship as one milestone. The timeout is a prerequisite for the run (H9's hang),
and the run is the natural first consumer of the `block_rate` score, so splitting
would create artificial inter-milestone coupling.

### D2 — LangFuse hosting: Cloud free tier

`cloud.langfuse.com`, free tier (sufficient for TFM trace volume). Self-hosting
(docker-compose) was rejected as operational overhead with no academic value at
this scale; the dashboard is a demonstration artifact, not production infra.

### D3 — Trace data: metadata-only (redaction allowlist)

Traces carry only hashes (`hash12()` = sha256[:12]), counts (`n_*`), categorical
verdicts, and numeric latency/cost — never raw query/document/citation text. A
runtime allowlist guard (`_assert_safe_keys`) enforces this at the egress
boundary: any non-allowlisted key raises before the SDK is called. Verified
end-to-end against the live LangFuse backend (a canary token placed in a query
was confirmed absent from the server-side trace; only `query_sha256_12` + the
allowlisted metadata were present).

### D4 — Instrumentation: orchestration-layer wrapper

A new `src/regulaitor/observability/langfuse_client.py` exposes `is_enabled()`,
`hash12()`, a `TurnTrace` dataclass, and a `trace_turn()` context manager.
`graph.run()` and `document_graph.run_document()` are wrapped; the H3–H5 agents
are untouched. Per-agent decorators were rejected (would require touching agent
code, violating the backend-read-only constraint).

### D5 — Redteam timeout: per-attack wrapper

Each attack runs under a per-attack time budget (`REGULAITOR_REDTEAM_TIMEOUT_CHAT`
= 300 s, `REGULAITOR_REDTEAM_TIMEOUT_DOC` = 900 s); on expiry the runner records
a synthetic `timeout` outcome (`blocked=False`, the safe direction) and continues
instead of hanging the whole suite (the H9 failure mode).

> **Amendment during implementation (deviation from brainstorming Q5).** The
> approved design and the implementation plan specified
> `ThreadPoolExecutor + future.result(timeout)`. Two-stage code review found this
> is a **Critical defect**: the `with ThreadPoolExecutor(...)` context-manager
> exit calls `shutdown(wait=True)`, which blocks the timeout return until the
> worker finishes — and `concurrent.futures` registers an `atexit` join over
> non-daemon workers — so on a true silent API hang the runner would still hang
> forever (the exact H9 failure this task exists to prevent). It was replaced
> with an **abandoned daemon `threading.Thread` + `join(timeout)`**: the daemon
> thread cannot block process exit and `join(timeout)` returns promptly. A
> wall-clock promptness regression test was added. Recorded per CLAUDE.md §22.1;
> the implementation plan's Task 6 snippet was corrected to match. See decisions
> log §H11 and §H9 amendment 6.

### D6 — Dashboard + langfuse-mcp

LangFuse's native dashboard + `docs/runbook.md` (setup, what the dashboard shows,
the §17 #7 latency interpretation, operational procedures).

> **Amendment during implementation (deviation from brainstorming Q6).**
> Adding `langfuse-mcp` (a community MCP, requiring a new `.mcp.json` — none
> existed) was **deferred by explicit user decision (2026-05-16)** as the
> lowest-value H11 item (assistant-only convenience, not a product or thesis
> deliverable; zero impact on H11 closure or any gate). Documented as a deferral,
> not done; can be added in any future session. CLAUDE.md §13 (explicit MCP
> approval) honoured by not editing/creating `.mcp.json`.

### Enfoque A — observability never breaks or slows the pipeline

Without the three `LANGFUSE_*` env vars, `trace_turn()` is a total no-op (the
SDK is not even imported — zero overhead, proven by a regression-zero test). With
keys, the module-level Langfuse client is cached (no per-turn thread accretion),
`flush()` is called per turn (drains the async queue without blocking), and every
LangFuse exception is swallowed with a WARNING. Synchronous/blocking tracing
(enfoque B) was rejected.

### Out-of-plan: gitleaks enforced in CI

Discovered during implementation that the `.pre-commit-config.yaml` gitleaks
hook cannot run on the Windows dev box (golang-based, no Go toolchain) **and**
was not enforced in CI either — gate §16.2 #6 had no working automated
enforcement. User chose to add a pinned (`v8.21.2`) gitleaks step to the CI
`Security` job (Linux, installs cleanly). Local Windows commits skip only that
hook via `SKIP=gitleaks` (all other hooks run; never `--no-verify`). Recorded as
a deliberate, user-approved arrangement.

## Consequences

**Positive:**
- Clean per-span latency now measurable in LangFuse — resolves the §17 #7 caveat
  (the dashboard latency is the real per-query SLA; the eval `latency_p95_ms` is
  explicitly documented as a non-SLA batch artifact in the runbook).
- The H9-deferred full 50-attack redteam run is closed (block_rate reported
  transparently — see §H9 amendment 6 / §H11).
- The metadata-only privacy contract is proven end-to-end against the real
  third-party backend, not just in unit tests — a strong Module-4 security
  evidence point.
- gate §16.2 #6 now has real automated enforcement (CI gitleaks).
- Zero behaviour/latency change when LangFuse is absent (default state).

**Negative / accepted trade-offs:**
- Trace metadata only — no content-level debugging from LangFuse (deliberate
  privacy choice; raw text stays in local structured logs only).
- Dashboard demonstration depends on a LangFuse Cloud account + keys in `.env`
  (a manual user step; by design, not automatable).
- The full redteam block_rate (0.28 raw) is depressed by Anthropic API
  degradation during the run (21/50 timeouts); the gate rests on the H9 smoke
  evidence (0.92, deterministic, API-immune) per the H10 reframe — this is an
  H15 calibration signal, not an H9 re-open.

## Alternatives considered

- **Self-hosted LangFuse (docker-compose):** rejected — operational overhead, no
  academic value at TFM scale (D2).
- **OpenTelemetry / Prometheus:** rejected for H11 — heavier, and the dashboard
  requirement (§10.5) is LangFuse-specific; OTel/Prometheus stays HX5.
- **Per-agent decorators / instrumenting agents directly:** rejected — violates
  the H1–H5 backend-read-only constraint (D4).
- **Eager/synchronous flush per call (enfoque B):** rejected — would add latency
  to the product path; async batching + per-turn `flush()` chosen instead.
- **`ThreadPoolExecutor` for the redteam timeout:** rejected after review (D5
  amendment) — blocks on context-exit/atexit; daemon thread used instead.
- **Full-content traces:** rejected (D3) — third-party egress; metadata-only.

## References

- Spec: `docs/superpowers/specs/2026-05-15-h11-observability-design.md`
- Plan: `docs/superpowers/plans/2026-05-15-h11-observability.md`
- Decisions log: `docs/technical_decisions_log.md §H11` (6 Qs + enfoque A +
  amendments + closure metrics); `§H9 amendment 6` (full redteam resolution).
- Runbook: `docs/runbook.md`. Security report: `docs/security_report.md`.
- Redteam report: `redteam/reports/latest.md` (full run, commit `602c2da`).
