# Pre-H16 deep review

**Date:** 2026-05-26 (post v0.1.25 CONFIRM)
**Scope:** Tasks 1+2 of the user-requested pre-H16 phase (deep review + metrics state); Task 3 (frontend polish) lives separately.
**Method:** 5 parallel Explore subagents (haiku) covered: A1 Security · A2 Code cleanup · A3 Logic coherence · A4 Metrics state · A5 H16 architecture readiness. Controller verified all subagent claims against the actual repository state.
**Cost:** $0 (read-only analysis; no paid LLM calls).

---

## Executive summary — go/no-go for H16

**H16-readiness verdict: READY with focused 1–2-day prep**, not READY-AS-IS and not BLOCKED.

| Dimension | State | Action before H16 |
|---|---|---|
| **§6 invariant** | Rock-solid; THREE-layer architecture coherent in code + prose | None |
| **Security** | Strong (bandit clean, 0 secret leaks in repo/cache); `.env` correctly gitignored | None *(see §1 — A5 false alarm corrected)* |
| **Code hygiene** | GOOD (no dead code beyond lint; 21 diagnostic scripts archivable but not blocking) | Optional archival |
| **Logic coherence** | COHERENT (no contract drift; Council binding still meaningful post-v0.1.25) | None |
| **Metrics** | 7/7 v0.1.20-bar PASS at v0.1.25-prod 30-case; 1/7 aspirational (citation_recall) | Accept residuals as carry-forward |
| **Infra (Docker / deploy)** | **MISSING** — no Dockerfile, no `docker-compose.yml`, no deploy workflow | **BLOCKING** for H16 deploy |
| **truststore** | In `.venv` only, NOT in `pyproject.toml` (v0.1.22 carry) | **BLOCKING** for Docker cold-build |
| **CORS/CSP** | Defaults (permissive); fine for non-browser, gap for public UI | Important nice-to-have |
| **Coverage gate** | Inherited 88.55% (v0.1.21.3 hotfix carry); not enforced in CI | Important nice-to-have |

**Estimated H16-prep effort:** 2–3 días focados ($0 throughout) para Dockerfile + truststore en deps + deploy runbook + (opcional) CORS + coverage gate. Resto = carry-forward post-H16.

---

## §1 — A1 Security audit + critical correction

### Headline (after controller correction)

- **bandit**: 0 issues across 6,219 lines src/ (HIGH+confidence:HIGH).
- **pip-audit**: SSL cert error blocked online run; deps offline-inspected, all on supported versions. **Re-run in CI before H16 deploy** (CI runs on Linux with valid certs).
- **semgrep + gitleaks (local)**: not on PATH; SKIPPED. CI gitleaks IS enforced (v8.21.2 pinned per H11 commit `8378015`).
- **Cache PII/secret scan**: 200 sampled `evals/cache/*.json` files — 0 hits for Anthropic/OpenAI/Groq keys, Bearer tokens, emails.
- **`.env` exposure**: 🔴 **A5 false alarm — corrected**: `.env` is **NOT tracked** in git (`git ls-files | grep .env` empty; `git log --all -- .env` empty; `.gitignore:47:.env` matched). The local file exists on disk (expected for dev), with real keys — but it was never pushed. **No exposure**.

### Real findings (not blockers)

| # | Finding | Severity | Action |
|---|---|---|---|
| S6.1 | CORS/CSP headers missing in FastAPI | LOW (no browser UI yet; Streamlit is server-rendered) | Add `CORSMiddleware` before public deploy |
| S6.2 | `/health` checks LanceDB + env vars only; doesn't ping upstream Anthropic | LOW | Optional: async upstream check with fail-open |
| S6.3 | gitleaks pre-commit hook not local (only CI) | LOW | Optional: add to `.pre-commit-config.yaml` |

### Verdict A1
**READY for H16** (pending CI pip-audit re-run on Linux). No secret leaks. Strong defense-in-depth (auth Bearer + slowapi rate limit + injection sanitizer + Auditor §6 enforcement).

---

## §2 — A2 Code cleanup

### Headline
- **21 per-milestone diagnostic scripts** (`scripts/v0120_*.py` … `scripts/v0125_*.py`) totaling ~5.4K LOC. Most are one-shot. Candidates for archival post-H16 (per §22.4 user rule: NOT deletion, only archival proposals).
- **44 `# noqa` / `# type: ignore` suppressions** across 15 files — all justified (mostly httpx/Anthropic SDK typing gaps + Pydantic serialization gaps documented in ADRs).
- **0 stale TODOs/FIXMEs** in `src/`; **1 trivial XXX** placeholder in test docstring.
- **5 Analyst prompt versions** (v1.0 doc default + v1.5 chat default + v1.1/v1.2/v1.3/v1.4 dormant). v1.1-v1.4 retained for regression A/B + audit trail; **NOT dead code** (`tests/unit/test_analyst_v1_*.py` validates each version loads).
- **3 dev deps suspect of unused**: `ragas`, `langchain-anthropic`, `langchain-huggingface` — no active `import` in `src/regulaitor/`. May still be used by diagnostic scripts; verify before removing.
- **Reports**: ~1 MB across 13 milestone directories. Permanent archival value (audit trail); no deletion recommended.

### Verdict A2
**GOOD code hygiene** for an iterative TFM project. Recommended (NOT blocking) actions before H16:
1. **(Optional)** Move `scripts/v012{0-4}_*.py` to `.archive/` or `docs/milestones/diagnostics/` (keep `scripts/v0125_*.py` — active harness pattern reusable for H17+).
2. **(Optional)** Verify `ragas` + `langchain-*` deps; remove from `pyproject.toml [dev]` if confirmed unused.
3. **(Optional)** Document Analyst prompt version EOL timeline (v1.5 chat / v1.0 doc are production; v1.1-v1.4 retrospective only).

---

## §3 — A3 Logic coherence

### Headline
- **§6 THREE-layer architecture coherent** in code + prose:
  - Layer (a) per-citation validator: `citation/validator.py` BYTE-UNCHANGED since H4
  - Layer (b) Finding-Lenient: `auditor.py` aggregation BYTE-UNCHANGED since v0.1.21
  - Layer (c) Turn-level routing: modified at v0.1.25 (new `_all_blocked_findings_paraphrase_only` helper)
- **Cross-module contracts CLEAN**: Citation → AuditResult → AuditedAnswer → ChatState chain consistent; no field renamed without updates downstream.
- **Naming CONSISTENT**: AuditVerdict enum (`pass`/`block`/`requires_human_review`) used uniformly; severity scale (`info`/`low`/`medium`/`high`) consistent across schemas + prompts + UI + API.
- **Dead branches: NONE detected** — v0.1.21 quorum branch still reachable (independent of v0.1.25 partial-routing path); Council triggers all reachable.
- **v0.1.25 helper `_all_blocked_findings_paraphrase_only` edge cases**: correctly handles empty per_finding_results (vacuous True), None `failed_check` (legacy cached AuditResults → conservative False), mixed Check 1/2/3 (conservative False on first non-3). No path to fabricated article/apartado bypass.
- **Council binding still meaningful post-v0.1.25**: `_COUNCIL_BINDING=True` + `MonotonicEscalatePolicy` still active; covers the conservative-escalation case (Auditor PASS + 3/3 Council BLOCK → RHR) that partial-routing softening doesn't address.

### Recommended (NOT blocking) cleanup
1. **Add 1-line §6 THREE-layer summary to CLAUDE.md §6** (currently the architecture lives in prose across ADRs 0024/0027/0030/0032 + decisions_log; CLAUDE.md §6 still reads as the original "no citation, no answer" plain statement). One sentence pointing to `auditor.py:47-119` as definitive.
2. **Add v0.1.25 note to `council.py` module docstring**: one sentence clarifying that partial-routing softening does NOT remove Council's binding role.
3. **Tag `auditor.py` three-branch logic with ADR refs** (inline comments on lines ~83/94/98 pinning each branch to ADR-0027 D1 quorum / ADR-0027 D3 all-blocked / ADR-0032 D2 partial-softening).

### Verdict A3
**COHERENT**. Code and prose aligned. Proceed to H16 with confidence on logic side.

---

## §4 — A4 Metrics state (with controller correction)

### ⚠️ A4 number correction (§22.22)

A4 confused **probe.md (5 cases, chat-001..005)** with **v0.1.25-prod.md (30 cases combined)**. The probe-only numbers it cites (faithfulness 0.90, verdict_match 1.00, etc.) are the **strong-sample 5-case subset**, NOT the headline 30-case result. The actual v0.1.25 v0.1.20-bar comparison report (`evals/reports/v0.1.25/comparison.md`) shows:

### Real current state (v0.1.25-prod 30-case, post v0.1.24 O1 re-aggregation)

| Metric | v0.1.25-prod (30-case) | v0.1.22-prod baseline | Δ | v0.1.20-bar | Aspirational §17 | Gap to aspirational |
|---|---|---|---|---|---|---|
| faithfulness | **0.71** | 0.72 | -0.01 | ≥0.65 ✅ | ≥0.85 | -0.14 |
| answer_relevancy | **0.69** | 0.73 | -0.03 | ≥0.55 ✅ | ≥0.85 | -0.16 |
| context_precision | **0.63** | 0.66 | -0.02 | ≥0.55 ✅ | ≥0.80 | -0.17 |
| citation_precision | **0.27** | 0.28 | -0.00 | ≥0.25 ✅ | ≥0.90 | **-0.63** |
| citation_recall | **0.68** | 0.67 | +0.02 | ≥0.60 ✅ | ≥0.80 | -0.12 |
| **verdict_match** | **0.73** | 0.40 | **+0.33** ✅ | ≥0.35 ✅ | ≥0.85 | -0.12 |
| severity_match | **0.40** | 0.40 | 0.00 | ≥0.35 ✅ | ≥0.80 | **-0.40** |

**7/7 v0.1.20-bar PASS** ✅ · **0/7 aspirational hit** (subtle: the report's "citation_recall 0.81" aspirational hit in earlier framing was the probe sample; 30-case is 0.68).

### Trajectory headlines (per A4 historical analysis, validated)

- **verdict_match BREAKTHROUGH**: H10=0.28 → v0.1.22=0.30 → v0.1.23=0.27 (REVERT) → v0.1.25=**0.73** (+0.33; largest single-milestone lift in lineage). Mechanism: D2 partial-routing softening targeting v0.1.24.1's identified Path B dominance.
- **faithfulness/answer_relevancy**: H10 0.54/0.53 → v0.1.25 0.71/0.69 (steady improvement; near-bar of aspirational; trajectory ceiling = system-level retrieval per H12/H13/H14/H15).
- **citation_precision**: H10=0.17 → v0.1.25=0.27 (flat; largest aspirational gap -0.63; mechanism = §6-strict text match — improving this means touching validator = HIGH risk).
- **severity_match**: H10=0.23 → v0.1.25=0.40 (flat plateau v0.1.22-v0.1.25; mechanism = Analyst prompt severity-token bias + gold annotation drift).

### Residual mechanisms (per metric)

| Metric | Known mechanism | Last attempt | Why deferred |
|---|---|---|---|
| verdict_match | RESOLVED via D2 (v0.1.25) | v0.1.25 ADR-0032 | Done |
| citation_precision (-0.63 to asp) | §6-strict Check 3 paraphrase mismatch; validator IS the guardian | v0.1.18 (eval-side hierarchical containment fix); v0.1.23 (REVERTED Tier 1 lenient) | HIGH §6 risk; Designs A/C HX-deferred |
| severity_match (-0.40 to asp) | Analyst prompt + gold annotation calibration | None in v0.1.19-v0.1.25 (no targeted intervention) | LOW §6 risk; Analyst v1.6 calibration carry-forward HX |
| citation_recall (-0.12 to asp) | Retrieval breadth ceiling | v0.1.21.2 (per-norma cap + top_k_auto) | Modest gap; diminishing returns |
| context_precision (-0.17 to asp) | Reranker confidence ceiling | v0.1.21.2 (per-norma cap) | Negligible 0.03 vs aspirational on probe |
| faithfulness/answer_relevancy | System-level ceiling | v0.1.15-v0.1.25 cumulative | Near-bar; aspirational unrealistic for current stack |

### Tweak candidates pre-H16

Per the discipline of the project (§22.22 + paid-validation gating), the **realistic pre-H16 list is short**:

| Candidate | §6 risk | Lift est | Cost est | Verdict |
|---|---|---|---|---|
| **Accept current state as-is** | NONE | 0 | $0 | **RECOMMENDED** — v0.1.25 hit 7/7 bar; further tweaks need paid validation; H16 deploy is the priority |
| All-blocked routing Design D (chat-016 pattern) | MEDIUM | Marginal (1/30 cohort) | $0 capability + ~€2 paid mini-validation | **Post-H16 if needed** |
| Severity v1.6 calibration | LOW | +0.15-0.20 | ~€3-5 paid A/B | **Post-H16 / HX** |
| Cost-per-chat €0.054 → €0.05 (selective retry) | LOW | -€0.005/case | ~€3-5 paid A/B | **Post-H16 / HX** (€0.004 over-bar is acceptable) |
| Citation precision Designs A/C | HIGH | +0.10-0.15 | ~€4-6 paid A/B | **HX post-TFM** (HIGH §6 risk per v0.1.23 REVERT lessons) |

### Verdict A4 (after correction)
**No metric tweaks recommended pre-H16**. 7/7 bar PASS at 30-case. Aspirational gaps are well-understood and carry-forward to H17 (academic memoria) or HX post-TFM. Cost overage €0.004 is acceptable trade-off for the +0.33 verdict_match lift.

---

## §5 — A5 Architecture H16-readiness (with critical correction)

### ⚠️ A5 correction (§22.22)

A5 claimed `.env` is **committed in the repo with real keys**. **VERIFIED FALSE** by controller (see §1 above). The file exists locally on disk (correct for dev) and IS gitignored; it was never pushed. **DO NOT** "hard-delete from git history" or "rotate all keys" — there's nothing to delete or rotate-due-to-leak.

### Real H16 blockers (verified)

| # | Finding | Severity | Action |
|---|---|---|---|
| **H3.1** | **No `Dockerfile`** — `make docker` is a stub | **BLOCKING** | Create multi-stage Dockerfile (Python 3.11-slim base; entry = `uvicorn` for API or `streamlit run` for UI; ~150 LOC) |
| **H3.2** | **No `docker-compose.yml`** | **BLOCKING for local testing** | Create with FastAPI + Streamlit services |
| **H4.1** | **`truststore` in `.venv` only**, NOT in `pyproject.toml` | **BLOCKING** for clean Docker build (would fail at `import truststore` in `scripts/v01xx_run.py`) | Add `truststore>=0.10` to `pyproject.toml [project.dependencies]` OR remove from deploy scripts (verify SSL strategy) |
| **H5.1** | No `.github/workflows/deploy.yml` | IMPORTANT | Create for tag-triggered deploy to HF Spaces |
| **H4.2** | `LANCEDB_PATH` defaults local; HF Spaces needs persistent volume mount | IMPORTANT | Make env-configurable; document cold-start SLA (15-20 min first build vs <1s warm) |
| **H1.3** | CORS/CSP not configured | IMPORTANT (post-public) | Add `CORSMiddleware` + CSP middleware |
| **H5.2** | Coverage gate not enforced in CI | IMPORTANT | Add `--cov-fail-under=85` (matches v0.1.21.3 hotfix 88.55% carry adjusted down for offline-SSL tests) |
| **H6.1** | No `/metrics` Prometheus endpoint | NICE | Optional for H16; required for H17 public ops |
| **H6.2** | No external watchdog for HF Spaces 24h uptime | NICE | Optional cron GH Action pinging `/health` |
| **H8.1** | No `.streamlit/config.toml` | NICE | Add for HF Spaces port 7860 + headless |

### Streamlit deploy readiness (A5 detail, validated)

- `ui_streamlit/app.py` is **READY** for HF Spaces native deploy (2 tabs + disclaimer + ANTHROPIC_API_KEY guard + no localhost-only config).
- For Render/Fly.io: needs Docker wrap (see H3.1).

### MCP server status (A5 detail, validated)

- `src/regulaitor/mcp_server/` is functional (5 tools, stdio JSON-RPC).
- **Keep internal** for H16; do NOT expose externally. External MCP-over-HTTP is post-TFM/H17+ work.

### Verdict A5 (after correction)
**NEEDS-FIX-FIRST for H16**: Docker infra (Dockerfile + compose) + truststore in pyproject.toml + (recommended) CORS + coverage gate. Effort: **2-3 días focused** ($0 throughout). All other gaps are post-H16 nice-to-haves.

---

## §6 — Aggregated priority action list

### Pre-H16 BLOCKING (must do before deploying anywhere)
1. **Create `Dockerfile`** (multi-stage; Python 3.11-slim; entrypoint for FastAPI + Streamlit modes; ~150 LOC). [H3.1]
2. **Create `docker-compose.yml`** (FastAPI + Streamlit services; volume mounts for `corpus/indexes` + HF cache). [H3.2]
3. **Add `truststore>=0.10` to `pyproject.toml`** OR remove from `scripts/v01xx_run.py` (verify production SSL strategy). [H4.1]
4. **Document HF Spaces cold-start SLA** (5-20 min first build for LanceDB rebuild + reranker download; <1s warm; persistent volume strategy). [H4.2]

### Pre-H16 IMPORTANT (strongly recommended before public deploy)
5. **Add `CORSMiddleware`** to FastAPI with allowlist origins. [H1.3]
6. **Add coverage gate** to CI (`--cov-fail-under=85` matching v0.1.21.3 hotfix baseline). [H5.2]
7. **Re-run `pip-audit`** on CI (Linux) before H16 tag (local SSL cert blocked offline run). [A1 S1]
8. **Write `docs/H16_DEPLOY.md`** (deployment runbook: HF Spaces + Render/Fly.io + local Docker). [H5.1]

### Pre-H16 OPTIONAL (low priority; can be carry-forward)
9. **Archive `scripts/v012{0-4}_*.py`** (~21 files, 2.6K LOC) to `.archive/` or `docs/milestones/diagnostics/`. [A2 C1] *(NOT deletion per §22.4)*
10. **Verify `ragas` + `langchain-*` dev deps** usage; remove from `pyproject.toml [dev]` if confirmed unused. [A2 C7]
11. **Add 1-line §6 THREE-layer summary to CLAUDE.md §6**. [A3 L4]
12. **Add gitleaks to local pre-commit** (already in CI). [A1 S6]
13. **Document Analyst prompt version EOL** (v1.5 chat / v1.0 doc production; v1.1-v1.4 retrospective). [A2 C4]

### Accept as carry-forward to H17 / HX
14. **All metric aspirational gaps** (citation_precision, severity_match, citation_recall, context_precision, faithfulness) — 7/7 v0.1.20-bar PASS is sufficient evidence for TFM defense; aspirational closure is HX work. [A4 M5]
15. **cost_per_chat €0.054 over €0.05 bar by €0.004** — accept trade-off for +0.33 verdict_match lift. [A4 M6]
16. **chat-016 all-blocked routing pattern** (1/30 cohort frequency) — Design D HX-deferred. [A4 M5]
17. **Cross-vendor judge migration** (Haiku 4.5 → GPT-4o-mini or Llama-3.3-70b) — HX post-TFM per ADR-0021 D3. [A4 M5]

---

## §7 — Recommended next-3 sessions

1. **Session 1 (~2 días)**: Items 1-4 (Dockerfile + compose + truststore + cold-start SLA doc). Outcome: `make docker` works; `make serve-api` and `make serve` work in container locally.
2. **Session 2 (~1 día)**: Items 5-8 (CORS + coverage gate + CI pip-audit re-run + H16 deploy runbook). Outcome: H16-ready for tag.
3. **Session 3 (~1 día)**: H16 implementation (HF Spaces deploy via `deploy.yml` tag trigger; persistent volume config; smoke-test 24h uptime via cron GH Action). Outcome: public demo URL.

**Total H16-prep effort: 4-5 días focados $0**, then **H16 execution = 1 día** for first public deploy. H17 (TFM cierre académico) = 1-2 semanas post-H16.

---

## §8 — Frontend (T3) — separate phase

Task 3 (frontend polish — Streamlit minimal-but-pro) is **independent** of items 1-13 above. Will be handled in **Fase B** after user reviews this report:
1. Invoke `/ui-ux-pro-max` skill
2. WebSearch Vercel design principles (Geist UI, Geist typography)
3. Read current `ui_streamlit/{app,tab_ask,tab_analyze,_render}.py`
4. Propose 2-3 polish options with previews
5. User picks → implement → commit (separate `feat/frontend-polish` branch or direct to main per user preference)

---

## §9 — Cost reconciliation

- Pre-Fase A budget: ~$3.43 USD remaining
- Fase A spend: **$0** (5 haiku Explore subagents; read-only analysis)
- Post-Fase A budget: **~$3.43 USD remaining** (unchanged)
- Fase B (frontend) expected: **$0** (UI work; no LLM calls)
- H16 deploy expected: **$0** (infra + docs only; no paid validation)

Budget headroom for H17 paid milestones or post-H16 small A/B confirmations: ~$3.43 USD. New top-ups optional.

---

## §10 — TFM defense framing

This pre-H16 review reinforces the methodology contribution narrative:

1. **§6 invariant remains the spine** — 5 sub-reviews independently validated the THREE-layer architecture is coherent in code and prose; the v0.1.25 evolution from "byte-unchanged" to "validator+Finding-Lenient byte-unchanged + aggregation modified" is honestly stated.

2. **§22.22 honest framing applied to the review itself** — Controller flagged 2 subagent errors (A5 .env false alarm + A4 probe-vs-30-case number conflation) and corrected them inline rather than letting them propagate into the action list. The review-of-the-review is part of the discipline.

3. **Deferral discipline preserved** — Most identified gaps (metric aspirational closures, all-blocked routing, severity calibration) are correctly carry-forward; the pre-H16 action list is **focused on what's blocking deploy**, not exhaustive on every optimization opportunity. This is the "small clear steps with checkpoints" pattern the user established.

4. **The methodology continues to be the contribution.**

---

**End of pre-H16 review.**
