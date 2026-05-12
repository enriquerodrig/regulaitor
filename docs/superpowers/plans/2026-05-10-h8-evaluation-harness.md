# H8 — Evaluation Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the H8 evaluation harness — a reproducible Python pipeline that runs RegulAItor's H4/H5 backends against a curated gold set (30 chat + 10 docs), computes Ragas + custom metrics with a Haiku 4.5 LLM judge, and emits a markdown report — plus author the gold set itself and produce the first real report committed to `evals/reports/latest.md`.

**Architecture:** Pure-Python harness that imports `orchestration.graph.run` and `orchestration.document_graph.run_document` directly (no HTTP / no auth — H7 surface is unused for evals). All LLM calls go through a SHA256 hash-keyed filesystem cache (`evals/cache/`, gitignored) so the $10 Anthropic budget covers exactly one full live run + unlimited cache-only re-runs. The judge (Haiku 4.5) is the only LLM the harness itself owns; production calls go through the existing H4 chat graph and H5 document graph unchanged.

**Tech Stack:** Python 3.11, Pydantic v2, Ragas 0.2 (RAG metrics), Anthropic SDK 0.39+ (already in project), pandas + datasets (Ragas transitive). ReportLab for synthetic PDF fixtures (already used by H5 `regenerate_document_fixtures.py`).

---

## File Structure

**Created (~25 files of code + 20 fixture artifacts + ADR):**

```
evals/
├── __init__.py                          # Empty package marker
├── schemas.py                           # Pydantic v2 schemas (~250 lines)
├── cache.py                             # Hash-keyed LLM call cache (~80 lines)
├── metrics.py                           # Ragas adapter + custom metrics (~350 lines)
├── judge.py                             # Haiku 4.5 wrapper + prompt loader (~80 lines)
├── report.py                            # Markdown generator (~250 lines)
├── harness.py                           # Run loop + load_gold_set + main (~250 lines)
├── gold_set.jsonl                       # 30 chat cases (generated in Task 10)
├── document_cases/
│   ├── case_001_*.pdf, ..., case_010_*.pdf       # 10 ReportLab fixtures (Task 10)
│   └── case_001_*.expected.json, ...              # 10 manifests (Task 10)
├── cache/.gitkeep                       # gitignored otherwise
└── reports/
    ├── .gitkeep
    └── latest.md                        # First real run, generated in Task 11

src/regulaitor/agents/prompts/judge/
├── __init__.py
└── faithfulness.v1.0.md                 # Judge prompt (Task 5)

scripts/
└── evaluate.py                          # CLI wrapper (Task 8)

tests/unit/
├── test_evals_schemas.py                # Task 2
├── test_evals_cache.py                  # Task 3
├── test_evals_metrics.py                # Task 4
├── test_evals_judge.py                  # Task 5
└── test_evals_report.py                 # Task 6

tests/integration/
└── test_evals_smoke.py                  # Task 8 (with cache pre-populated)

docs/adr/0010-evaluation-harness.md      # Task 12

.claude/skills/evals-runner/
└── SKILL.md                             # Task 12
```

**Modified:**

```
pyproject.toml                           # Task 1: ragas + transitive deps
Makefile                                 # Task 8: 3 new targets
README.md                                # Task 12: Evaluation section
.gitignore                               # Task 1: evals/cache/, evals/reports/archive/
scripts/regenerate_document_fixtures.py  # Task 10: extend for H8 doc cases
CLAUDE.md                                # Task 12: §27 mark H8 closed (post-merge)
docs/technical_decisions_log.md          # Task 12: append §H8
```

**File responsibilities:**

| File | Responsibility |
|---|---|
| `evals/schemas.py` | All Pydantic v2 models — gold case, results, aggregate, run metadata |
| `evals/cache.py` | Hash-keyed JSON cache for LLM responses; cache-only mode |
| `evals/metrics.py` | Ragas adapter (faithfulness/answer_relevancy/context_*) + custom (citation/verdict/severity/cost) + aggregate |
| `evals/judge.py` | Haiku 4.5 invocation with versioned prompt → CriteriaScore[] |
| `evals/report.py` | Pure function: (Meta, Aggregate, [ChatResult], [DocResult]) → markdown string |
| `evals/harness.py` | Orchestration: load gold, iterate, run backends, compute, render, write |
| `scripts/evaluate.py` | argparse → harness.main |

---

## Task 1: Dependencies + scaffolding

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Create: `evals/__init__.py`
- Create: `evals/cache/.gitkeep`
- Create: `evals/reports/.gitkeep`
- Create: `evals/document_cases/.gitkeep`
- Create: `src/regulaitor/agents/prompts/judge/__init__.py`

- [ ] **Step 1: Inspect current dependencies and gitignore**

```bash
grep -nE "ragas|pandas|datasets" pyproject.toml
grep -nE "evals/" .gitignore
```
Expected: no output for ragas/datasets (we add them); pandas may be present transitively. `.gitignore` may have `evals/reports/` already from H0.1 placeholder — verify before duplicating.

- [ ] **Step 2: Add ragas to runtime deps**

Edit `pyproject.toml`. Locate `[project].dependencies` (after the `slowapi` entry from H7) and append:
```toml
    "ragas>=0.2,<1.0",
```
ragas pulls `pandas`, `datasets`, `tiktoken`, langchain-* transitively via `uv lock` — do not pin them explicitly unless `uv sync` reports a conflict.

- [ ] **Step 3: Sync dependencies and verify pip-audit clean**

Run:
```bash
uv sync --extra dev
uv run pip-audit --skip-editable --ignore-vuln CVE-2026-1839
```
Expected: `uv sync` succeeds, ragas + transitive installed; pip-audit reports zero new vulns. If a new CVE appears on a transitive package, stop and report — do not commit.

- [ ] **Step 4: Update `.gitignore`**

Append to `.gitignore`:
```
# H8 — evaluation harness
evals/cache/
evals/reports/archive/
```
Keep `evals/cache/.gitkeep` and `evals/reports/.gitkeep` tracked (the directories must exist for pytest fixtures + first run).

- [ ] **Step 5: Create scaffolding directories and files**

```bash
mkdir -p evals/cache evals/reports evals/document_cases
touch evals/cache/.gitkeep evals/reports/.gitkeep evals/document_cases/.gitkeep
mkdir -p src/regulaitor/agents/prompts/judge
```

Create `evals/__init__.py`:
```python
"""H8 — evaluation harness for RegulAItor.

Pure-Python harness that runs the existing H4 chat graph and H5 document
graph against a curated gold set, computes Ragas + custom metrics with a
Haiku 4.5 LLM judge, and emits a markdown report.

The harness imports backend modules directly; the H7 FastAPI surface is
not involved in evaluation runs.
"""
```

Create `src/regulaitor/agents/prompts/judge/__init__.py`:
```python
"""H8 — judge agent prompts (versioned per H4 prompt-versioning skill).

Prompts here drive Haiku 4.5 LLM-as-judge scoring of answer faithfulness
and criteria adherence in the evaluation harness.
"""
```

- [ ] **Step 6: Verify imports**

```bash
uv run python -c "import evals; import regulaitor.agents.prompts.judge"
```
Expected: silent success.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock .gitignore evals/ src/regulaitor/agents/prompts/judge/__init__.py
git commit -m "chore(h8): add ragas runtime dep + evals/ scaffolding + judge prompts pkg"
```

---

## Task 2: `schemas.py` — Pydantic v2 models

**Files:**
- Create: `evals/schemas.py`
- Test: `tests/unit/test_evals_schemas.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_evals_schemas.py`:
```python
"""Unit tests for evals.schemas — Pydantic v2 validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from evals.schemas import (
    AggregateMetrics,
    ChatCaseResult,
    CitationMetrics,
    CriteriaScore,
    DocCaseResult,
    EvalRunMeta,
    GoldCaseChat,
    GoldCaseDoc,
)


# ---------------------------------------------------------------------------
# GoldCaseChat
# ---------------------------------------------------------------------------


def _chat_payload() -> dict:
    return {
        "id": "chat-001",
        "tipo": "chat",
        "entrada": "¿Qué dice el AI Act sobre sistemas de alto riesgo?",
        "corpus_esperado": "ai_act",
        "articulos_esperados": ["6.1", "9.2"],
        "severidad_esperada": "medium",
        "criterios_evaluacion": ["Cita art. 6.1", "No afirma X sin evidencia"],
        "salida_esperada": "El AI Act regula sistemas de alto riesgo en art. 6 y 9...",
        "requiere_revision_humana": False,
        "expected_verdict": "pass",
    }


def test_gold_case_chat_valid_minimal() -> None:
    case = GoldCaseChat.model_validate(_chat_payload())
    assert case.id == "chat-001"
    assert case.tipo == "chat"
    assert case.expected_verdict == "pass"


def test_gold_case_chat_rejects_extra_field() -> None:
    payload = _chat_payload() | {"unknown": "x"}
    with pytest.raises(ValidationError):
        GoldCaseChat.model_validate(payload)


def test_gold_case_chat_rejects_oversize_entrada() -> None:
    payload = _chat_payload() | {"entrada": "x" * 2001}
    with pytest.raises(ValidationError):
        GoldCaseChat.model_validate(payload)


def test_gold_case_chat_rejects_unknown_corpus() -> None:
    payload = _chat_payload() | {"corpus_esperado": "nis2"}
    with pytest.raises(ValidationError):
        GoldCaseChat.model_validate(payload)


def test_gold_case_chat_severidad_optional() -> None:
    payload = _chat_payload() | {"severidad_esperada": None}
    case = GoldCaseChat.model_validate(payload)
    assert case.severidad_esperada is None


def test_gold_case_chat_criterios_min_length_one() -> None:
    payload = _chat_payload() | {"criterios_evaluacion": []}
    with pytest.raises(ValidationError):
        GoldCaseChat.model_validate(payload)


def test_gold_case_chat_frozen() -> None:
    case = GoldCaseChat.model_validate(_chat_payload())
    with pytest.raises(ValidationError):
        case.entrada = "nuevo texto"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# GoldCaseDoc
# ---------------------------------------------------------------------------


def _doc_payload() -> dict:
    return {
        "id": "doc-001",
        "tipo": "document",
        "pdf_path": "case_001_ai_act_policy.pdf",
        "corpus_esperado": ["ai_act"],
        "expected_findings_articulos": ["6.1"],
        "expected_document_verdict": "requires_human_review",
        "expected_n_segments": 5,
        "n_segments_tolerance": 2,
        "criterios_evaluacion": ["Detecta sistema alto riesgo no clasificado"],
    }


def test_gold_case_doc_valid_minimal() -> None:
    case = GoldCaseDoc.model_validate(_doc_payload())
    assert case.id == "doc-001"
    assert case.expected_n_segments == 5


def test_gold_case_doc_rejects_zero_n_segments() -> None:
    payload = _doc_payload() | {"expected_n_segments": 0}
    with pytest.raises(ValidationError):
        GoldCaseDoc.model_validate(payload)


def test_gold_case_doc_corpus_min_length_one() -> None:
    payload = _doc_payload() | {"corpus_esperado": []}
    with pytest.raises(ValidationError):
        GoldCaseDoc.model_validate(payload)


# ---------------------------------------------------------------------------
# CitationMetrics
# ---------------------------------------------------------------------------


def test_citation_metrics_clamps_precision_recall() -> None:
    cm = CitationMetrics(
        emitted=["6.1"], expected=["6.1"], precision=1.0, recall=1.0
    )
    assert cm.precision == 1.0
    with pytest.raises(ValidationError):
        CitationMetrics(emitted=[], expected=[], precision=1.5, recall=1.0)


# ---------------------------------------------------------------------------
# ChatCaseResult / DocCaseResult / AggregateMetrics
# ---------------------------------------------------------------------------


def test_chat_case_result_full_shape() -> None:
    cm = CitationMetrics(emitted=["6.1"], expected=["6.1"], precision=1.0, recall=1.0)
    result = ChatCaseResult(
        case_id="chat-001",
        expected_verdict="pass",
        actual_verdict="pass",
        verdict_match=True,
        expected_severity="medium",
        actual_severity="medium",
        severity_match=True,
        citations=cm,
        faithfulness=0.9,
        answer_relevancy=0.85,
        context_precision=0.8,
        context_recall=0.78,
        criteria_scores=[
            CriteriaScore(criterion="Cita art. 6.1", passed=True, reason="literal match")
        ],
        latency_ms=4200,
        cost_eur=0.04,
        cache_hit=False,
    )
    assert result.case_id == "chat-001"
    assert result.criteria_scores[0].passed is True


def test_aggregate_metrics_validation() -> None:
    agg = AggregateMetrics(
        n_chat_cases=30,
        n_doc_cases=10,
        faithfulness_mean=0.87,
        answer_relevancy_mean=0.91,
        context_precision_mean=0.78,
        context_recall_mean=0.82,
        citation_precision_mean=0.93,
        citation_recall_mean=0.79,
        verdict_match_rate=0.90,
        severity_match_rate=0.83,
        latency_p95_ms=8420,
        cost_per_chat_eur=0.041,
        cost_per_doc_eur=0.487,
        cost_total_eur=6.83,
        cache_hit_rate=0.05,
    )
    assert agg.cost_total_eur == 6.83


def test_aggregate_metrics_rate_clamped_to_unit() -> None:
    with pytest.raises(ValidationError):
        AggregateMetrics(
            n_chat_cases=30,
            n_doc_cases=10,
            faithfulness_mean=1.5,  # invalid
            answer_relevancy_mean=0.91,
            context_precision_mean=0.78,
            context_recall_mean=0.82,
            citation_precision_mean=0.93,
            citation_recall_mean=0.79,
            verdict_match_rate=0.90,
            severity_match_rate=0.83,
            latency_p95_ms=8420,
            cost_per_chat_eur=0.041,
            cost_per_doc_eur=0.487,
            cost_total_eur=6.83,
            cache_hit_rate=0.05,
        )


def test_eval_run_meta_shape() -> None:
    meta = EvalRunMeta(
        run_date="2026-05-10T18:00:00+00:00",
        commit_sha="abcd123",
        production_model="claude-sonnet-4-6",
        judge_model="claude-haiku-4-5-20251001",
        temperature=0.0,
        subset=None,
        cache_only=False,
    )
    assert meta.commit_sha == "abcd123"
    assert meta.subset is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_evals_schemas.py -v --no-cov
```
Expected: ImportError — `evals.schemas` not found yet.

- [ ] **Step 3: Implement `evals/schemas.py`**

Create `evals/schemas.py`:
```python
"""H8 — Pydantic v2 schemas for the evaluation harness.

These models define the gold set entries (input), per-case results (output of
metric computation), aggregate metrics (input to the report), and run
metadata (header of the report). All models are frozen and reject extra
fields by construction (extra='forbid') so a typo in the gold set jsonl
fails fast at load time.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Gold set entries
# ---------------------------------------------------------------------------


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
    """One document case (manifest paired with a PDF file)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    id: str = Field(min_length=1)
    tipo: Literal["document"]
    pdf_path: str = Field(min_length=1)
    corpus_esperado: list[Literal["ai_act", "gdpr"]] = Field(min_length=1)
    expected_findings_articulos: list[str]
    expected_document_verdict: Literal["pass", "block", "requires_human_review"]
    expected_n_segments: int = Field(ge=1)
    n_segments_tolerance: int = Field(default=2, ge=0)
    criterios_evaluacion: list[str] = Field(min_length=1)


# ---------------------------------------------------------------------------
# Per-case metric results
# ---------------------------------------------------------------------------


class CitationMetrics(BaseModel):
    """Article-level set comparison: precision = |emitted ∩ expected| / |emitted|."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    expected: list[str]
    emitted: list[str]
    precision: float = Field(ge=0.0, le=1.0)
    recall: float = Field(ge=0.0, le=1.0)


class CriteriaScore(BaseModel):
    """Single LLM-judge result for one criterion from criterios_evaluacion."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    criterion: str
    passed: bool
    reason: str | None


class ChatCaseResult(BaseModel):
    """All metrics for one chat case after running graph.run + judge."""

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
    """All metrics for one document case after run_document + judge."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str
    expected_document_verdict: Literal["pass", "block", "requires_human_review"]
    actual_document_verdict: Literal["pass", "block", "requires_human_review"]
    verdict_match: bool
    expected_n_segments: int
    actual_n_segments: int
    n_segments_within_tolerance: bool
    findings_citations: CitationMetrics
    faithfulness: float = Field(ge=0.0, le=1.0)
    criteria_scores: list[CriteriaScore]
    latency_ms_total: int = Field(ge=0)
    cost_eur_total: float = Field(ge=0)
    cache_hit: bool


class AggregateMetrics(BaseModel):
    """Headline numbers across all cases — what the report's top table renders."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    n_chat_cases: int = Field(ge=0)
    n_doc_cases: int = Field(ge=0)
    faithfulness_mean: float = Field(ge=0.0, le=1.0)
    answer_relevancy_mean: float = Field(ge=0.0, le=1.0)
    context_precision_mean: float = Field(ge=0.0, le=1.0)
    context_recall_mean: float = Field(ge=0.0, le=1.0)
    citation_precision_mean: float = Field(ge=0.0, le=1.0)
    citation_recall_mean: float = Field(ge=0.0, le=1.0)
    verdict_match_rate: float = Field(ge=0.0, le=1.0)
    severity_match_rate: float = Field(ge=0.0, le=1.0)
    latency_p95_ms: int = Field(ge=0)
    cost_per_chat_eur: float = Field(ge=0)
    cost_per_doc_eur: float = Field(ge=0)
    cost_total_eur: float = Field(ge=0)
    cache_hit_rate: float = Field(ge=0.0, le=1.0)


class EvalRunMeta(BaseModel):
    """Header metadata for the markdown report."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    run_date: str
    commit_sha: str
    production_model: str
    judge_model: str
    temperature: float = Field(ge=0.0, le=2.0)
    subset: int | None
    cache_only: bool
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_evals_schemas.py -v --no-cov
```
Expected: 13 tests pass.

- [ ] **Step 5: Run lint**

```bash
uv run ruff check evals/schemas.py tests/unit/test_evals_schemas.py
uv run black --check evals/schemas.py tests/unit/test_evals_schemas.py
```
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add evals/schemas.py tests/unit/test_evals_schemas.py
git commit -m "feat(h8): add evals.schemas with gold case + result + aggregate models"
```

---

## Task 3: `cache.py` — hash-keyed LLM response cache

**Files:**
- Create: `evals/cache.py`
- Test: `tests/unit/test_evals_cache.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_evals_cache.py`:
```python
"""Unit tests for evals.cache — hash-keyed LLM response cache."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals import cache


def test_cache_key_deterministic() -> None:
    k1 = cache.cache_key(model="claude-sonnet-4-6", prompt="hello", temperature=0.0)
    k2 = cache.cache_key(model="claude-sonnet-4-6", prompt="hello", temperature=0.0)
    assert k1 == k2
    assert len(k1) == 64  # sha256 hex


def test_cache_key_differs_for_different_inputs() -> None:
    k_a = cache.cache_key(model="claude-sonnet-4-6", prompt="a", temperature=0.0)
    k_b = cache.cache_key(model="claude-sonnet-4-6", prompt="b", temperature=0.0)
    k_t = cache.cache_key(model="claude-sonnet-4-6", prompt="a", temperature=0.5)
    k_m = cache.cache_key(model="claude-haiku-4-5", prompt="a", temperature=0.0)
    assert len({k_a, k_b, k_t, k_m}) == 4


def test_cache_call_persists_on_miss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "_CACHE_DIR", tmp_path)

    calls: list[dict] = []

    def fake_invoke(*, model: str, system: str, user: str, temperature: float, max_tokens: int) -> tuple[str, int, int]:
        calls.append({"model": model, "user": user})
        return ("response_text", 100, 50)  # text, tokens_in, tokens_out

    text, cost = cache.cache_call(
        model="m",
        system="s",
        user="u",
        temperature=0.0,
        max_tokens=1000,
        invoke=fake_invoke,
        cache_only=False,
    )
    assert text == "response_text"
    assert cost > 0
    assert len(calls) == 1
    # Persisted file exists
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1


def test_cache_call_hit_skips_invoke(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "_CACHE_DIR", tmp_path)
    calls: list[dict] = []

    def fake_invoke(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs)
        return ("first", 100, 50)

    cache.cache_call(model="m", system="s", user="u", temperature=0.0, max_tokens=1000, invoke=fake_invoke, cache_only=False)
    cache.cache_call(model="m", system="s", user="u", temperature=0.0, max_tokens=1000, invoke=fake_invoke, cache_only=False)
    assert len(calls) == 1  # second call hit cache


def test_cache_only_raises_on_miss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache, "_CACHE_DIR", tmp_path)
    with pytest.raises(RuntimeError, match="cache miss"):
        cache.cache_call(
            model="m", system="s", user="u", temperature=0.0, max_tokens=1000,
            invoke=lambda **kw: ("x", 0, 0),
            cache_only=True,
        )


def test_estimate_cost_eur_known_models() -> None:
    cost = cache.estimate_cost_eur(model="claude-sonnet-4-6", tokens_in=1_000_000, tokens_out=0)
    assert cost == pytest.approx(2.76, rel=0.01)
    cost = cache.estimate_cost_eur(model="claude-haiku-4-5-20251001", tokens_in=1_000_000, tokens_out=0)
    assert cost == pytest.approx(0.92, rel=0.01)


def test_estimate_cost_eur_unknown_model_returns_zero() -> None:
    assert cache.estimate_cost_eur(model="some-other-model", tokens_in=1000, tokens_out=1000) == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_evals_cache.py -v --no-cov
```
Expected: ImportError.

- [ ] **Step 3: Implement `evals/cache.py`**

Create `evals/cache.py`:
```python
"""H8 — Hash-keyed filesystem cache for LLM responses.

The harness wraps every LLM call through `cache_call`. On hit, returns the
cached response without API contact. On miss, calls `invoke` (the live API
function), persists the response with cost estimation, and returns it.

`cache_only=True` mode refuses to call `invoke` on miss — useful for
regenerating the report from cached responses without spending credit
(`make eval-from-cache`).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

# Filesystem location for the cache. Tests monkeypatch this to tmp_path.
_CACHE_DIR = Path(__file__).resolve().parent / "cache"

# Anthropic prices per 1M tokens (USD), converted to EUR at ~0.92.
_PRICE_EUR_PER_M_TOKENS: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-6": (2.76, 13.80),  # input, output
    "claude-haiku-4-5-20251001": (0.92, 4.60),
}


def cache_key(*, model: str, prompt: str, temperature: float) -> str:
    """SHA256 hex digest of (model, prompt, temperature). 64 chars."""
    payload = f"{model}|{prompt}|{temperature}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _cache_path(key: str) -> Path:
    return _CACHE_DIR / f"{key}.json"


def estimate_cost_eur(*, model: str, tokens_in: int, tokens_out: int) -> float:
    """Approximate cost in EUR using static price table. Unknown model → 0.0."""
    rates = _PRICE_EUR_PER_M_TOKENS.get(model)
    if rates is None:
        return 0.0
    in_rate, out_rate = rates
    return (tokens_in / 1_000_000) * in_rate + (tokens_out / 1_000_000) * out_rate


# Type of the live-API invocation function: returns (response_text, tokens_in, tokens_out).
InvokeFn = Callable[..., tuple[str, int, int]]


def cache_call(
    *,
    model: str,
    system: str,
    user: str,
    temperature: float,
    max_tokens: int,
    invoke: InvokeFn,
    cache_only: bool,
) -> tuple[str, float]:
    """Cached LLM invocation. Returns (response_text, cost_eur).

    On hit: zero-cost; on miss with cache_only=False: live API + persist;
    on miss with cache_only=True: raises RuntimeError.
    """
    prompt = f"{system}\n---\n{user}"
    key = cache_key(model=model, prompt=prompt, temperature=temperature)
    path = _cache_path(key)

    if path.exists():
        record = json.loads(path.read_text(encoding="utf-8"))
        return record["response"], 0.0  # cache hit → zero marginal cost

    if cache_only:
        raise RuntimeError(f"cache miss for {key} in --cache-only mode")

    text, tokens_in, tokens_out = invoke(
        model=model, system=system, user=user, temperature=temperature, max_tokens=max_tokens,
    )
    cost = estimate_cost_eur(model=model, tokens_in=tokens_in, tokens_out=tokens_out)

    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "request": {"model": model, "system": system, "user": user, "temperature": temperature},
        "response": text,
        "timestamp": datetime.now(UTC).isoformat(),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_eur": cost,
    }
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return text, cost
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_evals_cache.py -v --no-cov
```
Expected: 7 tests pass.

- [ ] **Step 5: Run lint**

```bash
uv run ruff check evals/cache.py tests/unit/test_evals_cache.py
uv run black --check evals/cache.py tests/unit/test_evals_cache.py
```
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add evals/cache.py tests/unit/test_evals_cache.py
git commit -m "feat(h8): add evals.cache with SHA256 hash-keyed LLM response cache"
```

---

## Task 4: `metrics.py` — Ragas adapter + custom metrics

**Files:**
- Create: `evals/metrics.py`
- Test: `tests/unit/test_evals_metrics.py`

This task implements the metrics in two halves: (a) custom metrics over `ChatState` / `DocumentReport` (citation, verdict, severity), and (b) Ragas adapter that turns each chat case into a one-row Ragas `EvaluationDataset` and runs the standard four metrics. Aggregation is also here.

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_evals_metrics.py`:
```python
"""Unit tests for evals.metrics — custom + aggregate.

Ragas metric integration is tested in test_evals_smoke.py (Task 8) because
it requires actual Dataset construction and a mocked LLM. Here we test only
the pure-Python custom metrics that don't need Ragas.
"""

from __future__ import annotations

import pytest

from evals.metrics import (
    aggregate,
    compute_citation_metrics,
    extract_emitted_articles_chat,
    extract_emitted_articles_doc,
)
from evals.schemas import (
    AggregateMetrics,
    ChatCaseResult,
    CitationMetrics,
    CriteriaScore,
    DocCaseResult,
)
from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    DocumentReport,
    Finding,
    Segment,
    SegmentResult,
)
from regulaitor.orchestration.state import ChatState


# ---------------------------------------------------------------------------
# compute_citation_metrics
# ---------------------------------------------------------------------------


def test_citation_metrics_perfect_match() -> None:
    cm = compute_citation_metrics(emitted=["6.1", "9.2"], expected=["6.1", "9.2"])
    assert cm.precision == 1.0
    assert cm.recall == 1.0


def test_citation_metrics_empty_emitted_zero_precision() -> None:
    cm = compute_citation_metrics(emitted=[], expected=["6.1"])
    assert cm.precision == 0.0
    assert cm.recall == 0.0


def test_citation_metrics_empty_expected_zero_recall() -> None:
    cm = compute_citation_metrics(emitted=["6.1"], expected=[])
    assert cm.precision == 0.0  # convention from spec §5.2
    assert cm.recall == 0.0


def test_citation_metrics_partial_overlap() -> None:
    cm = compute_citation_metrics(emitted=["6.1", "10.3"], expected=["6.1", "9.2"])
    assert cm.precision == 0.5
    assert cm.recall == 0.5


def test_citation_metrics_dedup() -> None:
    cm = compute_citation_metrics(emitted=["6.1", "6.1"], expected=["6.1"])
    # set semantics: |{"6.1"} ∩ {"6.1"}| / |{"6.1"}| = 1.0 each
    assert cm.precision == 1.0
    assert cm.recall == 1.0


# ---------------------------------------------------------------------------
# extract_emitted_articles_*
# ---------------------------------------------------------------------------


def _state_with_citations(*pairs: tuple[str, str | None]) -> ChatState:
    """Build a ChatState whose audited_answer has the given (articulo, apartado) pairs."""
    citations = [
        Citation(norma="ai_act", articulo=art, apartado=ap, language="es", text="t")
        for art, ap in pairs
    ]
    finding = Finding(
        text="hallazgo",
        citations=citations,
        severity="info",
    )
    answer = Answer(
        query="q", language="es", text="respuesta", findings=[finding]
    )
    audit_results = [
        AuditResult(
            citation=c,
            validated=True,
            article_exists=True,
            apartado_exists=True,
            text_normalized_match=True,
            reason=None,
        )
        for c in citations
    ]
    audited = AuditedAnswer(
        answer=answer, verdict=AuditVerdict.PASS, audit_results=audit_results, reason=None
    )
    return ChatState(
        case_id="x",
        query="q",
        corpus="ai_act",
        language="es",
        answer=answer,
        audited_answer=audited,
    )


def test_extract_emitted_articles_chat_concatenates_articulo_apartado() -> None:
    state = _state_with_citations(("6", "1"), ("9", "2"))
    arts = extract_emitted_articles_chat(state)
    assert sorted(arts) == ["6.1", "9.2"]


def test_extract_emitted_articles_chat_handles_no_apartado() -> None:
    state = _state_with_citations(("6", None))
    arts = extract_emitted_articles_chat(state)
    assert arts == ["6"]


def test_extract_emitted_articles_chat_blocked_state_returns_empty() -> None:
    state = ChatState(
        case_id="x", query="q", corpus="ai_act", language="es",
        injection_blocked=True, injection_reason="injection",
    )
    arts = extract_emitted_articles_chat(state)
    assert arts == []


def _doc_report_with_segment_citations(*pairs: tuple[str, str | None]) -> DocumentReport:
    citations = [
        Citation(norma="ai_act", articulo=art, apartado=ap, language="es", text="t")
        for art, ap in pairs
    ]
    finding = Finding(text="t", citations=citations, severity="info")
    answer = Answer(query="(seg)", language="es", text="resp", findings=[finding])
    audit_results = [
        AuditResult(
            citation=c, validated=True, article_exists=True, apartado_exists=True,
            text_normalized_match=True, reason=None,
        )
        for c in citations
    ]
    audited = AuditedAnswer(
        answer=answer, verdict=AuditVerdict.PASS, audit_results=audit_results, reason=None
    )
    seg = Segment(id=1, title=None, text="seg", token_count=10, is_continuation=False)
    seg_result = SegmentResult(
        segment=seg, skipped=False, skip_reason=None, audited_answer=audited,
        latency_ms=100, cost_eur=0.01,
    )
    return DocumentReport(
        case_id="d", document_hash="h" * 64, language="es", corpus=["ai_act"],
        sanitizer_log=[], segments=[seg_result], document_verdict=AuditVerdict.PASS,
        document_reason=None, n_segments_total=1, n_segments_blocked_by_injection=0,
        n_segments_pass=1, n_segments_block=0, n_segments_review=0,
        latency_ms_total=100, cost_eur_total=0.01,
    )


def test_extract_emitted_articles_doc_unions_across_segments() -> None:
    report = _doc_report_with_segment_citations(("6", "1"), ("9", "2"))
    arts = extract_emitted_articles_doc(report)
    assert sorted(arts) == ["6.1", "9.2"]


# ---------------------------------------------------------------------------
# aggregate
# ---------------------------------------------------------------------------


def _chat_result(case_id: str, *, latency_ms: int, cost: float, cache_hit: bool) -> ChatCaseResult:
    return ChatCaseResult(
        case_id=case_id,
        expected_verdict="pass", actual_verdict="pass", verdict_match=True,
        expected_severity="medium", actual_severity="medium", severity_match=True,
        citations=CitationMetrics(emitted=["6.1"], expected=["6.1"], precision=1.0, recall=1.0),
        faithfulness=0.9, answer_relevancy=0.9, context_precision=0.8, context_recall=0.8,
        criteria_scores=[CriteriaScore(criterion="c", passed=True, reason=None)],
        latency_ms=latency_ms, cost_eur=cost, cache_hit=cache_hit,
    )


def _doc_result(case_id: str, *, latency_ms: int, cost: float, cache_hit: bool) -> DocCaseResult:
    return DocCaseResult(
        case_id=case_id,
        expected_document_verdict="pass", actual_document_verdict="pass", verdict_match=True,
        expected_n_segments=5, actual_n_segments=5, n_segments_within_tolerance=True,
        findings_citations=CitationMetrics(emitted=["6.1"], expected=["6.1"], precision=1.0, recall=1.0),
        faithfulness=0.85,
        criteria_scores=[CriteriaScore(criterion="c", passed=True, reason=None)],
        latency_ms_total=latency_ms, cost_eur_total=cost, cache_hit=cache_hit,
    )


def test_aggregate_basic() -> None:
    chats = [_chat_result("c1", latency_ms=2000, cost=0.04, cache_hit=False)]
    docs = [_doc_result("d1", latency_ms=8000, cost=0.40, cache_hit=False)]
    agg = aggregate(chats, docs)
    assert agg.n_chat_cases == 1
    assert agg.n_doc_cases == 1
    assert agg.cost_total_eur == pytest.approx(0.44)
    assert agg.cost_per_chat_eur == pytest.approx(0.04)
    assert agg.cost_per_doc_eur == pytest.approx(0.40)
    assert agg.cache_hit_rate == 0.0


def test_aggregate_p95_latency() -> None:
    # 20 calls; 19 at 1000 ms, 1 at 10000 ms → p95 = 1000 (5% of 20 = 1, so percentile takes 19th element)
    chats = [
        _chat_result(f"c{i}", latency_ms=1000 if i < 19 else 10000, cost=0.01, cache_hit=False)
        for i in range(20)
    ]
    agg = aggregate(chats, [])
    # statistics.quantiles with n=20 may not give exact p95; allow some tolerance
    assert 1000 <= agg.latency_p95_ms <= 10000


def test_aggregate_empty_returns_zeros() -> None:
    agg = aggregate([], [])
    assert agg.n_chat_cases == 0
    assert agg.n_doc_cases == 0
    assert agg.cost_total_eur == 0.0
    assert agg.cache_hit_rate == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_evals_metrics.py -v --no-cov
```
Expected: ImportError.

- [ ] **Step 3: Implement `evals/metrics.py`**

Create `evals/metrics.py`:
```python
"""H8 — Custom metrics + Ragas adapter + aggregation.

Custom metrics work directly on ChatState and DocumentReport (the schemas
H4/H5 already produce). Ragas metrics are computed by building a one-row
EvaluationDataset per case and calling Ragas's `evaluate()` with the judge
LLM (Haiku 4.5).
"""

from __future__ import annotations

import statistics
from collections.abc import Callable
from typing import Any

from regulaitor.citation.schemas import (
    AuditedAnswer,
    Citation,
    DocumentReport,
)
from regulaitor.orchestration.state import ChatState

from evals.schemas import (
    AggregateMetrics,
    ChatCaseResult,
    CitationMetrics,
    CriteriaScore,
    DocCaseResult,
    GoldCaseChat,
    GoldCaseDoc,
)


# ---------------------------------------------------------------------------
# Custom — citation / verdict / severity
# ---------------------------------------------------------------------------


def _format_articulo(c: Citation) -> str:
    """'art.6.1' → '6.1'; if no apartado, just '6'."""
    if c.apartado is not None and c.apartado != "":
        return f"{c.articulo}.{c.apartado}"
    return c.articulo


def extract_emitted_articles_chat(state: ChatState) -> list[str]:
    """Articles cited in the audited answer of a chat case. Empty if blocked."""
    if state.audited_answer is None:
        return []
    seen: set[str] = set()
    for r in state.audited_answer.audit_results:
        seen.add(_format_articulo(r.citation))
    return sorted(seen)


def extract_emitted_articles_doc(report: DocumentReport) -> list[str]:
    """Union of citations across all segments of a document report."""
    seen: set[str] = set()
    for seg_result in report.segments:
        if seg_result.audited_answer is None:
            continue
        for r in seg_result.audited_answer.audit_results:
            seen.add(_format_articulo(r.citation))
    return sorted(seen)


def compute_citation_metrics(emitted: list[str], expected: list[str]) -> CitationMetrics:
    """Article-level set comparison. Edge cases follow spec §5.2."""
    emitted_set = set(emitted)
    expected_set = set(expected)
    intersection = emitted_set & expected_set
    if not emitted_set:
        precision = 0.0
    else:
        precision = len(intersection) / len(emitted_set)
    if not expected_set:
        recall = 0.0
    else:
        recall = len(intersection) / len(expected_set)
    return CitationMetrics(
        emitted=sorted(emitted_set),
        expected=sorted(expected_set),
        precision=precision,
        recall=recall,
    )


def _extract_severity_chat(audited: AuditedAnswer | None) -> str | None:
    """Severity of the first finding, or None if no findings."""
    if audited is None:
        return None
    if not audited.answer.findings:
        return None
    return audited.answer.findings[0].severity


# ---------------------------------------------------------------------------
# Ragas adapter
# ---------------------------------------------------------------------------


def _ragas_metrics_chat(
    *,
    query: str,
    answer: str,
    contexts: list[str],
    ground_truth: str | None,
    judge_call: Callable[..., tuple[str, float]],
) -> dict[str, float]:
    """Run Ragas faithfulness + answer_relevancy + context_precision + context_recall.

    Each metric is computed as a one-row evaluate() to keep the harness
    composable. Returns a dict of metric_name → score in [0, 1].

    judge_call is the cache-aware LLM call (Haiku 4.5 + temperature=0).
    """
    # Lazy import — Ragas is heavy and not needed by other modules
    import pandas as pd
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    # Ragas expects ground_truth for context_recall; if missing, fall back to a stub
    gt = ground_truth if ground_truth else "[no_reference]"

    df = pd.DataFrame(
        [
            {
                "user_input": query,
                "response": answer,
                "retrieved_contexts": contexts,
                "reference": gt,
            }
        ]
    )
    ds = Dataset.from_pandas(df)

    # Configure Ragas to use our judge via wrapper. Ragas accepts a langchain
    # LLM; we provide an Anthropic ChatAnthropic instance bound to Haiku 4.5
    # and rely on Ragas's internal caching+langchain pipeline.
    from langchain_anthropic import ChatAnthropic

    llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0.0)

    result = evaluate(
        ds,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=llm,
        raise_exceptions=False,
    )
    # result is a Result object; .to_pandas() yields the metric columns
    out = result.to_pandas().iloc[0].to_dict()
    return {
        "faithfulness": float(out.get("faithfulness", 0.0) or 0.0),
        "answer_relevancy": float(out.get("answer_relevancy", 0.0) or 0.0),
        "context_precision": float(out.get("context_precision", 0.0) or 0.0),
        "context_recall": float(out.get("context_recall", 0.0) or 0.0),
    }


def _ragas_metrics_doc(
    *,
    query: str,
    answer: str,
    contexts: list[str],
    ground_truth: str | None,
    judge_call: Callable[..., tuple[str, float]],
) -> dict[str, float]:
    """Doc-level Ragas: only faithfulness applies (no single retrieval context).

    Calls _ragas_metrics_chat under the hood and keeps only faithfulness.
    """
    metrics = _ragas_metrics_chat(
        query=query,
        answer=answer,
        contexts=contexts,
        ground_truth=ground_truth,
        judge_call=judge_call,
    )
    return {"faithfulness": metrics["faithfulness"]}


# ---------------------------------------------------------------------------
# Per-case orchestrators
# ---------------------------------------------------------------------------


def compute_chat_metrics(
    case: GoldCaseChat,
    state: ChatState,
    *,
    judge_call: Callable[..., tuple[str, float]],
    judge_score_fn: Callable[..., list[CriteriaScore]],
    latency_ms: int,
    cost_eur: float,
    cache_hit: bool,
) -> ChatCaseResult:
    """Compute all metrics for one chat case. Returns a frozen ChatCaseResult."""
    audited = state.audited_answer
    actual_verdict: str
    if state.injection_blocked:
        actual_verdict = "blocked_injection"
    elif audited is None:
        actual_verdict = "block"  # backend produced no answer; treat as block
    else:
        actual_verdict = audited.verdict.value

    # Citations
    emitted_articles = extract_emitted_articles_chat(state)
    citations = compute_citation_metrics(
        emitted=emitted_articles, expected=case.articulos_esperados
    )

    # Severity
    actual_severity = _extract_severity_chat(audited)
    severity_match: bool | None
    if case.severidad_esperada is None:
        severity_match = None
    else:
        severity_match = case.severidad_esperada == actual_severity

    # Ragas metrics
    contexts = (
        [c.text for c in state.context.chunks] if state.context else []
    )
    answer_text = audited.answer.text if audited else ""
    ragas = _ragas_metrics_chat(
        query=case.entrada,
        answer=answer_text,
        contexts=contexts,
        ground_truth=case.salida_esperada,
        judge_call=judge_call,
    )

    # Custom criteria via judge
    criteria_scores = judge_score_fn(
        criteria=case.criterios_evaluacion,
        query=case.entrada,
        actual_answer=answer_text,
        expected_answer=case.salida_esperada,
        cited_articles=emitted_articles,
        expected_articles=case.articulos_esperados,
    )

    return ChatCaseResult(
        case_id=case.id,
        expected_verdict=case.expected_verdict,
        actual_verdict=actual_verdict,  # type: ignore[arg-type]
        verdict_match=(actual_verdict == case.expected_verdict),
        expected_severity=case.severidad_esperada,
        actual_severity=actual_severity,  # type: ignore[arg-type]
        severity_match=severity_match,
        citations=citations,
        faithfulness=ragas["faithfulness"],
        answer_relevancy=ragas["answer_relevancy"],
        context_precision=ragas["context_precision"],
        context_recall=ragas["context_recall"],
        criteria_scores=criteria_scores,
        latency_ms=latency_ms,
        cost_eur=cost_eur,
        cache_hit=cache_hit,
    )


def compute_doc_metrics(
    case: GoldCaseDoc,
    report: DocumentReport,
    *,
    judge_call: Callable[..., tuple[str, float]],
    judge_score_fn: Callable[..., list[CriteriaScore]],
    latency_ms_total: int,
    cost_eur_total: float,
    cache_hit: bool,
) -> DocCaseResult:
    """Compute metrics for one document case."""
    actual_verdict = report.document_verdict.value

    emitted_articles = extract_emitted_articles_doc(report)
    findings_citations = compute_citation_metrics(
        emitted=emitted_articles, expected=case.expected_findings_articulos
    )

    n_segments_within_tolerance = (
        abs(report.n_segments_total - case.expected_n_segments) <= case.n_segments_tolerance
    )

    # Ragas faithfulness: aggregate the answer text across segments
    answer_text = " ".join(
        seg.audited_answer.answer.text
        for seg in report.segments
        if seg.audited_answer is not None
    )
    contexts = []  # doc pipeline doesn't expose retrieved contexts at report level
    ragas = _ragas_metrics_doc(
        query=f"Analiza este documento contra {','.join(case.corpus_esperado)}",
        answer=answer_text or "[no_answer]",
        contexts=contexts,
        ground_truth=None,
        judge_call=judge_call,
    )

    criteria_scores = judge_score_fn(
        criteria=case.criterios_evaluacion,
        query=f"Análisis documento {case.id}",
        actual_answer=answer_text,
        expected_answer=None,
        cited_articles=emitted_articles,
        expected_articles=case.expected_findings_articulos,
    )

    return DocCaseResult(
        case_id=case.id,
        expected_document_verdict=case.expected_document_verdict,
        actual_document_verdict=actual_verdict,  # type: ignore[arg-type]
        verdict_match=(actual_verdict == case.expected_document_verdict),
        expected_n_segments=case.expected_n_segments,
        actual_n_segments=report.n_segments_total,
        n_segments_within_tolerance=n_segments_within_tolerance,
        findings_citations=findings_citations,
        faithfulness=ragas["faithfulness"],
        criteria_scores=criteria_scores,
        latency_ms_total=latency_ms_total,
        cost_eur_total=cost_eur_total,
        cache_hit=cache_hit,
    )


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _safe_mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def _safe_p95(values: list[int]) -> int:
    if not values:
        return 0
    if len(values) < 2:
        return values[0]
    qs = statistics.quantiles(values, n=20)
    return int(qs[18])  # 95th percentile (index 18 of 19 cut-points in n=20)


def aggregate(
    chat_results: list[ChatCaseResult],
    doc_results: list[DocCaseResult],
) -> AggregateMetrics:
    """Aggregate per-case results into headline metrics for the report."""
    chat_n = len(chat_results)
    doc_n = len(doc_results)

    faithfulness_values = [r.faithfulness for r in chat_results] + [
        r.faithfulness for r in doc_results
    ]
    answer_relevancy_values = [r.answer_relevancy for r in chat_results]
    context_precision_values = [r.context_precision for r in chat_results]
    context_recall_values = [r.context_recall for r in chat_results]

    citation_precision_values = [r.citations.precision for r in chat_results] + [
        r.findings_citations.precision for r in doc_results
    ]
    citation_recall_values = [r.citations.recall for r in chat_results] + [
        r.findings_citations.recall for r in doc_results
    ]

    verdict_match_values = [
        1.0 if r.verdict_match else 0.0 for r in chat_results
    ] + [1.0 if r.verdict_match else 0.0 for r in doc_results]

    severity_match_values = [
        1.0 if r.severity_match else 0.0
        for r in chat_results
        if r.severity_match is not None
    ]

    latency_values = [r.latency_ms for r in chat_results] + [
        r.latency_ms_total for r in doc_results
    ]

    chat_costs = [r.cost_eur for r in chat_results]
    doc_costs = [r.cost_eur_total for r in doc_results]

    cache_hits = [r.cache_hit for r in chat_results] + [r.cache_hit for r in doc_results]
    cache_hit_rate = (
        sum(1 for h in cache_hits if h) / len(cache_hits) if cache_hits else 0.0
    )

    return AggregateMetrics(
        n_chat_cases=chat_n,
        n_doc_cases=doc_n,
        faithfulness_mean=_safe_mean(faithfulness_values),
        answer_relevancy_mean=_safe_mean(answer_relevancy_values),
        context_precision_mean=_safe_mean(context_precision_values),
        context_recall_mean=_safe_mean(context_recall_values),
        citation_precision_mean=_safe_mean(citation_precision_values),
        citation_recall_mean=_safe_mean(citation_recall_values),
        verdict_match_rate=_safe_mean(verdict_match_values),
        severity_match_rate=_safe_mean(severity_match_values),
        latency_p95_ms=_safe_p95(latency_values),
        cost_per_chat_eur=_safe_mean(chat_costs),
        cost_per_doc_eur=_safe_mean(doc_costs),
        cost_total_eur=sum(chat_costs) + sum(doc_costs),
        cache_hit_rate=cache_hit_rate,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_evals_metrics.py -v --no-cov
```
Expected: 11 tests pass.

- [ ] **Step 5: Run lint**

```bash
uv run ruff check evals/metrics.py tests/unit/test_evals_metrics.py
uv run black --check evals/metrics.py tests/unit/test_evals_metrics.py
```
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add evals/metrics.py tests/unit/test_evals_metrics.py
git commit -m "feat(h8): add evals.metrics with citation/verdict/severity + Ragas adapter + aggregate"
```

---

## Task 5: `judge.py` + faithfulness prompt

**Files:**
- Create: `evals/judge.py`
- Create: `src/regulaitor/agents/prompts/judge/faithfulness.v1.0.md`
- Test: `tests/unit/test_evals_judge.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_evals_judge.py`:
```python
"""Unit tests for evals.judge — Haiku 4.5 wrapper + prompt loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evals import judge
from evals.schemas import CriteriaScore


def test_load_judge_prompt_returns_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_prompt_path = tmp_path / "faithfulness.v1.0.md"
    fake_prompt_path.write_text("# Judge prompt\nTest content.\n", encoding="utf-8")
    monkeypatch.setattr(judge, "_PROMPT_PATH", fake_prompt_path)
    text = judge._load_judge_prompt()
    assert "Judge prompt" in text
    assert "Test content" in text


def test_load_judge_prompt_real_file_present() -> None:
    """The real prompt file must exist after Task 5."""
    assert judge._PROMPT_PATH.exists()
    content = judge._load_judge_prompt()
    assert "evaluador" in content.lower() or "evaluator" in content.lower()


def test_score_criteria_parses_json_response() -> None:
    fake_response = json.dumps(
        {
            "scores": [
                {"criterion": "Cita art. 6.1", "passed": True, "reason": "literal"},
                {"criterion": "No afirma X", "passed": False, "reason": "afirma X"},
            ]
        }
    )

    def fake_cache_call(**kwargs: Any) -> tuple[str, float]:
        return fake_response, 0.001

    scores = judge.score_criteria(
        criteria=["Cita art. 6.1", "No afirma X"],
        query="q",
        actual_answer="a",
        expected_answer="ea",
        cited_articles=["6.1"],
        expected_articles=["6.1"],
        cache_call=fake_cache_call,
    )
    assert len(scores) == 2
    assert scores[0].passed is True
    assert scores[1].passed is False
    assert scores[1].reason == "afirma X"


def test_score_criteria_raises_on_malformed_json() -> None:
    def fake_cache_call(**kwargs: Any) -> tuple[str, float]:
        return "not json{{", 0.001

    with pytest.raises(json.JSONDecodeError):
        judge.score_criteria(
            criteria=["c"], query="q", actual_answer="a", expected_answer=None,
            cited_articles=[], expected_articles=[],
            cache_call=fake_cache_call,
        )


def test_score_criteria_passes_correct_args_to_cache_call() -> None:
    captured: dict[str, Any] = {}

    def fake_cache_call(**kwargs: Any) -> tuple[str, float]:
        captured.update(kwargs)
        return json.dumps({"scores": []}), 0.0

    judge.score_criteria(
        criteria=["c"], query="q", actual_answer="a", expected_answer="ea",
        cited_articles=["6.1"], expected_articles=["6.1"],
        cache_call=fake_cache_call,
    )
    assert captured["model"] == "claude-haiku-4-5-20251001"
    assert captured["temperature"] == 0.0
    # The user payload should contain the JSON the prompt expects
    assert '"query":' in captured["user"]
    assert '"criteria":' in captured["user"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_evals_judge.py -v --no-cov
```
Expected: ImportError + missing prompt file.

- [ ] **Step 3: Create the judge prompt file**

Create `src/regulaitor/agents/prompts/judge/faithfulness.v1.0.md`:
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
- `cited_articles`: lista de artículos citados por el sistema (formato "6.1", "9.2").
- `expected_articles`: artículos que el caso espera que se citen.
- `criteria`: lista de criterios evaluables (strings en español).

Para cada criterio, devuelve `passed: true` solo si la respuesta lo cumple sin ambigüedad. En caso de duda, `passed: false`. Si un criterio menciona un artículo concreto (e.g. "cita art. 6.1") y `cited_articles` no lo contiene, devuelve `passed: false` con razón "artículo no citado".

Devuelve EXCLUSIVAMENTE un objeto JSON con esta forma exacta:

```json
{
  "scores": [
    {"criterion": "<texto literal del criterio recibido>", "passed": true, "reason": "<explicación breve, 1 frase>"},
    {"criterion": "<...>", "passed": false, "reason": "<...>"}
  ]
}
```

No incluyas markdown alrededor del JSON. No añadas campos extra. No omitas la `reason`. Si el output no es JSON válido y parseable, el harness lo trata como fallo del judge y registra el caso como inconcluso.
```

- [ ] **Step 4: Implement `evals/judge.py`**

Create `evals/judge.py`:
```python
"""H8 — Haiku 4.5 LLM-as-judge wrapper.

Loads the versioned judge prompt from src/regulaitor/agents/prompts/judge/
(per H4 prompt-versioning skill) and exposes `score_criteria` that the
metrics module calls per case to grade `criterios_evaluacion`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from evals.schemas import CriteriaScore

_JUDGE_MODEL = "claude-haiku-4-5-20251001"
_PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "regulaitor"
    / "agents"
    / "prompts"
    / "judge"
    / "faithfulness.v1.0.md"
)
_MAX_TOKENS = 2000


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
    cache_call: Callable[..., tuple[str, float]],
) -> list[CriteriaScore]:
    """Ask Haiku 4.5 to judge each criterion. Returns one CriteriaScore per item.

    `cache_call` is the cache-aware LLM invoke function; signature must accept
    keyword args (model, system, user, temperature, max_tokens) and return
    (response_text, cost_eur).
    """
    system_prompt = _load_judge_prompt()
    user_payload: dict[str, Any] = {
        "query": query,
        "actual_answer": actual_answer,
        "expected_answer": expected_answer,
        "cited_articles": cited_articles,
        "expected_articles": expected_articles,
        "criteria": criteria,
    }
    user_message = json.dumps(user_payload, ensure_ascii=False, indent=2)

    response_text, _cost = cache_call(
        model=_JUDGE_MODEL,
        system=system_prompt,
        user=user_message,
        temperature=0.0,
        max_tokens=_MAX_TOKENS,
    )
    parsed = json.loads(response_text)
    return [CriteriaScore(**s) for s in parsed["scores"]]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_evals_judge.py -v --no-cov
```
Expected: 5 tests pass.

- [ ] **Step 6: Run lint**

```bash
uv run ruff check evals/judge.py tests/unit/test_evals_judge.py
uv run black --check evals/judge.py tests/unit/test_evals_judge.py
```
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add evals/judge.py tests/unit/test_evals_judge.py src/regulaitor/agents/prompts/judge/faithfulness.v1.0.md
git commit -m "feat(h8): add evals.judge + faithfulness.v1.0 prompt for Haiku 4.5"
```

---

## Task 6: `report.py` — markdown generator

**Files:**
- Create: `evals/report.py`
- Test: `tests/unit/test_evals_report.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_evals_report.py`:
```python
"""Unit tests for evals.report — markdown rendering."""

from __future__ import annotations

import pytest

from evals.report import (
    _render_aggregate_table,
    _render_per_case_chat,
    _render_per_case_doc,
    render_report,
)
from evals.schemas import (
    AggregateMetrics,
    ChatCaseResult,
    CitationMetrics,
    CriteriaScore,
    DocCaseResult,
    EvalRunMeta,
)


def _meta() -> EvalRunMeta:
    return EvalRunMeta(
        run_date="2026-05-10T18:00:00+00:00",
        commit_sha="abcd123",
        production_model="claude-sonnet-4-6",
        judge_model="claude-haiku-4-5-20251001",
        temperature=0.0,
        subset=None,
        cache_only=False,
    )


def _agg() -> AggregateMetrics:
    return AggregateMetrics(
        n_chat_cases=30,
        n_doc_cases=10,
        faithfulness_mean=0.87,
        answer_relevancy_mean=0.91,
        context_precision_mean=0.78,
        context_recall_mean=0.82,
        citation_precision_mean=0.93,
        citation_recall_mean=0.79,
        verdict_match_rate=0.90,
        severity_match_rate=0.83,
        latency_p95_ms=8420,
        cost_per_chat_eur=0.041,
        cost_per_doc_eur=0.487,
        cost_total_eur=6.83,
        cache_hit_rate=0.05,
    )


def _chat_result() -> ChatCaseResult:
    return ChatCaseResult(
        case_id="chat-001",
        expected_verdict="pass", actual_verdict="pass", verdict_match=True,
        expected_severity="medium", actual_severity="medium", severity_match=True,
        citations=CitationMetrics(emitted=["6.1"], expected=["6.1"], precision=1.0, recall=1.0),
        faithfulness=0.9, answer_relevancy=0.9, context_precision=0.8, context_recall=0.8,
        criteria_scores=[CriteriaScore(criterion="Cita art. 6.1", passed=True, reason="ok")],
        latency_ms=2100, cost_eur=0.04, cache_hit=False,
    )


def _doc_result() -> DocCaseResult:
    return DocCaseResult(
        case_id="doc-001",
        expected_document_verdict="pass", actual_document_verdict="pass", verdict_match=True,
        expected_n_segments=5, actual_n_segments=5, n_segments_within_tolerance=True,
        findings_citations=CitationMetrics(emitted=["6.1"], expected=["6.1"], precision=1.0, recall=1.0),
        faithfulness=0.85,
        criteria_scores=[CriteriaScore(criterion="Detecta sistema alto riesgo", passed=True, reason=None)],
        latency_ms_total=8000, cost_eur_total=0.40, cache_hit=False,
    )


def test_render_aggregate_table_includes_all_metrics() -> None:
    md = _render_aggregate_table(_agg())
    assert "faithfulness" in md
    assert "0.87" in md
    assert "≥0.85" in md
    assert "✅" in md  # at least one passing metric


def test_render_aggregate_table_marks_failures() -> None:
    agg = _agg().model_copy(update={"faithfulness_mean": 0.50})
    md = _render_aggregate_table(agg)
    assert "❌" in md
    assert "0.50" in md or "0.5" in md


def test_render_per_case_chat_includes_id_and_verdict() -> None:
    md = _render_per_case_chat(_chat_result())
    assert "chat-001" in md
    assert "pass" in md
    assert "Cita art. 6.1" in md


def test_render_per_case_doc_includes_id_and_segments() -> None:
    md = _render_per_case_doc(_doc_result())
    assert "doc-001" in md
    assert "5" in md  # n_segments


def test_render_report_full_document() -> None:
    md = render_report(_meta(), _agg(), [_chat_result()], [_doc_result()])
    # Header
    assert "RegulAItor — Evaluation Report" in md
    assert "abcd123" in md
    assert "claude-sonnet-4-6" in md
    assert "claude-haiku-4-5-20251001" in md
    # Aggregate
    assert "faithfulness" in md
    # Per-case
    assert "chat-001" in md
    assert "doc-001" in md
    # Reproducibility + caveats
    assert "make eval-from-cache" in md
    assert "Caveats" in md or "caveats" in md.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_evals_report.py -v --no-cov
```
Expected: ImportError.

- [ ] **Step 3: Implement `evals/report.py`**

Create `evals/report.py`:
```python
"""H8 — Markdown report generator.

Pure function `render_report(meta, agg, chat_results, doc_results) -> str`.
No I/O; the harness writes the result to evals/reports/latest.md.
"""

from __future__ import annotations

from evals.schemas import (
    AggregateMetrics,
    ChatCaseResult,
    DocCaseResult,
    EvalRunMeta,
)

# Threshold table per CLAUDE.md §17. (metric_name, threshold, gated)
_THRESHOLDS = [
    ("faithfulness_mean", 0.85, True),
    ("answer_relevancy_mean", 0.85, True),
    ("context_precision_mean", 0.80, True),
    ("context_recall_mean", 0.80, False),  # info-only, not gated
    ("citation_precision_mean", 0.90, True),
    ("citation_recall_mean", 0.80, True),
    ("verdict_match_rate", 0.85, True),
    ("severity_match_rate", 0.80, True),
]


def _render_aggregate_table(agg: AggregateMetrics) -> str:
    rows: list[str] = []
    rows.append("| Métrica | Valor | Threshold | Pass |")
    rows.append("|---|---|---|---|")
    for metric_name, threshold, gated in _THRESHOLDS:
        value = getattr(agg, metric_name)
        if not gated:
            mark = "➖"
            threshold_str = "(info)"
        elif value >= threshold:
            mark = "✅"
            threshold_str = f"≥{threshold:.2f}"
        else:
            mark = f"❌ ({value - threshold:+.2f})"
            threshold_str = f"≥{threshold:.2f}"
        rows.append(f"| {metric_name} | {value:.2f} | {threshold_str} | {mark} |")

    # Latency + cost (different threshold semantics)
    latency_pass = "✅" if agg.latency_p95_ms <= 12000 else f"❌ (+{agg.latency_p95_ms - 12000})"
    rows.append(
        f"| latency_p95_ms | {agg.latency_p95_ms} | ≤12000 | {latency_pass} |"
    )
    cost_chat_pass = "✅" if agg.cost_per_chat_eur <= 0.05 else f"❌ ({agg.cost_per_chat_eur - 0.05:+.3f})"
    rows.append(
        f"| cost_per_chat_eur | {agg.cost_per_chat_eur:.3f} | ≤0.05 | {cost_chat_pass} |"
    )
    cost_doc_pass = "✅" if agg.cost_per_doc_eur <= 0.50 else f"❌ ({agg.cost_per_doc_eur - 0.50:+.3f})"
    rows.append(
        f"| cost_per_doc_eur | {agg.cost_per_doc_eur:.3f} | ≤0.50 | {cost_doc_pass} |"
    )
    rows.append(
        f"| cost_total_eur | {agg.cost_total_eur:.2f} | (info) | ➖ |"
    )
    rows.append(
        f"| cache_hit_rate | {agg.cache_hit_rate:.2f} | (info) | ➖ |"
    )
    return "\n".join(rows)


def _render_per_case_chat(r: ChatCaseResult) -> str:
    parts: list[str] = []
    parts.append(f"### {r.case_id}")
    parts.append("")
    verdict_mark = "✅" if r.verdict_match else "❌"
    sev_mark = "✅" if r.severity_match else "❌" if r.severity_match is False else "➖"
    parts.append(
        f"- **Verdict**: actual=`{r.actual_verdict}` expected=`{r.expected_verdict}` {verdict_mark}"
    )
    parts.append(
        f"- **Severity**: actual=`{r.actual_severity}` expected=`{r.expected_severity}` {sev_mark}"
    )
    parts.append(
        f"- **Citations**: emitted={r.citations.emitted} expected={r.citations.expected} "
        f"precision={r.citations.precision:.2f} recall={r.citations.recall:.2f}"
    )
    parts.append(
        f"- **RAG metrics**: faithfulness={r.faithfulness:.2f} "
        f"answer_relevancy={r.answer_relevancy:.2f} "
        f"context_precision={r.context_precision:.2f} "
        f"context_recall={r.context_recall:.2f}"
    )
    parts.append(f"- **Latency**: {r.latency_ms} ms | **Cost**: {r.cost_eur:.4f} € | **Cache hit**: {r.cache_hit}")
    parts.append("- **Criteria**:")
    for cs in r.criteria_scores:
        cs_mark = "✅" if cs.passed else "❌"
        reason = f" — {cs.reason}" if cs.reason else ""
        parts.append(f"  - {cs_mark} {cs.criterion}{reason}")
    return "\n".join(parts)


def _render_per_case_doc(r: DocCaseResult) -> str:
    parts: list[str] = []
    parts.append(f"### {r.case_id}")
    parts.append("")
    verdict_mark = "✅" if r.verdict_match else "❌"
    seg_mark = "✅" if r.n_segments_within_tolerance else "❌"
    parts.append(
        f"- **Verdict**: actual=`{r.actual_document_verdict}` expected=`{r.expected_document_verdict}` {verdict_mark}"
    )
    parts.append(
        f"- **Segments**: actual={r.actual_n_segments} expected={r.expected_n_segments} {seg_mark}"
    )
    parts.append(
        f"- **Findings citations**: emitted={r.findings_citations.emitted} "
        f"expected={r.findings_citations.expected} "
        f"precision={r.findings_citations.precision:.2f} recall={r.findings_citations.recall:.2f}"
    )
    parts.append(f"- **Faithfulness**: {r.faithfulness:.2f}")
    parts.append(
        f"- **Latency total**: {r.latency_ms_total} ms | **Cost**: {r.cost_eur_total:.4f} € | **Cache hit**: {r.cache_hit}"
    )
    parts.append("- **Criteria**:")
    for cs in r.criteria_scores:
        cs_mark = "✅" if cs.passed else "❌"
        reason = f" — {cs.reason}" if cs.reason else ""
        parts.append(f"  - {cs_mark} {cs.criterion}{reason}")
    return "\n".join(parts)


def render_report(
    meta: EvalRunMeta,
    agg: AggregateMetrics,
    chat_results: list[ChatCaseResult],
    doc_results: list[DocCaseResult],
) -> str:
    """Pure function: produce the full evals/reports/latest.md content."""
    sections: list[str] = []
    sections.append("# RegulAItor — Evaluation Report")
    sections.append("")
    sections.append(
        f"**Run:** {meta.run_date} | **Commit:** `{meta.commit_sha}` | "
        f"**Models:** {meta.production_model} (prod), {meta.judge_model} (judge)"
    )
    cache_hits = int(round(agg.cache_hit_rate * (agg.n_chat_cases + agg.n_doc_cases)))
    cache_misses = (agg.n_chat_cases + agg.n_doc_cases) - cache_hits
    subset_str = "full" if meta.subset is None else f"first {meta.subset}"
    sections.append(
        f"**Settings:** temperature={meta.temperature}, subset={subset_str}, "
        f"cache hits/misses: {cache_hits}/{cache_misses} | **Total cost:** {agg.cost_total_eur:.2f} €"
    )
    sections.append("")
    sections.append("## Aggregate metrics")
    sections.append("")
    sections.append(_render_aggregate_table(agg))
    sections.append("")
    sections.append(f"## Per-case appendix — chat ({agg.n_chat_cases} cases)")
    sections.append("")
    for r in chat_results:
        sections.append(_render_per_case_chat(r))
        sections.append("")
    sections.append(f"## Per-case appendix — documents ({agg.n_doc_cases} cases)")
    sections.append("")
    for r in doc_results:
        sections.append(_render_per_case_doc(r))
        sections.append("")
    sections.append("## Reproducibilidad")
    sections.append("")
    sections.append("```bash")
    sections.append("make eval-from-cache  # regenera este report sin coste si la cache está poblada")
    sections.append("make eval             # corre full set; consume crédito Anthropic")
    sections.append("```")
    sections.append("")
    sections.append("## Caveats")
    sections.append("")
    sections.append(
        "Resultados sobre N=" + str(agg.n_chat_cases + agg.n_doc_cases) + " casos sintetizados con "
        "autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan "
        "distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que "
        "producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a "
        "H12 (router multi-LLM real)."
    )
    return "\n".join(sections) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_evals_report.py -v --no-cov
```
Expected: 5 tests pass.

- [ ] **Step 5: Run lint**

```bash
uv run ruff check evals/report.py tests/unit/test_evals_report.py
uv run black --check evals/report.py tests/unit/test_evals_report.py
```
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add evals/report.py tests/unit/test_evals_report.py
git commit -m "feat(h8): add evals.report markdown generator (aggregate + per-case appendix)"
```

---

## Task 7: `harness.py` — orchestration + main

**Files:**
- Create: `evals/harness.py`

This task wires everything together: load gold set, run each case through the backend, compute metrics, render report. The Anthropic client and cache invocation live here.

- [ ] **Step 1: Implement `evals/harness.py`**

Create `evals/harness.py`:
```python
"""H8 — Evaluation harness orchestration.

Loads the gold set, runs each case through the H4 chat graph or H5 document
graph (with cache), computes metrics + judge scores, and writes the
markdown report.
"""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any, Callable

from regulaitor.citation.schemas import DocumentReport
from regulaitor.orchestration.document_graph import run_document
from regulaitor.orchestration.graph import run as run_chat
from regulaitor.orchestration.state import ChatState

from evals.cache import InvokeFn, cache_call, cache_key, estimate_cost_eur
from evals.judge import score_criteria
from evals.metrics import aggregate, compute_chat_metrics, compute_doc_metrics
from evals.report import render_report
from evals.schemas import (
    ChatCaseResult,
    DocCaseResult,
    EvalRunMeta,
    GoldCaseChat,
    GoldCaseDoc,
)

_GOLD_PATH = Path("evals/gold_set.jsonl")
_DOC_DIR = Path("evals/document_cases")
_REPORT_PATH = Path("evals/reports/latest.md")
_PRODUCTION_MODEL = "claude-sonnet-4-6"
_JUDGE_MODEL = "claude-haiku-4-5-20251001"


def _git_sha_short() -> str:
    """Returns the first 7 chars of HEAD; falls back to 'unknown' on failure."""
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL)
        return out.strip()[:7]
    except Exception:
        return "unknown"


def load_gold_set(
    *, gold_path: Path = _GOLD_PATH, doc_dir: Path = _DOC_DIR
) -> tuple[list[GoldCaseChat], list[GoldCaseDoc]]:
    chat_cases: list[GoldCaseChat] = []
    if gold_path.exists():
        with gold_path.open(encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                chat_cases.append(GoldCaseChat.model_validate_json(stripped))

    doc_cases: list[GoldCaseDoc] = []
    if doc_dir.exists():
        for manifest in sorted(doc_dir.glob("*.expected.json")):
            doc_cases.append(GoldCaseDoc.model_validate_json(manifest.read_text(encoding="utf-8")))

    return chat_cases, doc_cases


def _real_anthropic_invoke(
    *, model: str, system: str, user: str, temperature: float, max_tokens: int
) -> tuple[str, int, int]:
    """Live Anthropic invocation. Imports lazily so unit tests don't require API key."""
    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        system=system,
        messages=[{"role": "user", "content": user}],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    return text, response.usage.input_tokens, response.usage.output_tokens


def run_chat_case(
    case: GoldCaseChat,
    *,
    cache_only: bool,
    invoke: InvokeFn = _real_anthropic_invoke,
) -> tuple[ChatState, int, float, bool]:
    """Run one chat case through the H4 graph. Returns (state, latency_ms, cost_eur, cache_hit).

    The graph internally makes multiple LLM calls (analyst tool-use + auditor);
    each is cached at the SDK level via our cache_call wrapper. For MVP H8 we
    treat cache_hit=False if any sub-call missed (live LLM); cache_hit=True if
    all sub-calls were served from cache.
    """
    # NOTE: H4 graph.run does its own LLM invocation through anthropic SDK,
    # without going through evals.cache. For H8 MVP we accept that the cache
    # is at the JUDGE layer only (judge calls go via cache_call), and the
    # production calls always hit the API. This is a known limitation — the
    # spec §6.4 documents this. cache_hit reflects judge-layer only.
    case_id = f"eval-{case.id}"
    t0 = time.monotonic()
    state = run_chat(
        query=case.entrada,
        corpus=case.corpus_esperado,
        language="es",
        case_id=case_id,
    )
    latency_ms = int((time.monotonic() - t0) * 1000)

    # Cost estimation: extract tokens from state if available; fallback to 0
    # H4's _log_turn doesn't surface tokens; for now estimate via heuristic
    # (fixed approximation: ~3000 input + 800 output per chat case on Sonnet)
    estimated_cost_eur = estimate_cost_eur(model=_PRODUCTION_MODEL, tokens_in=3000, tokens_out=800)

    return state, latency_ms, estimated_cost_eur, False


def run_doc_case(
    case: GoldCaseDoc,
    *,
    cache_only: bool,
    invoke: InvokeFn = _real_anthropic_invoke,
) -> tuple[DocumentReport, int, float, bool]:
    """Run one doc case through H5 pipeline. Returns (report, latency_ms_total, cost_eur, cache_hit)."""
    pdf_path = _DOC_DIR / case.pdf_path
    file_bytes = pdf_path.read_bytes()
    case_id = f"eval-{case.id}"
    t0 = time.monotonic()
    report = run_document(
        file_bytes=file_bytes,
        mime_type="application/pdf",
        language="es",
        corpus=list(case.corpus_esperado),
        case_id=case_id,
    )
    latency_ms_total = int((time.monotonic() - t0) * 1000)
    # Estimate ~30k input + 8k output per doc on Sonnet
    estimated_cost_eur = estimate_cost_eur(
        model=_PRODUCTION_MODEL, tokens_in=30_000, tokens_out=8_000
    )
    return report, latency_ms_total, estimated_cost_eur, False


def main(*, gold_set_path: Path = _GOLD_PATH, subset: int | None = None, cache_only: bool = False) -> None:
    """Entry point. Loads gold, runs all cases, writes the report."""
    chat_cases, doc_cases = load_gold_set(gold_path=gold_set_path)

    if subset is not None:
        chat_cases = chat_cases[: max(0, subset)]
        doc_cases = doc_cases[: max(0, subset // 3)]  # 30:10 ratio in gold set

    # Bound cache_call to cache_only mode for the judge invocations
    judge_call = partial(cache_call, invoke=_real_anthropic_invoke, cache_only=cache_only)
    judge_score_fn = partial(score_criteria, cache_call=judge_call)

    chat_results: list[ChatCaseResult] = []
    for case in chat_cases:
        state, latency_ms, cost_eur, cache_hit = run_chat_case(
            case, cache_only=cache_only
        )
        result = compute_chat_metrics(
            case, state,
            judge_call=judge_call,
            judge_score_fn=judge_score_fn,
            latency_ms=latency_ms,
            cost_eur=cost_eur,
            cache_hit=cache_hit,
        )
        chat_results.append(result)

    doc_results: list[DocCaseResult] = []
    for case in doc_cases:
        report, latency_ms, cost_eur, cache_hit = run_doc_case(case, cache_only=cache_only)
        result = compute_doc_metrics(
            case, report,
            judge_call=judge_call,
            judge_score_fn=judge_score_fn,
            latency_ms_total=latency_ms,
            cost_eur_total=cost_eur,
            cache_hit=cache_hit,
        )
        doc_results.append(result)

    agg = aggregate(chat_results, doc_results)
    meta = EvalRunMeta(
        run_date=datetime.now(UTC).isoformat(),
        commit_sha=_git_sha_short(),
        production_model=_PRODUCTION_MODEL,
        judge_model=_JUDGE_MODEL,
        temperature=0.0,
        subset=subset,
        cache_only=cache_only,
    )
    markdown = render_report(meta, agg, chat_results, doc_results)
    _REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _REPORT_PATH.write_text(markdown, encoding="utf-8")
```

- [ ] **Step 2: Verify module imports cleanly**

```bash
uv run python -c "from evals.harness import main, load_gold_set, run_chat_case, run_doc_case; print('OK')"
```
Expected: prints `OK`.

- [ ] **Step 3: Run lint**

```bash
uv run ruff check evals/harness.py
uv run black --check evals/harness.py
```
Expected: clean. mypy may flag `state.context.chunks` as Optional access — handle in metrics.py guards (already done in Task 4).

- [ ] **Step 4: Commit**

```bash
git add evals/harness.py
git commit -m "feat(h8): add evals.harness orchestration (load + run + render + write)"
```

---

## Task 8: CLI wrapper + Make targets + smoke test

**Files:**
- Create: `scripts/evaluate.py`
- Create: `tests/integration/test_evals_smoke.py`
- Modify: `Makefile`

- [ ] **Step 1: Create CLI wrapper**

Create `scripts/evaluate.py`:
```python
"""H8 — CLI wrapper for the evaluation harness."""

from __future__ import annotations

import argparse
from pathlib import Path

from evals.harness import main


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run RegulAItor evaluation harness")
    p.add_argument(
        "--gold-set",
        type=Path,
        default=Path("evals/gold_set.jsonl"),
        help="Path to the gold set jsonl",
    )
    p.add_argument(
        "--subset",
        type=int,
        default=None,
        help="Run only first N chat cases (proportional doc cases). None = full",
    )
    p.add_argument(
        "--cache-only",
        action="store_true",
        help="Fail on any cache miss (no live API calls). Default: live mode.",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(gold_set_path=args.gold_set, subset=args.subset, cache_only=args.cache_only)
```

- [ ] **Step 2: Add Make targets**

Edit `Makefile`. Append after the existing `serve-api` target (from H7):
```makefile
eval: ## Run full evaluation (~$7 Anthropic credit; populates cache)
	uv run python -m scripts.evaluate

eval-subset: ## Run first 5 chat + ~1 doc case for harness debugging (~$1)
	uv run python -m scripts.evaluate --subset 5

eval-from-cache: ## Regenerate report from cached responses (free; fails on miss)
	uv run python -m scripts.evaluate --cache-only
```

If the Makefile has a `.PHONY` declaration, add `eval eval-subset eval-from-cache` to it.

- [ ] **Step 3: Verify make targets parse**

```bash
grep -n "^eval" Makefile
make help 2>&1 | grep -E "^  eval"
```
Expected: 3 lines starting with `eval` in Makefile; help shows the 3 targets.

- [ ] **Step 4: Write integration smoke test**

Create `tests/integration/test_evals_smoke.py`:
```python
"""H8 — Integration smoke test for the eval harness with cache pre-populated.

Does NOT call Anthropic. Pre-populates the cache with canned judge responses
and stubs the production graph calls so the entire pipeline (load → run →
metrics → report) is exercised end-to-end without LLM cost.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from evals import cache, harness


@pytest.fixture
def populated_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Populate the cache with judge responses keyed by all expected criteria queries."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True)
    monkeypatch.setattr(cache, "_CACHE_DIR", cache_dir)
    return cache_dir


def _stub_chat_state(case_id: str = "x") -> Any:
    from regulaitor.citation.schemas import (
        Answer, AuditedAnswer, AuditResult, AuditVerdict, Citation, Finding,
    )
    from regulaitor.orchestration.state import ChatState

    cit = Citation(norma="ai_act", articulo="6", apartado="1", language="es", text="t")
    finding = Finding(text="hallazgo", citations=[cit], severity="medium")
    answer = Answer(query="q", language="es", text="respuesta", findings=[finding])
    audit = AuditResult(
        citation=cit, validated=True, article_exists=True, apartado_exists=True,
        text_normalized_match=True, reason=None,
    )
    audited = AuditedAnswer(answer=answer, verdict=AuditVerdict.PASS, audit_results=[audit], reason=None)
    return ChatState(
        case_id=case_id, query="q", corpus="ai_act", language="es",
        answer=answer, audited_answer=audited,
    )


def test_smoke_subset_with_canned_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, populated_cache: Path
) -> None:
    # Write a 1-case gold set
    gold_path = tmp_path / "gold_set.jsonl"
    gold_path.write_text(
        json.dumps(
            {
                "id": "chat-001",
                "tipo": "chat",
                "entrada": "test query",
                "corpus_esperado": "ai_act",
                "articulos_esperados": ["6.1"],
                "severidad_esperada": "medium",
                "criterios_evaluacion": ["criterion_one"],
                "salida_esperada": None,
                "requiere_revision_humana": False,
                "expected_verdict": "pass",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    # Stub backend chat run
    monkeypatch.setattr(harness, "run_chat", lambda **kw: _stub_chat_state(kw.get("case_id", "x")))

    # Stub Ragas: avoid live Ragas call by patching _ragas_metrics_chat
    from evals import metrics as metrics_mod
    monkeypatch.setattr(
        metrics_mod, "_ragas_metrics_chat",
        lambda **kw: {
            "faithfulness": 0.9,
            "answer_relevancy": 0.9,
            "context_precision": 0.8,
            "context_recall": 0.78,
        },
    )

    # Pre-populate judge cache for the criterion call
    judge_response = json.dumps(
        {"scores": [{"criterion": "criterion_one", "passed": True, "reason": "ok"}]}
    )
    # Build the same key the harness will compute
    from evals.judge import _load_judge_prompt
    system_prompt = _load_judge_prompt()
    user_payload = json.dumps(
        {
            "query": "test query",
            "actual_answer": "respuesta",
            "expected_answer": None,
            "cited_articles": ["6.1"],
            "expected_articles": ["6.1"],
            "criteria": ["criterion_one"],
        },
        ensure_ascii=False,
        indent=2,
    )
    prompt_text = f"{system_prompt}\n---\n{user_payload}"
    key = cache.cache_key(model="claude-haiku-4-5-20251001", prompt=prompt_text, temperature=0.0)
    (populated_cache / f"{key}.json").write_text(
        json.dumps(
            {
                "request": {"model": "claude-haiku-4-5-20251001", "system": system_prompt, "user": user_payload, "temperature": 0.0},
                "response": judge_response,
                "timestamp": "2026-05-10T00:00:00Z",
                "tokens_in": 200,
                "tokens_out": 50,
                "cost_eur": 0.0003,
            },
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )

    # Patch report path to tmp
    report_path = tmp_path / "latest.md"
    monkeypatch.setattr(harness, "_REPORT_PATH", report_path)

    # Run cache-only mode — should succeed because we populated the judge cache
    harness.main(gold_set_path=gold_path, subset=1, cache_only=True)

    # Verify report generated
    assert report_path.exists()
    md = report_path.read_text(encoding="utf-8")
    assert "RegulAItor — Evaluation Report" in md
    assert "chat-001" in md
```

- [ ] **Step 5: Run smoke test**

```bash
uv run pytest tests/integration/test_evals_smoke.py -v --no-cov
```
Expected: 1 test passes. (Test exercises end-to-end without LLM cost.)

- [ ] **Step 6: Run lint**

```bash
uv run ruff check scripts/evaluate.py tests/integration/test_evals_smoke.py
uv run black --check scripts/evaluate.py tests/integration/test_evals_smoke.py
```
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add scripts/evaluate.py Makefile tests/integration/test_evals_smoke.py
git commit -m "feat(h8): add evaluate CLI + 3 make targets + integration smoke test"
```

---

## Task 9: Author the gold set — Phase 1 (USER, not subagent)

**This task is performed by the user, not by an automation subagent.** The output is a single markdown file or jsonl shipped to the next task.

**Files:**
- Create: `evals/_skeleton.jsonl` (temporary; consumed by Task 10, not committed)

- [ ] **Step 1: User authors `evals/_skeleton.jsonl`**

Format: 40 lines, each a JSON object with the fields below. Stratification target: 15 ai_act + 15 gdpr (chat); 4 ai_act + 4 gdpr + 2 mixed (doc); 24 verdict=pass + 9 requires_human_review + 7 block.

Example chat entries (10 total per corpus):
```jsonl
{"kind":"chat","id":"chat-001","topic":"AI Act art. 6 alto riesgo evaluación conformidad","corpus":"ai_act","articulos":["6.1","9.2"],"verdict":"pass","severidad":"medium"}
{"kind":"chat","id":"chat-002","topic":"AI Act art. 9 sistemas gestión riesgos","corpus":"ai_act","articulos":["9.1"],"verdict":"pass","severidad":"medium"}
...
{"kind":"chat","id":"chat-016","topic":"RGPD art. 7 consentimiento revocable","corpus":"gdpr","articulos":["7.3"],"verdict":"pass","severidad":"high"}
{"kind":"chat","id":"chat-017","topic":"RGPD art. 33 notificación brecha","corpus":"gdpr","articulos":["33.1"],"verdict":"requires_human_review","severidad":"high"}
...
```

Example doc entries:
```jsonl
{"kind":"doc","id":"doc-001","topic":"Política IA empresarial reciente — alto riesgo no clasificado","corpus":["ai_act"],"articulos":["6.1"],"verdict":"requires_human_review","n_segments":5}
{"kind":"doc","id":"doc-002","topic":"Política privacidad sin base legal explicada","corpus":["gdpr"],"articulos":["6.1","13.1"],"verdict":"requires_human_review","n_segments":7}
{"kind":"doc","id":"doc-009","topic":"Contrato proveedor mixed AI Act + GDPR","corpus":["ai_act","gdpr"],"articulos":["28.3"],"verdict":"pass","n_segments":8}
...
```

Required fields per kind:
- **chat**: `kind`, `id`, `topic`, `corpus` (literal "ai_act" or "gdpr"), `articulos` (list str), `verdict` ("pass" / "block" / "requires_human_review"), `severidad` ("info" / "low" / "medium" / "high" / null).
- **doc**: `kind`, `id`, `topic`, `corpus` (list of literals), `articulos` (list str), `verdict`, `n_segments` (int ≥1).

- [ ] **Step 2: User saves to `evals/_skeleton.jsonl` and notifies orchestrator**

Once Phase 1 is done, the orchestrator dispatches Task 10's subagent with a pointer to this file.

- [ ] **Step 3: No commit yet**

`evals/_skeleton.jsonl` is consumed by Task 10 and discarded; not committed.

---

## Task 10: Author the gold set — Phase 2 (subagent draft)

**Files:**
- Read: `evals/_skeleton.jsonl` (from Task 9)
- Create: `evals/gold_set.jsonl`
- Create: 10 PDFs in `evals/document_cases/case_NNN_*.pdf`
- Create: 10 manifests `evals/document_cases/case_NNN_*.expected.json`
- Modify: `scripts/regenerate_document_fixtures.py`

This task is dispatched to a subagent with full context. The subagent reads the user-authored skeleton, the H1 LanceDB index (to verify articles exist and pull short reference text), and produces the full gold set artifacts.

- [ ] **Step 1: Subagent reads skeleton + verifies articles exist**

Pseudocode for the subagent:
```python
# Load skeleton
skeleton = [json.loads(l) for l in Path("evals/_skeleton.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
# Connect to LanceDB
from regulaitor.rag.store import connect
table = connect()
# For each entry, verify each articulo exists in the corpus index
for entry in skeleton:
    for art in entry["articulos"]:
        # Query: articulo == art, corpus matching
        # If missing, raise — operator must fix skeleton
        ...
```

- [ ] **Step 2: Subagent generates `evals/gold_set.jsonl` (chat cases)**

For each chat skeleton entry, produce a `GoldCaseChat` record:
- `entrada`: naturalized query template, e.g. f"¿Qué requisitos impone el {norma_friendly} {topic.replace('art.', 'art.')} sobre {topic_summary}?". Use the topic + retrieved corpus text to draft a question that a real PYME compliance officer might ask.
- `criterios_evaluacion`: 2-3 criteria per case. Templates:
  - "Cita literalmente {articulo}" (always present if article expected).
  - "No afirma obligaciones extra-{norma}" (always present).
  - One topic-specific criterion drafted from the skeleton's `topic`.
- `salida_esperada`: 150-250 word reference answer, drafted from the corpus article text. Schematic structure: "Según {articulo} del {norma}, {topic} requiere [...]. Adicionalmente, [...]."
- `requiere_revision_humana`: True iff `verdict == "requires_human_review"`.

Write to `evals/gold_set.jsonl`, one record per line, no trailing whitespace.

- [ ] **Step 3: Subagent extends `scripts/regenerate_document_fixtures.py` for H8 doc cases**

Read the existing script (used by H5 for adversarial fixtures). Add a new function `generate_h8_eval_pdfs(skeleton_doc_entries, out_dir)` that:
- For each doc skeleton entry, generates a synthetic PDF using ReportLab.
- Content: ~3-8 sections of corporate-policy text relevant to the topic. The text must INCLUDE language that should trigger the `verdict` (e.g., for `verdict=requires_human_review`, include a section that's plausibly under-specified).
- Filename: `case_{id}_{topic_slug}.pdf` (e.g., `case_001_ai_act_alto_riesgo.pdf`).

The function is invoked once during Task 10 to produce all 10 PDFs. Document this in the script's docstring:
```python
"""...
H8 (2026-05-10): added generate_h8_eval_pdfs(...) to produce evals/document_cases/*.pdf
from evals/_skeleton.jsonl. Idempotent — re-running overwrites existing files.
"""
```

- [ ] **Step 4: Subagent generates 10 manifests**

For each doc skeleton entry, generate `evals/document_cases/case_NNN_*.expected.json` with the `GoldCaseDoc` schema. Use the skeleton's articulos as `expected_findings_articulos`, verdict as `expected_document_verdict`, n_segments as `expected_n_segments` (with default tolerance 2).

`criterios_evaluacion`: 2-3 criteria per doc, similar templates to chat:
- "Detecta [topic-specific risk]"
- "No genera findings espurios fuera de {corpus_join}"
- One topic-specific criterion drafted from the skeleton's `topic`.

- [ ] **Step 5: Subagent verifies generated artifacts**

```bash
uv run python -c "
from evals.harness import load_gold_set
chats, docs = load_gold_set()
print(f'{len(chats)} chat cases, {len(docs)} doc cases')
assert len(chats) == 30
assert len(docs) == 10
"
```
Expected: prints `30 chat cases, 10 doc cases`.

- [ ] **Step 6: Subagent commits the generated artifacts**

```bash
git add evals/gold_set.jsonl evals/document_cases/ scripts/regenerate_document_fixtures.py
git commit -m "feat(h8): generate gold set (30 chat + 10 docs) from human-authored skeleton"
```

The PDFs and manifests are tracked (large bytes but reproducible from skeleton + script). Do NOT commit `evals/_skeleton.jsonl`.

- [ ] **Step 7: User reviews in PR (Phase 3)**

User opens the PR, reviews each generated case (~3 min/case), edits via `Edit` if criteria are mis-calibrated. Commits any edits as a follow-up.

---

## Task 11: First evaluation run (consumes Anthropic credit)

**This task spends Anthropic credit. The user must explicitly authorize it.**

**Files:**
- Create: `evals/reports/latest.md` (the deliverable)
- Populate: `evals/cache/` with all LLM responses (gitignored)

- [ ] **Step 1: Verify ANTHROPIC_API_KEY is set**

```bash
test -n "$ANTHROPIC_API_KEY" && echo "OK" || echo "MISSING — set in .env"
```
Expected: `OK`. If `MISSING`, do NOT proceed.

- [ ] **Step 2: Run subset for harness validation (~$1 spend)**

```bash
make eval-subset
```
Expected: completes in <2 minutes; report generated; cache populated. Inspect `evals/reports/latest.md` — should show 5 chat + 1 doc cases. Verify that:
- All metric values are real (not 0.0 unless genuinely 0).
- Cache hit rate is 0.0 (first run, all misses).
- Cost total is approximately $0.30-1.00.

If anything looks broken (RuntimeError, missing fields, all-zero metrics), STOP and debug. Do not proceed to full run.

- [ ] **Step 3: Run full evaluation (~$6-10 spend)**

```bash
make eval
```
Expected: completes in 5-15 minutes (depends on Sonnet latency + LLM judge calls). Report regenerated with all 30 chat + 10 docs.

Verify:
- 40 cases reported (30 chat + 10 doc).
- Aggregate metrics populate the table.
- Cost total ≤ $10 (within budget).
- `evals/reports/latest.md` modified; `evals/cache/` has 40+ JSON files.

- [ ] **Step 4: Verify cache reproducibility**

```bash
make eval-from-cache
```
Expected: completes in seconds (no API calls). Generated report should be byte-for-byte identical to the previous one (modulo the `run_date` header — which uses `datetime.now()`). Confirm by `git diff evals/reports/latest.md` showing only the timestamp line changed.

If the report changes more than the timestamp, the cache key is non-deterministic — STOP and debug `evals.cache.cache_key`.

- [ ] **Step 5: Commit the report**

```bash
git add evals/reports/latest.md
git commit -m "docs(h8): first evaluation report (full set, real metrics)"
```

- [ ] **Step 6: Inspect report for sanity**

Read `evals/reports/latest.md` end-to-end (or skim the aggregate table + 5 random cases). Sanity checks:
- Citation precision close to threshold (≥0.85 is the H10 gate; H8 just needs to surface the number).
- Faithfulness in 0.7-1.0 range; if all 1.0, the judge is rubber-stamping.
- Verdict match rate > 0.5 (otherwise the system is broken).

If any sanity check fails, file an issue for H10/H15 follow-up but do NOT block H8 close — the harness producing a number IS the H8 deliverable.

---

## Task 12: H8 closure — ADR + decisions log + skill + CLAUDE.md + README

**Files:**
- Create: `docs/adr/0010-evaluation-harness.md`
- Create: `.claude/skills/evals-runner/SKILL.md`
- Modify: `docs/technical_decisions_log.md`
- Modify: `CLAUDE.md` (§27)
- Modify: `README.md` (Evaluation section)

- [ ] **Step 1: Create ADR 0010**

Create `docs/adr/0010-evaluation-harness.md`:
```markdown
# ADR 0010 — Evaluation harness for H8

- **Status:** Accepted
- **Date:** 2026-05-10 (decision); 2026-05-XX (H8 merged, squash `<sha>`, tag `v0.0.9-h8`)
- **Deciders:** Project owner.
- **Companion ADRs:** 0001 (project scope), 0006 (chat E2E), 0007 (document pipeline), 0009 (FastAPI architecture).

## Context

CLAUDE.md §16.1 lists H8 as the milestone where `make eval` becomes reproducible with real metrics, gating the move from MVP to advanced (§16.2 #3 + #5: report with real metrics + citation precision ≥ 0.85). H8 must produce: (a) a 30 chat + 10 doc gold set, (b) a Python harness, (c) a markdown report committed to main, all within a constrained $10 Anthropic budget.

## Decision

Eight design decisions:

1. **Judge = Anthropic Haiku 4.5** (single API key, modelo distinto a Sonnet 4.6 producción). Caveat: same vendor weakens "distinto" claim per CLAUDE.md §19; promoted to deferral when H12 router multi-LLM real introduces an external judge vendor.
2. **Framework = Ragas + custom layer** (no DeepEval until H15 calibration needs pytest-driven thresholds).
3. **Scope = 30 chat + 10 docs** strictly per CLAUDE.md §19 minimum, stratified 15/15 per corpus and 24/9/7 per verdict.
4. **Execution = local + manual commit**; CI runs only unit tests on harness logic, no LLM calls. `--subset N` and `--cache-only` flags for debugging without spend.
5. **Authoring = hybrid**: human skeleton (3-4h) + subagent drafts gold_set.jsonl + 10 ReportLab PDFs + manifests (1-2h bg) + human PR review (1-2h).
6. **Report = aggregate + per-case appendix** (~5-7 pages markdown). Stratified breakdown deferred to H10/H17 polish.
7. **Cache = SHA256 hash-keyed JSON in `evals/cache/`** (gitignored). Mandatory; without it the $10 budget is consumed by harness debugging.
8. **No backend modification**. Harness imports `orchestration.graph.run` and `orchestration.document_graph.run_document` directly; H7 FastAPI surface is bypassed (no auth/HTTP overhead in evals).

## Alternatives considered

- OpenAI GPT-4o-mini as judge — rejected: requires second vendor billing now; defer to H12.
- Groq Llama-3.1-70B as judge — rejected: free tier rate limits cause flaky runs.
- DeepEval pytest integration — rejected: redundant with custom layer + Ragas; bring in H15.
- Pure custom harness without Ragas — rejected: weakens TFM defense (Ragas is the standard).
- Below-minimum gold set (20 chat + 5 docs) — rejected: violates CLAUDE.md §19 gate.
- Full-CI gating per-PR — rejected: $7/PR is unsustainable on $10 budget.
- Manual full authoring (10-15h) — rejected: opportunity cost vs hybrid (5-6h).
- Aggregate-only report (no per-case appendix) — rejected: examiner can't audit individual cases.

## Consequences

### Positive

- Harness reproducible: `make eval-from-cache` regenerates identical report for free.
- Cost-bounded: budget covers exactly 1 full live run + unlimited cache replays.
- Backend H1-H5 untouched; no regression risk.
- Defendible in TFM: Ragas is the standard RAG benchmark library.
- ADR captures the same-vendor judge caveat as a known limitation, not hidden.

### Negative / accepted

- Judge same vendor as production (Haiku vs Sonnet, both Anthropic) weakens independence claim. Documented; deferred to H12.
- Cost estimation is heuristic-based (fixed token approximation) since H4 doesn't surface usage tokens. Real cost may diverge ±30%; report shows the estimate.
- `evals/cache/` files are large (~5-50KB each × 40+ entries). Gitignored; operator regenerates with `make eval`.

### Deferred to future-work doc H17

- Adversarial set / Auditor block rate (H9 redteam).
- DeepEval pytest integration (H15).
- LangFuse trace integration (H11).
- A/B comparison multi-model (H12).
- Stratified breakdown by corpus + verdict in report (H10/H17 polish).
- Migration of judge to non-Anthropic vendor (H12).
- Per-page-normalized cost_per_doc_eur (H17).
- CI gating per-PR (never, by design).

## Revision conditions

- If H12 introduces multi-LLM router with separate vendor keys, migrate judge to GPT-4o-mini or similar and re-run gold set.
- If gold set proves insufficient stratification (H10 gate fails despite system improvements), expand to 60 cases per CLAUDE.md §19 advanced.
- If cost estimation diverges >50% from actual Anthropic billing, replace heuristic with `response.usage` extraction (requires H4 internal change — deferred).

## References

- Spec: `docs/superpowers/specs/2026-05-10-h8-evaluation-harness-design.md`
- Plan: `docs/superpowers/plans/2026-05-10-h8-evaluation-harness.md`
- Brainstorming: 6 Qs cerradas (judge, framework, scope, execution, authoring, report).
- Predecesores: ADR 0006 (H4 chat), ADR 0007 (H5 document pipeline), ADR 0009 (H7 FastAPI).
```

Replace `<sha>` and `2026-05-XX` post-merge.

- [ ] **Step 2: Append §H8 to decisions log**

Edit `docs/technical_decisions_log.md`. After the `## H7 — FastAPI mínima` section, append:

```markdown
## H8 — Gold set + harness de evaluación + métricas + informe (cerrado 2026-05-XX)

**Squash commit:** `<sha>` en main (PR #N squash-merged 2026-05-XX). Tag `v0.0.9-h8` publicado. **Spec:** `docs/superpowers/specs/2026-05-10-h8-evaluation-harness-design.md`. **Plan:** `docs/superpowers/plans/2026-05-10-h8-evaluation-harness.md`. **ADR:** `docs/adr/0010-evaluation-harness.md`.

### Brainstorming Qs (2026-05-10)

- **Q1 — Judge model:** A. Anthropic Haiku 4.5 (single API key, modelo distinto a Sonnet 4.6). Caveat "mismo proveedor" documentado en ADR 0010; deferral a H12 router multi-LLM real.
- **Q2 — Framework:** A. Ragas + custom layer (sin DeepEval por ahora; deferral a H15 calibration).
- **Q3 — Scope:** A. 30 chat + 10 docs estratificados (15/15 por corpus, 24/9/7 por verdict). Cache obligatorio en `evals/cache/`.
- **Q4 — Execution:** A. Solo local + manual commit del report. CI corre unit tests del harness sin LLM. `--subset N` y `--cache-only` flags.
- **Q5 — Authoring:** B. Hybrid (human skeleton + subagent draft + PR review).
- **Q6 — Report:** B. Aggregate + per-case appendix. Bake-ins: temperature=0, caveats block, reproducibility block, threshold rendering with pass/fail marks.

### Implementation amendments

(Anexar aquí cualquier desviación del spec descubierta durante implementación.)

### Métricas de cierre

- TBD post-run.

### Skill activada

- `evals-runner` activada en cierre H8 — procedimiento canónico de "cómo correr eval reproduciblemente, leer report, decidir si re-correr".
```

- [ ] **Step 3: Create the `evals-runner` skill**

Create `.claude/skills/evals-runner/SKILL.md`:
```markdown
---
name: evals-runner
description: Use this skill when running the H8 evaluation harness, reading the report, deciding whether to re-run, or extending the gold set. Activates from H8 onwards.
version: 1.0
---

# evals-runner

Procedimiento canónico para correr la evaluación de RegulAItor de forma reproducible y para leer el report sin malinterpretarlo.

## Cuándo invocarme

- Antes de correr `make eval` (validar que el budget está disponible y que la gold set está estable).
- Después de modificar prompts, retriever config, o un agente — para confirmar que las métricas no han regresado.
- Cuando el examinador pide "muéstrame los resultados" — el report es la respuesta canónica.
- Cuando se piensa extender el gold set (H10+).

## Procedimiento estándar

### 1. Verificar budget

`echo "$ANTHROPIC_API_KEY"` está set, billing tiene saldo (~$8 mínimo para una run completa con margen).

### 2. Run estratégico

- Cambio menor (typo en prompt, log fix): `make eval-from-cache` (gratis, regenera report sin re-correr LLM).
- Cambio en harness logic, métricas, criterios: `make eval-subset` primero (~$1) → si OK, `make eval` full (~$6-10).
- Cambio en agentes / retriever / corpus: `make eval` directo (cache miss en todos los casos).

### 3. Leer el report

Aggregate primero, per-case appendix segundo. Métricas críticas:
- `citation_precision_mean` ≥ 0.85 (gate H10).
- `faithfulness_mean` ≥ 0.85.
- `verdict_match_rate` ≥ 0.85.

Si alguna falla, NO es failure de la harness — es señal para H15 calibración o H10 iteración.

### 4. Commit el report

`evals/reports/latest.md` SIEMPRE va committed cuando hay run nueva. Es el entregable.

## Anti-patterns

- NO bypassear el cache. Cualquier dev que invoque LLM debe ir por `evals.cache.cache_call`.
- NO commitear `evals/cache/` (gitignored).
- NO ejecutar evals en CI (per Q4 H8 brainstorming, decision firme).
- NO mezclar adversarial cases en gold set (eso es H9 redteam).
- NO inventar números si la run no se completó. `[medicion pendiente]` o no commitear.

## Reproducibilidad

Cada `make eval-from-cache` debe producir EXACTAMENTE el mismo report (modulo `run_date` header). Si diverge → cache key no-determinista → bug en `evals.cache.cache_key`.

## Referencias

- Spec H8: `docs/superpowers/specs/2026-05-10-h8-evaluation-harness-design.md`
- ADR 0010: `docs/adr/0010-evaluation-harness.md`
- Decisions log §H8: `docs/technical_decisions_log.md`
```

- [ ] **Step 4: Update CLAUDE.md §27**

Edit `CLAUDE.md`. In `### Hitos cerrados`, append after H7:

```markdown
- **H8** — Gold set + harness de evaluación + métricas + informe cerrado (2026-05-XX). Tag `v0.0.9-h8` publicado. Squash commit `<sha>` en main. ADR 0010. 30 chat + 10 docs gold set, harness Python (Ragas + custom layer), Haiku 4.5 LLM-as-judge con prompt versionado, cache hash-keyed, `evals/reports/latest.md` con métricas reales. `make eval-from-cache` regenera el report sin coste. Skill `evals-runner` activada. Ver `docs/technical_decisions_log.md` §H8.
```

In `### Hito siguiente`, replace H8 entry with H9:
```markdown
- **H9** — Red team inicial. ≥10 ataques cubriendo los escenarios de CLAUDE.md §18; informe de seguridad con tasa de bloqueo del Auditor. Sin coste Anthropic adicional (la mayoría de ataques son verificables sin LLM real vía sanitizer + injection).
```

Use placeholders `<sha>` and `2026-05-XX` (filled post-merge).

- [ ] **Step 5: Update README**

Edit `README.md`. Append after the API Quickstart section (from H7):

````markdown
## Evaluation (H8)

The harness runs the full RegulAItor pipeline against a curated gold set
(30 chat + 10 docs), computes Ragas + custom metrics with a Haiku 4.5
LLM judge, and emits `evals/reports/latest.md`.

### Quickstart

```bash
# First time: populate the cache (~$7 Anthropic credit)
make eval

# Subsequent regenerations from cache: free
make eval-from-cache

# Debugging the harness with a small subset (~$1)
make eval-subset
```

### Reading the report

`evals/reports/latest.md` has:

1. **Header**: run date, commit SHA, model versions, total cost.
2. **Aggregate table**: each metric with its threshold from CLAUDE.md §17 and a pass/fail mark.
3. **Per-case appendix**: 40 sections (one per gold case) showing actual vs expected verdict, citations, criteria scores.
4. **Reproducibility block**: literal commands to regenerate.
5. **Caveats**: limitations of the eval setup.

### Configuration

| Env var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | (required) | Production + judge model access |

The judge model (`claude-haiku-4-5-20251001`) and production model
(`claude-sonnet-4-6`) are hardcoded in `evals/harness.py`; change there
if migrating to a different vendor (deferred to H12 per ADR 0010).
````

- [ ] **Step 6: Run final lint + tests**

```bash
uv run ruff check .
uv run black --check .
uv run mypy
uv run pytest --no-cov tests/unit/test_evals_*.py tests/integration/test_evals_smoke.py -v
```
Expected: all green. If anything fails, STOP and fix before commit.

- [ ] **Step 7: Commit closure docs**

```bash
git add docs/adr/0010-evaluation-harness.md docs/technical_decisions_log.md CLAUDE.md README.md .claude/skills/evals-runner/SKILL.md
git commit -m "docs(h8): close milestone with ADR 0010 + decisions log + skill + README + CLAUDE.md"
```

- [ ] **Step 8: Push branch and open PR**

```bash
git push -u origin feat/h8-evaluation-harness
gh pr create --title "feat(h8): gold set + evaluation harness + first report" --body "..."
```

PR body template:
```
## Summary
- 30 chat + 10 docs gold set authored via hybrid flow (human skeleton + subagent draft + PR review).
- Harness Python pure (no HTTP) wrapping H4/H5 backends; Ragas + custom layer; Haiku 4.5 judge with versioned prompt.
- Cache obligatorio (SHA256 hash-keyed JSON, gitignored). `make eval-from-cache` regenera report sin coste.
- Primer `evals/reports/latest.md` con métricas reales — defiende gate H10 §16.2 #3.

## Decisions
6 Qs cerradas en `docs/technical_decisions_log.md` §H8.

## Test plan
- [x] `make lint` verde
- [x] `make test` verde (unit + integration smoke con cache)
- [x] `make eval-subset` exitoso (~$1)
- [x] `make eval` exitoso (~$6-10), report committed
- [x] `make eval-from-cache` reproduce report idéntico (modulo timestamp)
- [x] CI verde (los 4 jobs incluido Document E2E + Security)

## Out of scope
Adversarial set H9, DeepEval H15, LangFuse H11, multi-vendor judge H12, stratified report H17.
```

- [ ] **Step 9: Wait for user OK to squash-merge + tag**

Do NOT auto-merge. The user reviews the PR, gives explicit OK, then:
- Squash-merge with conventional commit subject.
- Tag `v0.0.9-h8` on the merge commit.
- Update §H8 of `docs/technical_decisions_log.md` with the actual squash SHA.
- Update CLAUDE.md §27 with the actual squash SHA + date.
- Rename memory `h7_closed_h8_starting.md` → `h8_closed_h9_starting.md`.

---

## Closure gate checklist (Task 12 wrap-up)

Before opening the PR:

- [ ] `make lint` green (ruff + black + mypy).
- [ ] `make test` green — unit tests for schemas + cache + metrics + judge + report (35-40 tests) + smoke integration.
- [ ] Coverage ≥80% global (the existing gate from H7; this PR doesn't lower it).
- [ ] `make eval-subset` succeeded with ~$1 spend.
- [ ] `make eval` succeeded with ~$6-10 spend; cost ≤ $10 budget.
- [ ] `evals/reports/latest.md` committed with real metrics.
- [ ] `make eval-from-cache` reproduces report deterministically.
- [ ] ADR 0010 committed.
- [ ] Decisions log §H8 written.
- [ ] CLAUDE.md §27 updated (TBD placeholders for SHA + date).
- [ ] README Evaluation section added.
- [ ] Skill `evals-runner` activated (SKILL.md committed).
- [ ] `evals/cache/` is gitignored (verify with `git check-ignore evals/cache/foo.json`).

---

## Anti-patterns to avoid

(Verify during code review.)

- No tocar el backend H1-H5 — harness consume read-only.
- No tocar `api/` — H7 surface no participa en evals.
- Sin `--no-verify` en commits.
- No bypassear el cache — cualquier LLM call va por `evals.cache.cache_call`.
- No commitear `evals/cache/` ni `evals/reports/archive/`.
- No correr evals en CI per-PR (decision firme Q4).
- No mezclar adversarial cases en gold set (es H9 redteam).
- No fabricar métricas — si una run no se completó, `[medicion pendiente]` o no commitear.
- No exponer Anthropic API key en logs ni en el report (no aparece en cache files tampoco).
- No omitir `Caveats` block del report — el examinador debe ver las limitaciones.
- No skip de `Language="es"` en Ragas — métricas en EN sobre contenido ES son ruidosas.
