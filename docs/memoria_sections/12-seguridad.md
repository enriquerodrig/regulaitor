# 12. Seguridad (SSDLC: sanitizer + injection + auth + rate-limit + PII + secrets)

La seguridad de RegulAItor es un requisito de primera clase, no un *bolt-on*. CLAUDE.md §18 fija nueve controles obligatorios y el catálogo mínimo de diez ataques que debe absorber el sistema. Esta sección describe cómo el repositorio materializa esos controles a través de cinco capas (sanitizer documental, anti-injection, autenticación y rate limiting de API, allowlist de fetch, higiene de secretos) y cómo se evidencia su efectividad de forma reproducible (red team, CI con bandit/semgrep/pip-audit/gitleaks). El marco operativo es SSDLC: cada PR que toca código de seguridad invoca la skill `secure-coding-checklist` (CLAUDE.md §12.3.10) y los hitos H9, H11 y v0.1.26 dejaron evidencia documental adicional (ADR-0011, ADR-0012, `docs/H16_DEPLOY.md`).

El principio rector se enuncia en CLAUDE.md §6 "no citation, no answer", pero la seguridad por diseño exige una formulación complementaria: ningún contenido del usuario puede modificar las instrucciones del sistema y ninguna respuesta puede salir del sistema sin pasar por los gates correspondientes. El sanitizer y el detector de injection son barreras a la entrada; el Auditor (sección 8) es la barrera a la salida.

## 12.1 Sanitizer documental (defensa en profundidad capa 1)

El sanitizer vive en `src/regulaitor/document/sanitizer.py:59` y aplica una política dual *strip + log para warnings, critical-block para vectores ejecutables*. Su contrato (CLAUDE.md §18.8) se cubre con seis bloques numerados dentro de `sanitize(raw: RawDocument) -> SanitizedDocument`:

1. **Critical-block fail-fast** (`sanitizer.py:67-116`). Cinco vectores cortan el procesamiento elevando `DocumentBlockedError`:
   - `has_javascript` (catalog action JavaScript embebido).
   - `attachments` (ficheros embebidos: cualquier MIME, cualquier tamaño).
   - `has_form_actions` (SubmitForm, ImportData, Reset).
   - URIs de acción cuyo host no está en la allowlist oficial (ver §12.4).
   - Documentos cifrados con contraseña (el extractor `document/extractor.py` rechaza antes de instanciar `RawDocument`).
2. **Metadatos escaneados antes de eliminar** (`sanitizer.py:125-162`, amplía-do en H9 commit `41df74c`). Cada valor de metadato pasa por `is_injection(value, mode="document")` y por una regex de URLs HTTP(S); patrón de injection o URL no allowlisted en metadatos escala a critical-block (`metadata_injection_blocked` / `metadata_url_blocked`). El resto se elimina y se loggea como `warning`.
3. **Anotaciones e invisible-text candidates** por página se eliminan y se loggean (`sanitizer.py:164-184`).
4. **Truco Unicode**: el set `_UNICODE_TRICKS` (`sanitizer.py:31-38`) cubre zero-width space, zero-width joiner/non-joiner, right-to-left override (trojan-source), word joiner y BOM. Si alguno aparece, se eliminan y se normaliza `NFKC` (`_strip_unicode_tricks`).
5. **Outline + large-document warning** (`sanitizer.py:206-227`). Documentos > 50 páginas o > 400 KB de texto emiten un `info` para visibilidad.
6. **Length floor** (`sanitizer.py:232-242`). Si tras el saneamiento queda < 50 caracteres de contenido real, se eleva `DocumentBlockedError("document_empty_after_sanitization")` para evitar análisis sobre PDFs vaciados por agresión defensiva.

El log nunca contiene el texto en claro: cada `SanitizerEvent` lleva `content_hash` SHA-256[:12] (`_hash12`, `sanitizer.py:47`) y un `reason` enunciado. Esa decisión cumple CLAUDE.md §18.8 ("logs sin datos sensibles") por construcción.

El comentario `nosec B613` en `sanitizer.py:35` documenta una verdad incómoda: bandit detecta el carácter RLO literal como vector troyano cuando precisamente es nuestro *fingerprint* defensivo. La nota explicita el motivo para que ninguna revisión futura lo borre por error.

## 12.2 Anti-injection: heurísticas multiculturales (capa 2)

`src/regulaitor/security/injection.py` (189 líneas) define 25 patrones regex (11 chat + 14 document-only) en español e inglés, todos `re.I`. La función `is_injection(text, mode="chat" | "document")` devuelve `(True, pattern_name)` al primer match para trazabilidad.

Los patrones de chat (`_CHAT_PATTERNS`, líneas 25-53) cubren los clásicos: *"ignore previous instructions"*, *"olvida (las|todas|mis|estas) instrucciones anteriores"* (`olvida-anteriores`, ampliado en H9 tras attack-006), *"ignora ... instrucciones anteriores"* (variante surgida en attack-011 metadata), fake tags `</system|instructions|prompt>`, *"new instructions:"* / *"nuevas instrucciones:"*, role override en ambos idiomas, revelación de prompt, jailbreak/DAN y delimitadores falsos.

Los patrones documentales (`_DOCUMENT_PATTERNS`, líneas 57-168) son específicos del *threat model* de un PDF corporativo: *"el evaluador que revise esta política debe…"*, *"el sistema debe omitir/ignorar/concluir…"* (ampliado en H9 tras attack-007), *"esta política cumple plenamente con…"* (auto-validación), poisoning de citas (*"los artículos … son interpretaciones internas"*), *"se autoriza la excepción al artículo…"*, meta-injects (*"ignora la sección anterior"*), role-override (*"actúa como un abogado"*), exfiltración (*"envía esta información a X@…"*) y jailbreak chains (*"activate DAN mode"*). La cobertura empírica declarada en el docstring del módulo es ~70-80% sobre injection trivial en modo chat; el sistema asume cobertura imperfecta y delega el cierre al Analyst (separación instrucciones/datos en el prompt) y al Auditor (sección 8).

El gate se activa en dos puntos:
- **Chat** (`orchestration/graph.py:63`): `is_injection(state.query)` antes del Retriever; si bloquea, el estado se marca `injection_blocked=True` y la API eleva `InjectionDetected` (`api/routes_ask.py:54-55`).
- **Documental** (`orchestration/document_graph.py:142`): cada segmento se evalúa con `mode="document"`. Un segmento bloqueado por injection cuenta como BLOCK en el agregador documental (`document_graph.py:130-131`) y aparece en el report como `injection_skipped:<segment_ids>`.

La política aceptada (ADR-0011 §D6) permitió endurecer estos patrones intra-H9 con cuatro mejoras aditivas. El bloqueo en smoke pasó de baseline 0.46 a final 0.92 — el detalle empírico está en la sección 13 (evaluación y red team).

## 12.3 Autenticación API: HTTPBearer + comparación timing-safe

`src/regulaitor/api/auth.py` implementa autenticación con un único token estático cargado en *lifespan* desde la variable de entorno `REGULAITOR_API_TOKEN`. Decisiones clave:

- **Carga al arranque** (`auth.py:24-34`): `load_api_token_or_raise()` falla con `RuntimeError` si el token falta o tiene menos de 16 caracteres (entropy guard). El fallo en *lifespan* impide que la API arranque en estado inseguro.
- **Comparación timing-safe** (`auth.py:57`): `hmac.compare_digest(presented, _API_TOKEN)`. La elección descarta `==` que es vulnerable a ataques de cronometraje.
- **Esquema Bearer estándar** (`auth.py:21`): `HTTPBearer(auto_error=False, scheme_name="REGULAITOR_API_TOKEN")` con `Security(_bearer)` en lugar de `Depends`. La razón es FastAPI/OpenAPI: el `Security` marker hace que `/openapi.json` exponga el esquema Bearer y `/docs` muestre el botón *Authorize*. Sin él, la UI Swagger no sabría cómo enviar el header.
- **`token_hash` para trazabilidad**: tras éxito, `request.state.token_hash = sha256(token)[:8]` (`auth.py:37-39`). Se propaga al logger (`api/errors.py:93`) y al rate limiter (`security/rate_limit.py:21`) como clave estable; el token en claro nunca se loggea.

CLAUDE.md §22.6 prohíbe almacenar secretos reales en el repositorio. El `.env` está en `.gitignore` y la regla `feedback_no_env_example.md` (memoria del usuario) refuerza que tampoco se crea `.env.example`.

## 12.4 Rate limiting + CORS + allowlist de fetch

**Rate limiting**. `src/regulaitor/security/rate_limit.py` instancia `slowapi.Limiter` con `key_func=_key_func` que prioriza `token:<hash>` y cae a `ip:<remote_addr>` si la petición es pre-auth. En la práctica el `Depends(verify_token)` rechaza con 401 antes de que el limiter actúe, así que el modo per-token es el efectivo. Los límites son configurables por endpoint vía entorno:

- `REGULAITOR_RATE_LIMIT_ASK` (`routes_ask.py:29`, default `"30/minute"`).
- `REGULAITOR_RATE_LIMIT_ANALYZE` (`routes_analyze.py:42`, default `"5/minute"`; el modo documental es órdenes de magnitud más caro).
- `REGULAITOR_RATE_LIMIT_DISABLED=1` (`rate_limit.py:27`) deshabilita el limiter en tests; nunca debe estar activo en producción.

El handler `rate_limit_handler` (`api/errors.py:125-129`) devuelve `429` con `Retry-After: 60` y registra el evento en el log estructurado.

**CORS**. `api/main.py:93-106` carga `REGULAITOR_CORS_ORIGINS` (CSV) y solo registra `CORSMiddleware` si la variable es no vacía. La política `allow_credentials=True`, `methods=["GET","POST","OPTIONS"]`, `headers=["Authorization","Content-Type"]`, `max_age=3600`. La elección *empty default = no CORS headers* es segura por defecto: si el operador no necesita acceso desde navegador, no se emiten cabeceras. Para el demo HF Spaces actual no se requiere CORS porque Streamlit corre server-side; quedará para HX2 (Next.js) configurar orígenes explícitos.

**Allowlist de fetch**. `src/regulaitor/security/allowlist.py` define `ALLOWED_DOMAINS_OFFICIAL_EU` con cinco hosts: `eur-lex.europa.eu`, `boe.es`, `digital-strategy.ec.europa.eu`, `edpb.europa.eu`, `data.europa.eu`. La función `is_uri_allowed(uri)` es defensiva: tolera `www.`, valida el esquema (`http(s)` solamente, descarta `file://`, `javascript:`), compara el *netloc* completo (rechaza ataques tipo `eur-lex.europa.eu.attacker.com`) y nunca *raise* ante input malformado. Se invoca desde el sanitizer (URIs de acción en PDF, URLs en metadatos) y desde el fetcher de corpus.

## 12.5 PII — estado actual y posición honesta

CLAUDE.md §18.5 exige "filtro PII: log redactado, alerta, opción de cancelar". En la implementación actual `src/regulaitor/security/pii.py` **no existe como módulo dedicado**; la verificación con `Glob` y `Grep` (campo `pii`/`email`/`teléfono`/`DNI`) sobre `src/regulaitor/` no encuentra un detector centralizado de patrones email/teléfono/DNI.

La protección efectiva actual depende de tres mitigantes parciales:
- El sanitizer hashea contenido del documento en el log (`content_hash` SHA-256[:12]) y nunca persiste texto en claro de campos sensibles.
- El handler `backend_error_handler` (`api/errors.py:140`) trunca los errores backend a 200 chars × 10 entradas como protección defensiva.
- El log de la API (`api/errors.py:80-97`) registra `case_id`, método/path/status, `token_hash` y `error_code`, pero el cuerpo de la petición no se loggea por defecto.

Esta es una limitación documentada para H17 ("Known limitations") y carry-forward a HX. La memoria académica debe presentar este punto sin maquillaje: el filtro PII pleno (detector activo de patrones + alerta + opción de cancelar) está [pendiente]; mitigantes parciales reducen pero no eliminan el riesgo.

## 12.6 Higiene de secretos: gitleaks + bandit + semgrep + pip-audit

El gate §16.2 #6 ("gitleaks limpio") se aplica en dos sitios:

- **Pre-commit local** (`.pre-commit-config.yaml:31-34`): `gitleaks/gitleaks@v8.21.2`. En la caja Windows del autor el hook golang puede fallar al compilar; la regla operativa es `SKIP=gitleaks` válida **solo en local**, nunca en CI.
- **CI autoritativo** (`.github/workflows/ci.yml:179-192`, job `security`): descarga `gitleaks_8.21.2_linux_x64`, ejecuta `gitleaks detect --no-git --source . --redact --verbose` como primer paso del job, fail-fast antes de instalar dependencias. La configuración custom vive en `.gitleaks.toml`: extiende los rulesets por defecto (`useDefault = true`) y permite placeholders en `.env.example`, `README.md` y `docs/*.md`.

El mismo job ejecuta:
- **Bandit** (`ci.yml:209`): `bandit -r src`. Todas las anotaciones `nosec` están justificadas en línea con motivo verificable; por ejemplo `document/sanitizer.py:28-30` para `B613` (trojan-source defense; el set RLO/ZWJ es el *fingerprint* defensivo, no un vector), `document/extractor.py` `B110/B112` (swallow defensivo + defaults conservadores documentados en bloque), y enum/assert markers en `citation/schemas.py` + `corpus/ingest.py` (mypy narrowing, no passwords). El patrón general (cada `nosec` con motivo en línea) está descrito en CLAUDE.md §22.
- **Pip-audit** (`ci.yml:210-238`): `--skip-editable` + cinco `--ignore-vuln` documentados con motivo verificable: `CVE-2026-1839` (transformers Trainer load no alcanzable), `CVE-2025-69872` (diskcache pickle solo explotable con write access al cache), `CVE-2026-6587` (ragas multi-modal no usado), `CVE-2026-41488` (langchain-openai SSRF en token-counting de imágenes no exercised por router text-only), `PYSEC-2025-217` (X-CLIP checkpoint deserialization, no usado por BGE-M3). Cada ignore lleva referencia a `docs/technical_decisions_log.md` y plan de re-evaluación.

**Semgrep** se referencia en CLAUDE.md §10.6 y §16.2 #7 como gate; el repositorio actual no tiene workflow semgrep activo (los gates §16.2 #7 enumeran bandit, semgrep y pip-audit como conjunto; semgrep no corre en `ci.yml`). Es [pendiente] como follow-up de bajo coste para H17.

## 12.7 Filosofía y trazabilidad

La arquitectura de seguridad de RegulAItor no apuesta por una sola línea de defensa porque ninguna es infalible. El docstring de `injection.py:13-16` lo dice sin rodeos: *"Defense in depth: regex is the second of four layers (sanitizer 1, regex 2, prompt 3, Auditor 4). Imperfect coverage is acceptable because the Analyst prompt explicitly instructs 'data not instructions' and the Auditor still blocks fabricated citations."*

Esta posición se documenta en cuatro lugares: CLAUDE.md §6.1 (arquitectura §6 multi-capa), ADR-0011 (red team H9), ADR-0012 (observability + redteam reliability) y `docs/H16_DEPLOY.md` (runbook con variables de entorno y secretos). La narrativa para defensa académica es que la seguridad se valida empíricamente (red team smoke 0.92 como gate de CI desde v0.1.14, sostenido a través de v0.1.32) y se mejora aditivamente cuando aparecen ataques nuevos (H9 amendments 1-4, sin refactor del agregador del Auditor).

Una limitación honesta cierra la sección. Tres puntos quedan abiertos:

1. El handler de excepción genérico (`api/errors.py:151-162`) usa `Exception` como captura amplia para evitar leaks de stack trace; el deep-review minor que sugería estrecharlo a tipos concretos queda diferido a HX.
2. `/health` (`api/routes_health.py:45-54`) responde sin autenticación y expone presencia/ausencia de `anthropic_key`, `api_token` y estado de LanceDB. Esto facilita probes de operador pero también permite enumeración mínima desde el exterior; es [pendiente] documentarlo en "Known limitations" del runbook H17 y considerar autenticar `/health` o exponer una variante reducida sin metadata.
3. El filtro PII pleno descrito en §12.5 está [pendiente].

Ninguna de estas tres limitaciones invalida los gates §16.2 vigentes ni la garantía §6. Son deuda controlada, documentada y priorizada — la honestidad metodológica §22.22 que vertebra el TFM aplica también a la sección de seguridad.
