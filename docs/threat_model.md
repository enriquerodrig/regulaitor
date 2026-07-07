# RegulAItor — Threat Model (HX, post pre-pilot hardening + P3 operability)

> Estado: 2026-07-07 (roadmap post-P3). Refresca el modelo de amenazas del
> `security_report.md` (congelado en H9 / alcance MVP) al estado real HX: API
> multi-tenant, frontend BFF, filtro PII, el batch de endurecimiento pre-piloto
> (`docs/professionalization_roadmap.md` Fases P1-P2) y la fase de operabilidad P3
> (observabilidad §6, GDPR DSR, gestión de secretos, red team a las 9 normas).
> **No sustituye una auditoría de seguridad profesional**; es evidencia interna del
> proceso SSDLC (CLAUDE.md §18).

## 1. Activos y fronteras de confianza

| Activo | Sensibilidad | Frontera |
|---|---|---|
| Corpus normativo + índice LanceDB | público (EUR-Lex) — integridad crítica | commit/LFS; sólo lectura en runtime |
| §6 citation validator + Auditor | **el moat** — integridad crítica | in-process; ficheros sagrados byte-controlados |
| Bearer token de tenant | secreto | cookie httpOnly (BFF) / header (API); nunca en modelo ni log |
| Consulta / documento del usuario | puede contener PII | in-memory; nunca persistido en claro (§18.8) |
| Traza de auditoría (opt-in) | metadatos + hash | SQLite por-tenant; sólo SHA-256 de la query |
| Claves de proveedor (6-8) | secreto alto | `.env` (dev) / secret-manager (deploy) |

**Superficies de entrada:** API FastAPI (`/ask`, `/analyze`, `/audit`, `/health`) ·
BFF Next.js (route handlers server-only) · ingesta de corpus (operador, no usuario) ·
egress a LLM (Mistral/Anthropic/…) + LangFuse (opt-in).

## 2. Amenazas y controles por superficie

### 2.1 §6 — fabricación de citas (la amenaza central del producto)
- **Amenaza:** el modelo emite una afirmación con una cita inventada o sin evidencia.
- **Controles:** arquitectura §6 de **cuatro capas** (CLAUDE.md §6.1): (a) validador
  per-cita 3-checks (article/apartado/text-match) + strict-tightenings aditivos
  (whitespace v0.1.32-post, floor de longitud `_MIN_CITATION_CHARS=20` sec6-01/ADR-0043,
  ambos → `failed_check=4` que enruta estricto en `validator.py`); (b) Finding-Lenient +
  (c) Turn-aggregation (`auditor.py`, v0.1.25/v0.1.29); (d) prompt-level forbid.
  Fabricación **nunca** es PASS por construcción. Property/fuzz tests (P1.3) asertan el
  invariante sobre entradas generadas + 4 auditorías de mutación
  (`scripts/sec6_*_mutation_audit.py` + `scripts/sec18_*_mutation_audit.py`); los 2
  bypasses históricos (substring trivial, whitespace) están cerrados.
- **Residual:** el match es substring, no *entailment* semántico — una cita real ≥20
  chars que no *apoye* la afirmación pasa Check 3 (claim-support boundary documentado en
  `model_card.md §8.1`; NLI = HX). Riesgo de precisión, no de fabricación.

### 2.2 Prompt injection / documento malicioso
- **Amenaza:** un documento (o consulta) intenta secuestrar las instrucciones, ocultar
  texto, o inyectar metadatos.
- **Controles:** sanitizer (`document/sanitizer.py`: texto invisible, metadatos,
  JavaScript embebido → block); injection regex (`security/injection.py`); separación
  system/usuario en prompts; red team smoke gate `block_rate ≥ 0.90` (0.92).
- **Residual:** red team ampliado a las 9 normas (P3.5 CERRADO — `redteam/attacks.jsonl`
  59 filas, ataques 051-059 cubren NIS2/DORA/RTS/AMLR/MiCA/TFR + test de rechazo del
  validador $0). Detección regex, no semántica (queda como residual real).

### 2.3 API auth + aislamiento multi-tenant
- **Amenaza:** acceso sin token; un tenant lee/afecta datos de otro; bypass de cuota.
- **Controles:** Bearer constant-time (`api/auth.py`); default-deny a nivel router
  (authz-01); `enforce_corpus_allowlist` fail-closed (authz-03); `/audit` fuerza
  `tenant_id` de `request.state` (nunca del cliente) → aislamiento probado
  (`test_api_audit.py`); rate-limit por-tenant; envelope de error uniforme sin fugas
  (err-04); `/docs` gateable en prod (authz-02).
- **Residual:** cuota contada, no impuesta (sin 429 over-budget — roadmap P5); limiter
  `memory://` por-worker (single-worker OK; multi-worker necesita backend compartido).

### 2.4 Frontend BFF (superficie de despliegue soberano)
- **Amenaza:** XSS, CSRF, robo de token, downgrade de cookie, SSRF en el forward.
- **Controles:** token sólo en cookie httpOnly + SameSite=Strict + Secure fail-secure
  (fe-01); CSP por-petición con nonce + `strict-dynamic` (`proxy.ts`); guard CSRF
  same-origin en POST (fe-02); `server-only` impide que el origin/token llegue al
  bundle; 413 temprano en upload (fe-05); render §6 fiel (nunca re-deriva veredictos).
- **Residual:** `style-src 'unsafe-inline'` requerido por next/font (sin path XSS —
  script-src estricto); host esperado del CSRF = header Host (no allowlist) — aceptable
  para piloto single-tenant.

### 2.5 PII / datos personales (§18.5/§18.8)
- **Amenaza:** PII de una consulta se registra en claro, se filtra a un tercero, o se
  envía al LLM sin aviso.
- **Controles:** `security/pii.py` (regex MVP: email/tel-ES/DNI-NIF/NIE/IBAN/tarjeta) →
  gate pre-pipeline en chat Streamlit + recuento in-pipeline en doc-mode + `pii_summary`
  advisory en `/ask` (P2.3); logs redactados (recuentos, nunca el valor); egress LangFuse
  con allowlist (sólo `n_errors`/categorías, no texto libre — obs-06); la query cruda
  nunca se persiste (sólo SHA-256).
- **Residual:** el `/ask` es **advisory** — la PII de la consulta sí llega al LLM (un
  modo hard-block/redact es opción documentada); detector regex-MVP, no NER exhaustivo.
  GDPR DSR sobre la traza CERRADO (P3.3 — `scripts/dsr.py`: acceso Art. 15 / borrado
  Art. 17 mediado por operador + purga de retención 365d; `docs/data_retention.md`).

### 2.6 Secretos + cadena de suministro
- **Amenaza:** clave filtrada (spend, push al Space público, lectura de trazas); CVE en
  dependencia transitiva.
- **Controles:** `.env` gitignored (nunca committeado — verificado); gitleaks + bandit +
  pip-audit gateados en CI; CVEs transitivas al día (P1.5: 33 limpiadas; ignores con
  análisis-de-ruta documentado); `source_url` canónico sin fuga de ruta local (P2.2);
  runbook de secretos + Dependabot semanal (P3.4 CERRADO — `docs/secret_management.md` +
  `.github/dependabot.yml`).
- **Residual:** **6-8 claves en `.env` en claro pendientes de ROTACIÓN** — la ejecución
  (rotar antes del primer tenant + adoptar secret-manager) es una acción de operador que
  el runbook P3.4 documenta pero no puede realizar por sí sola; sigue siendo el
  bloqueante operativo real.

### 2.7 Egress a terceros (LLM soberanía + LangFuse)
- **Amenaza:** datos del usuario a una entidad US (CLOUD Act); trazas con texto sensible.
- **Controles:** router con modo `self_hosted` (bridge Mistral La Plateforme, FR/EU);
  `self_hosted` excluido del fallback a GPT-4o (sin sustitución US silenciosa); LangFuse
  opt-in + allowlist de egress.
- **Residual:** inferencia self-hosted real (vLLM/GPU EU) aún no desplegada — Mistral-API
  satisface soberanía pero no el literal "self-hosted" (roadmap P4); deploy demo en HF
  Spaces es US-hosted (no soberano — es demo, no target).

### 2.8 Disponibilidad / DoS
- **Amenaza:** una petición agota el worker (reranker CPU), upload gigante, hammering.
- **Controles:** cap de segmentos por documento (dos-01, →RHR); 413 por Content-Length
  temprano; rate-limit por-tenant; `/audit` offloaded del event loop.
- **Residual:** single-worker + CPU reranker = throughput bajo (GPU = roadmap P4); sin
  HA/réplicas (deliberado pre-piloto).

## 3. Riesgos residuales priorizados (→ roadmap)

Residuales abiertos (los que quedan):
1. **Rotación de secretos** — el único bloqueante operativo real. El tooling P3.4
   (runbook + Dependabot) está CERRADO; la *ejecución* de la rotación es acción de
   operador aún pendiente.
2. **Inferencia self-hosted + deploy soberano** (P4) — la tesis C1/C3, aún seams
   (infra: vLLM/GPU EU no desplegado; Mistral-API satisface soberanía, no el literal).

Cerrados por la fase P3 (antes en esta lista):
- ~~Observabilidad del block-rate §6 en prod~~ — CERRADO (P3.1: `observability/metrics.py`
  + `GET /metrics`, block-rate §6 en vivo).
- ~~Red team a las 9 normas~~ — CERRADO (P3.5: `redteam/attacks.jsonl` 59 filas,
  ataques 051-059 cubren las 7 normas restantes).
- ~~GDPR DSR + retención sobre la traza~~ — CERRADO (P3.3: `scripts/dsr.py` acceso/borrado
  + purga 365d; `docs/data_retention.md`).
- ~~Gestión de secretos (tooling)~~ — CERRADO (P3.4: `docs/secret_management.md` +
  `.github/dependabot.yml`); sólo queda la *rotación* como acción de operador (residual 1).

## 4. Referencias
- `docs/security_report.md` (H9, alcance MVP — este doc lo refresca a HX).
- `docs/professionalization_roadmap.md` (fases que cierran los residuales).
- CLAUDE.md §6 / §6.1 (invariante §6), §18 (seguridad), §22.22 (honestidad).
- ADRs 0024/0031/0032/0034/0043 (§6), 0039 (multi-tenancy), 0040 (BFF), 0041 (auditoría),
  0042 (per-tenant policy).
