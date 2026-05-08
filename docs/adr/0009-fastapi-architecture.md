# ADR 0009 — FastAPI mínima architecture for H7

- **Status:** Accepted
- **Date:** 2026-05-08 (H7 closure)
- **Deciders:** Project owner.
- **Companion ADRs:** 0001 (project scope), 0007 (document pipeline architecture), 0008 (Streamlit UI architecture).

## Context

H6 cerró la UI Streamlit como primera superficie del producto. CLAUDE.md §5.3
+ §16.1 lista la API (FastAPI) como tercera superficie y entregable de H7.
La API debe consumir programáticamente lo mismo que la UI sin tocar el
backend H1-H5, exponer una superficie mínima defendible, y aplicar la regla
"no citation, no answer" con la misma disciplina SSDLC ya validada en H6.

## Decision

Tres endpoints (`POST /ask`, `POST /analyze`, `GET /health`) en módulos thin
bajo `src/regulaitor/api/`:

### D1 — Auth Bearer estático

`REGULAITOR_API_TOKEN` vía env var (≥16 chars). Validación con
`hmac.compare_digest`, exact-match tras split `Bearer ` — sin `.strip()`,
per RFC 6750. Single-operator MVP. No multi-tenant, no rotación automática,
no OAuth.

### D2 — Rate limiting con slowapi

In-memory, per-token, configurable vía env vars
(`REGULAITOR_RATE_LIMIT_ASK=30/minute`, `REGULAITOR_RATE_LIMIT_ANALYZE=5/minute`).
Switch `REGULAITOR_RATE_LIMIT_DISABLED=1` para tests y CI. Storage backend
intercambiable (Redis para H16 multi-instance).

### D3 — Upload `/analyze` vía UploadFile multipart

Cap 10 MB configurable (`REGULAITOR_MAX_UPLOAD_BYTES`). Magic-byte detection
antes que extension. URL-based descartado por riesgo SSRF y porque los
documentos corporativos de PYMEs no tienen URL pública.

### D4 — Exception handlers globales con redacción centralizada

Mapping table → `ErrorResponse` JSON. Redacción explícita de stack traces,
raw exception messages, `pattern_name`, `skip_reason`, `injection_reason`,
`SanitizerEvent.location`. `BackendError.errors` truncado a 200 chars/string,
10 entries/list antes de logging (CLAUDE.md §18 — logs sin datos sensibles).
Mismo principio que H6 `_render.error_message`.

### D5 — DTOs explícitas en `api/schemas.py`

No mirror de backend models. Converters backend→DTO con redacción SSDLC
por construcción. `SanitizerCategory` Literal espejado del backend para
contrato OpenAPI estricto. Allowlist de fields auditables y explícita.

### D6 — `/health` readiness completo

Verifica: LanceDB `count_rows`, `ANTHROPIC_API_KEY` present,
`REGULAITOR_API_TOKEN` loaded. Sin auth, sin rate limit. 503 con
`detail` por check fallido. Semántica readiness (¿puede servir tráfico?)
sobre liveness (¿está vivo el proceso?).

### D7 — Logging API-level

Extiende `_log_turn` / `_log_document_turn` del backend con HTTP fields
(`http_status`, `token_hash`, IP redactada /24 o /48). Anthropic handlers
logean `exc_type=type(exc).__name__` para distinguir billing vs otros 502,
sin leak de `str(exc)`.

### D8 — Tests dual: schemathesis + httpx + unit

Schemathesis 4.x fuzz contra OpenAPI spec (20 examples × 3 endpoints = 60
fuzz cases), focused en `not_a_server_error`. Hand-written httpx integration
tests por endpoint. Unit tests por módulo. Backend fakes vía monkeypatch —
cero coste LLM. `reset_limiter` autouse fixture para aislar contadores
in-memory entre tests.

## Alternatives considered

- **No-auth MVP** — rechazado: convertiría `/analyze` en free LLM proxy,
  abre puerta a abuso si H16 despliega públicamente.
- **API keys per-cliente con DB** — rechazado: overkill para single-operator
  TFM; hipoteca tiempo sin aporte proporcional a la defensa.
- **slowapi vs custom rate-limit counter** — slowapi gana por madurez,
  storage backend intercambiable (in-memory MVP → Redis H16), y zero-config
  en tests con el switch `_DISABLED=1`.
- **Mirror backend models en API** — rechazado: filtro implícito de fields
  internos es frágil; DTOs explícitas hacen el allowlist auditable.
- **Per-route try/except en lugar de handlers globales** — rechazado:
  duplicación de la lógica de redacción SSDLC en N rutas, riesgo de leak
  por inconsistencia entre rutas.
- **Liveness vs readiness en `/health`** — readiness gana: H16 (HF Spaces)
  necesita saber si el sistema sirve tráfico, no solo si el proceso está
  vivo.
- **URL-based `/analyze` con allowlist EU** — rechazado por SSRF y por
  incompatibilidad con el caso de uso primario (documentos corporativos
  de PYMEs sin URL pública).
- **Schemathesis 3.x** — rechazado: v3.40 no existe en PyPI; v3.x conflicta
  con `pytest>=9` y `starlette>=1.0`. v4.0+ resuelve clean.

## Consequences

### Positivas

- Backend H1-H5 no tocado; los riesgos de regresión son cero por construcción.
- SSDLC defensa en profundidad replicada de H6 a la API: `pattern_name` y
  `skip_reason` no atraviesan la frontera serializable.
- Token + rate limit configurables por entorno vía env vars: dev local laxo,
  H16 producción tight, tests con switch `DISABLED=1`.
- Schemathesis 4.x con `not_a_server_error` check genera fuzz reproducible
  defendible en evidence_matrix (Módulo 3 evaluación + Módulo 4 seguridad).
- `/health` readiness es input directo para `docs/runbook.md` (H17).
- 481 tests, 92.40% coverage global al cierre.

### Negativas / aceptadas

- Coste de mantenimiento: 19 archivos nuevos + tests, magnitud similar a
  H5/H6.
- Cold start de uvicorn ~3s en Windows (similar al cold-start de Streamlit
  con lazy import en H6).
- Tests de integración necesitan TestClient + monkeypatch del backend;
  coste fijo por test ~50 líneas de fake en conftest. Auto-reset de rate
  limit vía `reset_limiter` autouse fixture.

### Diferidos a future-work doc en H17

- `GET /cases` (case history con persistencia).
- CORS configurable (HX2 cuando exista frontend Next.js).
- Prefix `/v1/`.
- Multi-tenant API keys.
- Token TTL / rotación automática.
- WebSocket streaming en `/analyze`.
- OAuth2 / OIDC.
- Integración UI Streamlit → API (HX2).
- Inconsistencia `datetime.utcnow()` (H6) vs `datetime.now(UTC)` (H7) —
  cleanup PR separado en próximo hito.

## Revision conditions

- Si H16 (HF Spaces) requiere despliegue multi-instance, reemplazar storage
  in-memory de slowapi por Redis (ya soportado por la lib, cambio de env var).
- Si HX2 introduce frontend Next.js, configurar CORS con allowlist explícita.
- Si en H8 los gold-set runs saturan rate limits, exportar `_DISABLED=1`
  durante el harness o ajustar defaults.

## References

- Spec: `docs/superpowers/specs/2026-05-08-h7-fastapi-design.md`
- Plan: `docs/superpowers/plans/2026-05-08-h7-fastapi-mvp.md`
- Brainstorming: 10 Qs cerradas (auth, rate limit, upload, exception mapping,
  scope, logging, schemas, tests, health, rate limit values). Ver §H7 en
  `docs/technical_decisions_log.md`.
- Predecesor: ADR 0008 (Streamlit UI architecture).
