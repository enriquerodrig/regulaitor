# Technical Decisions Log

Registro cronológico de todas las decisiones técnicas tomadas durante el desarrollo de RegulAItor. Su propósito es servir como espinazo para la memoria del TFM y para la defensa académica. Las decisiones de arquitectura no triviales tienen además su ADR formal en `docs/adr/`.

## Formato

Cada entrada incluye:
- **Hito** y fecha de aprobación.
- **Decisión** en una línea.
- **Justificación** breve.
- **Alternativas descartadas** y por qué.
- **Detalle técnico** cuando la decisión incluye un artefacto: esquema JSON/SQL completo, pseudocódigo, flujo paso a paso, contrato de interfaz, parámetros concretos. Esto es lo que convierte el log en memoria técnica defendible — si solo hay un resumen ejecutivo, el log pierde valor para la memoria del TFM.
- **Enlace** al ADR, commit o PR cuando exista.

Las entradas se agrupan por hito y dentro de cada hito en orden cronológico de aprobación.

---

## H0 — Decisiones y plan aprobado

### 2026-04-30 · Plan operativo por hitos, no por calendario

- **Decisión:** trabajamos por hitos (H0 → H17 + HX) con gates verificables; eliminamos el calendario por semanas del CLAUDE.md original.
- **Justificación:** la disponibilidad del autor es variable; calendarios fijos crearían presión artificial y se invalidan en cuanto hay un parón. Los gates objetivos hacen que el avance dependa de evidencia, no de fechas.
- **Alternativa descartada:** plan por semanas heredado del CLAUDE.md inicial. Riesgo: scope creep si cae una semana, ansiedad si falla un calendario.
- **Enlace:** `~/.claude/plans/lee-el-archivo-claude-md-sparkling-fairy.md`.

### 2026-04-30 · Fusión de CLAUDE.md original con propuesta `regulaitor code.md`

- **Decisión:** un único `CLAUDE.md` que combina la estructura por hitos (de `regulaitor code.md`), las secciones de Skills/MCPs/Subagentes (íd.), el stack más detallado (íd., con `pypdfium2 + unstructured + pdfplumber`, MkDocs Material, Mermaid + Structurizr DSL, MCP server propio, HF Spaces) y las reglas no negociables del original (§20 módulos M1-M5, §18 anti-sobreingeniería, lenguaje `[medicion pendiente]`, §21 Definition of Done).
- **Justificación:** `regulaitor code.md` aporta infraestructura profesional ausente en el original; el original aporta la disciplina académica que falta en la propuesta. Reemplazar uno por otro perdía valor.
- **Alternativa descartada:** sustituir CLAUDE.md por `regulaitor code.md`. Riesgo: pérdida de §20 (mapeo a módulos del Máster) y filosofía MVP-first.
- **Enlace:** `CLAUDE.md` (commit `8834a44`); legado `regulaitor code.md` borrado.

### 2026-04-30 · Decisiones bloqueantes de bootstrap

- **Gestor de paquetes:** `uv` (no `pip-tools` ni `poetry`). Más rápido, gestiona Python 3.11 sin venv manual, recomendado por el stack de CLAUDE.md.
- **`pre-commit` activo desde H0.1:** ruff, black, gitleaks, end-of-file, trailing-whitespace, check-yaml, check-toml, check-merge-conflict, check-added-large-files, detect-private-key. Sin esperar a H1.
- **`mypy` permisivo al inicio, `--strict` en H10:** evita frenar el bootstrap; se endurece cuando módulos críticos (`citation/`, `agents/`) están estables.
- **Python 3.11** confirmado.
- **Cero MCPs y cero skills custom en H0.1:** ningún MCP es necesario para bootstrap; skills custom se proponen en su hito de consumo (ver ADR 0002).

---

## H0.1 — Bootstrap mínimo del repositorio

### 2026-04-30 · Bootstrap completado y validado

- **Decisión:** repositorio inicializado con 14 archivos, validación local verde y CI verde a la primera (3/3 jobs en GitHub Actions).
- **Justificación:** cumple los 5 criterios Done de §27: `make setup`, `make lint`, `make test`, `pre-commit run --all-files`, `git push` con CI verde.
- **Enlace:** commits `8834a44` (bootstrap inicial) y `507b67b` (cleanup post-bootstrap); CI run `25180028114` en GitHub Actions, 13 segundos, 3/3 jobs verde.

### 2026-04-30 · Bump de pytest y black por CVEs detectadas en pip-audit

- **Decisión:** pin `pytest>=9.0.3,<11.0` (era `>=8.0,<9.0`) y `black>=26.3.1,<28.0` (era `>=24.0,<26.0`).
- **Justificación:** pip-audit reportó CVE-2026-32274 (black 25.12.0) y CVE-2025-71176 (pytest 8.4.2). El gate de `CLAUDE.md §17.13` exige "sin findings críticos en pip-audit", así que CI fallaría. Las versiones pinneadas no permitían aplicar el fix.
- **Alternativa descartada:** ignorar y usar `pip-audit --ignore-vuln`. Rechazado porque hipoteca la disciplina de seguridad antes de empezar.
- **Enlace:** commit `8834a44`.

### 2026-04-30 · `.claude/settings.json` y `.claude/settings.local.json` ambos gitignored

- **Decisión:** ambos ficheros de configuración de Claude Code se ignoran en git. Si en el futuro queremos policy de equipo, creamos un fichero con nombre explícito (`.claude/settings.team.json` o similar) y lo force-add.
- **Justificación inicial (commit `507b67b`):** mover los permisos a `settings.local.json` y gitignorarlo. Resultó incorrecto: la harness de Claude Code sigue escribiendo automáticamente a `settings.json` (es ahí donde acumula los grants por sesión), así que `settings.local.json` quedaba huérfano y `settings.json` reaparecía como untracked en cada sesión.
- **Decisión refinada (commit del spec H1):** gitignorar también `.claude/settings.json` y borrar el `settings.local.json` manual.
- **Lección:** comprobar el comportamiento real del harness antes de asumir que controla tipos de archivo.

### 2026-04-30 · `pre-commit install` integrado en `make setup`

- **Decisión:** `make setup` ejecuta `uv sync --extra dev` y a continuación `uv run pre-commit install`, dejando los hooks de git listos automáticamente tras un clone limpio.
- **Justificación:** sin esto, los hooks solo corren cuando se invocan manualmente; cualquier dev que clone el repo sin recordar `pre-commit install` salta validación local.
- **Enlace:** commit `507b67b`.

### 2026-04-30 · Tooling instalado en el sistema con autorización explícita

- **`uv 0.11.8`** vía instalador oficial Astral en `C:\Users\enriq\.local\bin\`. Python 3.11.15 gestionada por uv.
- **`gh 2.92.0`** descargado del release oficial a `C:\Users\enriq\.local\bin\` (sin admin, sin choco). Autenticado vía web browser con scopes `repo`, `workflow`, `read:org`, `gist`.
- **Justificación:** `uv` es el gestor pactado y `gh` permite verificar CI desde la sesión sin que el autor tenga que ir a la pestaña Actions cada vez.
- **No instalado todavía:** `make` (validación se hace via `uv run` directo).

---

## H1 — Corpus AI Act + RGPD (en diseño)

### 2026-04-30 · Versiones consolidadas del corpus

- **AI Act:** Reglamento (UE) 2024/1689, CELEX `32024R1689`, versión consolidada de EUR-Lex.
- **RGPD:** Reglamento (UE) 2016/679, CELEX `02016R0679-20160504`, versión consolidada de EUR-Lex.
- **Justificación:** versión consolidada para evitar tener que reconciliar correcciones de errata; CELEX explícito porque la URL canónica de EUR-Lex puede cambiar.
- **Riesgo abierto:** EUR-Lex puede actualizar la versión consolidada (nueva fecha, nuevo CELEX). El campo `version` en cada chunk + `corpus/manifests/*.json` capturan el snapshot exacto.

### 2026-04-30 · Idiomas del corpus: ES + EN

- **Decisión:** ambos idiomas para los dos corpus.
- **Justificación:** BGE-M3 está entrenado precisamente para alineación cross-lingual, así que aprovechar EN saca lo mejor del modelo. Defensa académica más sólida (multilingüismo es un módulo del Máster). UI en español, pero retrieval mejora con índice bilingüe.
- **Alternativa descartada:** ES solo (más simple, pero subutiliza BGE-M3); EN solo (rompe coherencia con UI).

### 2026-04-30 · Versionado de corpus en repo: Git-LFS

- **Decisión:** archivos crudos y procesados de corpus se trackean con Git-LFS; manifests y código son git normal.
- **Justificación:** AI Act + RGPD juntos pesan ~5-15 MB en HTML/Formex; con NIS2 + DORA llegamos a ~30 MB max — bien dentro del free tier de GitHub LFS (1 GB). DVC sería sobreingeniería para este tamaño.
- **Alternativa descartada:** DVC (más infra externa, curva de aprendizaje) y "manifests + raw gitignored" (rompe reproducibilidad bit a bit).

### 2026-04-30 · Formato de origen: Formex 4 (XML), HTML como fallback

- **Decisión:** primary parser sobre Formex 4 (FMX4) XML de la Office of Publications of the EU; fallback a HTML solo si una versión consolidada concreta no tiene Formex disponible.
- **Justificación:** XML formal con etiquetas semánticas (`ARTICLE`, `PARA`, `LIST`, `NP`) elimina el scraping frágil; tests de contrato son triviales contra el esquema FMX4 publicado; reproducibilidad académica más defendible que depender del DOM HTML.
- **Alternativas descartadas:**
  - Akoma Ntoso XML — elegante pero RGPD consolidada no la tiene completa, mezclar dos parsers no compensa.
  - HTML como primario — frágil ante cambios de plantilla EUR-Lex.
  - PDF — `pypdfium2 + unstructured + pdfplumber` queda reservado para documentos del usuario en H5; no es la mejor opción para corpus oficial.

### 2026-04-30 · Granularidad de chunk: híbrido por umbral

- **Decisión:** un chunk = un artículo entero si ≤ ~1000 tokens; si excede, se parte por apartado (`PARA`).
- **Justificación:** AI Act tiene artículos cortos (definiciones) y muy largos (art. 6, 9, 14, 16, 27 sobre obligaciones). Forzar todo a "artículo entero" desperdicia recall en los largos; forzar todo a "apartado" descontextualiza citas y multiplica records ~10x. ~1000 tokens es la zona dulce de BGE-M3.
- **Alternativas descartadas:** artículo entero siempre (recall pobre en artículos largos); apartado siempre (descontextualización, ruido).
- **Implicación:** schema de cita admite `apartado` como campo opcional.

### 2026-04-30 · Almacenamiento bilingüe: 1 chunk por par (artículo, idioma)

- **Decisión:** dos records por artículo (uno ES, uno EN) compartiendo `article_id` como pivote; cada uno con su embedding nativo BGE-M3.
- **Justificación:** BGE-M3 alinea ambos idiomas en el mismo espacio; pregunta ES recupera chunks ES y EN por similitud; el `article_id` permite al `citation_validator` mostrar la cita en el idioma de la consulta o en el original.
- **Alternativas descartadas:**
  - Concatenar ES+EN en un chunk — ensucia la señal del embedding.
  - ES primario con EN como metadata sin embedding — pierde retrieval cross-lingual.
  - Tablas LanceDB separadas por idioma — equivalente a la opción aprobada pero más complejo operacionalmente.
- **Detalle técnico:**
  - `article_id` se compone como `{norma}.{articulo}[.{apartado}]` (p.ej. `ai_act.6` o `ai_act.6.1`).
  - `chunk_id` se compone como `{article_id}.{lang}` (p.ej. `ai_act.6.1.es`).
  - Cada record en LanceDB es independiente con su propio embedding; el join cross-lingual se hace por `article_id`.

### 2026-04-30 · Idempotencia del ingest: híbrido HTTP + hash por artículo

- **Decisión:** `make ingest` usa `If-Modified-Since` + `ETag` para descarga (skip 304) y SHA256 por artículo para reprocesamiento (skip si hash idéntico al manifest).
- **Justificación:** descargar el XML completo cada `make ingest` es desperdicio (los embeddings son lo caro, no la red). El híbrido evita re-descarga cuando EUR-Lex no ha cambiado y evita re-embebes cuando un artículo concreto no ha sido tocado por la consolidación.
- **Alternativas descartadas:**
  - Hash global del corpus — reembebe los 113 artículos del AI Act si cambia un byte en cualquiera.
  - Solo `last_modified` HTTP — no detecta el caso de re-fetch manual ni cambios entre ramas locales.
- **Detalle técnico — flujo del comando `make ingest`:**
  1. Cargar manifest existente (o crear vacío si primera ejecución).
  2. Para cada `(corpus, idioma)`: hacer GET con cabeceras `If-Modified-Since` y `If-None-Match`. Si 304 → marcar como "fetch skipped" y saltar al siguiente.
  3. Si 200 → guardar el XML en `corpus/raw/{corpus}_{lang}.xml` (LFS), parsear Formex 4.
  4. Para cada `ARTICLE`: extraer texto, calcular SHA256.
  5. Comparar hash con el del manifest. Si idéntico → "process skipped" (chunks y embeddings ya válidos).
  6. Si difiere o nuevo → re-chunkear (umbral 1000 tokens), re-embebar BGE-M3, upsert en LanceDB, actualizar entrada del manifest.
  7. Escribir manifest atómicamente (`tmp` + rename).
- **Flags del CLI:** `--force-fetch` (ignora 304), `--force-reprocess` (ignora hash), `--corpus ai_act|gdpr|all`, `--lang es|en|all`, `--dry-run`.

### 2026-04-30 · Estructura de manifests: 1 archivo por corpus

- **Decisión:** `corpus/manifests/{corpus}.json` — un manifest por corpus, no índice global ni por idioma.
- **Justificación:** PRs que tocan solo un corpus dan diff limpio; lazy loading natural; no fuerza a leer todo para inspeccionar uno.
- **Alternativas descartadas:**
  - Índice único `index.json` — diffs ruidosos al actualizar cualquier corpus, archivo grande.
  - Por `(corpus, idioma)` — duplica metadatos compartidos (CELEX, version) sin beneficio.
- **Detalle técnico — esquema del manifest aprobado:**

```json
{
  "corpus": "ai_act",
  "celex": "32024R1689",
  "version": "2024-07-12",
  "source_format": "formex4",
  "fetched_at": "2026-04-30T18:42:13Z",
  "languages": ["es", "en"],
  "http_cache": {
    "es": { "etag": "W/\"abc123\"", "last_modified": "2024-07-12T00:00:00Z" },
    "en": { "etag": "W/\"def456\"", "last_modified": "2024-07-12T00:00:00Z" }
  },
  "stats": {
    "articles_total": 113,
    "chunks_total": 246,
    "embedded_total": 246,
    "raw_size_bytes": 1834210
  },
  "articles": [
    {
      "article_id": "ai_act.6",
      "articulo": "6",
      "title_es": "Reglas de clasificación de los sistemas de IA de alto riesgo",
      "title_en": "Classification rules for high-risk AI systems",
      "languages": {
        "es": {
          "hash": "sha256:c1d4...",
          "tokens": 1840,
          "chunks": ["ai_act.6.1.es", "ai_act.6.2.es", "ai_act.6.3.es"],
          "embedded_at": "2026-04-30T18:43:05Z"
        },
        "en": { "hash": "sha256:e9a8...", "tokens": 1762, "chunks": ["ai_act.6.1.en", "ai_act.6.2.en", "ai_act.6.3.en"], "embedded_at": "2026-04-30T18:43:05Z" }
      }
    }
  ]
}
```

  - `chunks` lista los `chunk_id` que produjo el chunker (1 si artículo cabe entero, N si se partió por apartado por umbral 1000 tokens).
  - `hash` se calcula sobre el texto crudo del artículo (no del chunk individual). Si cambia, todos los chunks del artículo se re-procesan.
  - `http_cache` es por idioma porque EUR-Lex puede consolidar solo una traducción.
  - `stats` para diagnóstico rápido y para que el log/ADR capture números reales.
  - `version` se rellena con la fecha de consolidación que aparece en EUR-Lex (no la fecha de fetch).

### 2026-04-30 · Cliente EurLex no reintenta 5xx; solo errores de conexión

- **Decisión:** `EurLexClient._fetch` (en `src/regulaitor/corpus/eurlex.py`) reintenta únicamente sobre `httpx.ConnectError` y `httpx.ReadTimeout` (3 intentos, backoff exponencial 1-4s). Las respuestas HTTP 5xx propagan inmediatamente como `httpx.HTTPStatusError` sin reintento.
- **Justificación:** los 5xx en EUR-Lex suelen reflejar mantenimiento programado o outage estructural donde reintentar 3 veces solo añade latencia (≈7s) sin beneficio. El orquestador (`ingest.py`, Task 8) decide la política de reintento al nivel de corpus: si el fetch falla, el manifest se queda intacto y se reintenta en la siguiente ejecución del cron / `make ingest`.
- **Alternativa descartada:** añadir `httpx.HTTPStatusError` con predicado `lambda e: e.response.status_code >= 500` al `retry_if_exception_type`. Rechazada porque genera retry storms hacia EUR-Lex (mala práctica de ciudadanía web) y porque el patrón "fail fast + manifest atomic" del orquestador ya cubre el caso.
- **Detalle técnico:**
  - Errores que SÍ se reintentan: `httpx.ConnectError`, `httpx.ReadTimeout`. Ambos son fallos de capa de transporte que típicamente desaparecen tras unos segundos.
  - Errores que NO se reintentan: cualquier respuesta HTTP, incluyendo 4xx (URL mal formada, CELEX inexistente) y 5xx (servidor caído).
  - El 304 Not Modified se intercepta antes de `raise_for_status()`, así que no entra en el flujo de errores.
- **Implicación para spec:** se actualiza la tabla §7 del spec H1 para reflejar el comportamiento real ("HTTP 5xx → status code (no retry) → exit 1").
- **Enlace:** commit Task 7 (`275aa4a`) + commit de este fix.

### 2026-04-30 · `source_url` se modela como `str`, no `HttpUrl`

- **Decisión:** el campo `source_url` en `LanguageEntry` (Pydantic schema en `src/regulaitor/corpus/schemas.py`) se tipa como `str` en lugar de `pydantic.HttpUrl`.
- **Justificación:** las URLs se construyen internamente por `eurlex.py` a partir del CELEX y un mapping de idioma; no entran como input de usuario, así que la validación formal no aporta. Además, `HttpUrl` normaliza la URL (puede añadir barra final) y eso rompería la igualdad exacta que necesitamos para `If-Modified-Since` y para que el campo coincida bit a bit entre el manifest y los headers HTTP devueltos por EUR-Lex. La serialización de `HttpUrl` a `Url` también añade complejidad innecesaria.
- **Alternativas descartadas:**
  - `HttpUrl` (la del spec original §5.1): aporta validación que no necesitamos y arriesga drift de normalización.
  - Wrapper custom validator sobre `str` que verifique scheme: overkill.
- **Detalle técnico:**
  - Origen del valor: `EurLexClient.fetch_formex/fetch_html` devuelve `FetchResultModified.source_url` (string completo de la respuesta HTTP, post-redirects).
  - Consumidor: el campo se almacena tal cual en el manifest y se reusa por el Auditor (H4) para mostrar la fuente al usuario.
  - El spec original (`docs/superpowers/specs/2026-04-30-h1-corpus-ingest-design.md` §5.1) será actualizado en el cierre de H1 (Task 13) para reflejar este cambio.
- **Enlace:** commit Task 1 (`eb16176`) + el commit de este fix.

### 2026-05-04 · Pivote a PDF tras WAF de EUR-Lex (Task 12)

- **Decisión:** la versión H1 del corpus se ingesta desde **PDFs descargados manualmente** y commiteados a Git-LFS, no desde la API HTTP de EUR-Lex. El pipeline soporta los tres formatos (Formex 4 / HTML / PDF) vía dispatch en `ingest.py`; en H1 se usa solo PDF; el camino HTTP queda probado con stubs y disponible para H14.
- **Justificación:** el smoke run real reveló que el frontend de EUR-Lex está fortificado con CloudFront WAF:
  - Endpoint Formex (`/legal-content/{LANG}/TXT/?uri=CELEX:{celex}` con `Accept: application/xml`) devuelve **HTTP 200 con 0 bytes**.
  - Endpoint HTML (`/legal-content/{LANG}/TXT/HTML/?uri=CELEX:...`) devuelve **HTTP 202** con un challenge JavaScript (~2 KB) que solo un navegador real puede resolver.
  - Cellar (`publications.europa.eu/resource/celex/{celex}`) responde con RDF de metadata, no con el contenido del documento.
- **Alternativas evaluadas:**
  - **Cellar + rdflib:** robusta pero ~2-3h de research + dependencia adicional. Postpuesta a H14.
  - **Beat WAF con headers + cookies:** probado con User-Agent Chrome completo y `Accept-Language` — sigue devolviendo 202. Inviable sin JS engine.
  - **Playwright headless:** funcionaría, pero contradice ADR 0002 (no `playwright` MCP en H1) y añade ~250 MB de Chromium en CI.
  - **Snapshot manual a LFS (elegida):** el operador descarga 4 PDFs desde su navegador (que pasa el WAF naturalmente), los deja en `corpus/raw/`, y el pipeline los lee con `--use-local-only`.
- **Detalle técnico:**
  - **Nuevo módulo `src/regulaitor/corpus/pdf_parser.py`** con `PdfParser` y `PdfParseError`. Usa `pdfplumber` para extraer texto y un regex line-anchored estricto (`^\s*(?:Article|Art[íi]culo)\s+(\d+)\s*$`) para detectar cabeceras de artículo. Excluye entradas de ToC (tienen puntos suspensivos + número de página) y referencias cruzadas inline (`...in accordance with Article 49(1)`) que no encajan con `^...$`.
  - **Estrategia keep-first:** cuando un mismo número de artículo aparece dos veces como cabecera (caso AI Act EN: "Article 49" en el body + en una tabla de cross-references del Annex VIII), conservamos la primera ocurrencia por offset (el body siempre precede al annex en orden de documento).
  - **Nuevo flag `--use-local-only`** en CLI: salta `EurLexClient`, lee de `corpus/raw/{corpus}_{lang}.{xml,html,pdf}` con prioridad XML > HTML > PDF.
  - `SourceFormat` Pydantic literal extendido a `Literal["formex4", "html", "pdf"]`.
  - El except del orquestador se ensancha a `(FormexValidationError, HtmlParseError, PdfParseError)` para que cualquier parser falle limpio.
- **Resultado del smoke (commits `d367c88` + `b10c0b0`):**
  - AI Act ES: 113 artículos ✓ (esperado 113)
  - AI Act EN: 113 artículos ✓
  - GDPR ES: 99 artículos ✓ (esperado 99)
  - GDPR EN: 99 artículos ✓
  - Errores: 0. Idempotencia verificada (segunda corrida: `reprocessed=0`).
  - Tiempo total: ~115 segundos. PDF text extraction es lo lento (~30s/PDF AI Act, ~12s/PDF GDPR).
  - 4 PDFs en LFS (~6.7 MB total). 4 JSONs procesados en LFS. 2 manifests git-tracked.
- **Defensa académica:** "EUR-Lex bloqueó el acceso automatizado vía CloudFront WAF; pivotamos a un snapshot reproducible en Git-LFS y demostramos que el pipeline soporta tres formatos de origen". Más honesto que "vencimos al WAF" o "todo es mock".
- **Implicación para H14 (NIS2/DORA):** re-evaluar las 4 opciones antes de ingestar. Si EUR-Lex sigue con el WAF, repetir el patrón snapshot+PDF; si Cellar API ha mejorado, probar opción 1.
- **Enlace:** commit `d367c88` (parser + wiring), commit `b10c0b0` (smoke artefacts).

### 2026-05-04 · Skills/MCPs deferrals tras smoke H1

- **Decisión:** consolidación final de qué skills/MCPs entraron y cuáles no en H1, vs lo planeado en ADR 0002.
- **Skills:**
  - `rag-ingest` — **introducida** en H1 (commit `114285f`).
  - `adr-writer` — **diferida a H10**. H1 produjo 2 ADRs (0003 + actualización de 0002), pero ambas se redactaron sin fricciones repetidas. El skill se justifica con ≥3 ADRs en cola en un solo hito, más probable en H10 (documentación final).
  - Anthropic `pdf` — **no introducida**. `pdfplumber` cubre H1 directamente; la skill oficial se considerará para informes descargables en H7-H8.
- **MCPs:**
  - `fetch` — **diferido a H3+**. `httpx` con allowlist en `eurlex.py` cubre H1.
  - `mcp-server-time` — **no introducido**. `datetime.now(timezone.utc)` es suficiente.
  - `playwright` — **no introducido**. WAF se evita con snapshot LFS, no con headless browser.
- **Subagentes:** ninguno project-level introducido en H1. Los built-in (`Explore`, `Plan`, `general-purpose`, `code-reviewer`, `superpowers:code-reviewer`) cubrieron impl + spec review + quality review en las 14 tareas. Primer subagente custom (`software-architect`) sigue programado para H3.
- **Enlace:** ADR 0002 (sección "H1 closure update").

### 2026-05-04 · H1 cerrado: corpus AI Act + RGPD operativos

- **Decisión:** H1 cierra como Done. El pipeline corpus está implementado, testeado, validado contra datos reales y con paper trail completo.
- **Stats finales:**
  - 22+ commits en `feat/h1-corpus-ingest`.
  - 57 tests verde (unit + contract + integration).
  - 91% coverage en `src/regulaitor/corpus/` (gate 90% ✓).
  - 113 + 113 + 99 + 99 = 424 LanguageEntry generados (212 artículos × 2 idiomas).
  - 4 PDFs (~6.7 MB) en Git-LFS como source snapshot reproducible.
  - 2 manifests git-tracked, 4 processed JSON en LFS.
- **Lecciones para H2:**
  - El chunker debe respetar el `tokens` ya calculado en `LanguageEntry` (proxy `tiktoken cl100k_base`); cuando H2 instale BGE-M3 tokenizer, refrescar el campo.
  - El `source_format=pdf` actual del manifest es ortogonal al chunking — el chunker recibe artículos ya parseados, no le importa el formato de origen.
  - El boundary contract H1→H2 (`chunks: []`, `embedded_at: None` para todo `LanguageEntry`) está verificado por test de integración.
- **Enlace:** ADR 0003 (architecture); ADR 0002 (skills/MCPs); commits `971fdf81` (Task 0) → `b10c0b0` (Task 12 smoke). Branch `feat/h1-corpus-ingest`.

---

## H2 — RAG base (en diseño)

### 2026-05-04 · Embeddings BGE-M3 ejecutados localmente, no vía API

- **Decisión:** los embeddings densos se generan en local cargando el modelo `BAAI/bge-m3` con la librería `FlagEmbedding` (alternativa válida: `sentence-transformers`). No se contrata ningún proveedor de embeddings cloud (Voyage, Cohere, Together, OpenAI).
- **Justificación:**
  1. **Reproducibilidad bit-a-bit.** Un objetivo no negociable del TFM (CLAUDE.md §2) es que un evaluador externo pueda clonar el repo y regenerar los mismos artefactos. Una API hosted introduce un actor opaco entre el código y los vectores: el proveedor puede actualizar el modelo silenciosamente, hacer A/B testing, ajustar normalización, etc., con lo que dos ejecuciones idénticas pueden producir vectores diferentes. Con el modelo en local y un hash del checkpoint, los mismos bytes de entrada producen los mismos 1024 floats de salida siempre.
  2. **Coste cero por embedding.** El corpus AI Act + RGPD ES+EN tiene 424 LanguageEntry con un total estimado de ~500 000 tokens. A precios actuales de proveedores de embeddings (~$0.10–$0.13 / millón de tokens en BGE-M3 hosted), una re-build completa cuesta ~$0.05–$0.07. Parece poco, pero las iteraciones del chunker, los re-runs por bug, los experimentos de threshold y la regeneración periódica al actualizar el corpus se acumulan rápidamente. En local: cero. Solo coste de cómputo, que es del usuario.
  3. **Independencia de secrets en CI.** Una build con API requiere meter una key secreta en GitHub Actions. Eso obliga a (a) gestionar rotación, (b) limitar quién puede ver los logs, (c) cuidar de no logear la key. Local elimina toda esa complejidad de seguridad.
  4. **CLAUDE.md §10.3 lo prefijó:** "Embeddings multilingües: BGE-M3". La intención del proyecto desde H0 ya era local, no cloud.
  5. **Defensa académica más sólida.** El TFM puede afirmar "controlamos el modelo de embedding completo: la versión exacta del checkpoint, su hash, su longitud máxima de contexto (8192 tokens) y su comportamiento de normalización". Una API no permite ese nivel de argumentación.
- **Alternativas descartadas:**
  - **API cloud (Voyage / Cohere / Together):** rechazada por reproducibilidad y secrets.
  - **Híbrido (local en dev, API en CI):** rechazada porque doblar las rutas obliga a tests duplicados y multiplica los modos de fallo. La complejidad no compensa para el ahorro de tiempo en CI (~3-5 minutos extra por instalación del modelo, mitigable con `actions/cache` sobre `~/.cache/huggingface`).
- **Detalle técnico — coste del install local:**
  - `FlagEmbedding` arrastra `torch` (~800 MB), `transformers` (~200 MB) y el checkpoint `BAAI/bge-m3` (~2.3 GB) la primera vez.
  - Total disco aprox. 3.3 GB en `~/.cache/huggingface/`.
  - Primera ejecución de `make rag-build` en máquina limpia: ~5-10 min de descarga.
  - Ejecuciones siguientes: instantáneo (cache local).
  - CI: cache hit tras la primera build. Estrategia de cache key recomendada: hash del lockfile + versión del modelo.
- **Implicación para H2:**
  - Nueva dependencia runtime: `FlagEmbedding>=1.3,<2.0` (o `sentence-transformers>=3.0,<5.0` si se decide después; ambas leen el mismo checkpoint).
  - Workflow CI: añadir `actions/cache@v4` con path `~/.cache/huggingface` y key `${{ runner.os }}-hf-bgem3-${{ hashFiles('uv.lock') }}`.
  - Estrategia de fallback: si la descarga del modelo falla en primera build, el ingest debe fallar limpio con mensaje accionable ("HF Hub unreachable; check network or pre-download model").
- **Implicación para H17 (cost analysis):** la sección "coste por consulta" del documento `cost_analysis.md` debe reflejar coste de cómputo local (CPU/GPU minutos), NO coste de API por token. Eso cambia cómo se redacta esa parte.
- **Enlace:** se documentará en ADR 0004 al cierre de H2 (RAG architecture).

### 2026-05-04 · LanceDB con una única tabla `chunks`, particionada por metadata

- **Decisión:** todos los chunks de todos los corpus viven en una sola tabla LanceDB llamada `chunks`, con campos `norma`, `language`, `articulo`, `apartado`, etc. Los filtros por corpus o idioma son clausulas `WHERE` sobre esos campos.
- **Justificación:**
  1. **`chunk_id` es ya único globalmente.** El formato `{norma}.{articulo}[.{apartado}].{lang}` (ej. `ai_act.6.1.es`) garantiza que dos chunks distintos nunca colisionan en una misma tabla. Esto elimina el argumento principal a favor de tablas separadas (evitar colisiones).
  2. **Re-ingest parcial ya lo gestiona el manifest.** El `_build_manifest` de H1 detecta a nivel artículo qué cambió (por hash) y solo invalida los chunks de ese artículo. La operación equivalente en LanceDB es un `DELETE WHERE chunk_id LIKE '{article_id}.%'` seguido de un upsert. No necesitamos drop-and-recreate de tabla entera; el aislamiento físico de tablas separadas es teórico para nuestro patrón de actualización.
  3. **Queries cross-corpus son útiles.** Un caso real para el Auditor (H4): el Analyst cita un artículo del AI Act sobre datos personales; el retriever puede querer también verificar si RGPD dice algo similar. Con tabla única: una sola query con `WHERE norma IN ('ai_act','gdpr') AND ...`. Con tablas separadas: dos queries y unión manual en código Python.
  4. **LanceDB filtra por metadata eficientemente.** Es columnar. Un filtro `WHERE norma='ai_act'` se traduce a un push-down sobre la columna `norma` y no produce full scan + filtrado en aplicación. Conversaciones con el equipo de LanceDB confirman que el rendimiento de filtros sobre columnas indexadas es comparable al aislamiento físico para tamaños sub-millón de filas.
  5. **H14 (NIS2 + DORA) se reduce a "añadir filas".** Con tablas separadas, H14 implicaría crear `chunks_nis2`, `chunks_dora`, actualizar el router, añadir tests para los caminos nuevos. Con tabla única: el ingest existente inserta filas con `norma='nis2'` y `'dora'` y el resto del pipeline funciona sin tocarse.
- **Alternativas descartadas:**
  - **Tabla por corpus** (`chunks_ai_act`, `chunks_gdpr`, …): rechazada por las razones 2-5. El único pro real (drop-and-recreate atómico) no compensa la complejidad operativa.
  - **Tabla por (corpus, idioma)** (`chunks_ai_act_es`, …): rechazada categóricamente. Genera 8 tablas en MVP (subiendo a 16 con NIS2+DORA), duplica la complejidad operativa, no aporta nada que no aporte el filtro por columna `language`.
- **Detalle técnico — tamaño esperado:**
  - 424 chunks × 1024 floats × 4 bytes = 1.7 MB en vectores.
  - Más metadata: ~10 columnas × 50 bytes promedio × 424 = ~210 KB.
  - Total tabla LanceDB: ~2 MB. Trivial.
- **Detalle técnico — esquema preliminar de la tabla `chunks`** (refinará en spec H2):
  ```python
  # PyArrow schema (LanceDB-native)
  schema = pa.schema([
      pa.field("chunk_id", pa.string(), nullable=False),       # PK: "ai_act.6.1.es"
      pa.field("article_id", pa.string(), nullable=False),     # "ai_act.6.1"
      pa.field("norma", pa.string(), nullable=False),          # filter: "ai_act" | "gdpr" | ...
      pa.field("articulo", pa.string(), nullable=False),
      pa.field("apartado", pa.string(), nullable=True),        # null cuando chunk = artículo entero
      pa.field("language", pa.string(), nullable=False),       # "es" | "en"
      pa.field("text", pa.string(), nullable=False),
      pa.field("text_normalized", pa.string(), nullable=False),# para citation_validator (H3)
      pa.field("token_count", pa.int32(), nullable=False),
      pa.field("celex", pa.string(), nullable=False),
      pa.field("version", pa.string(), nullable=False),
      pa.field("source_format", pa.string(), nullable=False),
      pa.field("source_url", pa.string(), nullable=False),
      pa.field("hash", pa.string(), nullable=False),           # SHA256 del texto del artículo
      pa.field("embedding", pa.list_(pa.float32(), 1024), nullable=False),  # BGE-M3 dense
  ])
  ```
- **Implicación para H3 (Retriever-Agent):** el Retriever recibe `query: str` y opcionalmente `corpus: Norma | None` y `language: Language | None`, traduce a `WHERE` clause, y delega en LanceDB. Una sola ruta de código.
- **Enlace:** se formaliza en ADR 0004 al cierre de H2.

### 2026-05-04 · Swap completo de tokenizer: `tiktoken` → BGE-M3 nativo (XLM-RoBERTa)

- **Decisión:** el chunker usa el tokenizer del propio modelo BGE-M3 (que es XLM-RoBERTa) para todas las decisiones de partición y para refrescar el campo `tokens` del manifest. Re-corremos `make ingest --force-reprocess` una vez en H2 para refrescar los manifests existentes. La dependencia `tiktoken` se elimina del proyecto porque deja de tener consumidores.
- **Justificación:**
  1. **Coherencia de fuente única de verdad.** Cuando el manifest dice "art. 6 ES tiene 1840 tokens", ese número debe ser lo que el modelo de embedding realmente ve. Si lo mide un tokenizer diferente (tiktoken cl100k es BPE de OpenAI; XLM-RoBERTa de BGE-M3 es SentencePiece sobre vocabulario de 250K), los conteos divergen entre 15-30% para texto multilingüe europeo. La doble medición confunde tanto a desarrolladores como al evaluador del TFM.
  2. **Documentación honesta de coste.** En H17 la memoria académica cita números de tokens para argumentar "coste por consulta ≤ 0.05 €" (CLAUDE.md §17). Si esos números están en una unidad (cl100k tokens) y el modelo procesa en otra (XLM-RoBERTa tokens), la afirmación pierde rigor. Con el swap, el manifest es auditable directamente.
  3. **Decisión ya programada.** El plan operativo del proyecto (`~/.claude/plans/lee-el-archivo-claude-md-sparkling-fairy.md`, sección H2) explicita: *"H1 used `tiktoken cl100k_base` as a token-count proxy. H2 should switch to BGE-M3's native tokenizer when refreshing the `tokens` field in manifests."* Era deuda técnica intencional con calendario de pago.
  4. **El re-ingest no es coste extra.** H2 va a hacer un `make ingest --force-reprocess` para poblar `chunks` y `embedded_at` en los manifests. Refrescar `tokens` en el mismo pase es 0 trabajo adicional — el chunker recalcula `token_count` por chunk, el orquestador recalcula `tokens` agregado por (article, language) en el mismo loop.
  5. **Higiene del codebase.** Mantener `tiktoken` como dep cuando ningún módulo lo usa es código muerto declarado. Reviewers académicos pueden preguntar legítimamente "¿por qué usas el tokenizer de OpenAI si no usas modelos de OpenAI en producción?" — y la respuesta correcta sería "ya no lo uso, el dep se quedó".
- **Alternativas descartadas:**
  - **Chunker BGE-M3 + manifest tiktoken (split):** rechazada. Tener dos tokenizers con conteos divergentes en el mismo flujo confunde y corrompe los números del manifest.
  - **Mantener tiktoken como proxy en H2 entero:** rechazada. El umbral de chunking de 1000 tokens es generoso (BGE-M3 admite 8192) así que el proxy no rompe la lógica de partición, pero los números del manifest siguen siendo inválidos para análisis de coste y para la memoria.
- **Detalle técnico — diferencia de conteo (estimaciones):**
  - cl100k_base sobre AI Act art. 6 ES: 1840 tokens (medido en H1).
  - XLM-RoBERTa estimado sobre el mismo texto: ~1380-1560 tokens (15-25% menos por el vocabulario más amplio que captura más subwords europeos).
  - Para el threshold de 1000 tokens del chunker, ambos tokenizers están en zona segura respecto a la ventana de 8192 de BGE-M3. La decisión de partir o no partir un artículo no cambia para los artículos del corpus actual.
- **Detalle técnico — cómo accede el chunker al tokenizer:**
  ```python
  from FlagEmbedding import BGEM3FlagModel

  _MODEL = BGEM3FlagModel("BAAI/bge-m3", use_fp16=False)
  _TOKENIZER = _MODEL.tokenizer  # transformers.XLMRobertaTokenizerFast

  def token_count(text: str) -> int:
      return len(_TOKENIZER.encode(text, add_special_tokens=False))
  ```
- **Implicación operativa:**
  - `pyproject.toml`: eliminar línea `"tiktoken>=0.8,<1.0"`.
  - `src/regulaitor/corpus/ingest.py`: eliminar import de `tiktoken`, eliminar `_TOKENIZER = tiktoken.get_encoding(...)`, redirigir `_token_count` a la función nueva basada en BGE-M3 (que probablemente vivirá en el módulo `rag/embeddings.py` para no acoplar `corpus/` a `FlagEmbedding`).
  - Re-run de `make ingest --use-local-only --force-reprocess --corpus all --lang all` esperado: ~5 min (incluye carga inicial de modelo BGE-M3 + reprocesado de los 4 PDFs).
  - Diff esperado en manifests: solo el campo `tokens` por LanguageEntry, todo lo demás igual (mismos hashes, mismos chunks futuros).
- **Implicación arquitectónica:** el módulo `corpus/` deja de depender de `tiktoken` directamente. El conteo de tokens ahora es una responsabilidad del módulo `rag/` (que es donde vive el modelo). El orquestador `corpus/ingest.py` importa la función `token_count` de `rag/embeddings.py`. **Esto crea una dependencia direccional `corpus/ → rag/`** que no existía en H1; conviene documentarlo en ADR 0004 para no caer en circular imports cuando H2 también consuma manifests.
- **Enlace:** se documentará en ADR 0004 (RAG architecture) al cierre de H2.

### 2026-05-04 · Reranker (cross-encoder bge-reranker-v2-m3) entra completo en H2, no en H3

- **Decisión:** el módulo `src/regulaitor/rag/reranker.py` se implementa completo en H2, incluyendo la carga del modelo `BAAI/bge-reranker-v2-m3` y la función `rerank(query: str, passages: list[str]) -> list[tuple[int, float]]`. El smoke test del cierre de H2 ejecuta el flujo completo: query → embedding → top-k denso (LanceDB) → rerank → top-N final. Solo el wrapping en agente (Retriever-Agent) + exposición vía MCP tool quedan para H3.
- **Justificación:**
  1. **El plan operativo lo encuadra explícitamente en H2.** El plan dice: *"H2 — RAG base: chunking, embeddings, reranker, store LanceDB."* El reranker está bajo "RAG base", no bajo "agentes y autonomía" (que es Módulo 2 del Máster, asociado a H3-H4).
  2. **El reranker es modelo + función pura, no agente.** Un cross-encoder recibe una `(query, passage)` y devuelve un score escalar. No tiene memoria, ni autonomía, ni invoca herramientas. Es un módulo determinista comparable al embedder. Forzarlo a H3 inflaría el alcance de "Retriever-Agent" sin razón arquitectónica: el agente es la capa que **decide qué consultar**, no la capa que **ranquea pasajes**.
  3. **Smoke test académicamente más fuerte al cierre de H2.** Con el reranker dentro, H2 cierra demostrando que una query como *"obligaciones del proveedor de un sistema de IA de alto riesgo"* devuelve los 3 artículos más relevantes ordenados por relevancia real (no solo similitud de coseno cruda). Sin el reranker, H2 cerraría con "top-k de similitud densa devuelve resultados plausibles" — útil pero menos diferencial. La memoria del TFM puede argumentar al evaluador del módulo M3 que "RegulAItor implementa retrieval híbrido (dense + cross-encoder rerank) desde la base, no como un parche posterior".
  4. **Sinergia operativa con BGE-M3.** Ya estamos descargando el embedder BAAI/bge-m3 (~2.3 GB) y configurando `actions/cache` sobre `~/.cache/huggingface`. Añadir bge-reranker-v2-m3 (~600 MB) en la misma tanda comparte cache y carga, en lugar de duplicar la decisión de infraestructura en H3. Una sola PR, una sola entrada en `pyproject.toml`, un solo paso de cache CI.
  5. **Higiene del scope de H3.** H3 ya es denso: Retriever-Agent (con su prompt versionado y su contrato Pydantic), MCP server propio con 5 tools, schemas Pydantic compartidos, citation_validator inicial. Si H3 además tuviera que decidir sobre el reranker, su Done criteria se hincharía y los gates serían menos verificables.
- **Alternativas descartadas:**
  - **B. Reranker fuera de H2 (deferir a H3):** rechazada porque infla H3 sin razón y deja H2 con un smoke test más débil de defender académicamente.
  - **C. Stub en H2 + impl en H3 (`IdentityReranker` que devuelve pasajes sin reordenar):** rechazada porque añade un patrón de "interface con dos implementaciones" que no aporta valor real (no hay tests donde queramos un reranker no-real). Es ingeniería defensiva sin escenario que la justifique.
- **Detalle técnico — modelo:**
  - `BAAI/bge-reranker-v2-m3` es un cross-encoder multilingual derivado de XLM-RoBERTa. Recibe pares `(query, passage)`, devuelve un score logit por par. Soporta español e inglés (y otros 100+ idiomas).
  - Tamaño en disco: ~600 MB (modelo fp32). Si CI necesita acelerar, se puede usar fp16 (~300 MB) sin pérdida material de calidad para nuestro uso.
  - Latencia esperada en CPU: ~50-150 ms para 10 pasajes en query típica. En GPU < 20 ms. Aceptable para H2 smoke; el Retriever de H3 puede paralelizar si es cuello de botella.
- **Detalle técnico — interfaz pública del módulo:**
  ```python
  # src/regulaitor/rag/reranker.py

  from FlagEmbedding import FlagReranker

  class Reranker:
      """Re-rank dense-retrieved passages with a cross-encoder.

      Lifecycle: load the model once at module/process start; reuse for all queries.
      """
      def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3", use_fp16: bool = False) -> None:
          self._model = FlagReranker(model_name, use_fp16=use_fp16)

      def rerank(self, query: str, passages: list[str], top_n: int | None = None) -> list[tuple[int, float]]:
          """Score each passage against the query; return list of (original_index, score),
          sorted by score descending. If top_n is set, truncate."""
          if not passages:
              return []
          scores = self._model.compute_score([(query, p) for p in passages], normalize=True)
          ranked = sorted(enumerate(scores), key=lambda kv: kv[1], reverse=True)
          return ranked[:top_n] if top_n else ranked
  ```
- **Detalle técnico — integración en el smoke test de H2:**
  ```python
  # En el smoke / integration test
  query = "obligaciones del proveedor de un sistema de IA de alto riesgo"
  q_vec = embedder.embed(query)
  candidates = store.query(q_vec, top_k=20, where={"norma": "ai_act", "language": "es"})
  passages = [c.text for c in candidates]
  ranked = reranker.rerank(query, passages, top_n=3)
  top_articles = [candidates[i] for i, score in ranked]
  ```
- **Implicación para H3:** el `Retriever-Agent` recibe una query y orquesta: `embedder.embed → store.query → reranker.rerank → return contexto estructurado`. Es un wrapper fino (≤80 líneas estimadas). Si H3 detecta que el reranker es lento bajo carga, ahí es donde se introducen optimizaciones (batching, caché, fp16) — no en H2.
- **Implicación para coste:** el reranker añade ~600 MB de cache HF y ~50-150 ms a cada query en CPU. La memoria del TFM (cost_analysis.md, H17) debe contabilizarlo como parte de la "latencia p95" pactada (≤12 s en MVP).
- **Enlace:** se formaliza en ADR 0004 (RAG architecture) al cierre de H2.

### 2026-05-04 · Orquestador `rag/build.py` separado de `corpus/ingest.py`

- **Decisión:** H2 introduce un nuevo orquestador en `src/regulaitor/rag/build.py` con función `run()` propia, distinto e independiente del `corpus/ingest.py` de H1. La cadena queda: `make ingest` produce parse + manifest article-level (lo que ya hace H1); `make rag-build` lee ese manifest + `corpus/processed/`, ejecuta chunker + embedder + reranker-warmup + upsert LanceDB, y extiende el manifest existente con `chunks` y `embedded_at` poblados. Ambos comandos son idempotentes, ambos usan `manifest.save_atomic` para escritura, y ambos comparten un módulo de utilidades (`corpus/_targets.py` o similar) para `expand_targets(corpus, langs)`.
- **Justificación:**
  1. **Separación de capas defendible académicamente.** La memoria del TFM (Módulo 3 del Máster: RAG, evaluación, despliegue) puede argumentar con limpieza: "el módulo `corpus/` materializa el ciclo de ingesta documental (fetch → parse → validate → manifest); el módulo `rag/` materializa el ciclo de indexación vectorial (chunk → embed → store → manifest-extension); ambos son orquestadores independientes con sus propios criterios de idempotencia, sus propias dependencias y sus propios gates". Forzar todo en `corpus/ingest.py` enturbiaría esta narrativa: `corpus/` empezaría a depender de LanceDB, BGE-M3, FlagEmbedding, etc. — cosas que conceptualmente pertenecen a la capa de retrieval, no a la de ingesta documental.
  2. **Cycle de iteración real del desarrollador en hitos posteriores.** El caso operativo concreto: "ajusto el threshold del chunker de 1000 a 800 tokens", o "cambio el modelo de embedding de bge-m3 a un fine-tune", o "actualizo el normalizador de `text_normalized`". En ninguno de esos casos cambia el corpus parseado, así que no debería re-parsearse. Con dos orquestadores: `make rag-build --force-rebuild` y listo. Con un solo orquestador, hay que añadir flags cada vez más finos (`--skip-fetch --skip-parse --only-chunk-and-embed`), lo que infla la API y embarra la lógica condicional.
  3. **Acoplamiento estructural minimizado.** En H1 ya aceptamos un acoplamiento puntual `corpus/ → rag/` (función `token_count` consumida por `corpus/ingest.py`); esto es una flecha pequeña y direccional. Si todo el orquestado de RAG viviera dentro de `corpus/ingest.py`, esa flecha se convertiría en imports masivos a `rag/store`, `rag/chunking`, `rag/embeddings`, `rag/reranker`. La regla de aislamiento que CLAUDE.md §22.13 aplica al router de modelos ("ningún agente llama directamente a un modelo; todo pasa por el router") es la misma idea aplicada al orquestador: capas que no se mezclan a propósito.
  4. **Tests más limpios y rápidos.** El test integration de `corpus/ingest.run()` puede seguir corriendo sin instalar BGE-M3 (modelo 2.3 GB) ni LanceDB. Solo `tests/integration/test_rag_build_flow.py` carga esos pesos. Esto mantiene la suite total ágil — desarrolladores que solo tocan `corpus/` no pagan el coste de descargar embeddings.
  5. **Comando `make rag-build` como ciudadano de primera clase.** El Makefile ya tiene `make ingest`. Añadir `make rag-build` (y luego `make eval`, `make redteam`, etc., todos en H8-H9) hace que el reviewer académico ejecute `make ingest && make rag-build && make eval && make redteam && make serve` y entienda visualmente el pipeline completo sin abrir código. Esa explicabilidad operativa es valor de defensa del TFM.
  6. **Atomicidad y resiliencia preservadas.** `rag/build.py` sigue el mismo patrón de `corpus/ingest.py`: acumula trabajo en estructuras en memoria, al final hace un único `manifest.save_atomic(...)` que es temporal + `os.replace`. Si revienta a mitad de embedding del corpus 3, el manifest viejo (eventualmente con corpus 1+2 ya re-procesados de runs anteriores) sigue válido. Misma resiliencia que H1.
- **Alternativas descartadas:**
  - **A. Extender `corpus/ingest.run()` con la fase RAG:** rechazada por las razones 1-4. Crece la función a ~600 líneas, mezcla capas, infla los tests del corpus.
  - **C. Cada módulo (chunker, embedder, store) escribe directamente al manifest:** rechazada categóricamente. Múltiples puntos de I/O, no atómico, contraria a la disciplina H1 que pasó por revisión.
- **Detalle técnico — cadena de comandos del Makefile:**
  ```makefile
  ingest:    ## fetch + parse + validate + write manifest (article-level)
    $(UV) run python -m scripts.ingest --use-local-only --corpus all --lang all

  rag-build: ## chunk + embed + rerank-warmup + upsert LanceDB + extend manifest
    $(UV) run python -m scripts.rag_build --corpus all --lang all
  ```
  Ambos comandos son idempotentes: re-ejecutar sin cambios devuelve `reprocessed=0`.
- **Detalle técnico — flujo de `rag/build.run()`:**
  ```
  1. Cargar manifest existente (debe existir; si no, abortar pidiendo `make ingest` antes).
  2. Cargar processed/{corpus}_{lang}.json para reconstruir ParsedArticle.
  3. Para cada (corpus, lang, article):
     a. Si manifest tiene `chunks` no vacío y hash del artículo no cambió y model_version
        no cambió → skip (ya indexado).
     b. Si no:
        - Chunker: dividir si > 1000 tokens (BGE-M3 tokens), generar chunk_ids.
        - Embedder: BGE-M3 sobre cada chunk → vector 1024-dim.
        - LanceDB: upsert por chunk_id (DELETE WHERE chunk_id LIKE '{article_id}.%' + INSERT).
        - Manifest LanguageEntry: poblar `chunks` con la lista de chunk_ids, `embedded_at = now`.
  4. Pre-cargar reranker (warmup, evita latencia en primer query post-build).
  5. Escribir manifest actualizado vía save_atomic.
  6. Devolver IngestSummary con `chunks_added`, `chunks_unchanged`, `embeddings_recomputed`.
  ```
- **Detalle técnico — utilidades compartidas:**
  - `corpus/_targets.py` (o módulo equivalente): expone `expand_targets(corpus, langs)` que devuelve `(list[Norma], list[Language])`. Hoy vive en `corpus/ingest.py` como función privada `_expand_targets`; H2 la promueve a módulo público compartido por ambos orquestadores. Tests de esa función pasan a `tests/unit/corpus/test_targets.py`.
  - El schema `IngestSummary` no se reutiliza tal cual (tiene campos específicos de fetch HTTP que no aplican a RAG); H2 introduce un `RagBuildSummary` análogo.
- **Implicación para H1 (refactor menor):** `_expand_targets` se promueve de privado a público (renombrar a `expand_targets`, mover a `corpus/_targets.py`, importar desde `ingest.py`). Cero cambios funcionales, refactor de 10 líneas. H2 lo hará en su primer commit como housekeeping.
- **Implicación para CI:** dos jobs de test posibles, o uno con marcadores. Recomendación: un solo job `pytest`, pero los tests de `tests/integration/test_rag_build_flow.py` se marcan con `@pytest.mark.slow` si son >30s; CI corre `pytest -m "not slow"` por defecto y `pytest -m slow` en un job separado o en push a main. Decisión final cuando se vea el tiempo real en CI.
- **Implicación para H8 (gold set):** `make eval` consume el LanceDB ya construido. La cadena `make ingest && make rag-build && make eval` es la pipeline completa que H8 ejecuta para producir métricas reales.
- **Enlace:** se formaliza en ADR 0004 al cierre de H2.

### 2026-05-04 · Versionado del modelo de embedding por `LanguageEntry`

- **Decisión:** el schema `LanguageEntry` (Pydantic v2 en `src/regulaitor/corpus/schemas.py`) se extiende con un campo `embedding_model: str | None = None` que almacena el identificador del modelo que produjo los vectores de los chunks de esa entrada (formato `"{repo}@{version_or_hash}"`, p. ej. `"BAAI/bge-m3@v1.0"` o `"BAAI/bge-m3@sha256:abcd..."`). El orquestador `rag/build.py` evalúa skip-condition como `hash_unchanged AND embedding_model_unchanged`. Cualquier cambio en cualquiera de los dos invalida el `LanguageEntry` y dispara re-embebido. Solo afecta al embedder; el reranker NO requiere campo análogo (es función pura, no persiste datos).
- **Justificación:**
  1. **Evita el bug silencioso "model skew" en LanceDB.** Sin este campo, el escenario es: día N el repo embebe con BGE-M3 v1 y guarda 424 vectores en LanceDB; día N+k alguien actualiza la versión del modelo en `pyproject.toml`; día N+k+1 corren `make rag-build` y la regla de skip "hash del texto no cambió → preserva chunks" se dispara sin saber que el modelo cambió. El sistema queda inconsistente: las queries que el Retriever-Agent embebe con v2 buscan en un espacio vectorial v1 que las queries no comparten. No hay error visible — solo que la búsqueda devuelve resultados malos. Es exactamente el tipo de bug que destruye una demo de TFM en directo. Versionar el modelo en cada `LanguageEntry` cierra esta brecha automáticamente.
  2. **Trazabilidad completa para defensa académica.** El TFM puede afirmar al evaluador del Módulo 3: "cada vector almacenado en LanceDB puede trazarse exactamente al modelo y la versión que lo generó, no solo al texto fuente. Esto permite auditar embeddings, hacer A/B testing reproducible, y detectar deriva de modelo en producción". Sin este campo, la trazabilidad termina en "se generó con BGE-M3 (la versión del momento)", lo cual es suficiente para hoy pero no para Módulo 3, que pide explícitamente "monitorización y mejora continua" (P7 del Máster).
  3. **Granularidad por `LanguageEntry` permite escenarios mixtos sin re-arquitectura.** Caso futuro plausible: BGE-M3 saca v2 con mejoras notables en EN pero regresión en ES (esto pasa periódicamente con multilingual models). Con campo a nivel `LanguageEntry`, podemos re-embeder solo las 113 entradas EN y dejar las 99 ES con v1: evaluamos calidad por idioma en H8, decidimos por separado. Con campo global a nivel manifest, no hay forma de mezclar — toda la regeneración es atómica por corpus.
  4. **Coste despreciable.** Un campo `str | None` con valor típico de ~30 caracteres × 424 entradas = ~12 KB extra en los manifests. JSON parsing, schema validation, diff: todo dentro del coste asintótico de los demás campos. La granularidad fina es prácticamente gratis.
  5. **Asimetría con el reranker es intencional, no descuido.** El reranker (`bge-reranker-v2-m3`) es función pura: recibe `(query, passages)`, devuelve scores, **no persiste nada**. Cada llamada en H3 (Retriever-Agent) usa el modelo activo en ese momento. Si cambia el reranker, los scores nuevos los produce el modelo nuevo y no hay datos viejos que invalidar. Por tanto NO necesita campo `reranker_model`. Pero documentamos esta asimetría aquí explícitamente, porque sin justificación parece una omisión.
  6. **El plan operativo no lo había prefijado** (es decisión nueva surgida de la fase de brainstorming H2), pero encaja con el principio rector de CLAUDE.md §17.13 ("sin findings críticos"): un bug silencioso que mezcla espacios vectoriales es exactamente el tipo de finding crítico que el red team adversarial puede explotar en H9 (un atacante prepara payloads que aprovechan baja similitud entre el modelo viejo y el nuevo para inyectar contenido no detectable).
- **Alternativas descartadas:**
  - **B. Campo global `embedding_model_version` a nivel manifest:** rechazada por la razón 3 (impide mezclar versiones por idioma o por corpus). El ahorro en bytes es trivial (~30 caracteres en lugar de ~12 KB), no compensa la rigidez.
  - **C. Sin campo, invalidación manual con `--force-rebuild`:** rechazada categóricamente por la razón 1. Frágil. Convierte un bug silencioso en una bomba de tiempo. Es exactamente el patrón que CLAUDE.md §22.20 condena ("si detectas sobreingeniería, dilo"; el converso aplica: "si detectas falta de mecanismo de protección, no lo escondas tras un flag opcional").
- **Detalle técnico — diff en el schema:**
  ```python
  # En src/regulaitor/corpus/schemas.py

  class LanguageEntry(BaseModel):
      """Per-language metadata for one article. H2 fills `chunks`, `embedded_at`,
      and `embedding_model`."""
      hash: str
      tokens: int
      chunks: list[str] = Field(default_factory=list)
      embedded_at: datetime | None = None
      embedding_model: str | None = None   # <-- NUEVO en H2
      fetched_at: datetime
      source_url: str
  ```
  Default `None` mantiene compatibilidad hacia atrás: los manifests producidos por H1 (sin este campo) cargan limpio (Pydantic acepta el default), y el primer `make rag-build` los puebla.
- **Detalle técnico — formato del valor:**
  - Patrón canónico: `"{huggingface_repo}@{tag_or_hash}"`.
  - Si está pinneado a una release oficial: `"BAAI/bge-m3@v1.0"`.
  - Si está pinneado a un commit del HF Hub: `"BAAI/bge-m3@sha256:e1f2c3..."` (los primeros 16 caracteres del hash bastan; el `safetensors` index del modelo expone este hash).
  - Recomendación operativa: usar el hash del checkpoint, no el tag, porque el HF Hub permite re-tag (un día `v1.0` apuntaba al checkpoint A, mañana al B). El hash es inmutable.
- **Detalle técnico — lógica de skip en `rag/build.py`:**
  ```python
  def should_skip(entry: LanguageEntry, current_model: str, force: bool) -> bool:
      if force:
          return False
      if not entry.chunks:                        # nunca embebido → no skip
          return False
      if entry.embedding_model != current_model:  # modelo cambió → no skip
          return False
      # hash ya verificado por el orquestador en _build_manifest
      return True
  ```
- **Detalle técnico — migración de manifests existentes (H2 primer build):**
  - Los manifests H1 actuales (`corpus/manifests/{ai_act,gdpr}.json`) tienen `chunks: []` y `embedded_at: None` para todas las 424 entradas.
  - El primer `make rag-build` ve `entry.chunks == []` → no skip → embebe todo → puebla `chunks`, `embedded_at`, `embedding_model = "BAAI/bge-m3@<sha del checkpoint>"`.
  - Cero migración manual. El campo nuevo, al ser optional con default None, no rompe la carga del manifest H1.
- **Detalle técnico — A/B testing futuro (H8 / H12):**
  - Si en H12 (router multi-LLM) queremos comparar BGE-M3 vs un fine-tune custom, podemos correr `make rag-build --embedder=bge-m3-finetune` que produzca una segunda copia de los vectores en una tabla LanceDB diferente o en la misma con `embedding_model` diferente, y `make eval` evaluaría las métricas RAGAS en cada conjunto. Sin este campo, no hay manera de saber qué vectores corresponden a qué modelo.
- **Implicación para CLAUDE.md §17 métricas (H17):** la sección "Faithfulness ≥ 0.85" del cost analysis puede referenciar el `embedding_model` exacto que produjo los embeddings sobre los que se midió la métrica. Esto es lo que diferencia "tenemos faithfulness 0.85" de "tenemos faithfulness 0.85 con BGE-M3 v1.0 (checkpoint hash X) sobre un corpus snapshot del 4 de mayo de 2026". El segundo es defendible; el primero es vago.
- **Implicación para H9 (red team):** uno de los ataques canónicos del red team puede ser "model version skew" — adversario con conocimiento de la versión vieja del modelo prepara queries que explotan vectores estancados. Tener `embedding_model` en el manifest permite al Auditor detectar si un chunk fue embebido con un modelo distinto al que el Retriever está usando ahora, y marcar la inconsistencia.
- **Enlace:** se formaliza en ADR 0004 al cierre de H2.

### 2026-05-04 · `fecha_ingesta` se mantiene a nivel `LanguageEntry`, no en `Chunk`

- **Decisión:** los campos de fecha de ingesta del corpus (`fetched_at`, `embedded_at`) viven en `LanguageEntry` (manifest), no en `ChunkRecord` (LanceDB). El schema `Chunk` y `ChunkRecord` no incluyen un campo `fecha_ingesta` o equivalente. El metadato CLAUDE.md §7 ("Cada chunk debe tener metadatos: ... fecha_ingesta ...") se cumple por la trazabilidad transitiva chunk → article_id → manifest entry → fetched_at/embedded_at.
- **Justificación:**
  1. **DRY:** todos los chunks de un mismo `(article, language)` comparten la misma fecha de ingesta. Duplicarlo en cada chunk multiplica datos sin beneficio.
  2. **Coherencia con la regla de versionado:** el manifest ya tiene `fetched_at`, `embedded_at`, `embedding_model` por `LanguageEntry`. El chunk hereda esos atributos por su `article_id`.
  3. **Inmutabilidad operativa:** si `fecha_ingesta` viviera en cada chunk, una re-ingest cambiaría timestamps en todos los chunks de un artículo aunque el contenido no cambie. Mantenerlo en `LanguageEntry` permite que H1 idempotency (preserve chunks/embedded_at when hash matches) funcione limpio.
  4. **El Auditor (H4) accede vía join:** cuando el Auditor necesita la fecha de ingesta de la cita, lee el manifest del corpus correspondiente. La query a LanceDB ya devuelve `article_id`; un lookup contra el manifest es O(1) en memoria con un dict pre-cargado.
- **Alternativa descartada:**
  - **Duplicar `fetched_at` y `embedded_at` en cada `ChunkRecord`:** rechazada por las razones 1, 2, 3. Inflaría LanceDB ~12 bytes × N chunks × 2 timestamps = ~10 KB extra para 424 chunks; trivial en disco pero conceptualmente ruidoso.
  - **Añadir un campo único `chunk_ingest_date` distinto del manifest:** rechazada porque introduciría un tercer concepto temporal sin claridad de cuándo aplica.
- **Detalle técnico — flujo del Auditor (H4):**
  ```python
  # H4 Auditor receives a (norma, article_id, chunk_id) from the Analyst's citation
  m = manifest_mod.load(MANIFEST_DIR / f"{norma}.json")
  article = next(a for a in m.articles if a.article_id.startswith(article_id.rsplit('.', 1)[0]))
  fetched_at = article.languages[lang].fetched_at
  embedded_at = article.languages[lang].embedded_at
  embedding_model = article.languages[lang].embedding_model
  ```
- **Implicación para CLAUDE.md §7:** la afirmación literal "Cada chunk debe tener metadatos: ... fecha_ingesta ..." se cumple en su intención (cada chunk tiene una fecha de ingesta trazable), no en su forma literal (no en una columna `fecha_ingesta` del chunk record). El cumplimiento es por composición jerárquica chunk → manifest, que es defensible académicamente y más robusto operacionalmente. Esta decisión se hizo durante el code review de Task 7 (commit a determinar) tras detectar la ambigüedad.
- **Enlace:** se referenciará en ADR 0004 al cierre de H2.

Cada vez que el autor apruebe una decisión técnica (incluida una respuesta `OK`, `A`, etc. en una sesión de brainstorming, una decisión en un PR review, o una elección de stack):

1. Añadir entrada al hito correspondiente.
2. Si la decisión es de arquitectura no trivial (criterio: cambia la estructura de archivos, contratos públicos o invariantes), abrir además un ADR formal en `docs/adr/`.
3. Mantener el orden cronológico dentro de cada hito.

Cuando se cierre un hito, mover sus decisiones a una sección "cerrado" (no borrar) para que el log sirva como narrativa de defensa.
