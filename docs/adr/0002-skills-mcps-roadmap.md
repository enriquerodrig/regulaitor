# ADR 0002 — Skills, MCPs and subagents introduction roadmap

- **Status:** Accepted
- **Date:** 2026-04-30
- **Deciders:** Project owner (TFM author).

## Context

`CLAUDE.md` §12-§14 prescribes a substantial set of agent skills, external MCPs and specialised subagents. Installing all of them upfront would violate two project rules:

- §22.5 ("No instales dependencias, MCPs ni skills sin justificar y esperar OK").
- §22.20 ("Si detectas sobreingeniería, dilo").

Each skill, MCP and subagent must therefore be introduced at the milestone where it first earns its keep, with explicit owner approval. This ADR records the schedule so future sessions can plan against it without re-deriving the rationale.

## Decision

### Skills introduction calendar

| Skill | Milestone | Trigger | Owner of `SKILL.md` proposal |
|---|---|---|---|
| `superpowers` (Anthropic) | always active | session bootstrap | n/a — built-in |
| `adr-writer` | H1 | first batch of ADRs (≥2 in flight) | implementer |
| `rag-ingest` | H1 | first corpus ingestion run | implementer |
| `prompt-versioning` | H2-H3 | first non-trivial system prompt landing in `agents/prompts/` | implementer |
| `citation-validator` | H4 | Auditor-Agent online | implementer |
| `document-analysis` | H4 | document mode pipeline online | implementer |
| `evals-runner` | H8 | first reproducible `make eval` run | implementer |
| `model-card` / `data-card` | H8 | first dataset and first deployed model documented | implementer |
| `redteam-runner` | H9 | first reproducible `make redteam` run | implementer |
| `secure-coding-checklist` | H9 | merged with first PR after `make redteam` lands | implementer |
| `ai-act-assessment` | H17 | academic deliverable preparation | implementer |
| `cost-accounting` | H17 | cost/consulta and cost/documento numbers needed for memoria | implementer |
| Anthropic `pdf` | H7-H8 | downloadable reports / PDF corpus | n/a — official |
| Anthropic `xlsx` / `pptx` / `docx` | H17 | final deliverables | n/a — official |
| `lora-finetune-recipe` | HX1 | LoRA optional milestone | implementer |
| `next-frontend-architect` / `ui-style-guide` | HX2 | Next.js frontend optional | implementer |
| `incident-postmortem` | HX (post-deploy) | first production incident | implementer |

### MCPs introduction calendar

All MCPs are **propose-and-wait**: implementer proposes the exact installation command, owner approves before execution. Zero MCPs installed in H0.1.

| MCP | Milestone | Trigger | Scope |
|---|---|---|---|
| `fetch` | H1 | first corpus download | allowlist `eur-lex.europa.eu`, `boe.es`, `arxiv.org` |
| `playwright` or `puppeteer` | H1 (conditional) | EUR-Lex requires JS rendering | one-off scrape session |
| `git` | H1 (conditional) | only if Bash git becomes friction | repo only |
| `github` | H7 (conditional) | when issue/PR automation needed | least privilege |
| `sqlite` | H4 (conditional) | when metadata DB becomes interactive | local file only |
| `mcp-server-time` | H1 | corpus ingest needs accurate timestamps | n/a |
| `mcp-pandoc` | H17 | bilingual deliverables conversion | n/a |
| `langfuse-mcp` | H11 | trace and metric inspection | one workspace |
| `tavily-mcp` or `brave-search` | H17 | bibliographic references for memoria | rate-limited |
| `filesystem`, `memory`, `sequential-thinking` | not needed | covered by built-in tools and `~/.claude/.../memory/` | — |

### Subagents introduction calendar

Subagents in `.claude/agents/<name>.md` are introduced when their scope becomes load-bearing. Built-in subagents (`Explore`, `Plan`, `general-purpose`, `code-reviewer`) cover the common cases until then.

| Subagent | Milestone | Reason to introduce |
|---|---|---|
| `software-architect` | H3 | first non-trivial architectural decisions (MCP server, schemas) |
| `security-engineer` | H6 | document sanitizer and injection detection land |
| `evals-engineer` | H8 | gold set design and gate definition |
| `redteam-engineer` | H9 | adversarial suite design |
| `legal-aiact-reviewer` | H10 | first claims about own AI Act classification |
| `mlops-engineer` | H11 | LangFuse and observability rollout |
| `frontend-engineer` | H6 (Streamlit) / HX2 (Next.js) | UI work |
| `docs-writer` | H10 | documentation freeze prep |
| `tech-writer-academic` | H17 | memoria preparation |

### Rules of engagement

1. **Propose-and-wait** for every skill, MCP and subagent introduction (no exceptions).
2. **Justification template** for each proposal: (a) what triggers it, (b) why now and not earlier or later, (c) exact install command or `SKILL.md` content, (d) scope minimisation.
3. **No retroactive installation**: if a milestone closes without consuming a planned skill/MCP, push the entry to the next milestone in the calendar rather than installing it speculatively.
4. **Skill files** stay ≤ 150 lines and procedural per CLAUDE.md §12.6; long detail goes to `references/` adjacent to the skill.

## Consequences

### Positive

- Bootstrap (H0.1) ships with zero infrastructure debt.
- Each installation has a paper trail: an ADR mention or a PR description tying the install to a concrete task.
- Audit trail directly demonstrates the M4 "controles de producción" claim for the master defence.

### Negative

- More propose-and-wait cycles than installing everything upfront. Mitigation: most decisions are batched at milestone start.
- Risk of "we will install it in Hn" never materialising. Mitigation: per-milestone Done criteria (CLAUDE.md §25) include "skills/MCPs introduced as scheduled".

## References

- `CLAUDE.md` §12 (Skills), §13 (MCPs), §14 (Subagents).
- `0001-project-scope.md` (parent ADR).
- `0003-corpus-pipeline.md` — companion ADR landed at H1 closure.

---

## H1 closure update (2026-05-04)

H1 closed with the following deviations vs the calendar above. All deferrals reduce scope; no skill or MCP was introduced earlier than planned.

### Skills

- **`rag-ingest`** introduced **as scheduled** in H1. SKILL.md committed at `.claude/skills/rag-ingest/SKILL.md` (commit `114285f`).
- **`adr-writer`** **deferred from H1 to H10**. Rationale: H1 produced two ADRs (0003 plus this update), but both were drafted by the implementer in a single batch with no signs of repeated friction. The skill earns its keep when ≥3 ADRs queue up in a single milestone, which is more likely at H10 (documentation freeze).
- **Anthropic `pdf` skill** **not introduced in H1**. The original calendar slot was H7-H8 (downloadable reports). `pdfplumber` was added as a runtime dependency for corpus ingestion instead, fully decoupled from the Anthropic `pdf` skill.

### MCPs

- **`fetch`** **deferred from H1 to H3+**. Rationale: `httpx` direct call in `eurlex.py` with explicit allowlist (`eur-lex.europa.eu`) is sufficient and simpler. `fetch` MCP was originally scoped for H1 corpus download; it will be reconsidered in H3 if other agents (Retriever, Auditor) need general browse capability.
- **`mcp-server-time`** **not introduced**. Python's `datetime.now(timezone.utc)` covers all timestamp needs in H1. No future re-introduction planned unless an external scheduling/cron MCP brings it as a dependency.
- **`playwright` / `puppeteer`** **not introduced**. The H1 smoke run revealed EUR-Lex CloudFront WAF blocks non-browser clients, but the operational pivot to local PDF snapshots (committed to LFS) avoided needing browser automation. Re-evaluate if H14 (NIS2/DORA) needs to scrape a JS-heavy source.

### Subagents

- No project-level subagents were introduced in H1. Built-in agents (`Explore`, `Plan`, `general-purpose`, `code-reviewer`, `superpowers:code-reviewer`) covered all H1 needs across implementation, spec review, and code-quality review. The first project-level subagent (`software-architect`) is still scheduled for H3.

### Calendar updates carried forward

The dependency installation calendar above remains the source of truth for H2 onwards. The H1 deferrals are reflected in `docs/technical_decisions_log.md` H1 closure entry "Skills/MCPs deferrals tras smoke H1" with the same rationales.

---

## H2 closure update (2026-05-05)

H2 closed with the following deviations vs the calendar above. As in H1, all deferrals reduced scope; nothing was introduced ahead of plan.

### Skills

- **`prompt-versioning`** **deferred from H2 to H3**. Rationale: H2 contained no LLM-facing prompts (BGE-M3 / bge-reranker are encoder-only models with no system prompt surface). The skill earns its keep when the first agent prompt lands in H3 (`agents/retriever.py`).

### MCPs

- **No MCPs introduced in H2.** The original calendar slot for `fetch` (H3+) and `langfuse-mcp` (H11) is unchanged. RAG build runs entirely against local files and the local LanceDB index — no external MCPs needed.

### Subagents

- No project-level subagents introduced in H2. Built-in `general-purpose` agent + `superpowers:code-reviewer` covered all 16 tasks (implementer + spec review + code quality review). The first project-level subagent (`software-architect`) remains scheduled for H3 — likely earning its keep on the citation-validator design and the MCP server contract.

### Calendar updates carried forward

- `prompt-versioning` shifts from H2 to H3 brainstorm.
- `citation-validator` skill arrives in H3 as planned (no shift).
- `document-analysis` remains H4 (originally H4-H5 boundary).

These shifts are reflected in `docs/technical_decisions_log.md` H2 closure entry.
