# Video Demo Script — RegulAItor (H17)

**Duración objetivo:** 3-5 minutos (4:30 nominal).
**Formato:** screencast 1080p, voz-en-off ES, captions burned-in ES (subtítulos EN opcionales si tiempo).
**Plataforma demo:** https://huggingface.co/spaces/enriro00/regulaitor (tag `v0.1.32-h16-deploy`).
**Repo:** https://github.com/<user>/regulaitor (URL exacta [pendiente] hasta verificar visibility GitHub).
**Audiencia:** tribunal TFM Máster IA Generativa + revisor académico externo.
**Tono:** técnico-académico, sin marketing, sin emojis.

---

## Pre-grabación — checklist (5 min antes)

- [ ] Streamlit Space "warm" (visitar URL 2 min antes para evitar cold-start ~5 min documentado en `docs/H16_DEPLOY.md` §7).
- [ ] Browser limpio: Chrome perfil nuevo, zoom 110%, sin extensiones que muevan layout.
- [ ] Resolución captura 1920x1080; OBS con escena única "Browser+Mic"; sample rate 48 kHz mono voz.
- [ ] Tema Streamlit navy/light cargado vía `.streamlit/config.toml` (`primaryColor = "#1E40AF"`; el mismo navy aparece en el palette de corpus, ver `src/regulaitor/ui_streamlit/_render.py:40` para `_NORMA_STYLE["ai_act"]`).
- [ ] Tener abierto en otra pestaña local: `evals/document_cases/case_doc-002_politica-ia-empresarial-sin-tr.pdf` (lo subiremos en escena 4).
- [ ] Cronómetro visible al grabar; cortes blandos cada ~30 s.

---

## Escena 1 — Intro + demo URL (0:00 → 0:20)

**Pantalla:** título-tarjeta estática 3 s con texto "RegulAItor — cumplimiento normativo asistido con verificación de citas" sobre fondo navy `#1E40AF`. Después fade a browser mostrando https://huggingface.co/spaces/enriro00/regulaitor cargado.

**Caption on-screen:** `TFM — Máster en IA Generativa · v0.1.32-h16-deploy · 2026-05-28`

**Narración (ES, ~45 palabras):**
> "RegulAItor es un servicio multi-agente de cumplimiento normativo europeo construido como Trabajo Fin de Máster. La diferencia frente a un chatbot legal: no responde sin cita textual verificable contra el corpus oficial. Lo veréis funcionando en tres ejemplos: pregunta directa, consulta cross-corpus y análisis documental."

**Timing nota:** corte limpio a 0:20; no entrar todavía a la pestaña.

---

## Escena 2 — Apertura del Space + tab Pregunta normativa (0:20 → 0:40)

**Pantalla:** scroll lento mostrando: banner aviso jurídico (`DISCLAIMER` en `src/regulaitor/ui_streamlit/app.py:19-23` "Esta herramienta no sustituye asesoría jurídica"), las dos pestañas "Pregunta normativa" y "Analiza documento", y el form vacío.

**Caption on-screen:** `Disclaimer persistente · 2 modos: chat + documento`

**Narración (ES, ~40 palabras):**
> "La interfaz tiene dos modos: pregunta normativa libre, y análisis de un documento corporativo. El aviso jurídico arriba es persistente. La arquitectura subyacente son tres agentes Retriever, Analyst y Auditor orquestados en LangGraph, más un Council de tres jueces."

---

## Escena 3 — Ejemplo chat AI Act → PASS + Findings + chips (0:40 → 1:30)

**Pantalla:** en la pestaña "Pregunta normativa", escribir en el textarea (despacio para que se lea) la consulta:

```
¿Qué obligaciones impone el AI Act a los sistemas de alto riesgo en evaluación de la conformidad?
```

Mantener Corpus = `auto`, Idioma = `es`. Click en "Analizar". Spinner "Analizando — Retriever → Analyst → Auditor..." durante ~15-30 s.

**Caption durante spinner:** `Retriever (BGE-M3 + reranker) → Analyst (Sonnet 4.6) → Auditor (validator)`

**Pantalla cuando responde:** badge verdict PASS (color emerald-700 según `_VERDICT_STYLE` en `src/regulaitor/ui_streamlit/_render.py:99-107`); chip "AI Act" azul (palette `_NORMA_STYLE` línea 39-44); ≥1 Finding con severidad y cita en blockquote literal.

**Caption on-screen al aparecer respuesta:**
- (a) `PASS — el Auditor valida las citas contra el corpus`
- (b) `Cita literal: si el texto no coincide, no se emite`

**Narración (ES, ~70 palabras):**
> "Pregunto por las obligaciones del AI Act para sistemas de alto riesgo. El Retriever busca en LanceDB con embeddings BGE-M3 y reranker bge-reranker-v2-m3. El Analyst genera la respuesta como Findings estructurados con severidad y citas candidatas. El Auditor valida cada cita contra el texto oficial del corpus: tres checks, artículo existe, apartado existe, texto coincide. Si falla, la respuesta se bloquea. Aquí vemos verdict PASS y dos Findings con cita literal."

---

## Escena 4 — Cross-corpus hospital + IA → Council notice (1:30 → 2:30)

**Pantalla:** nueva consulta en el mismo form (sin recargar página):

```
Un hospital quiere desplegar un asistente de IA para triaje en urgencias.
¿Qué obligaciones del AI Act y del RGPD aplican simultáneamente?
```

Corpus = `auto` (clave: deja que el Retriever resuelva multi-norma). Click "Analizar".

**Caption durante spinner:** `corpus=auto → retriever cross-corpus + purity gate (ADR-0017)`

**Pantalla al responder:** chips "AI Act" + "GDPR" lado a lado en "Fuentes consultadas" (`_sources_summary` en `src/regulaitor/ui_streamlit/_render.py:57-73`, helper `_norma_chip` en líneas 47-54); Findings de ambos corpus; **posible aviso amarillo del Council** si `_council_notice` retorna texto (definido en `src/regulaitor/api/schemas.py:308`, gated por `state.council_review`).

**Caption on-screen cuando aparezca Council notice (si aparece):**
- (a) `Council of Judges — 3 LLM independientes votan`
- (b) `Aviso visible cuando el Council diverge del Auditor mecánico`

**Si NO aparece Council notice en esta toma:** mantener narración pero decir "el Council es advisory por defecto y solo aparece como aviso cuando los tres jueces divergen del veredicto mecánico — en este caso coincidieron". Esto es honesto §22.22.

**Narración (ES, ~80 palabras):**
> "Segundo ejemplo, una situación realista: un hospital que despliega IA para triaje. Aquí cruzan dos normativas: el AI Act por el sistema de IA de alto riesgo y el RGPD por los datos de salud. Pongo Corpus en auto: el Retriever decide automáticamente qué normas consultar. Vemos chips de ambos corpus. Sobre los Findings opera además el Council of Judges, tres jueces LLM independientes: si divergen del Auditor mecánico, aparece un aviso. La política por defecto es advisory."

**Timing nota:** si la query tarda más de 35 s, hacer corte de edición y acelerar 2x durante el spinner.

---

## Escena 5 — Análisis documental: subir doc-002 → 4 segmentos + sanitizer log (2:30 → 3:30)

**Pantalla:** click en pestaña "Analiza documento". El form muestra uploader de PDF.

Subir el fichero `evals/document_cases/case_doc-002_politica-ia-empresarial-sin-tr.pdf` (política IA empresarial sin transparencia; expected `pass` con 4 segmentos según `case_doc-002_politica-ia-empresarial-sin-tr.expected.json:12-13`).

Click "Analizar documento". Spinner ~30-60 s (segmenter + ciclo Retriever→Analyst→Auditor por segmento).

**Caption durante spinner:** `Pipeline H5: extract → sanitize → segment → loop[Retriever→Analyst→Auditor] → aggregate`

**Pantalla al responder:** badge verdict global; fila de 6 métricas (PASS / BLOCK / REVIEW / SKIPPED / LATENCY / COST €, definidas en `_render.py:258-265`); 4 expanders por segmento; al final el expander "Sanitizer log (N eventos)" si hubo limpieza.

**Caption on-screen:**
- (a) `4 segmentos esperados — gold set doc-002`
- (b) `Sanitizer detecta inyección embebida y texto oculto`

**Narración (ES, ~75 palabras):**
> "Tercer ejemplo, modo documento. Subo una política de IA empresarial. El pipeline extrae texto, sanitiza prompt injection embebido, segmenta lógicamente y, por cada segmento, ejecuta el mismo ciclo Retriever-Analyst-Auditor. La sanitización es de primera clase: bloquea texto invisible, metadatos y JavaScript embebido — varios documentos del gold set son adversariales por diseño. Aquí veo un badge global, métricas agregadas por veredicto, y un expander por segmento. El sanitizer log queda accesible para auditoría."

---

## Escena 6 — Expander "Detalles del Auditor" → tabla audit_results (3:30 → 4:00)

**Pantalla:** dentro de uno de los segmentos PASS (por ejemplo el primero), abrir el expander "Detalles del Auditor". Se renderiza `_audit_results_table` (definido en `src/regulaitor/ui_streamlit/_render.py:194-207`): tabla con columnas `norma · articulo · apartado · validated · article_exists · apartado_exists · text_normalized_match · reason`.

Hacer zoom suave a una fila donde `validated=True`; después otra donde `validated=False` con `reason=text_not_in_apartado` (típico Check 3 paraphrase mismatch — el invariante que permitió la evolución §6.1 capa (c) del v0.1.25 D2 y v0.1.29 D Mirror, ADR-0032 y ADR-0034).

**Caption on-screen:**
- (a) `3 checks: artículo · apartado · texto`
- (b) `Trazabilidad por cita — defensa académica reproducible`

**Narración (ES, ~55 palabras):**
> "El panel Detalles del Auditor expone la trazabilidad por cita: artículo, apartado, si el texto coincide normalizado, y la razón en caso de fallo. Esto es el corazón de la regla 'no citation, no answer' del documento marco. Es lo que permite defender cada afirmación del sistema contra el corpus oficial."

---

## Escena 7 — Cierre: arquitectura §6.1 + repo + licencia (4:00 → 4:30)

**Pantalla:** card final estática de 10 s con cuatro líneas tipo bullet, fondo navy `#1E40AF`, tipografía sans tabular-nums:

```
RegulAItor — arquitectura §6 multi-capa

(a) Validator per-cita        — 3 checks estrictos
(b) Finding-Lenient aggreg.   — byte-unchanged H4
(c) Turn-level routing        — v0.1.25 + v0.1.29
(d) Prompt-level forbid       — v1.5 + v1.6

13 hitos consecutivos con honesty framing §22.22
2 REVERT documentados: v0.1.23, v0.1.30

Demo:   huggingface.co/spaces/enriro00/regulaitor
Repo:   github.com/<user>/regulaitor
Licencia:  [pendiente — confirmar en LICENSE del repo]
```

**Caption final (overlay 3 s):** `Gracias — preguntas en defensa TFM`

**Narración (ES, ~70 palabras):**
> "Cierro con la idea estructural: la regla 'no citation, no answer' está implementada en cuatro capas independientes, validator por cita, agregación Lenient, ruteo a nivel de turno, y prohibición a nivel de prompt. El proyecto cuenta con trece hitos consecutivos publicados bajo disciplina de honesty framing y dos REVERTs documentados como hallazgo científico. Código y trazas están en el repositorio. Gracias."

---

## Captions clave — resumen burned-in

Reusables (mantener cada uno ~3-5 s en pantalla):
1. `no citation, no answer — invariante §6`
2. `Retriever → Analyst → Auditor → (Council advisory)`
3. `Cita literal validada vs corpus oficial`
4. `Council disagrees → aviso amarillo prominente`
5. `Sanitizer bloquea inyección · texto oculto · JS embebido`
6. `Arquitectura §6 four-layer (validator + lenient + routing + prompt)`
7. `13 hitos honest framing · 2 REVERTs documentados`

---

## Recording tips (operacional)

- **Resolución y bitrate:** 1920x1080 @ 30 fps, H.264 CRF 18, audio AAC 192 kbps mono. OBS escenas mínimas para evitar cuts duros.
- **Mouse:** activar cursor highlight (OBS plugin `obs-mouse-emote` o equivalente) para que se vea bien dónde clico — el form de Streamlit es pequeño en 1080p.
- **Voz:** grabar la narración en pista separada y montar en post; permite corregir errores sin re-grabar pantalla. Marcadores cada 30 s para sincronizar.
- **Subtítulos:** generar archivo `.vtt` ES desde el guion (cada bloque "Narración" → un cue). Versión EN opcional si queda tiempo (traducción literal, no doblaje).
- **Caption burn-in:** Premiere/DaVinci con estilo "lower third" navy `#1E40AF` + fondo translúcido 70%; tipografía sans-serif (Inter o similar) para coincidir con el tema de la UI.
- **Color theme verificable:** el Streamlit usa el navy `#1E40AF` real (declarado como `primaryColor` en `.streamlit/config.toml` y replicado en `_NORMA_STYLE["ai_act"]` línea 40 de `_render.py`); cualquier overlay del video debe armonizar con ese color para que la transición pantalla→cards no chirríe.
- **Cold-start mitigación:** si la grabación del Space se enfría durante el rodaje, hacer una consulta dummy 2 min antes de cada escena chat/doc para mantener BGE-M3 y LanceDB en memoria.
- **Edge case Council:** si Council notice no aparece naturalmente en escena 4, NO forzar — la narración ya prevé esa rama. Honesty §22.22.
- **Export final:** MP4 H.264 1080p ≤200 MB para subir directo a YouTube unlisted + adjuntar al ZIP entregable TFM.

---

## Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Cold-start del Space ~5 min interrumpe grabación | Pre-warm 2 min antes; tener captura de fallback grabada offline |
| Sonnet 4.6 da respuesta diferente entre tomas | Re-grabar la escena entera; aceptar variación cualitativa y narrar honest §22.22 si verdict cambia |
| Council nunca diverge en la toma cross-corpus | Mantener narración prevista; el aviso de "coincidieron" ES la lectura honesta |
| Sanitizer log vacío en doc-002 | Caso doc-002 es limpio por diseño; si quiero log no-vacío usar `synthesized_policy_adversarial.pdf` como alternativa |
| Quota API Anthropic se agota mid-toma | Re-cargar `.env` del Space; tener €5 buffer pre-rodaje |
| Demo URL caída justo en defensa | Grabación offline backup + Local Docker `make docker-up` reproducible (`docs/H16_DEPLOY.md` §6) |

---

**Conteo aprox de palabras de narración hablada:** 435 palabras → ~3:45 leído a ritmo 115 wpm, encaja dentro del rango 3-5 min objetivo.

**Próxima acción:** grabar primer take completo de prueba (sin edición) para medir tiempo real; ajustar pausas si excede 4:45.
