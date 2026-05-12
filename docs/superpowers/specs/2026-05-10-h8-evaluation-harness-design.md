# H8 — Gold set + harness de evaluación + métricas + informe — Design

**Status:** approved (brainstorming closed 2026-05-10)
**Milestone:** H8
**Predecessor:** H7 (FastAPI mínima, tag `v0.0.8-h7`, squash `5b1f664`) + chore CI cleanup `e32a6a2`
**Successor:** H9 (red team)
**ADR:** 0010 (to be created during implementation)

---

## 1. Goal

Cerrar H8 entregando: (1) gold set estratificado de 30 casos chat + 10 documentos siguiendo el contrato CLAUDE.md §19, (2) harness Python que llama directo al backend H4/H5 sin tocarlo, computa métricas Ragas estándar (faithfulness, answer_relevancy, context_precision/recall) + custom layer (citation_precision/recall, verdict_match, severity_match, latencia, coste), y (3) primer `evals/reports/latest.md` reproducible con métricas reales — no `[medicion pendiente]`.

**Narrativa ancla** (CLAUDE.md §10.6 + §17): H8 cierra el lazo de "evaluación reproducible" del MVP. Es el hito donde las métricas objetivo del proyecto se vuelven medidas concretas que defienden o desafían el gate MVP→avanzado (CLAUDE.md §16.2 puntos 3 y 5: report con métricas reales + citation precision ≥0.85 sobre gold set).

## 2. Context

### 2.1 Estado heredado de H7

- **Backend H1-H5 + API H7 estables.** `run(query, corpus, language, case_id) -> ChatState` y `run_document(file_bytes, mime_type, language, corpus, case_id) -> DocumentReport`. H8 NO los modifica.
- **Esquemas estables** (Pydantic v2): `ChatState`, `Citation`, `Finding`, `Answer`, `AuditedAnswer`, `AuditResult`, `AuditVerdict`, `DocumentReport`, `SegmentResult`, `SanitizerEvent`. Inputs y outputs del harness se serializan via estos schemas existentes.
- **Anthropic API key activa** ($10 cargados al cierre H7-cleanup). Suficiente para 1 run completa (~$7) + margen ~30% para iteración.
- **Skill `prompt-versioning` activa** (H4+). Judge prompt vive en `src/regulaitor/agents/prompts/judge/faithfulness.v1.0.md` siguiendo el patrón de H4 Analyst/Auditor.
- **Skill `evals-runner` definida en CLAUDE.md §12.3 #5 pero NO activa** hasta cierre H8.
- **CI verde post-cleanup** (squash `e32a6a2`): Lint + Test + Document E2E + Security todos passing. Bandit con `# nosec` rationale, pip-audit clean, paths-filter desbloqueado.
- **481 tests fast pass, 92.99% coverage**. H8 añade tests del harness (sin LLM) que mantienen el gate.

### 2.2 H8 deliverables (per CLAUDE.md §16.1 + §11)

1. `evals/gold_set.jsonl` — 30 chat cases, 1 línea por caso, schema `GoldCaseChat`.
2. `evals/document_cases/` — 10 PDFs ReportLab-generated + 10 manifests `.expected.json` con schema `GoldCaseDoc`.
3. `evals/harness.py` — entry point + run loop + cache integration.
4. `evals/metrics.py` — Ragas adapter (faithfulness, answer_relevancy, context_precision/recall) + custom layer (citation_precision/recall, verdict_match, severity_match, latency_p95, cost).
5. `evals/judge.py` — Haiku 4.5 wrapper con prompt versionado.
6. `evals/report.py` — markdown generator (aggregate + per-case appendix).
7. `evals/schemas.py` — Pydantic v2 (GoldCaseChat, GoldCaseDoc, EvalResult, AggregateMetrics, ChatCaseResult, DocCaseResult).
8. `evals/cache/` — gitignored hash-keyed LLM response cache.
9. `scripts/evaluate.py` — CLI wrapper (argparse → harness.main).
10. `scripts/regenerate_document_fixtures.py` extendido para los 10 doc cases.
11. `src/regulaitor/agents/prompts/judge/faithfulness.v1.0.md` — judge prompt versionado.
12. Tests unit en `tests/unit/test_evals_*.py` (metrics, schemas, report, cache).
13. Make targets `eval`, `eval-subset`, `eval-from-cache`.
14. Primera generación de `evals/reports/latest.md` con métricas reales (consume ~$7 Anthropic credit).
15. ADR 0010 + decisions log §H8 + CLAUDE.md §27 + README sección Evaluation.

## 3. Architecture overview

### 3.1 Estructura de archivos

```
evals/
├── __init__.py
├── gold_set.jsonl                       # 30 chat cases, JSONL
├── document_cases/
│   ├── case_001_<topic>.pdf
│   ├── case_001_<topic>.expected.json   # GoldCaseDoc serialized
│   ├── ... (10 docs)
├── cache/                               # gitignored
│   └── {sha256_hash}.json
├── harness.py                           # entry point + run loop
├── metrics.py                           # Ragas adapter + custom metrics
├── report.py                            # markdown generator
├── schemas.py                           # Pydantic v2
├── judge.py                             # Haiku wrapper + prompt loader
└── reports/
    ├── latest.md                        # entregable; committed
    └── archive/                         # opcional, runs anteriores

src/regulaitor/agents/prompts/judge/
└── faithfulness.v1.0.md                 # judge system prompt + criteria template

scripts/
├── evaluate.py                          # CLI wrapper
└── regenerate_document_fixtures.py     # extended for H8 cases (existing for H5 fixtures)

tests/unit/
├── test_evals_metrics.py
├── test_evals_schemas.py
├── test_evals_report.py
└── test_evals_cache.py

docs/adr/0010-evaluation-harness.md
```

### 3.2 Diagrama de flujo

```
make eval [--subset N] [--cache-only]
  └─> scripts.evaluate.main(args)
       └─> harness.run_gold_set(gold_path, subset, cache_only)
            ├─ load gold_set.jsonl + document_cases/*.expected.json
            ├─ for each chat_case:
            │    ├─ compute SHA256 cache key (model, prompt, temp)
            │    ├─ if cache hit: load ChatState from cache
            │    ├─ if cache miss + cache_only=True: ABORT
            │    ├─ else: invoke graph.run(...) → ChatState; persist cache
            │    ├─ compute_chat_metrics(case, state) → ChatCaseResult
            │    │   ├─ Ragas: faithfulness, answer_relevancy, context_precision/recall
            │    │   ├─ Custom: citation_precision, citation_recall, verdict_match, severity_match
            │    │   └─ judge calls (Haiku 4.5, temp=0) on faithfulness criteria
            │    └─ append to per_case_results
            ├─ for each doc_case:
            │    ├─ load PDF bytes
            │    ├─ same cache flow
            │    ├─ invoke document_graph.run_document(...) → DocumentReport
            │    └─ compute_doc_metrics(case, report) → DocCaseResult
            ├─ aggregate_metrics(all_results) → AggregateMetrics
            ├─ render_report(aggregate, all_results) → markdown
            └─ write to evals/reports/latest.md
```

### 3.3 Dependencias entre módulos

- `harness.py` → `schemas.py` (todos los modelos), `metrics.py` (compute_*), `judge.py` (LLM judge), `report.py` (render), backend `orchestration.graph.run` y `orchestration.document_graph.run_document`.
- `metrics.py` → `schemas.py`, `ragas` (deps externa), `judge.py` (criteria-based scoring).
- `judge.py` → `anthropic` SDK, `agents.prompts.judge` (prompt loading, versioning helpers per H4 patterns).
- `report.py` → `schemas.py`. NO llama a LLM.
- `schemas.py` → solo Pydantic + `regulaitor.citation.schemas` (re-uses `AuditVerdict`, `Citation` types).
- `cache/`: implementado como funciones puras en `harness.py` (no módulo separado; ~30 líneas).

### 3.4 No se toca

- `src/regulaitor/orchestration/` — backend H4/H5 immutable.
- `src/regulaitor/api/` — H7 surface no requerida (harness llama directo a Python functions).
- `src/regulaitor/agents/prompts/{retriever,analyst,auditor}/` — sólo se añade `judge/`.

## 4. Components

### 4.1 `evals/schemas.py`

```python
"""Pydantic v2 schemas for the H8 evaluation harness."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from regulaitor.citation.schemas import AuditVerdict


class GoldCaseChat(BaseModel):
    """One chat case in evals/gold_set.jsonl."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(min_length=1)
    tipo: Literal["chat"]
    entrada: str = Field(min_length=1, max_length=2000)
    corpus_esperado: Literal["ai_act", "gdpr"]
    articulos_esperados: list[str] = Field(min_length=1)
    severidad_esperada: Literal["info", "low", "medium", "high"] | None
    criterios_evaluacion: list[str] = Field(min_length=1)
    salida_esperada: str | None
    requiere_revision_humana: bool
    expected_verdict: Literal["pass", "block", "requires_human_review"]


class GoldCaseDoc(BaseModel):
    """One document case (manifest paired with a PDF)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(min_length=1)
    tipo: Literal["document"]
    pdf_path: str  # relative to evals/document_cases/
    corpus_esperado: list[Literal["ai_act", "gdpr"]] = Field(min_length=1)
    expected_findings_articulos: list[str]
    expected_document_verdict: Literal["pass", "block", "requires_human_review"]
    expected_n_segments: int = Field(ge=1)
    n_segments_tolerance: int = Field(default=2, ge=0)
    criterios_evaluacion: list[str] = Field(min_length=1)


class CitationMetrics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    expected: list[str]                # ["6.1", "9.2"]
    emitted: list[str]                  # ["6.1", "10.3"]
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)


class CriteriaScore(BaseModel):
    """LLM-judge result for one criterion."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    criterion: str
    passed: bool
    reason: str | None


class ChatCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str
    expected_verdict: Literal["pass", "block", "requires_human_review"]
    actual_verdict: Literal["pass", "block", "requires_human_review", "blocked_injection"]
    verdict_match: bool
    expected_severity: Literal["info", "low", "medium", "high"] | None
    actual_severity: Literal["info", "low", "medium", "high"] | None
    severity_match: bool | None
    citations: CitationMetrics
    faithfulness: float = Field(ge=0.0, le=1.0)
    answer_relevancy: float = Field(ge=0.0, le=1.0)
    context_precision: float = Field(ge=0.0, le=1.0)
    context_recall: float = Field(ge=0.0, le=1.0)
    criteria_scores: list[CriteriaScore]
    latency_ms: int = Field(ge=0)
    cost_eur: float = Field(ge=0)
    cache_hit: bool


class DocCaseResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str
    expected_document_verdict: Literal["pass", "block", "requires_human_review"]
    actual_document_verdict: Literal["pass", "block", "requires_human_review"]
    verdict_match: bool
    expected_n_segments: int
    actual_n_segments: int
    n_segments_within_tolerance: bool
    findings_citations: CitationMetrics  # over union of all segment citations
    faithfulness: float = Field(ge=0.0, le=1.0)
    criteria_scores: list[CriteriaScore]
    latency_ms_total: int = Field(ge=0)
    cost_eur_total: float = Field(ge=0)
    cache_hit: bool


class AggregateMetrics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    n_chat_cases: int
    n_doc_cases: int
    faithfulness_mean: float = Field(ge=0.0, le=1.0)
    answer_relevancy_mean: float = Field(ge=0.0, le=1.0)         # chat only
    context_precision_mean: float = Field(ge=0.0, le=1.0)         # chat only
    context_recall_mean: float = Field(ge=0.0, le=1.0)             # chat only
    citation_precision_mean: float = Field(ge=0.0, le=1.0)
    citation_recall_mean: float = Field(ge=0.0, le=1.0)
    verdict_match_rate: float = Field(ge=0.0, le=1.0)
    severity_match_rate: float = Field(ge=0.0, le=1.0)             # chat only
    latency_p95_ms: int = Field(ge=0)
    cost_per_chat_eur: float = Field(ge=0)
    cost_per_doc_eur: float = Field(ge=0)
    cost_total_eur: float = Field(ge=0)
    cache_hit_rate: float = Field(ge=0.0, le=1.0)


class EvalRunMeta(BaseModel):
    """Header metadata for the report."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    run_date: str                         # ISO 8601
    commit_sha: str                       # first 7 chars
    production_model: str                 # "claude-sonnet-4-6"
    judge_model: str                      # "claude-haiku-4-5"
    temperature: float                    # 0.0
    subset: int | None                    # None = full run
    cache_only: bool
```

### 4.2 `evals/judge.py`

```python
"""Haiku 4.5 LLM-as-judge wrapper."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import anthropic

from evals.schemas import CriteriaScore

_JUDGE_MODEL = "claude-haiku-4-5-20251001"
_PROMPT_PATH = Path(__file__).resolve().parents[1] / "src" / "regulaitor" / "agents" / "prompts" / "judge" / "faithfulness.v1.0.md"


def _load_judge_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def score_criteria(
    *,
    criteria: list[str],
    query: str,
    actual_answer: str,
    expected_answer: str | None,
    cited_articles: list[str],
    expected_articles: list[str],
    client: anthropic.Anthropic,
    cache_call: callable,
) -> list[CriteriaScore]:
    """Ask Haiku 4.5 to judge each criterion. Returns one CriteriaScore per criterion.

    `cache_call` is a closure injected by the harness that wraps the API call
    with the SHA256 cache layer (skips API on hit, persists on miss).
    """
    system_prompt = _load_judge_prompt()
    user_message = json.dumps(
        {
            "query": query,
            "actual_answer": actual_answer,
            "expected_answer": expected_answer,
            "cited_articles": cited_articles,
            "expected_articles": expected_articles,
            "criteria": criteria,
        },
        ensure_ascii=False,
        indent=2,
    )
    response_text = cache_call(
        model=_JUDGE_MODEL,
        system=system_prompt,
        user=user_message,
        temperature=0.0,
        max_tokens=2000,
        client=client,
    )
    # Response shape (enforced by judge prompt v1.0):
    # {"scores": [{"criterion": "...", "passed": true/false, "reason": "..."}]}
    parsed = json.loads(response_text)
    return [CriteriaScore(**s) for s in parsed["scores"]]
```

### 4.3 `src/regulaitor/agents/prompts/judge/faithfulness.v1.0.md`

```markdown
---
agent: judge
role: faithfulness_evaluator
version: 1.0
language: es
input_format: json
output_format: json
created: 2026-05-10
---

Eres un evaluador imparcial de respuestas jurídicas generadas por un sistema RAG sobre normativa europea (AI Act + RGPD). Tu trabajo es decidir, criterio a criterio, si la respuesta del sistema cumple cada criterio de evaluación. NO eres un experto jurídico; eres un evaluador de cumplimiento estricto de criterios formulados por humanos.

Recibes un objeto JSON con:
- `query`: pregunta del usuario.
- `actual_answer`: respuesta generada por el sistema.
- `expected_answer`: respuesta de referencia (puede ser null si solo hay criterios).
- `cited_articles`: artículos citados por el sistema.
- `expected_articles`: artículos que el caso espera que se citen.
- `criteria`: lista de criterios evaluables (strings en español).

Para cada criterio, devuelve `passed: true` solo si la respuesta lo cumple sin ambigüedad. En caso de duda, `passed: false`.

Devuelve EXCLUSIVAMENTE un objeto JSON con esta forma exacta:
```json
{
  "scores": [
    {"criterion": "<texto literal del criterio>", "passed": true, "reason": "<explicación breve>"},
    ...
  ]
}
```

No incluyas markdown, no incluyas comentarios, no añadas campos extra. Si el output no es JSON válido y parseable, el harness lo trata como fallo del judge y registra el caso como inconcluso.
```

### 4.4 `evals/metrics.py`

```python
"""Ragas adapter + custom metrics."""

from __future__ import annotations

import statistics
from typing import Any

from regulaitor.citation.schemas import AuditVerdict
from regulaitor.orchestration.state import ChatState
from regulaitor.citation.schemas import DocumentReport

from evals.schemas import (
    AggregateMetrics,
    ChatCaseResult,
    CitationMetrics,
    DocCaseResult,
    GoldCaseChat,
    GoldCaseDoc,
)


def compute_citation_metrics(emitted: list[str], expected: list[str]) -> CitationMetrics:
    """Article-level set comparison. Articles compared as strings ("6.1" vs "6.1")."""
    emitted_set = set(emitted)
    expected_set = set(expected)
    if not emitted_set:
        precision = 0.0
    else:
        precision = len(emitted_set & expected_set) / len(emitted_set)
    if not expected_set:
        recall = 0.0
    else:
        recall = len(emitted_set & expected_set) / len(expected_set)
    return CitationMetrics(
        emitted=sorted(emitted_set),
        expected=sorted(expected_set),
        precision=precision,
        recall=recall,
    )


def compute_chat_metrics(
    case: GoldCaseChat,
    state: ChatState,
    *,
    judge_client: Any,
    cache_call: Any,
    latency_ms: int,
    cost_eur: float,
    cache_hit: bool,
) -> ChatCaseResult:
    """Compute all chat metrics for one case. Calls Ragas + custom + judge."""
    # ... Ragas integration: build a Ragas Dataset row, call evaluate(...) on it.
    # ... custom: extract citations from state.audited_answer.audit_results,
    #             compute citation_precision/recall, verdict_match, severity_match.
    # ... judge: score criterios_evaluacion via judge.score_criteria(...).
    ...


def compute_doc_metrics(
    case: GoldCaseDoc,
    report: DocumentReport,
    *,
    judge_client: Any,
    cache_call: Any,
    latency_ms_total: int,
    cost_eur_total: float,
    cache_hit: bool,
) -> DocCaseResult:
    """Compute all doc metrics for one case."""
    ...


def aggregate(
    chat_results: list[ChatCaseResult],
    doc_results: list[DocCaseResult],
) -> AggregateMetrics:
    """Aggregate per-case metrics into headline numbers for the report."""
    # latency_p95: percentile 95 over all per-case latencies.
    # cost_per_chat_eur: mean over chat_results.
    # cost_per_doc_eur: mean over doc_results.
    # cost_total_eur: sum.
    # all rate metrics: mean.
    ...
```

### 4.5 `evals/harness.py`

```python
"""H8 — evaluation harness entry point."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import anthropic

from regulaitor.orchestration.graph import run as run_chat
from regulaitor.orchestration.document_graph import run_document

from evals.judge import score_criteria
from evals.metrics import aggregate, compute_chat_metrics, compute_doc_metrics
from evals.report import render_report
from evals.schemas import (
    AggregateMetrics,
    ChatCaseResult,
    DocCaseResult,
    EvalRunMeta,
    GoldCaseChat,
    GoldCaseDoc,
)


_CACHE_DIR = Path("evals/cache")


def _cache_key(*, model: str, prompt: str, temperature: float) -> str:
    payload = f"{model}|{prompt}|{temperature}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{key}.json"


def cache_call(
    *,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    client: anthropic.Anthropic,
    cache_only: bool = False,
) -> str:
    """Cached LLM invocation. Returns response text."""
    key = _cache_key(model=model, prompt=f"{system}\n{user}", temperature=temperature)
    path = _cache_path(key)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["response"]
    if cache_only:
        raise RuntimeError(f"Cache miss for key {key} in --cache-only mode")
    response = client.messages.create(
        model=model,
        system=system,
        messages=[{"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"request": {"model": model, "system": system, "user": user, "temperature": temperature}, "response": text}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return text


def load_gold_set(path: Path) -> tuple[list[GoldCaseChat], list[GoldCaseDoc]]:
    chat_cases: list[GoldCaseChat] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chat_cases.append(GoldCaseChat.model_validate_json(line))

    doc_cases: list[GoldCaseDoc] = []
    doc_dir = Path("evals/document_cases")
    for manifest in sorted(doc_dir.glob("*.expected.json")):
        doc_cases.append(GoldCaseDoc.model_validate_json(manifest.read_text(encoding="utf-8")))

    return chat_cases, doc_cases


def run_chat_case(case: GoldCaseChat, *, cache_only: bool) -> tuple[Any, int, float, bool]:
    """Returns (ChatState, latency_ms, cost_eur, cache_hit). Uses cache via _cache_key
    over (model, prompt, temperature) — but H4's run() makes multiple LLM calls
    internally. The harness caches at the run() boundary: hashes (case.entrada,
    case.corpus_esperado, case.language="es", H4 prompt versions) and stores the
    full ChatState as JSON. Live mode persists; cache-only mode requires hit."""
    ...


def run_doc_case(case: GoldCaseDoc, *, cache_only: bool) -> tuple[Any, int, float, bool]:
    """Returns (DocumentReport, latency_ms_total, cost_eur_total, cache_hit)."""
    ...


def main(*, gold_set_path: Path, subset: int | None, cache_only: bool) -> None:
    chat_cases, doc_cases = load_gold_set(gold_set_path)
    if subset is not None:
        chat_cases = chat_cases[: max(0, subset)]
        doc_cases = doc_cases[: max(0, subset // 3)]  # 30:10 chat:doc ratio in gold set

    client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var
    chat_results: list[ChatCaseResult] = []
    doc_results: list[DocCaseResult] = []

    for case in chat_cases:
        state, latency_ms, cost_eur, cache_hit = run_chat_case(case, cache_only=cache_only)
        result = compute_chat_metrics(
            case, state,
            judge_client=client,
            cache_call=lambda **kw: cache_call(**kw, cache_only=cache_only),
            latency_ms=latency_ms,
            cost_eur=cost_eur,
            cache_hit=cache_hit,
        )
        chat_results.append(result)

    for case in doc_cases:
        report, latency_ms, cost_eur, cache_hit = run_doc_case(case, cache_only=cache_only)
        result = compute_doc_metrics(
            case, report,
            judge_client=client,
            cache_call=lambda **kw: cache_call(**kw, cache_only=cache_only),
            latency_ms_total=latency_ms,
            cost_eur_total=cost_eur,
            cache_hit=cache_hit,
        )
        doc_results.append(result)

    agg = aggregate(chat_results, doc_results)
    meta = EvalRunMeta(
        run_date=datetime.now(UTC).isoformat(),
        commit_sha=_get_git_sha()[:7],  # helper that reads HEAD via subprocess
        production_model="claude-sonnet-4-6",
        judge_model="claude-haiku-4-5-20251001",
        temperature=0.0,
        subset=subset,
        cache_only=cache_only,
    )
    markdown = render_report(meta, agg, chat_results, doc_results)
    Path("evals/reports/latest.md").write_text(markdown, encoding="utf-8")
```

### 4.6 `evals/report.py`

Genera markdown con header (commit, models, settings, total cost), tabla aggregate (métrica | valor | threshold | pass), per-case appendix (40 secciones, una por caso), reproducibility block (instrucciones literal `make eval-from-cache`), caveat block (sintetizado N=40, no benchmark público).

```python
def render_report(
    meta: EvalRunMeta,
    agg: AggregateMetrics,
    chat_results: list[ChatCaseResult],
    doc_results: list[DocCaseResult],
) -> str:
    """Returns a complete markdown document for evals/reports/latest.md."""
    ...
```

### 4.7 `scripts/evaluate.py`

```python
"""CLI wrapper for the H8 evaluation harness."""

from __future__ import annotations

import argparse
from pathlib import Path

from evals.harness import main


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run RegulAItor evaluation harness")
    p.add_argument("--gold-set", type=Path, default=Path("evals/gold_set.jsonl"))
    p.add_argument("--subset", type=int, default=None, help="Run only first N cases (debugging)")
    p.add_argument("--cache-only", action="store_true", help="Fail on cache miss; no API calls")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(gold_set_path=args.gold_set, subset=args.subset, cache_only=args.cache_only)
```

## 5. Métricas — definitions y thresholds

### 5.1 Standard RAG (Ragas, Language="es")

| Métrica | Threshold (CLAUDE.md §17) | Aplica a |
|---|---|---|
| `faithfulness` | ≥ 0.85 | chat + doc (segmento agregado) |
| `answer_relevancy` | ≥ 0.85 | chat |
| `context_precision` | ≥ 0.80 | chat |
| `context_recall` | (no gate, info) | chat |

Nota: Ragas espera tuplas `(question, contexts, answer, ground_truth)`. Construcción:
- `question` = `case.entrada`.
- `contexts` = lista de `chunk.text` desde `state.context.chunks`.
- `answer` = `state.audited_answer.answer.text`.
- `ground_truth` = `case.salida_esperada` si presente, else `case.criterios_evaluacion[0]` como proxy.

### 5.2 Custom — citation matching

`articulos_esperados` y `expected_findings_articulos` se almacenan como strings ("6.1", "9.2"). Las citas emitidas se extraen como `f"{c.articulo}.{c.apartado or ''}"` y se normalizan trim.

| Métrica | Cómputo | Threshold |
|---|---|---|
| `citation_precision` | `|emitted ∩ expected| / |emitted|` | ≥ 0.90 |
| `citation_recall` | `|emitted ∩ expected| / |expected|` | ≥ 0.80 |

Edge cases:
- `|emitted| = 0`: precision = 0.0 (sistema no citó nada cuando se esperaba).
- `|expected| = 0`: recall = 0.0 (no aplica; no debería haber casos así en gold set).

### 5.3 Custom — verdict / severity match

| Métrica | Cómputo | Threshold |
|---|---|---|
| `verdict_match_rate` | mean(actual == expected) sobre chat + doc | ≥ 0.85 |
| `severity_match_rate` | mean(actual == expected) sobre chat con severidad_esperada ≠ None | ≥ 0.80 |

`actual_severity` = severidad del primer Finding del answer (la severidad "headline" del case). Si no hay findings, `actual_severity = None` y el match cuenta como `False` cuando expected ≠ None.

### 5.4 Custom — latencia + coste

| Métrica | Cómputo | Threshold |
|---|---|---|
| `latency_p95_ms` | percentil 95 sobre todas las llamadas (chat + doc) | ≤ 12000 |
| `cost_per_chat_eur` | sum(chat costs) / n_chat_cases | ≤ 0.05 |
| `cost_per_doc_eur` | sum(doc costs) / n_doc_cases (no normalizado por páginas en MVP) | ≤ 0.50 |
| `cost_total_eur` | sum total | informativo |

Coste en € se calcula via tasas conocidas:
- Sonnet 4.6: $3 / 1M input, $15 / 1M output. EUR/USD ≈ 0.92 → €2.76 / €13.80.
- Haiku 4.5: $1 / 1M input, $5 / 1M output → €0.92 / €4.60.

Tokens via `response.usage` del Anthropic SDK.

### 5.5 No incluido

- Tasa de bloqueo del Auditor en adversarial set (CLAUDE.md §17.6) — H9 redteam, no H8.
- Cobertura de tests / sin secrets / sin findings altos (CLAUDE.md §17.10-13) — gates CI, no eval gates.

## 6. Cache

### 6.1 Hash key

`SHA256(model_id || "\n" || prompt_text || "\n" || str(temperature))`. Hex digest.

`prompt_text` para chat producción = system_prompt + "\n---\n" + canonical_user_message (donde canonical incluye tools, query, case_id pero excluye timestamps). Para judge = system_prompt + "\n---\n" + json.dumps(payload, ensure_ascii=False).

### 6.2 Cache file shape

```json
{
  "request": {
    "model": "claude-sonnet-4-6",
    "system": "...",
    "user": "...",
    "temperature": 0.0
  },
  "response": "<text>",
  "timestamp": "2026-05-10T18:00:00Z",
  "tokens_in": 3210,
  "tokens_out": 580,
  "cost_eur": 0.018
}
```

### 6.3 Modes

- **Live (default)**: cache miss → call API → persist response.
- **`--cache-only`**: cache miss → `RuntimeError`. Útil para regenerar el report tras editing un criterio sin gastar.

### 6.4 Caveats

- El cache es por-llamada, no por-caso. Si H4 hace N llamadas internas (Analyst tool use loop), cada una se cachea independientemente.
- Cache invalidation: cambiar el prompt versioned (faithfulness.v1.0.md → v1.1.md) cambia el hash → cache miss automático → re-generación.
- `evals/cache/` es gitignored. Operador re-popula con `make eval` cuando cambia el prompt.

## 7. Determinismo

- `temperature=0` siempre (producción + judge).
- Anthropic SDK no expone `seed` (verificado).
- Cached responses son single source of truth para `--cache-only`.
- Tests unitarios del harness con respuestas canned (no LLM real) + smoke test E2E con `--cache-only` sobre cache pre-poblada.

## 8. Authoring flow

### Phase 1 — Esqueleto humano (3-4h tuyas)

Tú entregas una hoja (markdown table o jsonl) con 40 filas:

```jsonl
{"topic":"AI Act art. 6 alto riesgo evaluación conformidad","corpus":"ai_act","articulos":["6.1","9.2"],"verdict":"pass","severidad":"medium"}
{"topic":"RGPD art. 7 consentimiento revocable","corpus":"gdpr","articulos":["7.3"],"verdict":"pass","severidad":"high"}
...
```

40 filas: 30 chat + 10 doc. Estratificación recomendada: 15 ai_act + 15 gdpr (chat); 4 ai_act + 4 gdpr + 2 mixed (doc); 24 verdict=pass + 9 verdict=requires_human_review + 7 verdict=block.

### Phase 2 — Subagente bg (1-2h)

Consume la hoja, accede al corpus indexado (LanceDB) para verificar que `articulos` existen, genera:
- `evals/gold_set.jsonl` — 30 entradas `GoldCaseChat` completas (query naturalizada, criterios_evaluacion drafted, salida_esperada esquemática).
- `evals/document_cases/case_NNN_<topic>.pdf` — 10 PDFs ReportLab con contenido drafteado (políticas IA / privacidad / contratos sintéticos).
- `evals/document_cases/case_NNN_<topic>.expected.json` — 10 manifests `GoldCaseDoc`.

Templates:
- query natural: "¿Qué obligaciones impone el {norma} art. {articulo} sobre {topic}?"
- criterios_evaluacion: ["Cita literalmente art. X.Y", "No afirma X sin evidencia"]
- salida_esperada esquemática: "Según art. X.Y del {norma}, {topic} requiere [...]" (180-300 palabras)

### Phase 3 — Tu review (1-2h)

PR review — `Edit` cambios o aceptar. Foco: criterios_evaluacion calibrados (no demasiado permisivos ni imposibles de cumplir), queries con texto natural (no calcado del artículo), salida_esperada enraizada.

## 9. Make targets

```makefile
eval: ## Run full evaluation (~$7 Anthropic; populates cache)
	uv run python -m scripts.evaluate

eval-subset: ## Run first 5 chat + 1 doc cases (~$1)
	uv run python -m scripts.evaluate --subset 5

eval-from-cache: ## Regenerate report from cache only (free; fails on miss)
	uv run python -m scripts.evaluate --cache-only
```

## 10. Tests

### 10.1 Unit (sin LLM real)

- `test_evals_schemas.py` — validación de GoldCaseChat / GoldCaseDoc / EvalResult (extra="forbid" rechaza fields, frozen=True bloquea mutación, Literal rechaza valores fuera de set).
- `test_evals_metrics.py` — `compute_citation_metrics([], [])` → precision/recall = 0; `compute_citation_metrics(["6.1"], ["6.1"])` → 1.0/1.0; partial overlap ratios; aggregate_metrics con canned per-case results.
- `test_evals_report.py` — `render_report(canned_meta, canned_agg, [], [])` produce markdown con header + tabla + caveats; pass/fail rendering correcto.
- `test_evals_cache.py` — `_cache_key` determinista, `cache_call` hit retorna cache, miss + `cache_only=True` levanta RuntimeError.

### 10.2 Smoke (con cache pre-poblada, sin LLM)

- Test que pre-popula `evals/cache/` con 2 entradas (1 chat + 1 doc), corre `harness.main(subset=2, cache_only=True)`, verifica que `evals/reports/latest.md` se genera sin LLM real. Marca `@pytest.mark.smoke`.

### 10.3 NO en CI

- NO se llaman a Anthropic API en CI.
- NO se ejecuta `make eval` en CI.
- Solo unit tests + smoke con cache.

## 11. Report `evals/reports/latest.md`

Estructura literal del entregable:

```markdown
# RegulAItor — Evaluation Report

**Run:** 2026-05-10T18:00:00Z | **Commit:** `abcd123` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0, subset=full, cache hits/misses: 38/2 | **Total cost:** 6.83 €

## Aggregate metrics

| Métrica | Valor | Threshold | Pass |
|---|---|---|---|
| faithfulness (mean) | 0.87 | ≥0.85 | ✅ |
| answer_relevancy (mean) | 0.91 | ≥0.85 | ✅ |
| context_precision (mean) | 0.78 | ≥0.80 | ❌ (-0.02) |
| context_recall (mean) | 0.82 | (info) | ➖ |
| citation_precision (mean) | 0.93 | ≥0.90 | ✅ |
| citation_recall (mean) | 0.79 | ≥0.80 | ❌ (-0.01) |
| verdict_match_rate | 0.90 | ≥0.85 | ✅ |
| severity_match_rate | 0.83 | ≥0.80 | ✅ |
| latency_p95_ms | 8420 | ≤12000 | ✅ |
| cost_per_chat_eur | 0.041 | ≤0.05 | ✅ |
| cost_per_doc_eur | 0.487 | ≤0.50 | ✅ |
| cache_hit_rate | 0.05 | (info) | ➖ |

## Per-case appendix

### chat-001 — AI Act art. 6 sistemas alto riesgo

- **Entrada**: "¿Qué requisitos impone el AI Act sobre sistemas de IA de alto riesgo?"
- **Expected**: verdict=pass, articulos=["6.1","9.2"], severidad=medium
- **Actual**: verdict=pass, citations=["6.1","9.2"], severidad=medium
- **citation_precision**: 1.0 ✅ | **citation_recall**: 1.0 ✅
- **Criteria**:
  - ✅ Cita art. 6.1 literal
  - ✅ Menciona evaluación de conformidad
  - ✅ No afirma obligaciones extra-AI Act

[... 39 secciones más]

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si cache poblada
make eval             # corre full; consume crédito Anthropic
```

## Caveats

Resultados sobre N=40 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
```

## 12. Dependencies (pyproject.toml updates)

**Runtime (added to `[project].dependencies`):**
- `ragas>=0.2,<1.0` — Ragas evaluation framework.
- `pandas>=2.0,<3.0` — Ragas internal dependency, may need explicit add.
- `datasets>=2.0,<5.0` — Ragas internal, used to build evaluation Dataset rows.

**Dev (no new):** ya tenemos pytest, hypothesis, schemathesis. Tests del harness no requieren extra.

**Risk:** ragas pulls langchain transitively. Si conflicta con nuestra langchain-core 1.3.3 fijo, ajustar pin. Verificar con `uv lock --upgrade-package ragas` antes de merging deps.

## 13. ADR + decisions log + skill

### 13.1 ADR 0010

`docs/adr/0010-evaluation-harness.md`. Captura:
- Por qué Ragas + custom (vs DeepEval, vs custom-only).
- Por qué Haiku 4.5 como judge (vs OpenAI, vs Groq, vs no-judge).
- Por qué cache hash-keyed obligatorio (reproducibilidad + budget).
- Por qué authoring hybrid (vs manual, vs LLM-full).
- Por qué report aggregate + per-case (vs aggregate-only, vs stratified).
- Caveats: judge mismo proveedor que producción (limitación documentada, defer a H12).

### 13.2 Decisions log §H8

Append entries Q1-Q6 cerradas en brainstorming + amendments durante implementación.

### 13.3 Skills

- **`evals-runner`** — activada al cierre H8. Procedimiento canónico de "cómo correr eval reproduciblemente, leer report, decidir si re-correr". Sigue patrón H4/H5 skills.

## 14. Files touched

**NEW (~25 archivos de código + ADR + docs):**
```
evals/__init__.py
evals/schemas.py
evals/harness.py
evals/metrics.py
evals/report.py
evals/judge.py
evals/gold_set.jsonl                                              # generado por subagente Phase 2
evals/document_cases/case_001_*.pdf  ... case_010_*.pdf          # 10 fixtures
evals/document_cases/case_001_*.expected.json ... case_010_*.expected.json
evals/cache/.gitkeep                                               # placeholder
evals/reports/.gitkeep
src/regulaitor/agents/prompts/judge/__init__.py                    # si no existe
src/regulaitor/agents/prompts/judge/faithfulness.v1.0.md
scripts/evaluate.py
tests/unit/test_evals_schemas.py
tests/unit/test_evals_metrics.py
tests/unit/test_evals_report.py
tests/unit/test_evals_cache.py
tests/integration/test_evals_smoke.py                              # con cache pre-poblada
docs/adr/0010-evaluation-harness.md
.claude/skills/evals-runner/SKILL.md                               # activación skill
```

**MODIFY:**
```
pyproject.toml                          # ragas + transitive
Makefile                                # 3 targets nuevos
README.md                               # sección Evaluation
CLAUDE.md                               # §27 mark H8 closed (post-merge)
docs/technical_decisions_log.md         # append §H8
.gitignore                              # evals/cache/* (gitkeep), evals/reports/archive/
scripts/regenerate_document_fixtures.py # extender para H8 doc cases (10 PDFs nuevos)
```

## 15. Anti-patterns to avoid

- **No tocar el backend H1-H5** (graph.py, document_graph.py, agents/, rag/). El harness los consume read-only.
- **No tocar `api/`** — H7 surface no es necesaria; harness llama Python directo.
- **No bypassear el cache** — cualquier dev/debug también va por `cache_call` para no quemar crédito.
- **No pin a `pytest-asyncio` adicional** — ya gestionado en H7.
- **No `-S` mode en bandit** que rompa cleanup H7.
- **No commitear `evals/cache/`** ni `evals/reports/archive/`.
- **No hardcodear modelo en código** — `_JUDGE_MODEL` y producción son constantes en un sitio (judge.py + harness.py respectivamente).
- **No exponer Anthropic API key en logs ni reports** — `_log_*` y `render_report` son auditables.
- **No correr evals en CI per-PR** — nunca, per Q4 decision. CI solo unit tests del harness.
- **No mezclar adversarial cases en gold set** — adversarial es H9 redteam separado per CLAUDE.md §18.
- **No usar `--no-verify` en commits.**
- **No skip de Ragas Language="es" config** — si Ragas evalúa en EN sobre contenido ES, las métricas saldrán ruidosas.
- **No incluir per-case detail con `salida_esperada` completa en report si excede 300 palabras** — truncate to first 200 chars con elipsis para respetar cohesión visual.

## 16. Gate de cierre H8

Pre-merge:

1. `make lint` verde (ruff + black + mypy).
2. `make test` verde — incluye tests unit `test_evals_*` + smoke con cache (sin LLM).
3. Coverage ≥80% global, ≥90% en `evals/metrics.py` y `evals/cache_call` (SSDLC: cache es trust boundary).
4. `make eval-subset` corre exitosamente con $1 de crédito (validación end-to-end del harness).
5. `make eval` corre full set y genera `evals/reports/latest.md` válido.
6. `evals/reports/latest.md` committed con métricas reales (no `[medicion pendiente]`).
7. `make eval-from-cache` regenera el mismo report sin gastar crédito (cache reproducibility).
8. ADR 0010 commited.
9. Decisions log §H8 actualizado.
10. README sección Evaluation commited.
11. CLAUDE.md §27 actualizado a H8 closed.
12. Skill `evals-runner` activada (SKILL.md committed).
13. Tag `v0.0.9-h8` publicado tras squash merge.
14. CI verde (los 4 jobs).

Métrica gate específica que H8 acompaña pero no bloquea per se (gate H10 lo verifica): citation precision ≥ 0.85 sobre el gold set (CLAUDE.md §16.2 punto 5). Si el primer report no llega, el harness está bien pero el sistema necesita iteración (NO es failure de H8 — es input para H15 calibración).

## 17. Out of scope (deferred — captured for H17 future-work doc)

- Adversarial set / tasa de bloqueo Auditor (H9 redteam).
- DeepEval pytest integration con `@assert_test` (H15 calibration).
- LangFuse trace integration (H11).
- A/B comparison multi-modelo en harness (H12 router multi-LLM).
- Stratified breakdown by corpus + verdict en report (H10/H17 polish).
- Migración del judge a otro proveedor (H12 cuando router multi-LLM exista).
- CI gating per-PR de evals (nunca, decision Q4).
- Runtime caching backend Redis/SQLite (filesystem JSON suficiente MVP).
- Per-language eval (gold set MVP es ES; EN llega con HX2 Next.js o si UI lo demanda).
- Cost-per-page normalization en `cost_per_doc_eur` (MVP usa promedio simple; H17 puede afinar).

## 18. Decisiones brainstorming → spec mapping

| Q | Decisión | Sección spec |
|---|---|---|
| Q1 | Judge = Anthropic Haiku 4.5 (single API key, modelo distinto a Sonnet 4.6) | §4.2 judge.py, §17 deferred (multi-vendor a H12) |
| Q2 | Framework = Ragas + custom layer (sin DeepEval por ahora) | §4.4 metrics.py, §5.1 Ragas config |
| Q3 | Scope = 30 chat + 10 docs estratificados, cache obligatorio | §3, §6 cache, §8 authoring flow |
| Q4 | Ejecución = solo local + manual commit; CI corre solo unit tests del harness | §9 make targets, §10.3 |
| Q5 | Autoría = hybrid (skeleton humano + subagente draft + revisión PR) | §8 phases 1-3 |
| Q6 | Report = aggregate + per-case appendix; bake-ins (temp=0, caveats, reproducibilidad) | §11 report structure |

---

**Status:** approved. Ready for writing-plans skill.
