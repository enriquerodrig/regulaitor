# AI Act Assessment — RegulAItor (auto-evaluación)

Este documento es la auto-evaluación del propio sistema RegulAItor bajo el Reglamento (UE) 2024/1689 ("AI Act"). Se redacta como ejercicio de cumplimiento académico TFM y como evidencia para los módulos M2 (Agentes) y M4 (Seguridad). No sustituye certificación por un organismo notificado conforme al Capítulo III, Sección 4 del AI Act; la clasificación presentada es **provisional** y se documenta con el rigor §22.22 característico del proyecto.

Versión evaluada: `v0.1.32-h16-deploy` (demo público en Hugging Face Spaces, 2026-05-28).
Referencia normativa: REGULATION (EU) 2024/1689, OJ L 12.7.2024, ELI `http://data.europa.eu/eli/reg/2024/1689/oj`. Corpus interno: `corpus/processed/ai_act_es.json` (113 artículos parseados; 687 chunks tras chunking en LanceDB), versión consolidada base-act 2024-12-27.

## 1. Identificación del sistema

| Campo | Valor |
|---|---|
| Nombre | RegulAItor |
| Versión | v0.1.32 |
| Proveedor (artículo 3.3) | TFM author (uso académico) |
| Responsable del despliegue (artículo 3.4) | Mismo autor en demo HF; potenciales PYMEs en despliegues derivados |
| Finalidad prevista (artículo 3.12) | Asistente de primera línea de compliance europeo (AI Act, RGPD, NIS2, DORA) con citación verificable obligatoria |
| Modalidad | Servicio multi-agente con interfaz Streamlit + FastAPI |
| Modelos base | Claude Sonnet 4.6 (producción), Haiku 4.5 (judge), Llama-3.3-70B (Council/Groq); ver `docs/model_card.md` |
| Idiomas soportados | Español, inglés |
| Ámbito territorial | Unión Europea (corpus oficial EUR-Lex) |

## 2. Ámbito de aplicación (artículo 2)

RegulAItor cae dentro del ámbito del Reglamento porque sus *outputs* se generan para usuarios en la Unión (artículo 2.1.c). No aplican exclusiones del artículo 2.3-2.12: no es uso militar/defensa, no es exclusivamente investigación científica (sí, pero también demo público), no es uso doméstico no profesional, y aunque parte del código se distribuye con licencia abierta (artículo 2.12), el demo está "puesto en servicio" en HF Spaces, por lo que el régimen se mantiene activo. La interacción con datos personales se cubre adicionalmente vía RGPD (artículo 2.7) — ver §6 de este documento.

## 3. Clasificación de riesgo (artículos 5-6 y Anexo III)

### 3.1 ¿Práctica prohibida? (artículo 5)

No. RegulAItor no realiza ninguna de las prácticas prohibidas: no manipula comportamiento subliminal, no clasifica socialmente, no infiere emociones en el lugar de trabajo, no compila bases de datos de reconocimiento facial scraping, no realiza identificación biométrica remota en tiempo real, no perfila para predecir delitos.

### 3.2 ¿Alto riesgo por artículo 6.1 (componente de seguridad)?

No. RegulAItor no es componente de seguridad de un producto del Anexo I (maquinaria, juguetes, ascensores, dispositivos médicos, vehículos, etc.). No procede evaluación de la conformidad por terceros del régimen del Anexo I.

### 3.3 ¿Alto riesgo por artículo 6.2 (Anexo III)?

Revisión literal de los ocho ámbitos del Anexo III:

| Anexo III ámbito | Aplica a RegulAItor | Razonamiento |
|---|---|---|
| 1. Biometría | No | No procesa datos biométricos |
| 2. Infraestructuras críticas | No | No gestiona tráfico, electricidad, agua, gas, calefacción ni digital crítica del Anexo II de NIS2 (aunque cite NIS2) |
| 3. Educación y formación profesional | No | No admite, evalúa ni asigna estudiantes |
| 4. Empleo, RR.HH. | No | No criba currículos, no evalúa rendimiento laboral, no decide despidos |
| 5. Servicios esenciales públicos/privados | **Borderline (ver §3.4)** | Podría argumentarse como apoyo a compliance privado; no decide acceso a servicios ni elegibilidad |
| 6. Aplicación de la ley | No | No usado por autoridades policiales |
| 7. Migración, asilo, control fronterizo | No | No clasifica personas en estos contextos |
| 8. Administración de justicia y procesos democráticos | **Borderline (ver §3.4)** | "Investigación e interpretación de hechos y de la ley y aplicación de la ley a un conjunto concreto de hechos" — la asistencia a compliance privada queda fuera del literal (que cubre autoridades judiciales), pero la cercanía conceptual merece análisis |

### 3.4 Análisis del borderline Anexo III(8a)

El Anexo III(8a) cubre sistemas usados por **autoridad judicial o un órgano administrativo en su nombre** para investigar e interpretar hechos y aplicar la ley. RegulAItor:

- Está dirigido a equipos privados de compliance, no a tribunales (CLAUDE.md §4 usuarios objetivo).
- Su finalidad declarada es preparar borradores y evidencias — no resolver casos jurídicos (CLAUDE.md §3 "no sustituye a un asesor jurídico").
- Sus respuestas vienen acompañadas de un disclaimer persistente ("Esta herramienta no sustituye asesoría jurídica. Las respuestas están respaldadas por citas validadas pero pueden contener errores. Consulta a un profesional para decisiones vinculantes" — `src/regulaitor/ui_streamlit/app.py:19-23`).

**Conclusión provisional**: RegulAItor **no** entra en Anexo III(8a) por ausencia de uso por autoridad judicial. La cercanía conceptual recomienda mantener la salvaguarda human-in-the-loop como elección de diseño, aunque no sea jurídicamente exigible.

Adicionalmente, la cláusula de exención del artículo 6.3 sería invocable aunque el sistema entrara en Anexo III: RegulAItor realiza tareas preparatorias para una evaluación (artículo 6.3.d) y no sustituye la valoración humana (artículo 6.3.c). No efectúa elaboración de perfiles de personas físicas — operativo agnóstico a datos personales del usuario consultante.

### 3.5 Clasificación adoptada

**RegulAItor es un sistema de IA de riesgo limitado** bajo el artículo 50 (obligaciones de transparencia). No es alto riesgo. La determinación es **provisional**, sujeta a las directrices de aplicación práctica del artículo 6 que la Comisión debía publicar a más tardar el 2 de febrero de 2026 (artículo 6.5 AI Act, ver `corpus/processed/ai_act_es.json`).

## 4. Obligaciones de transparencia (artículo 50)

Como sistema de riesgo limitado destinado a interactuar directamente con personas físicas, aplican las obligaciones del artículo 50.1 y 50.5.

### 4.1 Artículo 50.1 — Informar que se interactúa con un sistema de IA

**Cumplido** mediante banner persistente en la UI Streamlit (`src/regulaitor/ui_streamlit/app.py:19-54`) que aparece en cada vista. El texto del banner explicita que se trata de una herramienta automatizada con respuestas respaldadas por citas validadas pero falibles.

En la superficie API (`src/regulaitor/api/`), la documentación OpenAPI generada automáticamente describe los endpoints como agentes IA; los integradores asumen el rol de "responsables del despliegue" (artículo 3.4) y heredan la obligación de informar al usuario final.

### 4.2 Artículo 50.2 — Marcado de contenido sintético

**Aplica parcialmente**. RegulAItor no genera deepfakes, audio sintético ni vídeo. Sí genera texto, pero éste se entrega siempre estructurado como `Answer` con `Findings` explícitos y `audit_results` adjuntos (`src/regulaitor/citation/schemas.py`) — el formato deja visible al receptor que el output viene de un sistema automatizado. La detección máquina-legible adicional (watermarking criptográfico, manifiestos C2PA) no se ha implementado: **[pendiente para HX]**.

### 4.3 Artículo 50.3 — Reconocimiento de emociones / categorización biométrica

**No aplica**. RegulAItor no realiza ninguna de estas funciones.

### 4.4 Artículo 50.4 — Ultrasuplantación y contenido generado para informar al público

**No aplica directamente**. RegulAItor no produce imágenes ni vídeo. El texto producido tiene una capa de revisión humana implícita (el disclaimer indica que el usuario final debe consultar a un profesional; los integradores API son responsables editoriales) que encajaría en la salvedad del párrafo segundo del artículo 50.4 (ver `corpus/processed/ai_act_es.json`, artículo 50 apartado 4).

### 4.5 Artículo 50.5 — Información clara y distinguible en la primera interacción

**Cumplido**. El banner aparece en la primera vista de Streamlit (antes de cualquier input) y antes de los tabs `Pregunta normativa` / `Analiza documento` (`src/regulaitor/ui_streamlit/app.py:49-67`).

## 5. Salvaguardas alineadas con régimen de alto riesgo (defense-in-depth)

Aunque la clasificación es **riesgo limitado**, varios controles propios del régimen de alto riesgo se han implementado preventivamente. Esto es una elección de diseño justificada por el principio rector del proyecto ("no citation, no answer" — CLAUDE.md §6) y por la proximidad conceptual al Anexo III(8a).

### 5.1 Supervisión humana (artículo 14, anticipado)

- El Auditor-Agent (`src/regulaitor/agents/auditor.py`, clase `AuditorAgent` en línea 51) es el "safety floor" mecánico: valida cada cita contra el corpus oficial; cualquier fallo bloquea o marca como `requires_human_review` (RHR).
- El Council of Judges (ADR-0014, `src/regulaitor/agents/council.py`) actúa como segunda capa cuando el verdict es `RHR` o `severity=="high"`. Una decisión unánime de tres jueces independientes puede escalar `PASS → RHR` (binding conservador, ADR-0025, activado en v0.1.19).
- El verdict `requires_human_review` impone explícitamente intervención humana antes de cualquier decisión accionable.

### 5.2 Datos y gobernanza de datos (artículo 10, anticipado)

- Corpus solo de fuentes oficiales (EUR-Lex, allowlist en `src/regulaitor/security/allowlist.py`). Versionado y manifest hash-tracked (`corpus/manifests/`).
- Data card describe limitaciones y procedencia (`docs/data_card.md` — ver documento hermano).

### 5.3 Documentación técnica (artículo 11, anticipado)

- 35 ADRs (`docs/adr/0001-*.md` a `0035-*.md`), `docs/technical_decisions_log.md` (5335+ líneas), `docs/architecture.md` (C4 L1/L2/L3), `docs/evidence_matrix.md` (M1-M5), `docs/auditor_calibration.md` (estudio H15), model card, data card. Trazabilidad completa.

### 5.4 Registro de eventos (artículo 12, anticipado)

- Logs estructurados por `case_id` con verdict, latencia, tokens, coste estimado (`src/regulaitor/observability/langfuse_client.py`, ver `TurnTrace` y `trace_turn`).
- Integración LangFuse opcional, **metadata-only** con allowlist de claves seguras (`src/regulaitor/observability/langfuse_client.py:27-60`) — ningún texto crudo de usuario sale del proceso.

### 5.5 Transparencia y suministro de información (artículo 13, anticipado)

- Cada `Finding` lleva su `Citation` explícita; el verdict del Auditor (`pass`, `requires_human_review`, `block`) y, cuando procede, la opinión del Council se renderizan en la UI (`src/regulaitor/ui_streamlit/_render.py`).
- Model card pública con descripción de capacidades y limitaciones.

### 5.6 Exactitud, robustez y ciberseguridad (artículo 15, anticipado)

- Suite red team con 50 ataques (`redteam/attacks.jsonl`, gate §16.2 #4 ≥0.90 verde a 0.92).
- Suite evaluación con 64 casos chat + 10 doc (`evals/gold_set.jsonl`).
- Estudio de calibración del Auditor (ADR-0016, H15) y ciclo diagnose-intervene-measure-refute-revert documentado (ADRs 0027-0034; 13 hitos consecutivos con framing §22.22; 2 REVERTs honestos v0.1.23 y v0.1.30).
- Sanitización PDF anti-prompt-injection (`src/regulaitor/document/sanitizer.py`).

## 6. Interacción con RGPD (artículo 2.7)

RegulAItor no procesa categorías especiales de datos personales (artículo 9 RGPD) en su operación normal:

- Las consultas chat son textuales en lenguaje natural sobre obligaciones normativas; el usuario es libre de incluir o excluir PII.
- El modo análisis documental procesa documentos corporativos (políticas, procedimientos, registros) — el operador es responsable de pseudonimizar antes de subir.
- Los logs aplican redacción por allowlist (`src/regulaitor/observability/langfuse_client.py:27-60`); no se persiste texto crudo del usuario en LangFuse.
- No se implementa aún detección automática PII en input (`src/regulaitor/security/pii.py` **[pendiente]**, planeado en CLAUDE.md §11 estructura objetivo pero no construido en H0-H16).

**DPIA simplificada**: dado que la base de uso esperada es texto no-personal sobre normas, el riesgo RGPD es **bajo**; un DPIA formal artículo 35 RGPD sería exigible solo si el sistema se integrara con datasets de empleados/clientes en el ámbito del responsable del despliegue. Ese análisis quedaría a cargo del responsable del despliegue, no del proveedor.

## 7. Modelos de IA de uso general (artículos 51-55)

RegulAItor no entrena ni proporciona modelos de IA de uso general; consume modelos de terceros (Anthropic, OpenAI, Groq vía router `src/regulaitor/models/router.py`). Las obligaciones del Capítulo V recaen sobre los proveedores upstream. La clasificación umbral del artículo 51.2 (10^25 FLOPs) no aplica directamente; sí aplica indirectamente si Sonnet/GPT-4o/Llama-3.3-70b se designan con riesgo sistémico (lista de la Comisión, artículo 52.6).

## 8. Limitaciones de esta evaluación

1. **Provisional**: realizada por el autor del TFM, no por organismo notificado. Una certificación formal requerirá el ramp-up del régimen 2025-2027.
2. **Anexo III(8a) borderline**: si futuras directrices de la Comisión (artículo 6.5) extendieran la noción de "administración de justicia" a asistencia compliance, el sistema requeriría re-clasificación.
3. **Marcado máquina-legible artículo 50.2**: no implementado watermarking criptográfico; el formato estructurado `Answer/Finding/Citation` es la única señal actual.
4. **PII detection**: módulo planeado (CLAUDE.md §11) pero no construido en H0-H16; **[pendiente HX]**.
5. **Evaluación de conformidad externa**: no aplicable bajo riesgo limitado, pero documentación técnica acumulada (35 ADRs + decisions log + evidence matrix) está formateada para sustentar una auditoría futura.

## 9. Conclusión

RegulAItor se auto-clasifica como **sistema de IA de riesgo limitado** bajo el AI Act, sujeto a las obligaciones de transparencia del artículo 50, todas cumplidas en la versión `v0.1.32`. Como elección de diseño se han implementado preventivamente salvaguardas alineadas con el régimen de alto riesgo (Auditor mecánico, Council of Judges, validación de citas literal, logs redactados, red team continuo), apoyadas por la regla central "no citation, no answer" (CLAUDE.md §6) y la arquitectura §6.1 de cuatro capas (validator + Finding-Lenient aggregation + Turn-level aggregation policy + prompt-level forbid). La clasificación es provisional; cualquier integración productiva por un tercero exigirá nueva evaluación contextual.

## Referencias

- REGULATION (EU) 2024/1689 (AI Act), `corpus/processed/ai_act_es.json`.
- CLAUDE.md §3, §4, §6, §6.1, §18 (controles de seguridad).
- `docs/model_card.md`, `docs/data_card.md`, `docs/architecture.md`.
- `docs/technical_decisions_log.md`, `docs/evidence_matrix.md`.
- ADR-0014 (Council), ADR-0016 (Auditor calibration), ADR-0025 (Council binding), ADR-0027 a ADR-0034 (linaje §6 multi-capa).
- `src/regulaitor/ui_streamlit/app.py:19-67` (disclaimer y banner artículo 50.1+50.5).
- `src/regulaitor/agents/auditor.py:20-48` (helper `_all_blocked_findings_paraphrase_only` Layer (c) §6.1).
- `src/regulaitor/observability/langfuse_client.py:27-60` (redaction allowlist).
