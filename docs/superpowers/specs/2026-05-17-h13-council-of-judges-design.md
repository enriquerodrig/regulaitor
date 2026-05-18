# H13 — Council of Judges · Design Spec

**Date:** 2026-05-17 (brainstorming closed). **Milestone:** H13 (advanced track; H12 closed `v0.1.2-h12`).

**Goal:** Add a 3-judge multi-provider **Council** that, on high-severity / ambiguous chat findings, casts independent votes recorded as auditable evidence — **without changing the deterministic verdict** (advisory), surfacing a visible notice on divergence, and built so H15 can promote it to a monotonic gate with a one-line flip. Backend H1–H3 / Analyst / mechanical-Auditor-aggregation stay read-only (regression-zero).

---

## 1. Context (current state)

- Chat graph (`orchestration/graph.py`, H4): `injection_check → (cond) retriever → analyst → auditor → END`. `ChatState` (Pydantic v2, mutable container; inner objects frozen) carries `audited_answer`.
- `AuditorAgent.audit(answer) -> AuditedAnswer` is **pure-Python, deterministic, no LLM**: validates each `Citation` via `citation/validator.py`, Lenient-strict aggregation → `verdict ∈ AuditVerdict{PASS, BLOCK, REQUIRES_HUMAN_REVIEW}`. Its docstring already anticipates this: *"H13 may add LLM-based Auditor for high-severity cases; H4 stays mechanical."*
- **Known gap this milestone covers:** the mechanical Auditor validates citation *existence / text-match / article-exists* but NOT CLAUDE.md §6.4 *"que la cita apoya la afirmación"* (semantic support) — it cannot, it is matching not reasoning.
- `citation/schemas.py`: `Finding.severity: Literal["info","low","medium","high"]`; `Answer{query,language,text,findings}` (frozen); `AuditedAnswer{answer,verdict,audit_results,reason}`; `AuditVerdict` StrEnum already = the exact 3-state vote space.
- Router (H12, `models/router.py`): `complete(messages, system, tools, tool_choice, model_choice, max_tokens) -> CompletionResult`. `ModelChoice = Literal["default","quality","cost","evaluation","fallback"]`; `_MODE_MAP`: default/quality=Sonnet 4.6, cost=Llama-3.3-70b(Groq), evaluation=GPT-4o, fallback=GPT-4o-mini. Pure Anthropic↔OpenAI `_translate` makes tool-use work across all 3 providers. `.env` already has ANTHROPIC/OPENAI/GROQ/LANGFUSE keys (H12 T10).
- `prompts/judge/faithfulness.v1.0.md` exists but is the **H8 offline eval judge** (Haiku, read-only) — conceptually distinct from this production-time Council; Council prompts live in a separate role dir.
- Boundary: H11/H12 kept `graph.py` read-only (edge changes). **H13 differs:** §16.3 mandates *"integración en graph"* — graph/state/API are in-scope for H13; H1–H3 + Analyst + the mechanical-Auditor aggregation logic remain read-only.

## 2. Decisions (brainstorming, user-approved 2026-05-17)

- **D1 — Authority = advisory + visible notice + promotion-ready.** The Council **never mutates `state.verdict`** in H13; the deterministic mechanical Auditor stays the sole gate ("no citation, no answer" invariant 100% intact, reproducible). The reproducibility contract is `verdict`; `council_*` is **explicitly non-deterministic advisory evidence**. When the Council aggregate diverges from the Auditor verdict, the user-facing response carries a visible `council_notice` string. Aggregation is a **swappable `AggregationPolicy`**: H13 ships `AdvisoryMajorityPolicy` (default, never touches verdict); `MonotonicEscalatePolicy` is implemented + unit-tested **but wired OFF** — the H15 promotion seam (single documented constant `_COUNCIL_BINDING=False`; flipping it + selecting the monotonic policy is the entire promotion).
- **D2 — Trigger = hybrid.** Auto (when `council_override is None`): fire iff `audited_answer.verdict == REQUIRES_HUMAN_REVIEW` **OR** any `finding.severity == "high"`. API override `council: bool|None`: `True` → force-on (iff an `audited_answer` exists), `False` → force-off, `None` → auto. Always skip if `injection_blocked` or `audited_answer is None`.
- **D3 — Judges = 3 distinct providers via router.** Haiku 4.5 (Anthropic, **new `judge` router mode**) + GPT-4o (`evaluation`, exists) + Llama-3.3-70b Groq (`cost`, exists). All ≠ production Sonnet (§19 satisfied). Per-judge failure (incl. the documented Groq free-tier cap) → that judge `ok=False` with `error_category`; aggregate over successful judges (≥1); 0 ok → `council_verdict = REQUIRES_HUMAN_REVIEW`, reason `council_unavailable`. Every exception swallowed with WARNING — the chat turn and `verdict` are never affected (H11 advisory-layer pattern).
- **D4 — Scope = chat only.** Document pipeline (`document_graph.py`) untouched (read-only). Document-mode Council = documented follow-up (future).
- **D5 — Success = divergence study on the triggered subset (honest reframe).** Because advisory cannot change output, "Done when … mejora en alta severidad" is **impossible by construction**; the honest reframe (recorded decisions §H13, mirroring the H10 gate-reframe precedent): success = a committed `docs/council_analysis.md` divergence study + Council operative in the graph with green tests. Eval is **gated/announced** (explicit user OK before spend, H12 T10 pattern).
- **D6 — Architecture = Approach 1** (new `council` graph node + conditional edge after `auditor`). Rejected: post-processor outside the graph (forces a backend `run()` signature change anyway, Council not a real node — weak Módulo 2 story, duplicated trigger logic); composite Auditor+Council node (mixes responsibilities, mutates the tested H4 Auditor node).
- **D7 — Router mode extension.** Add a `judge` `ModelChoice` mode → Haiku 4.5. Minimal, ADR-worthy (ADR 0014), keeps "all LLM via the router" (§13). The H8 eval harness keeps its own Haiku usage (read-only; not refactored to the router this milestone).

## 3. Architecture & components

**`models/config.py`** — add `ANTHROPIC_HAIKU_4_5 = "claude-haiku-4-5-20251001"` constant + its `PRICING` entry (published USD/1M, same dict pattern; reuse existing `PRICING_SNAPSHOT_DATE` or bump it).

**`models/router.py`** — `ModelChoice` gains `"judge"`; `_MODE_MAP["judge"] = ProviderModel(PROVIDER_ANTHROPIC, ANTHROPIC_HAIKU_4_5)` (Anthropic bespoke path, already model-id-parametric since H12). No other router change; regression-zero for the 5 existing modes.

**`citation/schemas.py`** (additive only):
- `JudgeVote(BaseModel, frozen)`: `model_id: str`, `provider: str`, `vote: AuditVerdict`, `reason: str`, `ok: bool`, `error_category: str | None`.
- `CouncilReview(BaseModel, frozen)`: `triggered: bool`, `trigger_reason: Literal["auditor_rhr","high_severity","api_override","not_triggered"]`, `judges: list[JudgeVote]`, `council_verdict: AuditVerdict`, `agreement: Literal["unanimous","majority","split","degraded"]`, `diverges_from_auditor: bool`, `reason: str`.

**`orchestration/state.py`** — `ChatState` += `council_override: bool | None = None`, `council_review: CouncilReview | None = None`.

**`agents/council.py`** (new):
- `AggregationPolicy` (Protocol/ABC): `aggregate(votes: list[JudgeVote]) -> tuple[AuditVerdict, Literal["unanimous","majority","split","degraded"]]`.
- `AdvisoryMajorityPolicy` (H13 default): consider only `ok` votes; verdict = the modal vote if ≥2 `ok` votes agree, else `REQUIRES_HUMAN_REVIEW`. `agreement` label by strict precedence: `degraded` if `<3` ok votes (incl. 0 ok → verdict `REQUIRES_HUMAN_REVIEW`); else `unanimous` if all 3 agree; else `majority` if exactly 2 agree; else `split` (1/1/1 → verdict `REQUIRES_HUMAN_REVIEW`).
- `MonotonicEscalatePolicy` (implemented, unit-tested, **NOT wired into the node**): same `aggregate`, plus a separate `would_escalate(audited_verdict, votes) -> AuditVerdict` returning `REQUIRES_HUMAN_REVIEW` only on unanimous 3/3 `BLOCK`-equivalent over `ok` votes when `audited_verdict == PASS`; never relaxes `BLOCK`. H13 never calls `would_escalate` from the graph (the `_COUNCIL_BINDING=False` seam); it exists only so H15 inherits proven logic.
- `CouncilAgent(judge_modes=("judge","evaluation","cost"), policy=AdvisoryMajorityPolicy(), prompt_version="v1.0")`: `.review(audited: AuditedAnswer, context: Context) -> CouncilReview`. Builds one judge message set = the `Answer.text` + the **findings under review** + their `Citation`s + matching `AuditResult`s + the relevant retrieved `Context` chunks (so a judge can assess §6.4 semantic support). *Findings under review* = the union of every `severity=="high"` finding and (when `audited.verdict != PASS`) every finding with ≥1 non-validating `AuditResult`; if that union is empty (e.g. forced `override=True` on a clean PASS), all findings are reviewed. For each mode: `router.complete(model_choice=mode, tools=[vote_tool], tool_choice={"type":"tool","name":"cast_vote"}, system=<versioned prompt>, max_tokens≈600)`; parse `JudgeVote`; any exception → `JudgeVote(ok=False, error_category=type(e).__name__, vote=REQUIRES_HUMAN_REVIEW, reason="judge_failed")`. Aggregate via `policy`. `diverges_from_auditor = council_verdict != audited.verdict`. Reuses H12 `_translate` (tool-use across all 3 providers).

**`agents/prompts/council/judge.v1.0.md`** (+ `__init__.py`) — versioned prompt, frontmatter `agent: council`, `role: council_judge`, `model_compatibility: [claude-haiku-4-5-20251001, gpt-4o, llama-3.3-70b-versatile]`, changelog. Instructs: vote `valid|invalid|requires_human_review` on whether each presented finding's citations **support the assertion** (§6.4), one-sentence reason, structured via the `cast_vote` tool. Separate role dir from `prompts/judge/` (H8 eval judge) — no collision.

**`orchestration/graph.py`** — add `_council_node(state)` (lazy-cached `_council()` like the other agents; calls `CouncilAgent.review`, returns `{"council_review": ...}`, swallows all exceptions → `{}` + WARNING). `_council_triggered(state) -> bool` (D2 logic). `_route_after_audit(state) -> str` returns `"council"` if `_council_triggered` else `END`; never raises (`audited_answer is None` → `END`). Edges: replace `auditor → END` with `auditor → conditional(_route_after_audit){council, END}`, `council → END`. `run()` gains a `council_override: bool | None = None` kwarg threaded into `ChatState` (H13-scoped graph change per §16.3). Extend `_trace_record`/`_log_turn` with metadata-only council summary (`council_triggered`, `n_judges_ok`, `council_verdict`, `diverges`) — hash12 + redaction allowlist (H11 pattern); no raw text.

**`api/schemas.py` + `routes_ask.py`** — `AskRequest` += `council: bool | None = None`. `AskResponse` += `council_notice: str | None` (the prominent advisory text, present **iff** `council_review.diverges_from_auditor`) and `council: CouncilReviewDTO | None` (redacted detail: per-judge `model_id/provider/vote/ok/error_category` + `council_verdict/agreement/diverges_from_auditor/reason`; no raw query/text). `routes_ask` passes `request.council` into `graph.run(council_override=...)`. `verdict` field byte-identical to today.

**`ui_streamlit/tab_ask.py`** — when `council_notice` present, render it **prominently** (warning-style banner). Per-judge breakdown in an **optional collapsible** "Council (evidencia)" expander. Thin wrapper, no backend touch (H6 pattern); the collapsible detail may be time-boxed in the plan, the notice is core.

**`scripts/council_eval.py`** (new, thin; `ab_eval.py` pattern) — runs the 30 chat gold cases through `graph.run(..., council_override=True)` once (forces Council on every case to measure across the full chat set; Analyst stays Sonnet default — **no Ragas/judge re-score**, only the Council layer over existing pipeline outputs). Emits `docs/council_analysis.md` + raw `evals/reports/latest.council.md` (gitignore exception, H12 pattern): (a) N of the auto-trigger subset (RHR or high-sev), (b) council-vs-auditor agreement/divergence on the subset and on all-30, (c) per-judge vote distribution + abstain rate (Groq cap), (d) count where Auditor=PASS but Council=BLOCK/RHR (the safety signal). Honest, caveated (H12 `cost_analysis.md` tone).

## 4. Data flow

- **Prod, not triggered:** … → auditor → `_route_after_audit` → END (Council never constructed/called; zero added cost/latency).
- **Prod, triggered (auto or override=True):** auditor → council node → 3 router calls (judge/evaluation/cost modes) → policy aggregate → `council_review` in state; `verdict` **unchanged**; if `diverges_from_auditor` → `council_notice` set → API/UI surface it.
- **Degraded:** any judge raises → that `JudgeVote.ok=False`; aggregate over the rest; 0 ok → `council_verdict=REQUIRES_HUMAN_REVIEW reason=council_unavailable`; turn + verdict unaffected.
- **Eval:** `council_eval.py` forces `council_override=True` over 30 chat cases → divergence study docs.

## 5. Error handling & invariants

- **Advisory safety invariant:** the mechanical Auditor is the sole gate; the Council can never pass what the Auditor blocked nor change `state.verdict` in H13. "No citation, no answer" stays 100% deterministic & reproducible (gate §16.2 applies to `verdict`; `council_*` is declared non-deterministic evidence).
- Council node swallows **every** exception (judge failure, router error, aggregation bug) → WARNING + `council_review` None/degraded; the chat turn and verdict are byte-identical to the no-Council path (regression-zero user path, H11 pattern).
- `_route_after_audit` and `_council_triggered` never raise (`audited_answer is None` → END).
- SSDLC: no raw user query/answer text in logs / LangFuse / DTO — only `hash12` + categorical metadata via the existing redaction allowlist (§18.8).
- Missing OpenAI/Groq key only fails if that judge is invoked; the failure is contained per-judge (`ok=False`), never crashes the turn.

## 6. Testing

- **Unit ($0, router.complete mocked per judge):** trigger matrix (RHR / high-sev / override True|False|None / injection→skip / no-answer→skip / trigger_reason correctness); `AdvisoryMajorityPolicy` (3/0 unanimous, 2/1 majority, 1/1/1→RHR split, degraded 2-ok, degraded 1-ok, 0-ok→RHR); `MonotonicEscalatePolicy.would_escalate` in isolation (unanimous-3/3 escalate, never relax BLOCK, non-unanimous no-escalate) **+ a test asserting the graph node does NOT mutate `state.verdict` even when the monotonic policy would escalate** (proves the seam is OFF); exception swallowing (1 judge raises → abstain aggregate; all raise → degraded; turn+verdict unaffected); `CouncilReview`/`JudgeVote` schema; API DTO redaction + `council_notice` present **iff** diverges; trace record shape.
- **Integration:** chat graph with `council` node + mocked judges → assert `verdict` unchanged, `council_review` attached, and **all existing chat/Analyst/Auditor tests stay green untouched** (regression-zero).
- **Gated paid eval** = the success deliverable (explicit user OK before spend) → `docs/council_analysis.md`.
- CI 5 jobs green; coverage gate ≥90% on changed subsystems (new files fully covered).

## 7. Gate / definition of done (operative plan §16.3, §25, §24 Módulo 2)

1. `council` node wired (Approach 1); hybrid trigger (auto union + API override); advisory (`verdict` deterministic/unchanged); `council_notice` on divergence (API + Streamlit).
2. 3 distinct-provider judges via router (`judge`/`evaluation`/`cost`); degrade-on-failure; all exceptions swallowed (turn unaffected).
3. `AggregationPolicy` swappable; `AdvisoryMajorityPolicy` default ON; `MonotonicEscalatePolicy` implemented + unit-tested + wired OFF (`_COUNCIL_BINDING=False`, the H15 promotion seam).
4. Regression-zero: H1–H3 / Analyst / mechanical-Auditor untouched; existing tests green; coverage ≥90%.
5. Gated divergence-study eval executed (user OK) → `docs/council_analysis.md` committed (honest, caveated) + `evals/reports/latest.council.md`.
6. ADR 0014 + decisions §H13 (incl. honest "Done when" reframe + the explicit H15 promotion path) + evidence_matrix (Módulo 2 Council ✅) + CLAUDE.md §27 (→ Hito siguiente H14) + memory roll-forward.
7. Tag `v0.1.3-h13`.

## 8. Non-goals (YAGNI)

No verdict mutation in H13 (gate stays deterministic; promotion is H15); no document-mode Council; no full gold-set Ragas re-eval; no Auditor/Analyst/H1–H3 change; no new MCP; no new skill (`cost-accounting` stays H17); no latency optimization; the Streamlit per-judge collapsible detail may be time-boxed (the `council_notice` banner is core).

## 9. Risks

- **Judges uncalibrated (H12 finding: verdict_match 0.17–0.28).** Exactly why H13 is advisory; the divergence study *characterizes* this for H15 — it is the deliverable, not a defect to mask (§22.22).
- **Groq free-tier contamination (empirical H12 I-2).** Handled by per-judge degrade-to-available + honest documentation, **no re-run** (H12 precedent).
- **Router-mode extension reopens a closed module.** Minimal, additive, ADR 0014-documented, regression-zero for the 5 existing modes; flagged explicitly (milestone discipline).
- **Cross-provider tool-use parity for `cast_vote`.** Reuses the proven H12 `_translate`; Llama may emit weaker structured votes → recorded honestly as a finding.
- **Cost.** Gated/announced before the run; Haiku is cheap and is 1 of 3 judges; only the triggered subset calls judges in prod.

## 10. Boundary contract H13 inherits / narrows

H1–H3 (corpus/rag/retriever/citation) + Analyst + mechanical-Auditor aggregation **read-only / regression-zero**. In H13 scope (per §16.3 "integración en graph"): `graph.py`, `state.py`, `api/schemas.py`+`routes_ask.py`, new `agents/council.py`, additive `citation/schemas.py`, `models/router.py`+`config.py` (judge mode only), new `prompts/council/*`, new `scripts/council_eval.py`, Streamlit `tab_ask.py` (thin), docs. `.env` already holds all keys (H12); `.env.example` PROHIBITED (single `.env`). Decisions log = TFM backbone (every approved decision incl. option picks → §H13). gitleaks CI-enforced; local commits `SKIP=gitleaks` (never `--no-verify`). subagent-driven-development with 2-stage review per task. Honest metrics §22.22 (advisory ⇒ no fabricated "improvement").

## 11. References

- CLAUDE.md §6 (esp. §6.4 — the semantic-support gap this covers), §8.3/§8.4 (Council of Judges), §16.3 H13, §19 (judge ≠ production model), §24 Módulo 2.
- Decisions log §H4 (mechanical Auditor + the `auditor.py` docstring anticipating an H13 LLM layer), §H10 (gate-reframe precedent + H15 calibration plan), §H12 (router multi-provider reused; uncalibrated-quality finding; honest-doc / gated-paid-run pattern).
- ADR 0006 (chat graph), ADR 0013 (router multi-LLM). Spec: `docs/superpowers/specs/2026-05-16-h12-router-cost-design.md` (structure + gated-eval pattern).
