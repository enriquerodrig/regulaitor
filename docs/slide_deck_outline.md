# Slide Deck Outline — RegulAItor (Defensa TFM)

Outline de ~20 diapositivas en español para la defensa del TFM
*RegulAItor — servicio multi-agente de cumplimiento normativo europeo*.
Formato pensado para 15-20 min de presentación + 10-15 min de Q&A.

Cada diapositiva incluye: **título**, **bullets visibles**, **notas del orador**
(con presupuesto de tiempo y transiciones), y **anticipación Q&A** cuando
aplica. Las citas a `file:line` y `ADR-NNNN` están pensadas para que el
ponente pueda profundizar bajo presión.

Anclajes documentales globales: `CLAUDE.md` §6 (invariante "no citation, no
answer"), §6.1 (arquitectura 4 capas), §16.3 (linaje H0→v0.1.32), §22.22
(disciplina honesty), `docs/technical_decisions_log.md`,
`docs/evidence_matrix.md`, 35 ADRs en `docs/adr/`.

---

## Slide 1 — Portada

**Título visible**:
RegulAItor — Cumplimiento normativo europeo con citas verificables.
TFM Máster en IA Generativa. Autor: [nombre]. Tutor: [nombre]. Fecha defensa.

**Bullets**:
- Servicio multi-agente: chat normativo + análisis documental.
- Regla central: *no citation, no answer* (CLAUDE.md §6).
- Demo en vivo: `https://huggingface.co/spaces/enriro00/regulaitor`.
- Tag `v0.1.32-h16-deploy`; cierre académico `v1.0.0` (H17 en curso).

**Notas del orador (60 s)**:
Presentación personal breve. Anclar la narrativa: "RegulAItor no responde sin
cita verificable; convierte la consulta normativa rutinaria y la revisión
documental en un acto auditable, en minutos y por céntimos". Avisar que el
material está disponible: repo + demo + memoria + 35 ADRs.

---

## Slide 2 — El problema (Hook)

**Título**: Cuatro problemas del cumplimiento normativo en PYME europeas.

**Bullets**:
1. Coste alto de consulta jurídica/compliance externa.
2. Lentitud en revisión documental interna.
3. Riesgo de alucinación de LLMs generalistas.
4. Falta de trazabilidad para auditoría.

**Notas (60 s)**:
Anchor en usuario primario `CLAUDE.md` §4: responsable de calidad/compliance/DPO
o IT manager en PYME 50-500 empleados. Aclarar limitación: **no sustituye
asesor jurídico** (CLAUDE.md §3); es herramienta de primera línea. Transición
al §6 como la respuesta directa al problema #3 y #4.

---

## Slide 3 — La solución: regla "no citation, no answer"

**Título**: §6 — invariante central de RegulAItor.

**Bullets**:
- Toda salida del Analyst pasa por el Auditor (`src/regulaitor/agents/auditor.py:54`).
- Auditor valida 3 checks por cita: artículo existe / apartado existe /
  texto coincide con corpus (`src/regulaitor/citation/validator.py:36`).
- Sin cita verificable → BLOCK o `requires_human_review`.
- Citas verificadas **contra el corpus oficial**, nunca contra el conocimiento del modelo (CLAUDE.md §22.15).

**Notas (90 s)**:
Este es el centro de la contribución del proyecto. Subrayar que el invariante
se ha mantenido a través de 30+ milestones y 2 REVERTs documentados.
Transición a la demo.

**Q&A anticipado**: "¿Y si el modelo paraphrasea la cita?" → Slide 8 4-capa.

---

## Slide 4 — Demo (screencast 30s + captura estática)

**Título**: Demo en producción (HF Spaces).

**Bullets**:
- Caso: "AI Act sistemas alto riesgo" con `corpus=auto`.
- Verdict: PASS · 2 Findings · 1 cita valid + 1 paraphrase.
- Tiempo respuesta usuario final: 15-60 s (CLAUDE.md §17 #7).
- URL: `https://huggingface.co/spaces/enriro00/regulaitor`.

**Notas (90 s)**:
Reproducir screencast pre-grabado de 30 s (evita riesgos de demo en vivo: red,
cold-start ~5 min). Después captura estática con el verdict, las citas y el
notice del Auditor. Resaltar el rojo/verde por cita: 1 paraphrase visible
demuestra v0.1.25 D2 §6.1 architecture funcionando (ADR-0032).

**Q&A anticipado**: latencia y coste → Slide 12.

---

## Slide 5 — Arquitectura C4 L1

**Título**: Contexto del sistema.

**Bullets**:
- Actores: Compliance Officer + Tutor TFM.
- Fronteras: Streamlit UI + FastAPI HTTP.
- Servicios externos: EUR-Lex (corpus), Anthropic (Sonnet 4.6 prod + Haiku 4.5 judge), HuggingFace Hub (BGE-M3 + reranker).
- Trust boundary: sanitizer + injection regex antes del LLM (`src/regulaitor/security/injection.py`).

**Notas (60 s)**:
Mostrar diagrama C4 L1 de `docs/architecture.md`. Énfasis en que es un sistema
*cerrado* sobre corpus oficial, no un buscador web. Transición a la capa de
pipeline interna.

---

## Slide 6 — Pipeline RAG

**Título**: Recuperación estructurada por artículo.

**Bullets**:
- Chunking estructural por artículo (CLAUDE.md §10.3) — no mezcla artículos.
- Embeddings multilingües BGE-M3 (`rag/embeddings.py`).
- Reranker bge-reranker-v2-m3 (`rag/reranker.py`).
- LanceDB local: **1569 chunks** (AI Act 687 + GDPR 324 + NIS2 244 + DORA 314).
- Metadatos por chunk: `norma, articulo, apartado, idioma, version, fuente, fecha_ingesta, hash`.

**Notas (75 s)**:
Anclar en ADR-0004 (RAG architecture H2) y ADR-0015 (NIS2+DORA H14).
Mencionar la decisión de pivote a PDF (ADR-0003) y el bypass WAF con
Playwright para EUR-Lex (legítimo, doc público). Hito v0.1.30 intentó
title-augmented corpus embeddings → REVERTED (anti-patrón documentado).

---

## Slide 7 — Sistema multi-agente

**Título**: Tres agentes + Council of Judges.

**Bullets**:
- **RetrieverAgent** (`agents/retriever.py`, H3) — recupera artículos relevantes.
- **AnalystAgent** (`agents/analyst.py`, H4) — genera Findings con citas.
- **AuditorAgent** (`agents/auditor.py`, H4) — valida citas, agrega verdict.
- **Council of Judges** (`agents/council.py`, H13, ADR-0014) — 3 jueces LLM independientes (Haiku/GPT-4o/Llama-3.3-70b vía router).
- Orquestación: LangGraph (`orchestration/graph.py`).

**Notas (90 s)**:
Recalcar que el Analyst nunca emite directamente al usuario. El Auditor es
pure-Python (mecánico, no LLM), garantizando determinismo. El Council es
advisory por defecto (`AdvisoryMajorityPolicy`); v0.1.19 ADR-0025 activó
`MonotonicEscalatePolicy` con dirección conservative-only (PASS→RHR en
unanimidad BLOCK, nunca relaja). Router multi-LLM en H12 (ADR-0013).

---

## Slide 8 — §6 arquitectura 4 capas (centerpiece)

**Título**: La invariante §6 como contrato evolutivo, no monolítico.

**Bullets**:
- **Capa (a)** Per-citation validator — `citation/validator.py` (byte-equivalent semantics desde H4; v0.1.24 ADR-0031 añadió `failed_check` observabilidad aditiva).
- **Capa (b)** Finding-Lenient — `auditor.py:65` `any(r.validated)` (byte-unchanged desde v0.1.21).
- **Capa (c)** Turn-level aggregation — v0.1.21 quorum (ADR-0027); v0.1.25 partial-routing softening (ADR-0032); v0.1.29 all-blocked Mirror (ADR-0034).
- **Capa (d)** Prompt-level forbid — v0.1.28 v1.6 doc_analyst Hard rule 4 inviolable (ADR-0033).

**Notas (120 s — slide más densa, justificado)**:
Este es el punto más técnico de la defensa. Explicar que cada capa preserva
el enforcement boundary §6 por construcción. Ejemplo concreto: el helper
`_all_blocked_findings_paraphrase_only` (`auditor.py:20-48`) sólo retorna True
si TODAS las citas invalid de los Findings bloqueados tienen `failed_check==3`
(Check 3 paraphrase mismatch donde artículo Y apartado SÍ existen en corpus).
Cualquier Check 1 (article fabrication) o Check 2 (apartado fabrication)
fuerza False → preserva routing original. **Fabricación nunca es PASS por
construcción**.

**Q&A anticipado**: "¿No es esto loosening?" → respuesta: ablation diagnostic
v0.1.25 5-bucket (Bucket A=0, C=0); §6 enforcement boundary no se mueve.

---

## Slide 9 — Contribución metodológica: §22.22 honesty discipline

**Título**: 13 milestones consecutivos con framing honesto.

**Bullets**:
- v0.1.19 → v0.1.32: cada cierre incluye disclosures verbatim de gaps medidos vs prometidos, costes inesperados, decisiones reverted.
- Patrón: per-task reviews validan correctness; cumulative empirical validation vive a cadencia paid-milestone.
- Ejemplo v0.1.22 (ADR-0029, 10 disclosures): SSL Windows CryptoAPI CRL bloqueó 3 probes ($0 cada); Capa A schema bug shipped silently broken 12 h; budget €1.91 vs forecast high €3.78.
- Metodología: **diagnose → intervene → measure → refute → revert → document** = science cycle.

**Notas (90 s)**:
Argumento central para la defensa: la honestidad metodológica es parte de la
contribución del TFM, no una nota al pie. Mostrar fragmento de un disclosure
verbatim del decisions log. Mencionar que esto refuerza el ethos académico
frente a "demo theater" comunes en proyectos LLM. Transición a los REVERTs
como evidencia.

---

## Slide 10 — Los dos REVERTs (science cycle empírico)

**Título**: Cuando el método produce REVERT, también es contribución.

**Bullets**:
- **v0.1.23 REVERT** (Auditor lenient quorum Design B; ADR-0030 §REVERT).
  Predicción: verdict_match +0.10. Resultado: -0.03; 0/10 H1 cases flipped
  (vs predicho 6-7). Causa: Tier 1 quorum **no era el bottleneck** — la
  capa de routing correcta era Strict-Answer partial (Layer c) no la quorum-count.
- **v0.1.30 REVERT** (title-augmented corpus embeddings; ADR-0035 §REVERT).
  Predicción: citation_recall ≥0.38 doc-mode. Resultado: 0.33 flat; doc-001
  precision 0.50→0.00 (5x over-citation). Mismo mecanismo que v0.1.28
  T4-extra: breadth dilution.
- En ambos casos: §6 invariante HELD; reversión atómica; ADR retenido con §REVERT como registro científico.

**Notas (120 s)**:
Honest framing fuerte. El REVERT no es un fracaso del método; el método
*es* lo que permite revertir sin perder ni la safety ni el rigor. Esto es
literalmente lo que separa la investigación rigurosa de la ingeniería de
producto cortoplacista. Citar la cifra: 30+ milestones, sólo 2 REVERTs,
ambos documentados y reproducibles.

**Q&A anticipado**: "¿Y por qué no probó esto en sandbox antes?" → respuesta:
$0 cache-mining diagnostics existen (v0.1.22.1, v0.1.24.1) pero algunos
mecanismos sólo son observables con paid runs reales; ése es el coste honesto
del método.

---

## Slide 11 — Asimetría científica v0.1.30 (query-side vs corpus-side)

**Título**: Un hallazgo no-obvio del REVERT v0.1.30.

**Bullets**:
- v0.1.28 T4-bis (SHIP): title-prepend al **query** lifted citation_recall 0→0.33.
- v0.1.30 (REVERT): title-prepend al **corpus** broke precision 0.50→0.00.
- Misma intervención conceptual, **opuesto efecto empírico**.
- Mecanismo: corpus-side amplía recall del retrieval → v1.6 doc_analyst sobre-emite Findings → precision colapsa.

**Notas (90 s)**:
Insight defendible: la simetría no es trivial en sistemas RAG cuando el
modelo downstream tiene un prompt "emit Finding per relevant chunk". Este
hallazgo se incluye explícitamente en `docs/technical_decisions_log.md`
§v0.1.30 y ADR-0035 §REVERT (lección c). Vale como hallazgo científico
publicable.

---

## Slide 12 — Métricas headline

**Título**: Resultados medidos (no prometidos).

**Bullets**:
- **verdict_match +0.33** (v0.1.25 D2; 0.40→0.73 H10 30-case; mayor lift del linaje).
- **citation_recall 0.81** aspirational ≥0.80 PRESERVED (v0.1.29).
- **redteam-smoke 0.92** (gate §16.2 #4 ≥0.90) — carry desde v0.1.14.
- **7/7 v0.1.20-bar PASS** en v0.1.25 y v0.1.29.
- **§6 invariante 100% preservada** a través de 30+ milestones.
- Coste medido por consulta: ~€0.054 (sobre soft bar €0.05 por overhead Capa C retry; ADR-0027 D4).

**Notas (90 s)**:
**Importante (§22.22)**: distinguir métricas medidas vs aspiracionales (CLAUDE.md
§17). Los thresholds aspiracionales (≥0.85 faithfulness, ≥0.90 citation
precision) son targets; los medidos están documentados con sus N + cohort +
provider drift caveats. La narrativa NO es "RegulAItor cumple §17"; es
"RegulAItor mide rigurosamente y documenta gaps".

**Q&A anticipado**: "¿Por qué citation_precision 0.27?" → respuesta: v1.5
Finding-based refusal emite más citas por refusal (mecanismo conocido); en
H15 a HX está la calibración Auditor + Council para ese cierre.

---

## Slide 13 — Despliegue (HF Spaces live demo)

**Título**: H16 — despliegue público reproducible.

**Bullets**:
- Hugging Face Spaces (gratis, Streamlit SDK): demo TFM público.
- Docker multi-stage (`Dockerfile`) + docker-compose (api:8000 + streamlit:8501).
- Corpus baked-in vía Git-LFS (1569 chunks); cold-start ~5 min.
- Foundation reusable para Render/Fly.io (CLAUDE.md §10.8).
- Runbook completo en `docs/H16_DEPLOY.md`.

**Notas (60 s)**:
Distinguir entre el demo live (HF Spaces, optimizado para "future product"
preference del autor) y el target original CLAUDE.md (HF Spaces como MVP
public). 12 rounds de iteración deploy (R1-R12) documentados en memoria
`v0.1.32_h16_deployed_H17_ready.md`.

---

## Slide 14 — Limitaciones honestas

**Título**: §22.22 — lo que no funciona aún.

**Bullets**:
- Doc-mode citation_recall máximo 0.33 (N=10) — gap retrieval semántico descriptivo→prescriptivo no cerrado.
- Latencia p95 user-facing 15-60 s vs target 12 s (CLAUDE.md §17 #7).
- citation_precision 0.27 vs aspirational 0.90 (over-emission en refusal Findings).
- Council Groq I-2: ~6 panels degraded a 2-OpenAI por cap free-tier.
- Corpus limitado a 4 normas; multilingüe sólo ES+EN.
- HF token leaked en sesión deploy (memoria flag) — pendiente rotación post-demo.

**Notas (90 s)**:
Reconocer estas limitaciones explícitamente fortalece, no debilita, la
defensa. Marca el contraste con presentaciones "todo verde". Cada limitación
tiene carry-forward documentado (HX1-HX5 o H17).

---

## Slide 15 — Cumplimiento M1-M5 del Máster

**Título**: Evidencia por módulo.

**Bullets**:
- **M1 Modelos+prompts**: router multi-LLM `models/router.py`, prompts versionados `agents/prompts/`, ADR-0013.
- **M2 Agentes+autonomía**: 3 agentes + Council, LangGraph, Auditor §6, ADR-0006/0014.
- **M3 RAG+evals+despliegue+monitorización**: `rag/`, `evals/`, deploy HF, LangFuse ADR-0012.
- **M4 Seguridad+red team**: sanitizer, injection regex, redteam-smoke 0.92, ADR-0011.
- **M5 Proyecto integrador P1-P7**: README, ADRs, evals reports, redteam reports, deploy, observability.

**Notas (60 s)**:
Remitir a `docs/evidence_matrix.md` para detalle exhaustivo. Cada celda tiene
file:line + ADR. Mencionar que es el "spine" de la memoria académica H17.

---

## Slide 16 — Roadmap post-TFM (HX1-HX5)

**Título**: Trabajo futuro identificado.

**Bullets**:
- **HX1** LoRA fine-tune severity classifier (Llama-3.1-8B).
- **HX2** Frontend Next.js (App Router, triple superficie).
- **HX3** Webhook / GitHub Action conector.
- **HX4** MCP server externo.
- **HX5** Prometheus + Grafana avanzado.
- Otros: HyDE / hybrid BM25+dense / custom legal reranker (post-v0.1.30 REVERT, ADR-0035 alternatives).

**Notas (45 s)**:
Énfasis en que estos no son ideas sueltas: están priorizados en CLAUDE.md
§15.3 y referenciados desde los REVERTs como carry-forwards.

---

## Slide 17 — Anticipación Q&A

**Título**: Cuestiones probables del tribunal.

**Bullets** (preguntas + atajos a slides):
- "¿Cómo evita alucinaciones?" → Slide 3 + 8 + validator file:line.
- "¿Cuánto cuesta operar?" → Slide 12 + `docs/cost_analysis.md`.
- "¿Por qué no usar GPT-4o como prod?" → ADR-0013 router multi-LLM + H12 A/B contaminada (Llama 19/40 Groq cap; calidad system-level no model-bound).
- "¿Cómo lidia con el AI Act sobre el propio sistema?" → `docs/ai_act_assessment.md` (H17).
- "¿Y la PII?" → redacción en logs (allowlist egress en `observability/langfuse_client.py`); módulo dedicado `security/pii.py` [pendiente — carry-forward].
- "¿REVERTs son malos?" → Slide 10 framing science cycle.
- "¿Sobre-engineering?" → CLAUDE.md §22.20 disciplina autoaplicada.

**Notas (60 s)**:
No leer las respuestas, sólo señalar. Las slides backup tienen el detalle.

---

## Slide 18 — Reconocimientos

**Título**: Reconocimientos.

**Bullets**:
- Tutor TFM: [nombre].
- Máster IA Generativa: [institución + cohort].
- Stack open-source: BGE-M3 (BAAI), LangGraph (LangChain), LanceDB, Pydantic, FastAPI, Streamlit.
- APIs: Anthropic Claude, OpenAI, Groq, HuggingFace.
- Claude Code (Anthropic) como pareja de programación durante el desarrollo (CLAUDE.md §1).

**Notas (30 s)**:
Transparencia sobre uso de IA durante el desarrollo (relevante para TFM
en IA generativa): el repo es 100% versionado en git con ADRs por cada
decisión no trivial, evals reproducibles y red team auditable. Decisiones
finales humanas.

---

## Slide 19 — Acceso

**Título**: Recursos públicos.

**Bullets**:
- **Demo live**: `https://huggingface.co/spaces/enriro00/regulaitor`.
- **Repo GitHub**: (URL del repo) — tag `v0.1.32-h16-deploy`.
- **Memoria académica**: `docs/memoria/` (H17 en curso).
- **35 ADRs**: `docs/adr/0001-...0035-`.
- **Decisions log completo**: `docs/technical_decisions_log.md` (5335+ líneas).
- **Evidence matrix**: `docs/evidence_matrix.md`.

**Notas (30 s)**:
QR code en la slide hacia el repo + demo. Mencionar que toda la trazabilidad
está disponible para reviewer / tutor.

---

## Slide 20 — Cierre

**Título**: La metodología es la contribución.

**Bullets**:
- RegulAItor responde con citas verificables o no responde.
- 35 ADRs, 13 milestones §22.22, 2 REVERTs documentados.
- §6 invariante intacta a través de 4 evoluciones interpretativas de la arquitectura.
- Demo público + repo + evals + red team reproducibles.
- Gracias.

**Notas (30 s)**:
Cierre limpio. No leer el slide. Pausa para Q&A.

---

# Slides backup (no contadas en las 20)

## Backup A — ADR-0030 §REVERT (Auditor lenient quorum) detalle

**Contenido**: 3 root-cause mechanisms documentados (API drift ~20% noise
floor 2-day windows; Design B assumption invalid — Tier 1 quorum no era el
gatekeeper; diagnostic measurement artifact pre-`failed_check` instrumentation).
Pre-v0.1.22 budget gap honesto ~$3.50 documentado en ADR-0029.

**Cuándo usarla**: si el tribunal profundiza en metodología empírica.

---

## Backup B — ADR-0035 §REVERT (title-augmented corpus embeddings) detalle

**Contenido**: probe €0.65 sunk evidence; 5x over-citation expansion median
(doc-001 1-2→12; doc-003 1→19); reusable lessons (descriptive→prescriptive
semantic gap; HyDE / hybrid BM25 carry-forward).

**Cuándo usarla**: si el tribunal pregunta por la calidad del retrieval doc-mode.

---

## Backup C — Diagrama §6 4-capa (visual)

**Contenido**: Diagrama vertical con las 4 capas (a)(b)(c)(d), flecha
"enforcement boundary preserved" cruzando todas, anotaciones de qué ADR
modificó cada capa.

**Cuándo usarla**: si el tribunal pregunta "¿qué cambió y qué no en §6?".

---

## Backup D — Tabla de tags + ADRs

**Contenido**: tabla con columnas (tag, milestone, src files modified,
ADR-NNNN, §6 invariant status, paid €, métrica headline). Útil como
referencia visual rápida del linaje H0→v0.1.32.

**Cuándo usarla**: si el tribunal pregunta por el roadmap o por trazabilidad
detallada.

---

## Backup E — Sequence diagram chat E2E

**Contenido**: secuencia LangGraph (`orchestration/graph.py`) usuario →
Retriever → Analyst → Auditor → (Council si trigger) → Response. Anotar
los puntos de §6 enforcement.

**Cuándo usarla**: si el tribunal pregunta por la orquestación interna.

---

## Backup F — Limitaciones detalladas + carry-forwards H17/HX

**Contenido**: tabla con cada limitación de Slide 14, ADR asociado, y plan
de cierre (H17, HX1-HX5 o post-deploy real-traffic).

**Cuándo usarla**: si el tribunal insiste en honesty disclosure detallado.

---

# Notas globales del orador

- **Tiempo total objetivo**: 17 min presentación + 10-15 min Q&A.
- **Distribución sugerida**:
  - Slides 1-4 (problema + solución + demo): 4-5 min.
  - Slides 5-8 (arquitectura + §6 centerpiece): 5-6 min (la 8 es la más densa).
  - Slides 9-11 (metodología §22.22 + REVERTs + asimetría): 4 min.
  - Slides 12-14 (resultados + deploy + limitaciones): 3 min.
  - Slides 15-20 (cumplimiento + cierre): 2 min.
- **Idioma**: español. Términos técnicos del código (Auditor, Finding, citation,
  validator, Lenient, BLOCK, RHR, PASS) en inglés cuando aparecen en pantalla.
- **Tono**: técnico-académico, sin marketing, sin emojis. CLAUDE.md §26.
- **Backup slides** se usan sólo bajo pregunta directa; no se anuncian.
- **Demo en vivo**: NO recomendada por cold-start ~5 min + dependencia red.
  Usar screencast pre-grabado (Slide 4) y mostrar la URL.
- **Honest framing inviolable**: nunca presentar como medido lo no medido;
  nunca claim "X funciona" sin evidencia. Si el tribunal fuerza una respuesta
  no respaldada, decir "no medido — [pendiente]" explícitamente.

---

**Fuentes y trazabilidad**:
- CLAUDE.md §3 (problema), §4 (usuarios), §6 (invariante), §6.1 (4 capas),
  §8 (agentes), §10 (stack), §16.3 (linaje), §17 (métricas), §22 (reglas),
  §22.22 (honesty), §23 (idiomas), §26 (tono).
- `docs/technical_decisions_log.md` §H1-§v0.1.32.
- `docs/evidence_matrix.md` (M1-M5 mapping).
- `docs/architecture.md` (C4 L1/L2/L3).
- `docs/H16_DEPLOY.md` (runbook).
- ADRs `0001-0035` en `docs/adr/`.
- Memoria del proyecto `v0.1.32_h16_deployed_H17_ready.md`.
