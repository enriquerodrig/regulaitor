# RegulAItor — Architecture

Architecture overview of RegulAItor (MVP closure state at `v0.1.0-mvp`).
Diagrams follow the [C4 model](https://c4model.com/) (Context, Containers,
Components) rendered in Mermaid.

> Source of truth for design decisions: `CLAUDE.md` §8 (agents), §10 (stack),
> [ADR 0001-0011](adr/). Each diagram below references the ADR that justifies
> its structural choices.

---

## L1 — System Context

External actors and bounded contexts.

```mermaid
%%{init: {'theme':'neutral'}}%%
graph TB
    user[("Compliance Officer<br/>(PYME / asesoría)")]
    tutor[("TFM Tutor /<br/>External Reviewer")]

    subgraph RegulAItor["RegulAItor System"]
        direction LR
        sys["Multi-agent service<br/>chat + document analysis<br/>+ audit trail"]
    end

    eurlex[("EUR-Lex<br/>(AI Act, GDPR PDFs)")]
    anthropic[("Anthropic Claude<br/>(Sonnet 4.6 prod,<br/>Haiku 4.5 judge)")]
    hf[("HuggingFace Hub<br/>BGE-M3 + reranker")]

    user -->|"chat queries +<br/>policy documents"| sys
    sys -->|"audited answers +<br/>structured findings"| user
    sys -->|"corpus ingest<br/>(H1, manual)"| eurlex
    sys -->|"LLM calls<br/>(production + judge)"| anthropic
    sys -->|"model + reranker<br/>(local cache)"| hf
    tutor -.->|"reads reports +<br/>decisions log"| sys
```

**Boundaries**:
- **User-facing**: Streamlit UI (H6) on `localhost:8501` and FastAPI HTTP (H7) on
  `localhost:8000`. Both wrap the same backend pipelines.
- **External services**: Anthropic API (production + judge model calls;
  read-only HTTP). HuggingFace Hub (one-time model download per host).
- **Trust boundary**: user-uploaded documents pass through the sanitizer +
  injection regex defenses before reaching the LLM. See §6 + §18 of
  `CLAUDE.md`.

---

## L2 — Containers

The deployable units inside the system boundary.

```mermaid
%%{init: {'theme':'neutral'}}%%
graph TB
    subgraph external["External services"]
        eurlex["EUR-Lex<br/>(PDFs)"]
        anthropic["Anthropic API"]
        hf["HuggingFace Hub"]
    end

    subgraph regulaitor["RegulAItor process"]
        direction TB

        subgraph surfaces["Surfaces (entry points)"]
            ui["Streamlit UI<br/>(H6)<br/><i>ui_streamlit/</i>"]
            api["FastAPI HTTP<br/>(H7)<br/><i>api/</i>"]
            cli["CLI scripts<br/><i>scripts/</i>"]
            mcp["MCP server<br/>(H3)<br/><i>mcp_server/</i>"]
        end

        subgraph orchestration["Orchestration"]
            chat_graph["Chat graph<br/>(LangGraph)<br/><i>orchestration/graph.py</i>"]
            doc_graph["Document pipeline<br/><i>orchestration/document_graph.py</i>"]
        end

        subgraph agents["Agents"]
            retriever["RetrieverAgent<br/><i>agents/retriever.py</i>"]
            analyst["AnalystAgent<br/>(tool-use Sonnet)<br/><i>agents/analyst.py</i>"]
            auditor["AuditorAgent<br/>(Lenient-strict)<br/><i>agents/auditor.py</i>"]
        end

        subgraph defense["Defense in depth"]
            sanitizer["Sanitizer<br/>(12 categories)<br/><i>document/sanitizer.py</i>"]
            injection["Injection regex<br/>(25+ patterns)<br/><i>security/injection.py</i>"]
            validator["Citation validator<br/>(3 checks)<br/><i>citation/validator.py</i>"]
        end

        subgraph data["Data layer"]
            corpus[("Corpus<br/>JSON snapshots<br/><i>corpus/processed/</i>")]
            lance[("LanceDB<br/>BGE-M3 dense<br/><i>corpus/indexes/</i>")]
            evals_cache[("Eval judge cache<br/><i>evals/cache/</i>")]
        end

        subgraph models["Models"]
            router["Router<br/>(thin wrapper)<br/><i>models/router.py</i>"]
            embeddings["BGE-M3 embeddings<br/><i>rag/embeddings.py</i>"]
            reranker["bge-reranker-v2-m3<br/><i>rag/reranker.py</i>"]
        end
    end

    ui --> chat_graph
    ui --> doc_graph
    api --> chat_graph
    api --> doc_graph
    cli --> doc_graph
    cli --> chat_graph
    mcp --> retriever
    mcp --> validator

    chat_graph --> retriever
    chat_graph --> analyst
    chat_graph --> auditor

    doc_graph --> sanitizer
    doc_graph --> injection
    doc_graph --> retriever
    doc_graph --> analyst
    doc_graph --> auditor

    retriever --> lance
    retriever --> embeddings
    retriever --> reranker

    analyst --> router
    auditor --> validator
    validator --> corpus

    router --> anthropic
    embeddings --> hf
    reranker --> hf
    sanitizer -.->|"strip + log<br/>(critical-block on JS,<br/>attachments, exfil URLs)"| chat_graph

    corpus -.->|"H1 ingest<br/>(manual)"| eurlex
```

**Container responsibilities**:

| Container | Inbound | Outbound | Owns |
|---|---|---|---|
| `ui_streamlit/` | user HTTP | chat_graph / doc_graph | rendering + token-level redaction |
| `api/` | user HTTP (Bearer auth, rate-limited) | chat_graph / doc_graph | DTO schemas + global error handlers |
| `mcp_server/` | MCP stdio | retriever + validator + corpus loader | tool contracts for editor-side use |
| `scripts/` | CLI | full pipelines (incl. evals, redteam) | reproducibility commands |
| `orchestration/graph.py` | surfaces | retriever → analyst → auditor | chat E2E state |
| `orchestration/document_graph.py` | surfaces (PDF/MD bytes) | extractor → sanitizer → injection → segmenter → (loop chat_graph per segment) → aggregator | document E2E state |
| `models/router.py` | agents | Anthropic SDK | model selection (Sonnet default, H12 will route Sonnet/GPT-4o/Llama/fallback) |

ADR references: [0004](adr/0004-rag-architecture.md) (RAG stack), [0005](adr/0005-mcp-server-architecture.md) (MCP), [0006](adr/0006-chat-e2e-architecture.md) (chat orchestration), [0007](adr/0007-document-pipeline-architecture.md) (document pipeline), [0008](adr/0008-streamlit-ui-architecture.md) (Streamlit), [0009](adr/0009-fastapi-architecture.md) (FastAPI), [0010](adr/0010-evaluation-harness.md) (eval), [0011](adr/0011-redteam-runner.md) (red team).

---

## L3 — Components: agent chat flow

How a chat query flows from UI/API entry to audited answer.

```mermaid
%%{init: {'theme':'neutral'}}%%
sequenceDiagram
    actor User
    participant Surface as ui_streamlit /<br/>api
    participant CG as chat_graph<br/>(LangGraph)
    participant R as RetrieverAgent
    participant Store as LanceDB
    participant A as AnalystAgent<br/>(Sonnet tool-use)
    participant Aud as AuditorAgent
    participant V as CitationValidator
    participant Corp as Corpus loader

    User->>Surface: query (text, corpus, language)
    Surface->>CG: ChatState{query, corpus, language}
    CG->>R: retrieve(query, corpus, top_k=10)
    R->>Store: vector search + filter by corpus/lang
    Store-->>R: 10 candidate chunks
    R->>R: rerank with bge-reranker-v2-m3 (top_k=5)
    R-->>CG: Context{chunks: 5}
    CG->>A: analyze(query, context)
    A->>A: format prompt + call router.complete (tool-use)
    Note over A: emit_answer tool_use<br/>{text, findings[], citations[]}
    A-->>CG: Answer
    CG->>Aud: audit(answer)
    loop per Citation
        Aud->>V: validate(citation)
        V->>Corp: get_article + get_paragraph + normalize-compare
        V-->>Aud: AuditResult (validated/blocked + reason)
    end
    Aud->>Aud: Lenient-strict aggregate (per Finding then per Answer)
    Aud-->>CG: AuditedAnswer{verdict, audit_results, reason}
    CG-->>Surface: ChatState{answer, audited_answer, errors}
    Surface-->>User: rendered answer (PASS / BLOCK / REQUIRES_HUMAN_REVIEW)
```

**Key invariants**:
- AnalystAgent never produces text directly to the user. Output passes through
  AuditorAgent.
- A single invalid Citation can demote the Answer verdict from `PASS` to
  `REQUIRES_HUMAN_REVIEW`; if all Findings have all citations invalid, verdict
  escalates to `BLOCK`.
- The H4 retry-once mechanism (commit `0d0409a`) catches cases where Sonnet
  omits the `findings` field in tool_use response; one retry with a
  `tool_result` error recovers ~80% of such cases.

---

## L3 — Components: document analysis flow

How a corporate policy PDF flows from upload to per-segment audit.

```mermaid
%%{init: {'theme':'neutral'}}%%
sequenceDiagram
    actor User
    participant Surface as ui_streamlit /<br/>api
    participant DG as document_graph
    participant Ex as Extractor<br/>(pypdfium2 + pdfplumber)
    participant Sa as Sanitizer
    participant Inj as Injection regex
    participant Seg as Segmenter
    participant CG as chat_graph<br/>(per segment)
    participant Agg as Aggregator

    User->>Surface: PDF/MD upload + corpus + lang
    Surface->>DG: file_bytes, mime, corpus, lang
    DG->>Ex: extract(file_bytes)
    Ex-->>DG: RawDocument{pages, metadata, annotations,<br/>has_javascript, attachments, uri_actions}
    DG->>Sa: sanitize(raw)
    alt critical hit (JS, attachments, non-allowlisted URL,<br/>injection in metadata)
        Sa--xDG: DocumentBlockedError(reason)
        DG-->>Surface: DocumentReport(verdict=REQUIRES_HUMAN_REVIEW)
    end
    Sa-->>DG: SanitizedDocument{clean_text, sanitizer_log}
    DG->>Inj: is_injection(clean_text, mode="document")
    Note over Inj: 25+ regex patterns<br/>(metadata + body + jailbreak)
    alt injection detected
        Inj-->>DG: (True, pattern_name)
        DG-->>Surface: DocumentReport(verdict=BLOCK,<br/>n_segments_blocked_by_injection)
    end
    DG->>Seg: segment(clean_text)
    Seg-->>DG: List[Segment]
    loop per Segment
        DG->>CG: ChatState{query=segment_text, corpus, lang}
        CG-->>DG: AuditedAnswer per segment
    end
    DG->>Agg: aggregate(segments + audited_answers)
    Agg-->>DG: DocumentReport{document_verdict, n_pass, n_block,<br/>n_review, latency_ms_total, cost_eur_total}
    DG-->>Surface: DocumentReport
    Surface-->>User: structured report (per-segment expand)
```

**Defense layer order**: sanitizer (1) → injection regex (2) → per-segment
chat_graph (3, includes validator + auditor as L3 components above) →
aggregator (4). A single critical sanitizer hit short-circuits the entire
pipeline; chat-graph per-segment hits demote only that segment.

---

## Data flow: corpus → retrieval

```mermaid
%%{init: {'theme':'neutral'}}%%
graph LR
    eurlex["EUR-Lex<br/>HTML / PDF"] -->|"scripts/ingest.py<br/>(H1, manual,<br/>idempotent)"| processed["corpus/processed/<br/>{norma}_{lang}.json<br/>(per-article JSON)"]
    processed -->|"scripts/rag_build.py<br/>(H2, idempotent)"| chunks["chunks<br/>(per-article or<br/>per-apartado)"]
    chunks -->|"BGE-M3<br/>(1024-dim dense)"| vectors[("LanceDB<br/>corpus/indexes/<br/>regulaitor.lance/")]
    processed -->|"corpus loader<br/>(eager warmup)"| loader["corpus_loader<br/>singleton cache<br/>(article → text)"]

    query["query text"] -->|"BGE-M3"| qvec["1024-dim<br/>query vector"]
    qvec -->|"top_k=10<br/>cosine search"| vectors
    vectors -->|"chunks"| rerank["bge-reranker-v2-m3<br/>top_k=5"]
    rerank -->|"Context"| analyst["AnalystAgent"]

    validator["CitationValidator"] -->|"article + apartado<br/>lookup"| loader
```

ADR references: [0003](adr/0003-corpus-pipeline.md) (PDF pivot from HTML),
[0004](adr/0004-rag-architecture.md) (BGE-M3 + LanceDB + reranker choice).

---

## Tech stack

Per `CLAUDE.md` §10. MVP-active components in **bold**.

| Layer | Tech | Status |
|---|---|---|
| Language / package mgr | **Python 3.11 · uv** | active |
| Schemas | **Pydantic v2 (frozen + extra="forbid")** | active |
| Surfaces | **Streamlit · FastAPI · MCP** | active (UI H6, API H7, MCP H3) |
| Orchestration | **LangGraph** | active |
| Vector store | **LanceDB local** | active |
| Embeddings | **BGE-M3 (multilingual, 1024-dim)** | active |
| Reranker | **bge-reranker-v2-m3** | active |
| LLM (production) | **Claude Sonnet 4.6** (via `models/router.py`) | active |
| LLM (judge) | **Claude Haiku 4.5** | active (H8 evals) |
| Evaluation | **Ragas + custom Python harness** | active (H8) |
| Red team | **redteam.runner standalone** | active (H9) |
| CI/CD | **GitHub Actions** (5 jobs) | active |
| Document extraction | **pypdfium2 + pdfplumber + pikepdf** | active |
| Document generation (fixtures) | **ReportLab** | active (H5, H9) |
| Lint / format / types | **ruff · black · mypy** | active |
| Security static | **bandit · pip-audit · gitleaks** | active |
| Observability | LangFuse | **deferred to H11** |
| Multi-LLM router | GPT-4o · Llama-3.1-70B Groq | **deferred to H12** |
| Council of Judges | 3-judge voting | **deferred to H13** |
| NIS2 + DORA corpus | parsers + manifests | **deferred to H14** |
| Auditor calibration | A/B + threshold tuning | **deferred to H15** |
| Public deploy | Hugging Face Spaces (Docker) | **deferred to H16** |
| LoRA severity classifier | fine-tune | **optional HX1** |

---

## Repository layout (MVP)

```
regulaitor/
├── src/regulaitor/           # production code (~13k LOC)
│   ├── agents/               # Retriever + Analyst + Auditor + prompts versionados
│   ├── api/                  # FastAPI surface (H7)
│   ├── citation/             # schemas + validator
│   ├── corpus/               # fetch + parse + loader
│   ├── document/             # extractor + sanitizer + segmenter (H5)
│   ├── mcp_server/           # 5 tools (H3)
│   ├── models/               # router + config
│   ├── observability/        # logging (LangFuse deferred H11)
│   ├── orchestration/        # LangGraph chat + document graphs
│   ├── rag/                  # chunking + embeddings + reranker + store
│   ├── security/             # allowlist + injection regex + rate_limit
│   └── ui_streamlit/         # MVP UI (H6)
├── corpus/                   # raw + processed (Git-LFS) + indexes (gitignored)
├── evals/                    # H8 harness + gold set + judge prompt + cache (gitignored)
├── redteam/                  # H9 attacks + runner + reports + PDFs
├── tests/                    # unit + integration + contract (538+ tests)
├── docs/                     # this folder
│   ├── adr/                  # 0001-0011
│   ├── architecture.md       # this file
│   ├── technical_decisions_log.md  # TFM defense memoria backbone
│   ├── security_report.md    # H9 deliverable
│   └── evidence_matrix.md    # H10 deliverable (TFM modules M1-M5)
└── .claude/                  # operational skills (rag-ingest, prompt-versioning,
                              # document-analysis, evals-runner, redteam-runner,
                              # secure-coding-checklist, citation-validator)
```

---

## References

- **Charter + roadmap**: `CLAUDE.md` (single source of truth for project scope, agents, stack, milestones, gates §16.2, metrics §17, security §18).
- **TFM defense memoria backbone**: `docs/technical_decisions_log.md` (every approved technical decision since H0).
- **ADRs**: `docs/adr/0001-0011` (architectural records, one per non-trivial design choice).
- **Specs + plans**: `docs/superpowers/specs/`, `docs/superpowers/plans/` (one pair per non-trivial milestone).
- **Security**: `docs/security_report.md` (defense-in-depth + red team results).
- **Evidence matrix**: `docs/evidence_matrix.md` (Máster modules M1-M5 → artifacts).
