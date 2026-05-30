# 09. Pipeline documental (extractor + sanitizer + segmenter)

El pipeline documental es la segunda superficie del producto (la primera es chat,
la tercera es API). Se cerró en H5 (ADR-0007) y se ha refinado en hitos
posteriores (v0.1.14 ADR-0019 para el segmentador; v0.1.27/v0.1.28 ADR-0033 para
el `document_analyst` v1.6). El invariante §6 "no citation, no answer" aplica
exactamente igual que en chat, con una diferencia operacional: la entrada del
usuario es un PDF o Markdown completo, no una pregunta corta, y por tanto el
sistema añade tres capas previas (extracción, sanitización, segmentación) antes
de entrar al bucle por segmento gate → Retriever → Analyst → Auditor.

## 9.1 Visión general del flujo

El orquestador `run_document()` en
`src/regulaitor/orchestration/document_graph.py:220` ejecuta secuencialmente:

```
extract -> sanitize -> segment -> [per-segment: anti-injection ->
  retrieve -> analyze -> audit] -> aggregate
```

A diferencia del chat (LangGraph en `orchestration/graph.py`), aquí se eligió
deliberadamente un bucle Python plano (ADR-0007 D6). Razones: control de flujo
lineal, menos modos de fallo y trazabilidad más simple para defensa académica.
La paralelización per-segmento se descartó por riesgo de no-determinismo en
H8 evals y para evitar problemas de rate-limit; queda diferida a HX
post-despliegue.

Si el sanitizer dispara un `DocumentBlockedError`, el pipeline corta antes de
segmentar y emite un `DocumentReport` con `document_verdict =
REQUIRES_HUMAN_REVIEW`, `segments=[]` y el `sanitizer_log` parcial
(`document_graph.py:250-271`). Esta es la ruta safe-by-default: el fallo no se
oculta, se documenta como evidencia auditable.

## 9.2 Extractor (`document/extractor.py`)

Dos formatos soportados:

- `application/pdf` mediante `pypdfium2` para texto + outline y `pikepdf` para
  el deep-scan del catálogo PDF (JavaScript, attachments, form actions, URI
  actions). El stack se redujo respecto a CLAUDE.md §10.2 que listaba
  `unstructured` + `pdfplumber` adicionales; la decisión D2 de ADR-0007 lo
  justifica por superficie SSDLC más estrecha y ~200-300 MB menos de
  dependencias transitivas.
- `text/markdown` parseado con `markdown-it-py` extrayendo cabeceras
  (`heading_open` tokens) como outline.

El extractor produce un `RawDocument` (`citation/schemas.py:234`) con:
`document_hash` (sha256), `mime_type`, `language` (heurística por caracteres
acentuados ES, `extractor.py:36-43`), lista de `Page` (con texto, fuentes,
anotaciones, candidatos de texto oculto), metadatos PDF (Title, Author,
Subject, Keywords, Creator, Producer; `extractor.py:107`), attachments,
outline, y banderas `has_javascript`, `has_form_actions`, `uri_actions`.

OCR se rechaza deliberadamente (D1 de ADR-0007): páginas con menos de 10
caracteres no-vacíos se marcan `likely_scanned=True` y el orquestador no
intenta OCR. La razón es SSDLC: un pipeline OCR estocástico podría inyectar
texto corrupto que el Analyst cite y el Auditor valide contra el corpus sin
detectar el error, rompiendo el invariante §6 desde una capa inferior. La
decisión es revisable en HX si un corpus de pruebas dominado por escaneos lo
justifica.

El `_deep_scan_pdf_bytes` (`extractor.py:159`) usa pikepdf para enumerar
estructuras que pypdfium2 no expone: árbol `/Names /JavaScript`, formularios
`/AcroForm`, acciones URI en anotaciones de página, y embedded files vía
`/Names /EmbeddedFiles`. Todos los fallos de surface API se tragan
defensivamente (devuelven defaults conservadores false/vacíos); el sanitizer
y el Auditor downstream son la red de seguridad final.

## 9.3 Sanitizer (`document/sanitizer.py`) — capa crítica §18.8

El sanitizer aplica la política **strip & log + critical-block** (D3 de
ADR-0007). Es el componente más sensible del pipeline desde el punto de
vista SSDLC: cualquier byte que escape del sanitizer al segmentador puede
acabar como contexto del Analyst, y por tanto como vector de prompt
injection.

### 9.3.1 Critical-blocks (fail-fast)

Cinco condiciones disparan `DocumentBlockedError` (`citation/schemas.py:335`)
y abortan el pipeline antes de la segmentación. Cada una genera un
`SanitizerEvent` con `severity="critical"`:

1. **`javascript_blocked`** (`sanitizer.py:68-78`): cualquier declaración de
   JavaScript en el catálogo PDF. Ejecución prohibida por contrato.
2. **`attachment_blocked`** (`sanitizer.py:80-91`): cualquier embedded file.
   Los attachments son superficie de ataque arbitraria (binarios, scripts,
   otros PDFs anidados).
3. **`form_action_blocked`** (`sanitizer.py:93-103`): `SubmitForm`,
   `ImportData`, `Reset` o cualquier action dictionary en `/AcroForm`.
4. **`uri_action_blocked`** (`sanitizer.py:105-116`): cualquier URI Action
   cuyo target no esté en `security/allowlist.py` (allowlist de dominios
   oficiales europeos).
5. **`metadata_injection_blocked` / `metadata_url_blocked`** (H9 amendment;
   `sanitizer.py:125-153`): patrones de injection detectados por
   `security.injection.is_injection(value, mode="document")` en cualquier
   campo de metadatos, o URLs no-allowlistadas embebidas en metadatos. El
   atacante que rellenase Author/Title/Creator con "ignore previous
   instructions" o con un URL exfiltrador era tratado igual que un metadato
   benigno antes de H9; ahora escala a critical-block.

### 9.3.2 Strip & log (warning) — política §18.8

Lo que no dispara critical-block se elimina del payload pero se registra:

- **Metadatos** (`sanitizer.py:154-162`): stripped incondicionalmente. El
  texto del cuerpo nunca incluye Title/Author/Subject/Creator/Producer.
- **Anotaciones por página** (`sanitizer.py:165-174`): stripped.
- **Candidatos de texto invisible** (`sanitizer.py:175-184`): stripped.
- **Trucos unicode** (`sanitizer.py:51-56`, `186-204`): zero-width space,
  zero-width joiner, right-to-left override, word joiner, BOM. Se eliminan
  caracter a caracter y se aplica `unicodedata.normalize("NFKC", ...)` para
  neutralizar variantes Unicode equivalentes. La constante `_UNICODE_TRICKS`
  está anotada con `nosec B613` porque Bandit marca el RLO literal como si
  fuera un vector trojan-source; aquí es la huella de detección, no el
  ataque.

Cada `SanitizerEvent` (`citation/schemas.py:251`) lleva un `content_hash` =
`sha256(value).hexdigest()[:12]`. **Nunca** se loguea el texto en claro,
solo el hash de 12 caracteres (regla §18.8). Esto permite auditoría
forense ("¿qué se eliminó?") sin filtrar datos potencialmente sensibles del
documento del usuario en los logs.

### 9.3.3 Length floor

Si el texto limpio acumulado (contado solo sobre el contenido real, no sobre
el scaffolding `--- p{n} ---` que añade el sanitizer para trazabilidad)
queda por debajo de 50 caracteres, se eleva
`DocumentBlockedError("document_empty_after_sanitization", log)`
(`sanitizer.py:232-242`). Un documento que tras sanitización queda vacío no
puede ser analizado de forma honesta; es preferible bloquear que producir un
informe sin sustancia.

## 9.4 Segmenter (`document/segmenter.py`)

El segmentador convierte el `SanitizedDocument.clean_text` en una lista de
`Segment` (`citation/schemas.py:288`) acotados a 1500 tokens BGE-M3 por
defecto. La estrategia tiene tres niveles (D4 de ADR-0007):

1. **Outline ≥ 1 entrada** → `_split_by_outline` (`segmenter.py:97-120`).
   Para cada título del outline se localiza su offset en el `clean_text` y
   se corta entre títulos. Si una sección excede el cap de tokens, se
   sub-divide por párrafos preservando límites (`_split_paragraphs_under_cap`,
   `segmenter.py:53-94`), marcando los chunks cola con
   `is_continuation=True`.
2. **Sin outline, ≥2 líneas heading-like detectadas** → pseudo-outline
   construido en memoria y se reutiliza `_split_by_outline`.
3. **Fallback** → ventana de tokens (`segmenter.py:153-154`). Se loguea
   `segmentation_fallback=token_windowed` como warning.

### 9.4.1 Regex `_HEADING_LIKE` — la evolución v0.1.14 (ADR-0019)

H15 calibración descubrió que la pipeline documental producía **un segmento
gigante por documento** en lugar de la granularidad esperada. La causa raíz
no era el sanitizer ni el extractor ni el `max_tokens`: era una ceguera del
regex `_HEADING_LIKE` (`segmenter.py:33-39`).

Antes de v0.1.14 el regex tenía solo dos alternativas: ALL-CAPS y Markdown
headings. Los documentos de compliance en español usan abrumadoramente el
patrón numerado canónico ("1. Introducción", "2.1 Subsección", "3.1.1
Detalle") que no era ni ALL-CAPS ni Markdown. El segmentador detectaba 0
headings, caía al fallback de ventana de tokens, y como cada fixture cabía
entera bajo 1500 tokens, devolvía un único segmento.

ADR-0019 añade una tercera alternativa al regex:

```python
r"\d+(?:\.\d+)*\.?\s+\S.{2,100}"
```

El filtro downstream `not stripped.endswith(".")` en `_detect_heading_lines`
(`segmenter.py:129`) sigue excluyendo frases normales como "1. Esta es una
frase normal." que también empiezan con número pero terminan en punto. Tras
el fix, **8/8 fixtures testables** en `evals/document_cases/` quedaron
dentro de `expected_n_segments ± tolerance` (2 de los 10 fixtures son casos
redteam blocked-by-design por JavaScript y no llegan al segmentador). El
deferred "0 segments" arrastrado desde H5 quedó cerrado.

El cambio es quirúrgico: una alternativa al regex, sin tocar
`_split_by_outline`, `_split_paragraphs_under_cap` ni el `segment()` entry
point. El §6 invariante queda intacto por construcción (el segmentador es
upstream del Auditor; cambios en la estructura de salida no afectan a la
validación de citas).

## 9.5 Bucle per-segmento y agregación

`_process_segment` (`document_graph.py:135-173`) ejecuta para cada segmento:

1. **Anti-injection** (`security/injection.py` en `mode="document"`, D7 de
   ADR-0007): ~13 patrones documento-específicos sobre los 10 base de chat.
   Si dispara, se devuelve `SegmentResult(skipped=True, skip_reason=pattern,
   audited_answer=None)`.
2. **Retriever**: query con title-prepend opt-in introducido en v0.1.28
   T4-bis (`document_graph.py:161`). Si el segmentador detectó un título
   para el segmento (`Segment.title is not None`), la query al retriever es
   `f"{seg.title}\n{seg.text}"`; en caso contrario, solo el cuerpo. La
   hipótesis es que los títulos de sección bridge el gap semántico
   descriptive-doc-segment → obligation-corpus-article que los embeddings
   BGE-M3 del cuerpo no cierran por sí solos.
3. **Analyst (`document_analyst` role)**: clase `AnalystAgent` reutilizada
   con `prompt_role="document_analyst"` (D5 de ADR-0007). Desde v0.1.28
   (ADR-0033) la versión por defecto del prompt para este role es **v1.6**,
   con Hard Rule 4 inviolable "Never emit placeholder citation strings
   (UNKNOWN/N/A/TBD)" + Rule 2 Finding-based refusal cuando el contexto es
   insuficiente. Esta es la capa (d) de la arquitectura §6.1 multi-capa:
   prompt-level explicit forbid como defensa en profundidad complementando
   la capa (a) validator.
4. **Auditor**: mismo `AuditorAgent.audit()` que en chat. El invariante §6
   se aplica por igual.

La agregación per-documento (`_aggregate_document`, `document_graph.py:72-132`)
sigue una política Lenient-strict:

- Cualquier segmento `skipped` por anti-injection cuenta como contribuyente
  a BLOCK.
- Cualquier segmento con `verdict=BLOCK` contribuye a BLOCK.
- Cualquier `REQUIRES_HUMAN_REVIEW` contribuye a REVIEW.
- Veredicto de documento: PASS solo si todos pasan; BLOCK si hay
  contribuyentes BLOCK o injection-skipped; REQUIRES_HUMAN_REVIEW en
  cualquier otro caso no-PASS.

El `DocumentReport` (`citation/schemas.py:313`) incluye `case_id`,
`document_hash`, `language`, `corpus`, `sanitizer_log` completo, lista de
`SegmentResult`, veredicto y razón, contadores por categoría, latencia
total y coste total en EUR.

## 9.6 Observabilidad y limitaciones operacionales

`_log_document_turn` (`document_graph.py:176-194`) emite una línea
estructurada JSON sin PII (counters + hashes) y `_doc_trace_record`
(`document_graph.py:197-217`) un resumen metadata-only para LangFuse con
`document_sha256_12` (prefijo del hash, no el texto). El `corpus` se
serializa como CSV.

Limitación operacional documentada en `docs/H16_DEPLOY.md` y reflejada en el
advisory de la pestaña `tab_analyze`: en el plan gratuito de HuggingFace
Spaces (cpu-basic, 2 vCPU, sin GPU) el bucle per-segmento añade ~30-60
segundos por segmento debido al reranker BGE ejecutándose en CPU
(`ui_streamlit/tab_analyze.py:48-56`). Un documento de 5-7 segmentos puede
tardar varios minutos en el demo público. El advisory está visible en la
pestaña `tab_analyze` de Streamlit para que el usuario lo sepa antes de
subir el PDF. La latencia real en infra dedicada con GPU es órdenes de
magnitud menor; la SLA de §17 #7 sigue como objetivo aspiracional medible
solo en producción real, no en el demo.

## 9.7 Estado actual y trabajo diferido

El pipeline documental funciona end-to-end y está medido. v0.1.27 produjo
una baseline pagada doc-mode (€0.16, cost_per_doc €0.053 dentro del soft
bar §17 #9 ≤ €0.50/10 páginas) y descubrió el bug del placeholder citation
en `document_analyst` v1.0 que motivó v0.1.28. v0.1.28 cerró ese bug
estructural y subió `citation_recall` de 0 a 0.33 (N=10 main), pero dejó
abierto el gap semántico descriptive-segment → obligation-article: title-prepend
del lado query ayuda; title-augmented corpus embeddings (probado en v0.1.30)
empeora por dilución de breadth (REVERT documentado en ADR-0035 §REVERT). El
trabajo futuro para cerrar este gap (HyDE, hybrid BM25, reranker legal
custom) queda como HX post-despliegue, informado por tráfico real.
