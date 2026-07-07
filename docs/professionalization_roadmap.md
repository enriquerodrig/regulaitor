# RegulAItor — Roadmap de Profesionalización (HX)

> Estado: **en ejecución** (propuesta original 2026-07-03; estado actualizado
> 2026-07-05). Anclado a una auditoría de madurez multi-agente read-only ($0,
> 9/10 dimensiones assess→verify + síntesis; workflow `wf_50a2c924-9fa`). Cada gap
> citado con evidencia de fichero y verificado adversarialmente contra el código real.
>
> **Estado de ejecución por fase (2026-07-05):**
> - **P1 — DONE** (frontend en CI + regresión retrieval $0 + property/fuzz/mutation §6 +
>   pytest hardening + pin lancedb/33 CVEs; commits `8b0d0f4`→`fafcba9`).
> - **P2 — DONE** (governance docs = código 9 corpora/PII built + `source_url` canónico
>   sin leak dev-path + PII advisory en `/ask` + aviso privacidad BFF + `threat_model.md`).
> - **P3 — DONE** (5/5: `/metrics` block-rate live + audit ON + GDPR DSR + gestión/rotación
>   de secretos documentada + red team a las 9 normas).
> - **P4 — PARCIAL**: el spike de release engineering y **P4.1 Council-skip** están DONE;
>   el **deploy soberano vivo (Régimen A) queda DEFERRED-infra** y el **A/B pagado de
>   Mistral (G1) queda DEFERRED-paid**.
> - **P5 — DEFERRED (pilot-gated)**: quotas/HA solo cuando exista un piloto agendado.
>
> Las anotaciones **[DONE] / [OPEN] / [DEFERRED-*]** por hito abajo son aditivas; el texto
> original del plan se conserva íntegro.

## 1. Contexto y tesis

Sin usuarios a corto plazo, el objetivo **no** es validación de mercado sino
**profesionalizar**: llevar la solución de "MVP sólido / demo pública" a
**production-grade**.

**Hallazgo central (la tesis del roadmap):** el **moat ya es production-correct**
— la verificación de citas §6 (validator + Auditor) está calibrada, es determinista,
está gateada en CI, y dos REVERTs pagados (v0.1.23, v0.1.30) prueban que esa capa
está afinada. Lo que **no** es production-grade es la **cáscara** alrededor del moat:
el CI no cubre el frontend, no hay observabilidad operable, no hay IaC/deploy, y los
**3 constraints del founder son "seams cableados + prosa", no capability corriendo**:

- **C1 — inferencia self-hosted open-model:** el seam `self_hosted` del router existe
  pero apunta a la API de Mistral La Plateforme (SaaS externo EU, no self-hosted).
- **C2 — expansión/currency del corpus:** 9 normas ingestadas, pero sin regresión de
  retrieval en CI, `source_url` roto en los manifests, y currency sin trackear.
- **C3 — deploy EU-soberano:** el demo vivo es HF Spaces (US-hosted); no hay target
  soberano ni IaC.

**Principio rector:** endurecer el moat y su cáscara **antes** de captación; no
construir superficie de producto (portales, quotas UI, i18n, HA) que nadie usa aún.

## 2. Scorecard de madurez

Escala: `demo` (feliz-path) · `mvp` (feature-complete pero rugoso) · `pilot-ready`
(seguro + observable para un piloto controlado) · `production-grade`.

> **Nota (2026-07-05):** este scorecard es el **snapshot de la auditoría original**
> (pre-ejecución). Varios "gaps titulares" ya están **cerrados** por P1-P3 (frontend en
> CI, `source_url` canónico, telemetría/block-rate §6 live, governance docs = código,
> red team a las 9 normas). Se conserva verbatim como línea base; el estado real vive en
> el header de ejecución arriba y en las anotaciones **[DONE]/[OPEN]/[DEFERRED-*]** por hito.

| Dimensión | Madurez | Gap titular |
|---|---|---|
| §6 moat (validator + Auditor) | **pilot-ready** | Correcto y gateado, pero solo example-tested — sin property/fuzz/mutation que cace el próximo bypass (los 2 ya parcheados se hallaron a mano). |
| Testing & code quality | **pilot-ready** | 1162 tests backend + cov 85% gateada, pero **frontend BFF con CERO CI** y moat sin property/mutation. |
| Security & SSDLC | **pilot-ready** | Defensa en profundidad fuerte, pero security report congelado en H9, sin threat model, sin gestión/rotación de las 8 keys en claro. |
| Observability & ops | **mvp** | Primitivas bien diseñadas pero **toda la telemetría durable OFF por defecto** (incluido el demo); sin métricas, sin señal live del block-rate §6, sin alertas. |
| CI/CD & release | **mvp** | CI sólido pero **deploy 100% manual**: sin workflow de deploy, sin IaC, sin scan/sign/SBOM, sin release automation. |
| Deployment & infra (C1/C3) | **pilot-ready** | Contenerización sólida en PaaS gestionada, pero C1 solo bridge Mistral-API y C3 sin target/IaC (demo US-hosted); sin backup/DR del audit DB. |
| Corpus & RAG (C2) | **pilot-ready** | Pipeline de 9 normas bien hecho, pero **sin regresión de retrieval $0 en CI**, `source_url` con path de la máquina de dev en cada manifest, currency sin trackear. |
| API, multi-tenancy & quotas | **pilot-ready** | Aislamiento fail-closed y seguro para pocos tenants, pero uso **contado-no-impuesto** (sin 429), limiter `memory://` per-worker, OpenAPI sin error shapes. |
| Frontend & UX | **mvp** | BFF endurecido (nonce-CSP, CSRF, render §6 fiel) pero cero CI, sin error/loading boundaries, sin e2e, sin streaming en la superficie de 15-60s. |
| Product compliance & data gov | **mvp** | Bloques existen pero AI Act assessment + model/data cards **contradicen el código** (4 vs 9 corpora, "PII no construido" vs construido); sin GDPR DSR/retención, sin DPA. |

> La 10ª dimensión (docs & reproducibility) no completó el structured-output; sus
> gaps probables (publicar MkDocs, docs de API para integradores, drift ADR↔decisions-log)
> están absorbidos en las Fases 2 y 4.

## 3. Roadmap por fases

Cada hito lleva `[esfuerzo | constraint | §6]`. Esfuerzo S/M/L/XL. Todas las Fases 1-2
son **$0** (sin runs LLM de pago, sin infra nueva).

### Fase P1 — Cerrar los puntos ciegos de CI (barato, máxima palanca, desbloquea todo) · $0 — **[DONE]**

> **[DONE]** Cerrada 2026-07-05 (commits `8b0d0f4`→`fafcba9`). Los 4 hitos P1.1-P1.4
> shipeados; el §6 pasa ahora de example-tested a **property/fuzz + mutation-tested**
> (4 auditorías de mutación: `scripts/sec6_*_mutation_audit.py` +
> `scripts/sec18_*_mutation_audit.py`). CI de `main` pasó de ROJO (~06-30) a VERDE 6/6.
> Incluyó el pin de lancedb + 33 CVEs no cubiertos en el plan original.

- **P1.1 · Frontend BFF en CI** `[S | C3 | no]` **[DONE]** — nuevo job/workflow: `npm ci` +
  `eslint` + `tsc --noEmit` + `vitest run` + `next build`. El BFF es la **frontera de
  seguridad del deploy soberano** (nonce-CSP por petición, CSRF same-origin, cookie
  httpOnly, proxy /audit); 7 suites / 44 tests ya existen pero `ci.yml` es solo-Python
  → una regresión de CSRF/cookie/CSP shipea con CI en verde. **Gap #1 verificado
  (aparece en 5 dimensiones).**
- **P1.2 · Harness de regresión de retrieval $0 en CI** `[M | C2 | no]` **[DONE]** — recall@k /
  purity cross-corpus sobre un mini-índice committeado + gold, gateado. Hoy todo test
  de recall es `@slow` (excluido de CI) y el único $0 valida lógica de gate, no
  recall@k. Un re-index / bump de embeddings / cambio de chunking regresa recall sin
  señal. **Keystone de C2** (desbloquea A/B seguro de modelo/reranker después).
- **P1.3 · Property/fuzz + mutation testing del §6** `[M | — | testea §6 sin tocarlo]`
  **[DONE]** — property Hypothesis: "ninguna cita cuyo texto normalizado esté ausente del párrafo
  del corpus puede validar" + `mutmut` sobre validator.py + auditor.py. **NO edita los
  ficheros sagrados** (el property solo *asserta* el invariante; mutmut corre sobre
  copias) → refuerza confianza §6 a $0 sin riesgo. Los 2 bypasses ya parcheados
  (substring 'el', whitespace) se hallaron a mano — esto los habría cazado.
- **P1.4 · Endurecer pytest** `[S | — | no]` **[DONE]** — `pytest-timeout` + `pytest-randomly`
  (order-dependence / flaky) como rider.

**DoD P1:** CI falla si el frontend rompe, si recall@k cae, o si un mutante del §6
sobrevive; suite determinista bajo orden aleatorio.

### Fase P2 — Credibilidad & compliance-de-sí-mismo (doc + código pequeño) · $0 — **[DONE]**

> **[DONE]** Cerrada 2026-07-05. Governance docs alineados a **9 corpora + PII
> construido**; `source_url` canónico EUR-Lex en los 9 manifests + índice (cero
> `file:///` en `corpus/manifests`); PII advisory shipeado en `/ask`; aviso de
> privacidad en el BFF; `docs/threat_model.md` publicado.

- **P2.1 · Governance docs = código** `[M | C2 | no]` **[DONE]** — refrescar
  `ai_act_assessment.md` + `model_card.md` + `data_card.md` a **9 corpora + PII
  construido** (hoy dicen "cuatro instrumentos / 1569 chunks / PII pendiente"). Una
  auto-evaluación de compliance que se equivoca sobre su propio alcance mata la tesis
  §22.22.
- **P2.2 · Fix `source_url` en los manifests** `[S | C2 | no]` **[DONE]** — ~~hoy~~
  (pre-fix) `file:///C:/Users/enriq/...` en cada artículo de cada manifest (226 solo en
  ai_act.json): era a la vez la **fuga del home dir** y el **link de procedencia roto**
  que un auditor sigue para verificar una cita. **Sustituido** por la URL canónica
  EUR-Lex CELEX (ya en `registry.py`); **cero `file:///` en `corpus/manifests`**.
- **P2.3 · PII gate en el path chat `/ask`** `[M | — | no]` **[DONE, con residual]** —
  ~~hoy el escaneo PII vive en doc-mode + Streamlit; el API `/ask` no escanea~~ (pre-fix).
  **Shipeado:** `GET /ask` escanea el query y adjunta un `pii_summary` **advisory**
  (counts-only, §18.8; `src/regulaitor/api/routes_ask.py`). **Residual abierto (por
  diseño):** es advisory, **no** hard-block; el escaneo es regex-MVP, **no NER
  exhaustivo** → falsos negativos posibles.
- **P2.4 · Aviso de privacidad/cookies en el BFF** `[S | — | no]` **[DONE]**.
- **P2.5 · Threat model + refresh del security report** `[M | — | no]` **[DONE]** — ~~el
  report está congelado en H9~~; **`docs/threat_model.md` publicado** documentando el
  modelo de amenazas actual (auth surface, BFF, multi-tenancy, PII, §6).

**DoD P2:** ningún doc de gobernanza contradice el código; toda cita enlaza a EUR-Lex;
paridad PII chat/doc; threat model publicado.

### Fase P3 — Suelo de operabilidad (que sea operable, no ciego) — **[DONE]**

> **[DONE]** Los 5 hitos P3.1-P3.5 shipeados. `observability/metrics.py` + `GET /metrics`
> (block-rate §6 live); audit-trail ON; GDPR DSR (`scripts/dsr.py` access/erasure + 365d
> retención + `docs/data_retention.md`); gestión/rotación de secretos documentada
> (`docs/secret_management.md` + `.github/dependabot.yml`); red team ampliado a las 9
> normas (`redteam/attacks.jsonl` = 59 filas, ataques 051-059 + test $0 de rechazo del
> validator). **Residual operator-side:** la **rotación** efectiva de las keys sigue
> siendo una acción de operador (documentada, no automatizada).

- **P3.1 · Suelo de observabilidad** `[L | C3 | no]` **[DONE]** — backend de métricas
  (`/metrics` Prometheus u OTel) + **gauge live del block-rate/verdict §6** (la única
  señal safety-relevant en prod; hoy solo existe redteam-smoke pre-merge) + **alerta
  on block-rate-collapse**. Suelo, no plataforma (una señal + una alerta).
- **P3.2 · Audit-trail ON-by-default + retención documentada** `[M | — | no]` **[DONE]** —
  el problema #4 del producto es trazabilidad-para-auditoría; ~~hoy shipea con auditoría
  OFF por defecto~~ → **audit-trail ON**.
- **P3.3 · GDPR DSR sobre el audit store** `[M | — | no]` **[DONE]** — `scripts/dsr.py`
  acceso/borrado + política de retención 365d (`docs/data_retention.md`).
- **P3.4 · Gestión + rotación de secretos** `[M | C1 | no]` **[DONE, con residual
  operator-side]** — cadencia documentada (`docs/secret_management.md`) + Dependabot
  (`.github/dependabot.yml`). **Residual abierto:** la **rotación efectiva** de las keys
  sigue siendo una acción de operador (bloqueante pre-captación que ya señalaste; la doc
  no lo automatiza).
- **P3.5 · Red team a las 9 normas** `[M | C2 | no]` **[DONE]** — ~~hoy 15 ataques AI Act
  + 11 GDPR; NIS2/DORA/DORA-RTS/AMLR/MiCA/TFR = 0 cobertura adversarial~~ (pre-fix) →
  **`redteam/attacks.jsonl` = 59 filas** (ataques 051-059 ampliando cobertura a las 9
  normas) + test $0 de rechazo del validator, manteniendo el gate `block_rate ≥ 0.90`.

**DoD P3:** el servicio se puede operar (señal + alerta del §6), auditoría por defecto,
DSR cumplible, secretos gestionados, red team cubre las 9 normas.

### Fase P4 — Release engineering & deploy soberano (la tesis C1/C3, mayor esfuerzo) — **[PARCIAL]**

> **[PARCIAL]** El **spike** de release engineering está DONE y la decisión **P4.1
> Council-skip (sec6-02) está DONE** (evaluada y RECOMENDADO-NO-HACER por
> over-engineering). Lo pendiente es la tesis soberana viva:
> - **Deploy soberano vivo (Régimen A): DEFERRED-infra** — requiere infra real
>   (GPU EU + target soberano OVHcloud/Scaleway + IaC), no shipeable a $0.
> - **A/B pagado de Mistral (G1): DEFERRED-paid** — requiere un run LLM de pago;
>   se agenda con decisión explícita de gasto.

- **P4.1 · IaC + workflow de deploy** `[L | C3 | no]` **[DEFERRED-infra]** — `build →
  scan → sign → SBOM → deploy on tag` + smoke post-deploy + backup/DR del audit DB.
  (Spike hecho; el workflow vivo sobre infra soberana queda diferido.)
- **P4.2 · Inferencia self-hosted real** `[XL | C1 | no]` **[DEFERRED-infra + DEFERRED-paid]**
  — vLLM/TGI sobre GPU EU detrás del seam `self_hosted` existente (cierra C1 de verdad;
  el code-slice `guided_json` diferido se prueba aquí). El **A/B pagado de Mistral (G1)**
  para validar el seam queda **DEFERRED-paid**.
- **P4.3 · Target EU-soberano** `[L | C3 | no]` **[DEFERRED-infra]** — OVHcloud
  SecNumCloud / Scaleway, validado con cold-start real sobre persistent-volume.
  (El **deploy soberano vivo — Régimen A** vive aquí; diferido por infra.)
- **P4.4 · DPA + registro de subprocesadores** `[M | C3 | no]` **[OPEN]** — respalda el
  claim "cero subprocesadores US". (Depende del target soberano P4.3.)

**DoD P4:** deploy reproducible y firmado sobre infra soberana; inferencia sin SaaS
externo; el claim de soberanía tiene papel legal detrás.

### Fase P5 — Production-hardening & quotas (SOLO cuando haya un piloto agendado) — **[DEFERRED (pilot-gated)]**

> **[DEFERRED — pilot-gated]** Quotas / HA no se activan hasta que exista un piloto
> con cliente nombrado; los seams (redis, Postgres) ya están cableados.

Quota enforcement (429/402 leyendo `count_turns`), limiter `redis://` multi-worker,
API URL-versioning + OpenAPI error shapes, corpus currency (CELEX consolidados +
amendment tracking), audit chain tamper-evident, paginación/export del audit. Los
seams (redis, Postgres) ya existen; se activan cuando la carga sea real.

## 4. Lo que NO haremos ahora (YAGNI — sin usuarios a corto plazo)

- **No** portales self-service de tenants, CRUD/admin de provisioning, ni UIs de
  rotación de tokens. Config estática env/fichero + restart basta.
- **No** UIs de quotas, dashboards de billing, ni gestión de presupuesto per-tenant.
  (El enforcement es P5; además bajo C1 self-hosted el coste es cómputo acotado, no
  gasto API metered → menos urgente de lo que parece.)
- **No** i18n / localización FR-DE-IT ni corpus multilingüe (24 idiomas). El pipeline
  ya es language-parametrizado y BGE-M3 multilingüe → mecánico más tarde. ES/EN cubre
  el mercado primario y el demo.
- **No** infra de escala/HA que nadie necesita: multi-worker gunicorn + redis,
  réplicas horizontales, Postgres, Grafana + on-call. Single-worker + SQLite +
  `memory://` es explícitamente correcto para un piloto controlado. Shipear el **suelo**
  de métricas (una señal + una alerta), no una plataforma.
- **No** pulido visual / landing de marketing / dark-mode / streaming-token UX. Sobrio
  por diseño es decisión de marca; error/loading boundaries son polish de fase tardía.
- **No** AI Act Art. 50.2 C2PA/watermarking, pentest externo/DAST, proceso formal de
  postmortem/on-call, ni endpoint `/cases` todavía. En el ledger, no en el corto plazo.
- **No** tocar `citation/validator.py` ni `agents/auditor.py` para perseguir
  verdict_match/retrieval — los ficheros §6 son sagrados, la capa está calibrada (2
  REVERTs pagados lo prueban), y cualquier cambio necesita ADR. El moat es lo único que
  ya está production-quality-correcto.

## 5. Secuenciación recomendada

> **Estado (2026-07-05):** los pasos 1-3 (P1 → P2 → P3) están **ejecutados y DONE**. El
> plan de secuenciación de abajo se conserva como estaba escrito; lo que resta es el paso
> 4 (P4, tesis soberana C1/C3 — parcial: spike + Council-skip DONE, deploy vivo y A/B
> Mistral diferidos) y el paso 5 (P5, pilot-gated).

1. **Arrancar por P1** — todo $0, máxima palanca, desbloquea el resto. **P1.1 (frontend
   en CI) primero**: es el gap #1 verificado, esfuerzo S, y hoy la frontera de seguridad
   del deploy soberano shipea sin gate.
2. **P2 en paralelo/seguido** — $0, cierra las contradicciones de credibilidad
   (governance docs, `source_url`) que son baratas y foundacionales para el moat.
3. **P3** — el salto de "seguro" a "operable"; P3.4 (secretos) alinea con tu bloqueante
   ya señalado.
4. **P4** — la tesis soberana C1/C3; mayor esfuerzo y coste (GPU), se aborda cuando P1-P3
   estén verdes y con decisión explícita de gasto.
5. **P5** — diferida hasta que exista un piloto con cliente nombrado.

Cada hito sigue el loop del proyecto: mini-plan → OK → implementar → review adversarial
→ gate verde → commit → push. Los que rozan §6 (ninguno edita los ficheros sagrados en
P1-P3) pasarían por ADR si eso cambiara.
