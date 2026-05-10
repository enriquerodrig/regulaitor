# H7 — FastAPI mínima (`/ask`, `/analyze`, `/health`) — Design

**Status:** approved (brainstorming closed 2026-05-08)
**Milestone:** H7
**Predecessor:** H6 (Streamlit MVP, tag `v0.0.7-h6`, squash `e53f295`)
**Successor:** H8 (gold set + evals)
**ADR:** 0009 (to be created during implementation)

---

## 1. Goal

Cerrar H7 entregando una FastAPI mínima con tres endpoints (`POST /ask`, `POST /analyze`, `GET /health`) que envuelve sin tocar los pipelines existentes H4 (`orchestration.graph.run`) y H5 (`orchestration.document_graph.run_document`), con auth Bearer token estático, rate limiting por-token configurable, exception handlers globales con redacción SSDLC, schemas DTO explícitas y una capa de logging que extiende los `_log_turn` / `_log_document_turn` existentes con campos HTTP-level.

**Narrativa ancla** (CLAUDE.md §5.3 + §6): la API es la tercera superficie del producto y la única que un tutor TFM puede consumir programáticamente. Debe transmitir las mismas garantías que la UI (no citation, no answer; SSDLC visible; defensa en profundidad) y exponer las verdades del Auditor sin filtrar metadata interna que un atacante podría usar para iterar evasiones.

## 2. Context

### 2.1 Estado heredado de H6

- **Backend H1-H5 estable.** `run(query, corpus, language, case_id) -> ChatState` y `run_document(file_bytes, mime_type, language, corpus, case_id) -> DocumentReport`. H7 NO los modifica.
- **Schemas estables** (Pydantic v2, `frozen=True, extra="forbid"`): `ChatState` (mutable container), `Citation`, `Finding`, `Answer`, `AuditedAnswer`, `AuditResult`, `AuditVerdict`, `Context`, `RawDocument`, `SanitizedDocument`, `Segment`, `SegmentResult`, `DocumentReport`, `SanitizerEvent`, `DocumentBlockedError`.
- **Excepciones tipadas en backend:** `DocumentBlockedError` (sanitizer critical → backend lo levanta y `run_document` ya construye `DocumentReport` con `verdict=REQUIRES_HUMAN_REVIEW`); anti-injection actual usa `injection_blocked` + `injection_reason` en `ChatState` (no excepción). Ver §3.4 cómo H7 traduce ambos.
- **UI Streamlit operativa** (H6): `make serve` arranca app de dos pestañas. NO consume API; llama a `run()` / `run_document()` directamente. H7 NO cambia esto; eventual integración UI→API queda fuera de alcance.
- **`security/allowlist.py`** con 5 dominios EU oficiales (eur-lex, boe, digital-strategy.ec, edpb, data.europa.eu). H7 NO extiende este módulo (ver Q3 brainstorming: opción C URL-based descartada).
- **`.env`** con `ANTHROPIC_API_KEY` slot. Cuenta sin créditos al cierre H6; H7 NO requiere créditos (tests usan backend fakes; smoke manual con LLM real esperará a H8).
- **CI verde, 418 fast + 2 slow + 3 AppTest smoke, ~92% coverage.** H7 añade tests que no requieren créditos.

### 2.2 H7 deliverables (per CLAUDE.md §16.1 + §11)

1. `src/regulaitor/api/main.py` — entry point FastAPI con OpenAPI auto-config, lifespan, exception handlers.
2. `src/regulaitor/api/auth.py` — Bearer token validation con `hmac.compare_digest`.
3. `src/regulaitor/api/routes_ask.py` — `POST /ask`.
4. `src/regulaitor/api/routes_analyze.py` — `POST /analyze` con `UploadFile`.
5. `src/regulaitor/api/routes_health.py` — `GET /health` readiness completo.
6. `src/regulaitor/api/schemas.py` — DTOs explícitas + converters backend→DTO.
7. `src/regulaitor/api/errors.py` — exception handlers + ErrorResponse.
8. `src/regulaitor/api/logging.py` — extiende `_log_turn` / `_log_document_turn` con HTTP fields.
9. `src/regulaitor/security/rate_limit.py` (NEW) — slowapi config + key func por `token_hash`.
10. Tests contract con schemathesis + integration httpx + unit por módulo.
11. `make serve-api` target.
12. ADR 0009 + decisions log §H7 + CLAUDE.md §27 + README sección API quickstart.

## 3. Architecture overview

### 3.1 Estructura de archivos (NEW)

```
src/regulaitor/api/
├── __init__.py
├── main.py                  (FastAPI app, lifespan, exception handlers, slowapi setup)
├── auth.py                  (verify_token dependency, hmac.compare_digest)
├── routes_ask.py            (POST /ask)
├── routes_analyze.py        (POST /analyze)
├── routes_health.py         (GET /health)
├── schemas.py               (DTOs: AskRequest, AskResponse, AnalyzeResponse, ErrorResponse, HealthResponse, converters)
├── errors.py                (exception handler functions, EXCEPTION_MAP)
└── logging.py               (extend _log_turn/_log_document_turn with HTTP fields)

src/regulaitor/security/
└── rate_limit.py            (Limiter instance + key_func + env var loaders)

tests/
├── contract/test_api_schemathesis.py
├── integration/test_api_ask.py
├── integration/test_api_analyze.py
├── integration/test_api_health.py
├── unit/test_api_auth.py
├── unit/test_api_rate_limit.py
├── unit/test_api_errors.py
└── unit/test_api_schemas.py
```

### 3.2 Diagrama de flujo

```
┌──────────────────────────────────────────────────────────────────────┐
│ FastAPI app (main.py)                                                 │
│  ├─ lifespan: load REGULAITOR_API_TOKEN; fail fast if missing         │
│  ├─ slowapi Limiter mounted (key_func = request.state.token_hash)     │
│  ├─ exception handlers registered (errors.py)                         │
│  └─ routes mounted: /ask, /analyze, /health                           │
└─────────┬──────────────────────────────┬─────────────────────────────┘
          │                              │
   /ask, /analyze (auth + rate)    /health (no auth, no rate)
          │                              │
          ▼                              ▼
  ┌─────────────────┐            ┌─────────────────────────┐
  │ verify_token    │            │ readiness checks        │
  │ (Depends)       │            │  - lancedb reachable    │
  │  - read header  │            │  - anthropic_key set    │
  │  - compare_     │            │  - corpus_index >0 chunks│
  │    digest       │            └─────────────────────────┘
  │  - inject hash  │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │ slowapi limit   │
  │  (per-token)    │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────────────────┐
  │ route handler                                                │
  │  ├─ Pydantic validation (AskRequest / multipart UploadFile) │
  │  ├─ generate case_id (api-ch-... / api-doc-...)             │
  │  ├─ call backend run() or run_document()                     │
  │  ├─ convert backend model → DTO (schemas.py converter)      │
  │  ├─ log via logging.py (HTTP fields + backend fields)       │
  │  └─ return DTO (FastAPI serializes)                          │
  └─────────────────────────────────────────────────────────────┘

  Exception path:
  Any raised exception → registered handler in errors.py → log + return ErrorResponse
```

### 3.3 Dependencias entre módulos

- `main.py` → `auth.py` (mount Depends), `routes_*.py` (mount routers), `errors.py` (register handlers), `security.rate_limit` (mount Limiter).
- `routes_*.py` → `schemas.py` (DTO models + converters), `auth.py` (Depends), `security.rate_limit` (decorator), backend `orchestration.graph.run` / `orchestration.document_graph.run_document`, `logging.py` (log records).
- `errors.py` → `schemas.py` (ErrorResponse), backend exceptions (`DocumentBlockedError`, etc.), `logging.py`.
- `logging.py` → backend `orchestration.graph._log_turn` patterns (importa o reproduce campos), Python `logging` stdlib.
- `security.rate_limit` → slowapi `Limiter`, `request.state.token_hash`.

### 3.4 Mapeo backend → API

| Backend signal | API translation |
|---|---|
| `run()` retorna `ChatState` con `injection_blocked=True` | `routes_ask` levanta `InjectionDetected` (custom exception); handler global mapea a 400 |
| `run()` retorna `ChatState` con `audited_answer` | converter → `AskResponse`, status 200 |
| `run()` retorna `ChatState` con `errors` no vacío | converter detecta y levanta `BackendError` (custom); handler 500 con `case_id` y `error_code` |
| `run_document()` levanta `DocumentBlockedError` (sanitizer critical) | handler global mapea a 422 con `error_code="document_blocked"` |
| `run_document()` retorna `DocumentReport` | converter → `AnalyzeResponse`, status 200 |
| `anthropic.AuthenticationError` levantada por Analyst | handler global → 502 (config server-side issue) |
| `anthropic.BadRequestError` con "credit balance" | handler global → 503 con `error_code="anthropic_billing"` |
| `slowapi.errors.RateLimitExceeded` | handler global → 429 con `Retry-After` header |
| `fastapi.exceptions.RequestValidationError` (Pydantic) | handler global → 422 con `error_code="validation"`, sin trace |
| Cualquier otra `Exception` | handler genérico → 500 con `"Internal server error. Reference: {case_id}"`, sin trace |

`InjectionDetected` y `BackendError` son nuevas excepciones definidas en `api/errors.py` (no modifican backend).

## 4. Components

### 4.1 `main.py` (entry point)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded

from regulaitor.api import auth, errors, logging as api_logging
from regulaitor.api.routes_ask import router as ask_router
from regulaitor.api.routes_analyze import router as analyze_router
from regulaitor.api.routes_health import router as health_router
from regulaitor.citation.schemas import DocumentBlockedError
from regulaitor.security.rate_limit import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast if REGULAITOR_API_TOKEN missing (mirrors H6 ANTHROPIC_API_KEY guard)
    auth.load_api_token_or_raise()
    yield


app = FastAPI(
    title="RegulAItor API",
    version="0.0.8",
    description="Multi-agent regulatory compliance API. No citation, no answer.",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, errors.rate_limit_handler)
app.add_exception_handler(errors.InjectionDetected, errors.injection_handler)
app.add_exception_handler(errors.FileSizeExceeded, errors.file_size_handler)
app.add_exception_handler(errors.UnsupportedMediaType, errors.unsupported_media_handler)
app.add_exception_handler(errors.BackendError, errors.backend_error_handler)
app.add_exception_handler(DocumentBlockedError, errors.document_blocked_handler)
# Anthropic SDK exceptions registered dynamically (lazy import to avoid forcing dep at startup)
errors.register_anthropic_handlers(app)
# Generic catch-all (LAST)
app.add_exception_handler(Exception, errors.generic_handler)

app.include_router(health_router)
app.include_router(ask_router)
app.include_router(analyze_router)
```

### 4.2 `auth.py`

```python
import hashlib
import hmac
import os
from fastapi import Header, HTTPException, Request

_API_TOKEN: str | None = None


def load_api_token_or_raise() -> None:
    global _API_TOKEN
    token = os.getenv("REGULAITOR_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "REGULAITOR_API_TOKEN missing or empty. Set it in .env before starting the API."
        )
    if len(token) < 16:
        raise RuntimeError(
            "REGULAITOR_API_TOKEN must be at least 16 characters (entropy guard)."
        )
    _API_TOKEN = token


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


async def verify_token(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    if _API_TOKEN is None:
        # Should be unreachable: lifespan loads token; double-check.
        raise HTTPException(status_code=500, detail="API token not loaded")
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    presented = authorization[len("Bearer "):].strip()
    if not hmac.compare_digest(presented, _API_TOKEN):
        raise HTTPException(status_code=401, detail="Invalid API token")
    request.state.token_hash = _token_hash(presented)
```

Notas:
- `len < 16` guard previene tokens débiles accidentales (≥16 chars ≈ ≥96 bits para alfabeto base64url).
- `hmac.compare_digest` previene timing attacks comparando byte a byte en tiempo constante.
- 401 mensajes son genéricos ("Missing", "Invalid") — no diferencian "no había header" vs "header inválido" para no dar pistas.
- `request.state.token_hash` consumido por rate-limit key_func y por logging.

### 4.3 `routes_ask.py`

```python
import os
import time
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from nanoid import generate

from regulaitor.api.auth import verify_token
from regulaitor.api.errors import InjectionDetected, BackendError
from regulaitor.api.logging import log_api_chat_turn
from regulaitor.api.schemas import AskRequest, AskResponse, to_ask_response
from regulaitor.orchestration.graph import run
from regulaitor.security.rate_limit import limiter

router = APIRouter(tags=["chat"])


def _generate_case_id() -> str:
    return f"api-ch-{datetime.utcnow():%Y%m%d}-{generate(size=8)}"


@router.post("/ask", response_model=AskResponse)
@limiter.limit(lambda: os.getenv("REGULAITOR_RATE_LIMIT_ASK", "30/minute"))
async def ask(
    request: Request,
    payload: AskRequest,
    _: None = Depends(verify_token),
) -> AskResponse:
    case_id = _generate_case_id()
    request.state.case_id = case_id
    t0 = time.monotonic()
    state = run(
        query=payload.query,
        corpus=payload.corpus,
        language=payload.language,
        case_id=case_id,
    )
    response_time_ms = int((time.monotonic() - t0) * 1000)
    if state.injection_blocked:
        raise InjectionDetected(case_id=case_id, reason_code="injection_blocked")
    if state.audited_answer is None or state.errors:
        raise BackendError(case_id=case_id, errors=list(state.errors))
    response = to_ask_response(state, response_time_ms=response_time_ms)
    log_api_chat_turn(request, state, response)
    return response
```

Notas:
- Rate limit value es leído lazy desde env por cada request (permite override en tests sin restart).
- `_generate_case_id` genera `api-ch-YYYYMMDD-{nanoid:8}` (mismo patrón que H6 UI con prefix `api-`).
- `injection_blocked` y `errors` traducidos a excepciones tipadas → handlers globales.
- Loggin se emite en path success; path error se logea en handler.

### 4.4 `routes_analyze.py`

```python
import os
import time
from datetime import datetime
from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from nanoid import generate

from regulaitor.api.auth import verify_token
from regulaitor.api.errors import FileSizeExceeded, UnsupportedMediaType
from regulaitor.api.logging import log_api_document_turn
from regulaitor.api.schemas import AnalyzeResponse, to_analyze_response
from regulaitor.orchestration.document_graph import run_document
from regulaitor.security.rate_limit import limiter

router = APIRouter(tags=["document"])


def _max_bytes() -> int:
    """Read at call time so tests can override via monkeypatch.setenv before the request."""
    return int(os.getenv("REGULAITOR_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))


def _generate_case_id() -> str:
    return f"api-doc-{datetime.utcnow():%Y%m%d}-{generate(size=8)}"


def _detect_mime(filename: str, head: bytes) -> str:
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    lower = filename.lower()
    if lower.endswith(".md") or lower.endswith(".markdown"):
        return "text/markdown"
    raise UnsupportedMediaType(reason="unsupported file format")


@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit(lambda: os.getenv("REGULAITOR_RATE_LIMIT_ANALYZE", "5/minute"))
async def analyze(
    request: Request,
    file: UploadFile = File(...),
    corpus: list[str] = Form(...),
    language: str = Form(...),
    _: None = Depends(verify_token),
) -> AnalyzeResponse:
    case_id = _generate_case_id()
    request.state.case_id = case_id

    body = await file.read()
    if len(body) > _max_bytes():
        raise FileSizeExceeded(size=len(body), max_size=_max_bytes())
    if len(body) == 0:
        raise UnsupportedMediaType(reason="empty file")

    mime_type = _detect_mime(file.filename or "", body[:8])

    if language not in ("es", "en"):
        raise UnsupportedMediaType(reason=f"unsupported language: {language}")
    if not all(c in ("ai_act", "gdpr") for c in corpus):
        raise UnsupportedMediaType(reason="unsupported corpus member")

    t0 = time.monotonic()
    report = run_document(
        file_bytes=body,
        mime_type=mime_type,
        language=language,  # type: ignore[arg-type]
        corpus=corpus,
        case_id=case_id,
    )
    response_time_ms = int((time.monotonic() - t0) * 1000)
    response = to_analyze_response(report, response_time_ms=response_time_ms)
    log_api_document_turn(request, report, response)
    return response
```

Notas:
- Body leído en memoria completa (justificado en Q3: el pipeline H5 necesita bytes completos para `pypdfium2.open()`).
- `_MAX_BYTES` configurable vía env var; default 10 MB.
- Magic-byte detection antes que extension (mismo patrón que H6 `tab_analyze._detect_mime`).
- `corpus` y `language` validados manualmente porque `Form()` recibe `str`/`list[str]` raw — usamos `UnsupportedMediaType` como handle común para inputs inválidos.
- `DocumentBlockedError` (sanitizer critical) y `RuntimeError` se propagan al handler global (no try/except aquí).

### 4.5 `routes_health.py`

```python
import os
from fastapi import APIRouter

from regulaitor.api.schemas import HealthResponse, HealthCheck
from regulaitor.rag.store import connect

router = APIRouter(tags=["meta"])


def _check_lancedb() -> HealthCheck:
    try:
        table = connect()  # uses DEFAULT_PATH from rag.store
        n_chunks = table.count_rows()
        if n_chunks < 1:
            return HealthCheck(name="lancedb", status="degraded", detail=f"{n_chunks} chunks")
        return HealthCheck(name="lancedb", status="ok", detail=f"{n_chunks} chunks")
    except Exception as exc:
        return HealthCheck(name="lancedb", status="unreachable", detail=type(exc).__name__)


def _check_anthropic_key() -> HealthCheck:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return HealthCheck(name="anthropic_key", status="missing", detail=None)
    return HealthCheck(name="anthropic_key", status="present", detail=None)


def _check_api_token() -> HealthCheck:
    from regulaitor.api.auth import _API_TOKEN
    if _API_TOKEN is None:
        return HealthCheck(name="api_token", status="missing", detail=None)
    return HealthCheck(name="api_token", status="present", detail=None)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    checks = [_check_lancedb(), _check_anthropic_key(), _check_api_token()]
    overall = "ok" if all(c.status in ("ok", "present") for c in checks) else "degraded"
    response = HealthResponse(
        status=overall,
        version="0.0.8",
        checks=checks,
    )
    if overall != "ok":
        # 503 via responsibility of FastAPI.responses.JSONResponse with status_code
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content=response.model_dump())
    return response
```

Notas:
- NO valida la Anthropic key haciendo llamada online (cuesta dinero, side-effects).
- Lee LanceDB count para verificar corpus index poblado (N>0).
- 503 retornado vía `JSONResponse` directamente (el `response_model` declara la forma; el status code se override).
- No requiere auth ni rate limit.

### 4.6 `schemas.py`

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from regulaitor.citation.schemas import (
    AuditedAnswer, AuditResult, AuditVerdict, Citation, DocumentReport, Finding,
    SanitizerEvent, SegmentResult,
)
from regulaitor.orchestration.state import ChatState

# === Request DTOs ===

class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=2000)
    corpus: Literal["ai_act", "gdpr"]
    language: Literal["es", "en"]


# === Response DTOs ===

class CitationDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    norma: str
    articulo: str
    apartado: str | None
    language: str
    text: str


class AuditResultDTO(BaseModel):
    """Subset of AuditResult: validated + 3 sub-flags + reason. No internal Citation echo."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    citation: CitationDTO
    validated: bool
    article_exists: bool
    apartado_exists: bool | None
    text_normalized_match: bool
    reason: str | None


class FindingDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str
    citations: list[CitationDTO]
    severity: Literal["info", "low", "medium", "high"]


class AnswerDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str
    findings: list[FindingDTO]


class AskResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str
    verdict: Literal["pass", "block", "requires_human_review"]
    answer: AnswerDTO
    audit_results: list[AuditResultDTO]
    reason: str | None
    response_time_ms: int = Field(ge=0)


class SanitizerEventDTO(BaseModel):
    """Subset of SanitizerEvent: severity + category + content_hash. No location, no reason raw."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    severity: Literal["info", "warning", "critical"]
    category: str
    content_hash: str


class SegmentResultDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    segment_id: int
    title: str | None
    skipped: bool
    skip_category: Literal["clean", "injection_blocked", "internal_error"]
    answer: AnswerDTO | None
    verdict: Literal["pass", "block", "requires_human_review"] | None
    audit_results: list[AuditResultDTO]
    latency_ms: int
    cost_eur: float


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    case_id: str
    document_verdict: Literal["pass", "block", "requires_human_review"]
    document_reason: str | None
    n_segments_total: int
    n_segments_pass: int
    n_segments_block: int
    n_segments_review: int
    n_segments_blocked_by_injection: int
    sanitizer_log: list[SanitizerEventDTO]
    segments: list[SegmentResultDTO]
    latency_ms_total: int
    cost_eur_total: float
    response_time_ms: int


class HealthCheck(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    name: str
    status: Literal["ok", "present", "missing", "unreachable", "degraded"]
    detail: str | None


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    status: Literal["ok", "degraded"]
    version: str
    checks: list[HealthCheck]


class ErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    error_code: str
    message: str
    case_id: str | None


# === Converters ===

def _to_citation_dto(c: Citation) -> CitationDTO: ...
def _to_audit_result_dto(r: AuditResult) -> AuditResultDTO: ...
def _to_finding_dto(f: Finding) -> FindingDTO: ...
def _to_answer_dto(a) -> AnswerDTO: ...

def to_ask_response(state: ChatState, response_time_ms: int = 0) -> AskResponse: ...

def to_analyze_response(report: DocumentReport, response_time_ms: int = 0) -> AnalyzeResponse:
    """
    Per-segment translation:
    - report.segments[].skipped True + skip_reason starts with "injection" → skip_category="injection_blocked"
    - report.segments[].skipped True + other skip_reason → skip_category="internal_error"  (NEVER expose raw reason)
    - report.segments[].skipped False → skip_category="clean"
    Sanitizer events: pass severity, category, content_hash. NEVER expose location or raw reason.
    """
    ...
```

**SSDLC controls en converters** (críticos):
- `skip_reason` (de `SegmentResult`) NUNCA se propaga literal al cliente. Se mapea a categoría coarse-grained (`injection_blocked` / `internal_error` / `clean`).
- `injection_reason` (de `ChatState`) NUNCA se propaga al cliente; el `verdict` y un `reason` redactado bastan.
- `SanitizerEvent.location` y `SanitizerEvent.reason` NUNCA se exponen — solo `severity`, `category`, `content_hash`.
- `Context` interno (chunks con score, version, source_url) NUNCA se incluye en `AskResponse`.
- `errors` (de `ChatState`) NUNCA se exponen — tratados como `BackendError` → 500 con mensaje genérico.

### 4.7 `errors.py`

```python
import logging
from typing import Any
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from regulaitor.api.schemas import ErrorResponse
from regulaitor.citation.schemas import DocumentBlockedError

logger = logging.getLogger(__name__)


# === Custom API exceptions ===

class InjectionDetected(Exception):
    def __init__(self, case_id: str, reason_code: str) -> None:
        super().__init__(reason_code)
        self.case_id = case_id
        self.reason_code = reason_code


class BackendError(Exception):
    def __init__(self, case_id: str, errors: list[str]) -> None:
        super().__init__("backend_error")
        self.case_id = case_id
        self.errors = errors  # only logged, never returned


class FileSizeExceeded(Exception):
    def __init__(self, size: int, max_size: int) -> None:
        super().__init__(f"size {size} exceeds max {max_size}")
        self.size = size
        self.max_size = max_size


class UnsupportedMediaType(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason_code = reason


# === Handlers ===

def _build(error_code: str, message: str, case_id: str | None) -> ErrorResponse:
    return ErrorResponse(error_code=error_code, message=message, case_id=case_id)


async def injection_handler(request: Request, exc: InjectionDetected) -> JSONResponse:
    body = _build("injection_blocked", "Input rejected by anti-injection gate.", exc.case_id)
    _log_error(request, status=400, error_code="injection_blocked", case_id=exc.case_id)
    return JSONResponse(status_code=400, content=body.model_dump())


async def document_blocked_handler(request: Request, exc: DocumentBlockedError) -> JSONResponse:
    case_id = getattr(request.state, "case_id", None)
    body = _build("document_blocked", "Document rejected by sanitizer (critical content).", case_id)
    _log_error(request, status=422, error_code="document_blocked", case_id=case_id)
    return JSONResponse(status_code=422, content=body.model_dump())


async def file_size_handler(request: Request, exc: FileSizeExceeded) -> JSONResponse:
    case_id = getattr(request.state, "case_id", None)
    body = _build("payload_too_large", f"File size exceeds {exc.max_size} bytes.", case_id)
    _log_error(request, status=413, error_code="payload_too_large", case_id=case_id)
    return JSONResponse(status_code=413, content=body.model_dump())


async def unsupported_media_handler(request: Request, exc: UnsupportedMediaType) -> JSONResponse:
    case_id = getattr(request.state, "case_id", None)
    body = _build("unsupported_media", "Unsupported file or input format.", case_id)
    _log_error(request, status=415, error_code="unsupported_media", case_id=case_id)
    return JSONResponse(status_code=415, content=body.model_dump())


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    case_id = getattr(request.state, "case_id", None)
    body = _build("rate_limit_exceeded", "Too many requests. Retry later.", case_id)
    _log_error(request, status=429, error_code="rate_limit_exceeded", case_id=case_id)
    headers = {"Retry-After": "60"}
    return JSONResponse(status_code=429, content=body.model_dump(), headers=headers)


async def backend_error_handler(request: Request, exc: BackendError) -> JSONResponse:
    body = _build("backend_error", f"Internal pipeline error. Reference: {exc.case_id}", exc.case_id)
    _log_error(request, status=500, error_code="backend_error", case_id=exc.case_id, extra={"errors": exc.errors})
    return JSONResponse(status_code=500, content=body.model_dump())


async def generic_handler(request: Request, exc: Exception) -> JSONResponse:
    case_id = getattr(request.state, "case_id", None)
    body = _build("internal_error", f"Internal server error. Reference: {case_id}" if case_id else "Internal server error.", case_id)
    _log_error(request, status=500, error_code="internal_error", case_id=case_id, exc_type=type(exc).__name__)
    return JSONResponse(status_code=500, content=body.model_dump())


def register_anthropic_handlers(app: FastAPI) -> None:
    """Lazy import to avoid forcing anthropic dep at API startup if not installed in CI."""
    try:
        from anthropic import AuthenticationError, BadRequestError
    except ImportError:
        return

    async def auth_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        case_id = getattr(request.state, "case_id", None)
        body = _build("upstream_auth_failed", "Upstream LLM auth failed (server config issue).", case_id)
        _log_error(request, status=502, error_code="upstream_auth_failed", case_id=case_id)
        return JSONResponse(status_code=502, content=body.model_dump())

    async def billing_handler(request: Request, exc: BadRequestError) -> JSONResponse:
        case_id = getattr(request.state, "case_id", None)
        msg = str(exc).lower()
        if "credit balance" in msg:
            body = _build("upstream_billing", "Upstream LLM billing issue. Try again later.", case_id)
            _log_error(request, status=503, error_code="upstream_billing", case_id=case_id)
            return JSONResponse(status_code=503, content=body.model_dump())
        body = _build("upstream_bad_request", "Upstream LLM rejected the request.", case_id)
        _log_error(request, status=502, error_code="upstream_bad_request", case_id=case_id)
        return JSONResponse(status_code=502, content=body.model_dump())

    app.add_exception_handler(AuthenticationError, auth_handler)
    app.add_exception_handler(BadRequestError, billing_handler)


def _log_error(request: Request, *, status: int, error_code: str, case_id: str | None, **extra: Any) -> None:
    record = {
        "case_id": case_id,
        "http_method": request.method,
        "http_path": request.url.path,
        "http_status": status,
        "token_hash": getattr(request.state, "token_hash", None),
        "error_code": error_code,
        **extra,
    }
    logger.warning("api_error: %s", record)
```

**SSDLC notas críticas:**
- Mensajes nunca contienen `str(exc)` para excepciones desconocidas — solo `type(exc).__name__` en log (no en response).
- `BackendError.errors` (lista interna) se logea pero NO se devuelve.
- `register_anthropic_handlers` lazy import previene fallo si anthropic no está instalado en algún entorno de CI parcial.
- `Retry-After: 60` en 429 como hint estándar.

### 4.8 `logging.py`

```python
import hashlib
import ipaddress
import json
import logging
from fastapi import Request

from regulaitor.api.schemas import AskResponse, AnalyzeResponse
from regulaitor.citation.schemas import DocumentReport
from regulaitor.orchestration.state import ChatState

logger = logging.getLogger(__name__)


def _redact_ip(client_ip: str | None) -> str | None:
    if not client_ip:
        return None
    try:
        ip = ipaddress.ip_address(client_ip)
        if isinstance(ip, ipaddress.IPv4Address):
            net = ipaddress.ip_network(f"{ip}/24", strict=False)
            return str(net.network_address)
        # IPv6: /48 prefix
        net = ipaddress.ip_network(f"{ip}/48", strict=False)
        return str(net.network_address)
    except ValueError:
        return None


def log_api_chat_turn(request: Request, state: ChatState, response: AskResponse) -> None:
    record = {
        "case_id": state.case_id,
        "http_method": request.method,
        "http_path": request.url.path,
        "http_status": 200,
        "token_hash": getattr(request.state, "token_hash", None),
        "client_ip_redacted": _redact_ip(request.client.host if request.client else None),
        "verdict": response.verdict,
        "n_findings": len(response.answer.findings),
        "n_citations": len(response.audit_results),
        "n_validated": sum(1 for r in response.audit_results if r.validated),
        "response_time_ms": response.response_time_ms,
        "corpus": state.corpus,
        "language": state.language,
    }
    logger.info("api_chat_turn: %s", json.dumps(record, ensure_ascii=False))


def log_api_document_turn(request: Request, report: DocumentReport, response: AnalyzeResponse) -> None:
    record = {
        "case_id": report.case_id,
        "http_method": request.method,
        "http_path": request.url.path,
        "http_status": 200,
        "token_hash": getattr(request.state, "token_hash", None),
        "client_ip_redacted": _redact_ip(request.client.host if request.client else None),
        "document_verdict": response.document_verdict,
        "n_segments_total": response.n_segments_total,
        "n_segments_pass": response.n_segments_pass,
        "n_segments_block": response.n_segments_block,
        "n_segments_review": response.n_segments_review,
        "n_segments_blocked_by_injection": response.n_segments_blocked_by_injection,
        "latency_ms_total": response.latency_ms_total,
        "cost_eur_total": response.cost_eur_total,
        "response_time_ms": response.response_time_ms,
        "corpus": report.corpus,
        "language": report.language,
    }
    logger.info("api_document_turn: %s", json.dumps(record, ensure_ascii=False))
```

Notas:
- IPv4 truncado a /24, IPv6 a /48 (compromise privacy/observability — suficiente para detección de origen geográfico, no para identificación individual).
- Backend ya emite su propio log via `_log_turn` / `_log_document_turn`. La API añade un segundo record con prefix `api_*_turn` que correlaciona por `case_id`. Esta es la forma más limpia de "reuse + extend" decidida en Q6: no modificamos los logs del backend; añadimos uno nuestro.

### 4.9 `security/rate_limit.py`

```python
import os
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _key_func(request: Request) -> str:
    """Per-token rate limit. Falls back to IP for unauthenticated paths (none in MVP)."""
    token_hash = getattr(request.state, "token_hash", None)
    if token_hash:
        return f"token:{token_hash}"
    return f"ip:{get_remote_address(request)}"


def _is_disabled() -> bool:
    return os.getenv("REGULAITOR_RATE_LIMIT_DISABLED", "").strip() == "1"


limiter = Limiter(
    key_func=_key_func,
    default_limits=[],
    enabled=not _is_disabled(),
    storage_uri="memory://",
)
```

Notas:
- `enabled` evaluado al import; tests deben setear env var antes de importar el módulo (o usar `monkeypatch` + reload).
- Storage `memory://` per slowapi convention; futuro `redis://` en H16 si multi-instance.
- `default_limits=[]` significa que solo aplica donde hay decorator explícito.

## 5. Endpoint examples (OpenAPI)

### 5.1 `POST /ask`

```bash
curl -X POST http://localhost:8000/ask \
  -H "Authorization: Bearer ${REGULAITOR_API_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query":"¿Qué dice el AI Act sobre sistemas de alto riesgo?","corpus":"ai_act","language":"es"}'
```

Response 200:
```json
{
  "case_id": "api-ch-20260508-a1b2c3d4",
  "verdict": "pass",
  "answer": {
    "text": "El AI Act regula los sistemas de alto riesgo en sus artículos 6-15...",
    "findings": [
      {
        "text": "Sistemas de alto riesgo requieren evaluación de conformidad",
        "citations": [{"norma": "ai_act", "articulo": "6", "apartado": "1", "language": "es", "text": "..."}],
        "severity": "info"
      }
    ]
  },
  "audit_results": [
    {"citation": {...}, "validated": true, "article_exists": true, "apartado_exists": true, "text_normalized_match": true, "reason": null}
  ],
  "reason": null,
  "response_time_ms": 4231
}
```

Response 400 (injection):
```json
{"error_code": "injection_blocked", "message": "Input rejected by anti-injection gate.", "case_id": "api-ch-20260508-a1b2c3d4"}
```

### 5.2 `POST /analyze`

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Authorization: Bearer ${REGULAITOR_API_TOKEN}" \
  -F "file=@policy.pdf;type=application/pdf" \
  -F "corpus=ai_act" \
  -F "corpus=gdpr" \
  -F "language=es"
```

Response 200: `AnalyzeResponse` con `case_id="api-doc-..."`, verdict por documento, segmentos, sanitizer log, métricas.

Response 422 (DocumentBlockedError):
```json
{"error_code": "document_blocked", "message": "Document rejected by sanitizer (critical content).", "case_id": "api-doc-20260508-..."}
```

### 5.3 `GET /health`

```bash
curl http://localhost:8000/health
```

Response 200:
```json
{
  "status": "ok",
  "version": "0.0.8",
  "checks": [
    {"name": "lancedb", "status": "ok", "detail": "1011 chunks"},
    {"name": "anthropic_key", "status": "present", "detail": null},
    {"name": "api_token", "status": "present", "detail": null}
  ]
}
```

Response 503:
```json
{
  "status": "degraded",
  "version": "0.0.8",
  "checks": [
    {"name": "lancedb", "status": "unreachable", "detail": "FileNotFoundError"},
    {"name": "anthropic_key", "status": "missing", "detail": null},
    {"name": "api_token", "status": "present", "detail": null}
  ]
}
```

## 6. Testing strategy

### 6.1 Unit tests (`tests/unit/test_api_*.py`)

- **`test_api_auth.py`**: token loader (missing → RuntimeError, <16 chars → RuntimeError, valid → loaded); `verify_token` (no header → 401, malformed → 401, invalid → 401, valid → state.token_hash set).
- **`test_api_rate_limit.py`**: key_func returns `token:<hash>` when token_hash set, `ip:<ip>` otherwise; `_is_disabled()` reads env correctly.
- **`test_api_errors.py`**: each handler returns correct status + ErrorResponse shape; SSDLC: `BackendError.errors` not in response body; `register_anthropic_handlers` skips silently if anthropic uninstalled (mocked).
- **`test_api_schemas.py`**: AskRequest validates length + literals; converters strip `skip_reason`, `injection_reason`, `location` (assertion: response JSON does NOT contain these keys).

### 6.2 Integration tests (`tests/integration/test_api_*.py`)

httpx async client + backend fakes via monkeypatch:

- **`test_api_health.py`**: ok all healthy → 200; lancedb fake raises → 503; missing anthropic → 503.
- **`test_api_ask.py`**:
  - happy path: monkeypatch `run` to return canned `ChatState` with valid `audited_answer` → 200 + AskResponse.
  - injection: monkeypatch returns state with `injection_blocked=True` → 400.
  - errors list: monkeypatch returns state with `errors=["x"]` → 500 BackendError.
  - auth missing: no header → 401.
  - auth invalid: wrong token → 401.
  - rate limit: `REGULAITOR_RATE_LIMIT_ASK=2/minute`, three requests → third gets 429.
  - validation: query too long (>2000 chars) → 422.
- **`test_api_analyze.py`**:
  - happy path: PDF fixture, monkeypatch `run_document` → 200.
  - DocumentBlockedError: monkeypatch raises → 422.
  - size: 11 MB file → 413.
  - MIME: .txt file → 415.
  - empty: 0 bytes → 415.
  - corpus invalid: `corpus=foo` → 415.
  - language invalid: `language=fr` → 415.
  - rate limit: `REGULAITOR_RATE_LIMIT_ANALYZE=1/minute`, two requests → 429.

### 6.3 Contract tests (`tests/contract/test_api_schemathesis.py`)

```python
import schemathesis
from fastapi.testclient import TestClient

from regulaitor.api.main import app

schema = schemathesis.openapi.from_asgi("/openapi.json", app)


@schema.parametrize(endpoint="/ask|/analyze|/health")
@schemathesis.settings(max_examples=20)
def test_api_contract(case):
    # backend fakes monkeypatched in conftest
    response = case.call(client=TestClient(app))
    case.validate_response(response)
```

Notas:
- `max_examples=20` per endpoint = ~60 fuzz cases total.
- Validates: schema conformance, status codes documented in OpenAPI, no 500s on valid inputs.
- Backend faking via `conftest.py` autouse fixture (mocks `run` y `run_document`).

### 6.4 Coverage gate

Target: ≥80% global, ≥90% en `api/auth.py`, `api/errors.py`, `security/rate_limit.py` (líneas SSDLC críticas).

### 6.5 No-LLM-credits compatible

Todos los tests funcionan sin créditos Anthropic — usan backend fakes. Manual smoke con LLM real se difiere a pre-H8 cuando los créditos se carguen.

## 7. Make targets

```makefile
serve-api: ## Run the FastAPI server with auto-reload
	uv run uvicorn regulaitor.api.main:app --reload --port 8000
```

`make serve` (existing) sigue arrancando Streamlit. Decisión: NO se cambia para arrancar ambos — separados, el operador elige cuál corre.

## 8. Dependencies (pyproject.toml updates)

**Runtime (added to `[project].dependencies`):**
- `fastapi>=0.115`
- `uvicorn[standard]>=0.32`
- `python-multipart>=0.0.20` (UploadFile parsing)
- `slowapi>=0.1.9`

**Dev (added to `[tool.uv.dev-dependencies]`):**
- `schemathesis>=3.40`
- `httpx>=0.28` (verify already present; used by AppTest in H6 transitively)

**No breaking changes to existing pins.** All additions are pip-audit-clean as of 2026-05-08.

## 9. ADR + decisions log + skill

### 9.1 ADR 0009

`docs/adr/0009-fastapi-architecture.md`. Captura:

- Why thin wrapper over backend (no business logic in API layer).
- Why static Bearer token (vs no-auth, vs API keys per client).
- Why slowapi (vs custom counter, vs fastapi-limiter).
- Why DTOs explícitas (vs mirror, vs `model_dump(exclude=...)`).
- Why global exception handlers (vs per-route, vs hybrid).
- Why readiness `/health` (vs liveness, vs split `/health` + `/health/ready`).
- Why configurable rate limit values (vs hardcoded).
- Decisiones diferidas: `/cases`, CORS, `/v1/`, multi-tenant, OAuth, WebSocket streaming.

### 9.2 Decisions log §H7

Anexar entradas para cada Q1-Q10 cerrada en brainstorming + cada amendment durante implementación.

### 9.3 Skills

NO se introduce skill nueva en H7. `superpowers` sigue activa. Skills oficiales `pdf`/`docx`/`xlsx` no aplican aquí.

## 10. Files touched

**NEW (19 archivos de código + 1 ADR):**

```
src/regulaitor/api/__init__.py
src/regulaitor/api/main.py
src/regulaitor/api/auth.py
src/regulaitor/api/routes_ask.py
src/regulaitor/api/routes_analyze.py
src/regulaitor/api/routes_health.py
src/regulaitor/api/schemas.py
src/regulaitor/api/errors.py
src/regulaitor/api/logging.py
src/regulaitor/security/rate_limit.py
tests/unit/test_api_auth.py
tests/unit/test_api_rate_limit.py
tests/unit/test_api_errors.py
tests/unit/test_api_schemas.py
tests/integration/test_api_ask.py
tests/integration/test_api_analyze.py
tests/integration/test_api_health.py
tests/contract/test_api_schemathesis.py
docs/adr/0009-fastapi-architecture.md
```

**MODIFY:**

```
pyproject.toml               (add fastapi, uvicorn, python-multipart, slowapi, schemathesis)
Makefile                     (add serve-api target)
README.md                    (add API quickstart section)
CLAUDE.md                    (§27 mark H7 closed after merge)
docs/technical_decisions_log.md (append §H7)
.env                         (operator adds REGULAITOR_API_TOKEN locally; not committed)
```

## 11. Anti-patterns to avoid

(Continuación de los anti-patterns de H1-H6.)

- **No exponer `pattern_name`, `skip_reason`, `injection_reason`, `SanitizerEvent.location`, `SanitizerEvent.reason` en responses.** Mismo principio que H6 UI: el atacante no debe poder iterar evasiones a partir de los nombres de las defensas.
- **No mostrar stack traces ni `str(exc)` de excepciones desconocidas.** Solo `case_id` reference; trace queda en logs server-side.
- **No comparar tokens con `==`.** Siempre `hmac.compare_digest`.
- **No leer el token desde request body o query string.** Solo header `Authorization: Bearer`.
- **No logear tokens en plano** ni `Authorization` header completo. Solo `token_hash` (sha256[:8]).
- **No logear IPs en plano.** Solo `/24` o `/48` prefix.
- **No tocar el backend H1-H5 desde H7.** Si una excepción del backend no encaja en el mapeo, se registra un handler global, NO se modifica el backend.
- **No mezclar liveness y readiness en endpoints separados** (decidido en Q9: un solo `/health` con readiness completo).
- **No persistir requests/responses a disco en H7.** Sin `/cases`, sin DB, sin cache. Logs sí, pero estructurados sin payloads en claro.
- **No saltarse pre-commit con `--no-verify`.**
- **No introducir CORS abierto.** CORS sigue cerrado (deny by default) hasta HX2.
- **No exponer Anthropic SDK exceptions raw.** Mapeo a 502/503 con mensaje genérico.
- **No usar `lifespan` para validar Anthropic key online** (cuesta dinero por cada arranque). Solo verifica presencia.

## 12. Gate de cierre H7

Pre-merge:

1. `make lint` verde (ruff + black + mypy).
2. `make test` verde con `REGULAITOR_API_TOKEN=test_token_at_least_16_chars` y backend fakes.
3. Coverage ≥80% global, ≥90% en `api/auth.py`, `api/errors.py`, `security/rate_limit.py`.
4. `make serve-api` arranca y `curl /health` responde 200 (con LanceDB poblada) o 503 (con explicación clara en `checks`).
5. `curl POST /ask` con token válido y backend real (con créditos cargados — NO bloqueante para H7, sí para smoke pre-H8) devuelve `AskResponse` válido.
6. Schemathesis CI run encuentra cero violaciones.
7. Pre-commit verde (gitleaks especialmente — no token leak en logs/tests).
8. ADR 0009 commiteado.
9. Decisions log §H7 actualizado.
10. README sección API quickstart commiteado.
11. CLAUDE.md §27 actualizado a H7 closed.
12. Tag `v0.0.8-h7` publicado tras squash merge.

## 13. Out of scope (deferred — captured for H17 future-work doc)

- **`GET /cases`** (read-only case history). Requiere persistencia (SQLite vs Postgres, schema, retention). CLAUDE.md §5.3 lo lista "si da tiempo"; defer a hito propio.
- **CORS allowlist configurable.** Defer a HX2 (Next.js frontend) — hoy no hay browser client que justifique.
- **Prefix `/v1/`.** YAGNI hasta v2 breaking change.
- **Multi-tenant auth (API keys per cliente + DB).** Single-operator MVP.
- **Token TTL / rotación automática.** Static-forever para MVP; rotación manual via env var update + restart.
- **OAuth2 / OIDC.** Single-token MVP.
- **WebSocket streaming** en `/analyze` (status updates per-segment). Synchronous response only.
- **Manual smoke con LLM real** end-to-end. Esperando carga de créditos pre-H8.
- **Integración UI Streamlit → API.** H6 sigue llamando backend directo; integración via HTTP queda para HX2.
- **Schemathesis stateful tests** (links entre endpoints). Property-based stateless es suficiente para MVP.
- **`/metrics` endpoint** (Prometheus). Defer a HX5 (Prometheus avanzado).

## 14. Decisiones brainstorming → spec mapping

| Q | Decisión | Sección spec |
|---|---|---|
| Q1 | Auth = token estático env var (`REGULAITOR_API_TOKEN`, Bearer header, hmac.compare_digest, ≥16 chars) | §4.2 auth.py, §11 anti-patterns |
| Q2 | Rate limit = slowapi (in-memory, key=token_hash, env-configurable) | §4.9 rate_limit.py, §10 deps |
| Q3 | Upload = `UploadFile` multipart + 10 MB cap (env configurable) | §4.4 routes_analyze.py |
| Q4 | Exception mapping = global handlers (mapping table, ErrorResponse, sin trace) | §4.7 errors.py, §3.4 mapping |
| Q5 | Scope = `/ask`, `/analyze`, `/health` + auth + rate limit. NO `/cases`, NO CORS, NO `/v1/` | §1 goal, §13 out of scope |
| Q6 | Logging = reuse + extend, prefix `api-` para case_id, segundo log record API-level | §4.8 logging.py |
| Q7 | Schemas = DTOs explícitas en `api/schemas.py` + converters; SSDLC redaction explícita | §4.6 schemas.py |
| Q8 | Tests = schemathesis (contract) + httpx (integration) + unit por módulo + backend fakes | §6 testing strategy |
| Q9 | `/health` = readiness completo (LanceDB, anthropic_key, api_token, version, checks list) | §4.5 routes_health.py |
| Q10 | Rate limit values = configurables vía env vars (defaults 30/min ask, 5/min analyze, switch DISABLED=1) | §4.9 rate_limit.py, §4.3-4.4 routes |

---

**Status:** approved. Ready for writing-plans skill.
