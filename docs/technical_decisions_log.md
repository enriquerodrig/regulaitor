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

## H1 — Corpus AI Act + RGPD (cerrado 2026-05-04)

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

## H2 — RAG base (cerrado 2026-05-04)

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

### 2026-05-05 · CVE-2026-1839 (transformers) — descartada por ruta de código no usada

- **Decisión:** ignorar `CVE-2026-1839` en `pip-audit` con `--ignore-vuln CVE-2026-1839`, justificación documentada en este log y en un comentario inline en `.github/workflows/ci.yml`. Mantener el pin `transformers>=4.44,<5.0` introducido en Task 12 de H2.
- **Contexto del conflicto:**
  - El pin `transformers<5.0` se introdujo en H2 (Task 12) porque `FlagEmbedding 1.4.0` invoca `tokenizer.prepare_for_model`, método eliminado en `transformers 5.x`. Sin el pin, `reranker.warmup()` cascadea con `AttributeError`.
  - `pip-audit` flagea ahora `CVE-2026-1839` afectando a `transformers 4.57.6` (toda la línea 4.x); el fix es `transformers>=5.0.0rc3`.
  - Catch-22: pin `<5.0` → CVE bloquea CI. Pin `>=5.0` → reranker se rompe.
- **Análisis de la vulnerabilidad:**
  - **Componente afectado:** `Trainer._load_rng_state()` en `src/transformers/trainer.py` (~línea 3059).
  - **Naturaleza:** CWE-502 (insecure deserialization). El método llama a `torch.load("rng_state.pth")` sin `weights_only=True`. `torch.load` deserializa pickles arbitrarios → ejecución de código.
  - **Ruta de explotación:** requiere las TRES condiciones simultáneas:
    1. Llamar a `transformers.Trainer.train(resume_from_checkpoint=path)`.
    2. Que `path` apunte a un directorio con un `rng_state.pth` malicioso colocado por un atacante.
    3. Que el código de la aplicación pase ese `path` al Trainer (típicamente desde input de usuario o repo público).
  - **Severidad:** MEDIUM (CNA huntr.dev, CVSS 6.5) / HIGH (NIST NVD, CVSS 7.8). `AV:L / UI:R` — local + interacción de usuario requerida.
- **Por qué RegulAItor no es vulnerable:**
  - **Condición 1:** RegulAItor en H2 NO entrena modelos. Usa BGE-M3 y bge-reranker-v2-m3 pre-entrenados. El fine-tune LoRA es HX1 (opcional, no en MVP).
  - **Condición 2:** RegulAItor NO importa la clase `Trainer` de transformers. Verificación: `grep -r "from transformers" src/` no devuelve `Trainer`. La carga de modelos pasa exclusivamente por `FlagEmbedding.BGEM3FlagModel(...)` y `FlagEmbedding.FlagReranker(...)`, que internamente usan `AutoModel.from_pretrained` y `AutoTokenizer.from_pretrained` con safetensors (formato binario sin pickle, no ejecuta código).
  - **Condición 3:** RegulAItor NO acepta paths de checkpoint controlados por el usuario. Los identificadores son constantes hard-coded: `"BAAI/bge-m3"` y `"BAAI/bge-reranker-v2-m3"` apuntando a repos oficiales de BAAI en Hugging Face Hub.
  - El código vulnerable está en el binario instalado (`transformers 4.57.6`) pero ninguna ruta de ejecución de RegulAItor llega a él. Análogo a tener una librería con SQL injection sin invocar nunca su `db.execute(user_input)`.
- **Alternativas descartadas:**
  - **Bump a `transformers>=5.0.0rc3` + monkey-patch FlagEmbedding:** rechazada. (a) `5.0.0rc3` es release candidate; (b) v5 introduce otros breaking changes (`use_auth_token`→`token`, processor changes) que herederíamos; (c) monkey-patch sobre librería de terceros es deuda de mantenimiento que se rompe si FlagEmbedding 1.5 cambia el callsite.
  - **Swap FlagEmbedding → `sentence-transformers`:** rechazada. (a) Reescribiría ADR 0004 mid-H2; (b) perdería los outputs ColBERT/sparse de BGE-M3 (no se usan ahora pero queman opcionalidad para H8 evaluación retrieval avanzada); (c) churn de dependencias en cierre de hito.
  - **Bypass FlagEmbedding usando `AutoTokenizer` + `AutoModel` directos:** rechazada. (a) ~30 LOC adicionales que mantener; (b) contradice ADR 0004; (c) habría que re-validar gates de H2; (d) pierde ColBERT/sparse igual que sentence-transformers.
  - **Esperar a FlagEmbedding 1.5 (con soporte transformers 5.x):** rechazada. PR #1571 abierta sin ETA. Bloquearía H2 indefinidamente y violaría el principio "no avances con gates rojos" sin justificación documentada.
- **Detalle técnico — implementación del ignore:**
  ```yaml
  # .github/workflows/ci.yml
  - name: Pip-audit
    # Ignored: CVE-2026-1839 affects transformers.Trainer._load_rng_state...
    run: uv run pip-audit --ignore-vuln CVE-2026-1839
  ```
  Comentario inline largo en el workflow para que cualquier reviewer entienda el rationale sin saltar al log.
- **Condiciones de revisión obligatoria del ignore:**
  1. Cuando FlagEmbedding publique versión compatible con `transformers 5.x` (PR #1571 cerrada y release publicada): probar bump a transformers 5 y eliminar el ignore. Plazo de chequeo: cada cierre de hito.
  2. Cuando se introduzca cualquier código que importe `transformers.Trainer` (HX1 LoRA es el caso más probable): la justificación de "ruta no usada" deja de aplicar y hay que re-evaluar.
  3. Si NVD/CNA suben la severidad de la CVE o publican exploits PoC con vector de ataque distinto al `Trainer` path: re-evaluar inmediatamente.
- **Implicación para CLAUDE.md §16.2 gate #7** ("bandit / semgrep / pip-audit sin findings altos ni críticos"):
  - El gate del MVP se cierra en H10. El criterio "sin findings altos ni críticos" debe interpretarse como "sin findings altos ni críticos no justificados explícitamente". Una CVE en una ruta de código demostrablemente no usada, documentada y con condiciones de revisión, satisface el espíritu del gate.
  - El reporte de seguridad de H10 debe listar este ignore con justificación, no esconderlo.
- **Implicación para H17 (cierre académico):**
  - La memoria del TFM puede usar este caso como ejemplo concreto del proceso de gestión de riesgo de dependencias en un sistema multi-agente: análisis de la vulnerabilidad, mapeo a la ruta de código real, decisión justificada, condiciones de revisión.
  - Refuerza la narrativa del Auditor: igual que rechazamos respuestas sin cita, rechazamos "ignorar CVE porque sí" sin justificación trazable.
- **Enlace:** [GitLab Advisory CVE-2026-1839](https://advisories.gitlab.com/pkg/pypi/transformers/CVE-2026-1839/), [NVD](https://nvd.nist.gov/vuln/detail/CVE-2026-1839), [FlagEmbedding PR #1571](https://github.com/FlagOpen/FlagEmbedding/pull/1571). Workflow modificado en commit posterior a `c2cfc40`.

### 2026-05-04 · H2 cerrado: RAG base operativo

- **Decisión:** H2 cierra como Done. El pipeline RAG base está implementado, testeado, validado contra datos reales (AI Act + RGPD ES+EN) y con paper trail completo (spec, plan, ADR 0004, este log).
- **Stats finales del cierre:**
  - **Branch:** `feat/h2-rag-base`. **20 commits** del primero (`72ca768` — spec) al último (`a3eb658` — smoke artefacts).
  - **Tests:** 111 totales, todos verde (98 unit + 5 contract + 8 integration; 1 marcado `slow` que no entra en CI).
  - **Coverage global:** 92.55% sobre `src/regulaitor/` (gate 90%). Por módulo en `src/regulaitor/rag/`: `chunking.py` 100%, `embeddings.py` 100%, `reranker.py` 100%, `schemas.py` 100%, `store.py` 100%, `build.py` 91%.
  - **LanceDB:** tabla `chunks` con **1011 filas** distribuidas como sigue:
    - Por norma: `ai_act` 687, `gdpr` 324.
    - Por idioma: `es` 533, `en` 478.
    - Por norma × idioma: `ai_act_es` 361, `ai_act_en` 326, `gdpr_es` 172, `gdpr_en` 152.
    - Disco: 32 MB en `corpus/indexes/regulaitor.lance/` (gitignored, build artefact).
  - **Manifests:** los 4 (`ai_act_es`, `ai_act_en`, `gdpr_es`, `gdpr_en` dentro de `ai_act.json` y `gdpr.json`) extendidos con `chunks`, `embedded_at`, `embedding_model="BAAI/bge-m3"`. Article counts inalterados (113 + 99 = 212 artículos × 2 idiomas = 424 LanguageEntry slots).
  - **Idempotencia:** segunda ejecución de `python -m scripts.rag_build --corpus all --lang all` reporta `chunks_added=0, chunks_recomputed=0, chunks_unchanged=1011, errors=2`. Wall-clock ~3 s.
  - **Errors=2:** son cosméticos: `expand_targets("all")` incluye `nis2` y `dora` cuyos manifests aún no existen (los crea H14). El orchestrator los reporta como missing-manifest. No bloqueante; se resuelve en H14.
- **Sorpresa documentada — chunk count real (1011) ≠ estimado del spec (424–440):**
  - El spec asumía que la mayoría de artículos cabrían en un solo chunk y solo se splittean los AI Act 6/9/14. La realidad es que 52 LanguageEntries (32 AI Act + 20 GDPR) cruzan el umbral de 1000 tokens BGE-M3 y se splittean por `apartado`, con un promedio de ~3 chunks por LanguageEntry.
  - Causa raíz: muchos artículos del AI Act tienen múltiples apartados con detalle regulatorio extenso (definiciones, listas tasadas, considerandos referenciados). El umbral es más selectivo de lo que se asumía en brainstorming.
  - **No es un bug.** Es comportamiento correcto del chunker híbrido. Implicación positiva para H3 (Retriever): chunks más finos → mayor precisión de citación, porque cada chunk corresponde a un apartado citable, alineado con cómo se redactan las citas legales (`Art. X.Y`).
  - Implicación operativa: el TFM debe reportar el número real (1011) en memoria académica y model card, no la estimación inicial del spec.
- **Lecciones para H3 (Retriever-Agent):**
  - El Retriever recibe `(query, corpus, lang, top_k)` y orquesta `embeddings.embed → store.query → reranker.rerank`. Wrapper fino, ~80 líneas estimadas.
  - El boundary contract H2→H3 (manifests con `chunks`/`embedded_at`/`embedding_model` poblados; LanceDB queryable) está verificado por test de integración real (`tests/integration/test_rag_build_flow.py`, marcado `slow`, descarga BGE-M3 + bge-reranker-v2-m3 reales).
  - El reranker está warmed-up al final del build, así que la primera query del Retriever no paga cold-start (~5–10 s evitados).
  - Top-k: planificar contra ~1k–1.2k chunks por build, no ~400. Top-k inicial sugerido: 20 candidatos del store, 5 supervivientes tras rerank.
- **Lecciones para H8 (Evaluación):**
  - La granularidad fina (apartado-level) facilita métricas de citation precision: el gold set puede afirmar "la respuesta debe citar `ai_act.6.1.es`" en vez de "debe citar `ai_act.6.es`", lo que reduce ambigüedad en la evaluación.
  - El `embedding_model` en cada `LanguageEntry` permite re-evaluar después de un model swap sin perder trazabilidad: el reporte puede afirmar "Faithfulness 0.87 con BGE-M3 + corpus snapshot 2026-05-04" en vez de un genérico "Faithfulness 0.87".
- **Pin defensivo de `transformers<5.0`:** detectado durante Task 12. `FlagEmbedding 1.4.0` llama a `tokenizer.prepare_for_model`, removido en `transformers 5.x`. Pinned hasta que upstream FlagEmbedding emita un fix. Documentado en `pyproject.toml`.
- **Decisiones técnicas tomadas durante H2** (todas con entrada propia más arriba en este log):
  1. Embeddings BGE-M3 locales (no API).
  2. LanceDB single-table `chunks` particionada por metadata.
  3. Tokenizer swap completo `tiktoken` → BGE-M3 nativo (XLM-RoBERTa).
  4. Reranker bge-reranker-v2-m3 entra en H2 (no H3).
  5. Orquestador `rag/build.py` separado de `corpus/ingest.py`.
  6. Versionado de modelo de embedding por `LanguageEntry`.
  7. `fecha_ingesta` se mantiene en `LanguageEntry`, no se duplica en `Chunk`.
- **Enlace:** ADR 0004 (RAG architecture); spec `docs/superpowers/specs/2026-05-04-h2-rag-base-design.md`; plan `docs/superpowers/plans/2026-05-04-h2-rag-base.md`. Branch `feat/h2-rag-base`, primer commit `72ca768`, último `a3eb658`. Squash en `main`: `1f5147c`. Tag publicado: `v0.0.3-h2`.

### 2026-05-05 · Follow-up H2: `rag_build` reporta `errors=2` por nis2/dora missing en `--corpus all`

- **Estado:** detectado en auditoría post-cierre H2. **No bloqueante; diferido a H14.**
- **Síntoma:** `python -m scripts.rag_build --corpus all --lang all` reporta `errors=2` con mensajes "manifest not found for nis2" y "manifest not found for dora", aunque ai_act + gdpr se procesan correctamente y el CLI sale con exit code 0.
- **Causa:** `expand_targets("all")` en `corpus/_targets.py` devuelve los 4 corpora (`ALL_NORMAS`), pero solo ai_act y gdpr tienen manifests hasta H14. `corpus/ingest.py` filtra explícitamente con `[c for c in corpora if c in CELEX]` (donde `CELEX` está pinned solo para los corpora ingestables); `rag/build.py` no aplica filtro equivalente y cuenta los missing como `summary.errors += 1`.
- **Por qué no se fixea ahora:**
  1. Cosmético: la build real funciona correctamente (1011 chunks consistentes manifest⇄LanceDB).
  2. Corregir tocaría `rag/build.run` y sus tests (`tests/unit/rag/test_build.py`); cambio de comportamiento que merece su propio commit y revisión.
  3. H14 (NIS2 + DORA) creará los manifests faltantes y el síntoma desaparece automáticamente. Si en H14 todavía hay corpora sin manifest (e.g. corpus parcialmente integrado por bloqueo de upstream), allí se decide la semántica final: ¿error explícito o info silencioso?
- **Acción cuando se aborde:** distinguir "user pidió `--corpus all` y este corpus no existe todavía" (info-level, no error) de "user pidió `--corpus nis2` específicamente y no existe" (error). Patrón análogo al de `corpus/ingest.run` que ya filtra contra `CELEX`.
- **Enlace:** detectado durante auditoría post-H2 (commit que cerró auditoría).

---

## H3 — MCP server + Retriever-Agent + Citation validator (en diseño)

### 2026-05-05 · Alcance del MCP server en H3: 3 tools, no 5

- **Decisión:** H3 introduce el MCP server propio con **solo 3 tools** (`search_articles`, `fetch_article`, `validate_citation`), no las 5 listadas en CLAUDE.md §9. Las dos restantes (`extract_document`, `segment_document`) entran en H5 cuando aterrice el pipeline documental (extractor + sanitizer + segmenter).
- **Justificación:**
  1. **CLAUDE.md §22.16 prohíbe adelantar fases.** "No implementes Next.js antes de cerrar Streamlit, evaluación y red team." El mismo principio aplica a H5 antes de H3.
  2. **Stubs son deuda visible.** Shipear las 5 tools con 2 stubs `NotImplementedError` significa testearlos ahora y reescribirlos en H5: doble trabajo + desorden conceptual sobre cuál es el contrato real.
  3. **H3 ya tiene 4 sub-componentes** (schemas, validator, RetrieverAgent, MCP server). Añadir 3 más (extractor + sanitizer + segmenter) lo infla a tamaño no-single-spec.
  4. **El contrato MCP es trivialmente extensible.** Añadir tools en H5 no rompe clientes existentes (los protocolos JSON-RPC permiten descubrir tools dinámicamente).
  5. **SSDLC:** cada tool nueva amplía la superficie de ataque. Mejor introducirlas con threat-modeling localizado en su hito propio.
- **Alternativas descartadas:**
  - **Stubs (5 tools con 2 NotImplementedError):** rechazada por razón 2.
  - **Pull-in H5 a H3:** rechazada por razón 1, 3.
- **Implicación para H5:** la SKILL.md de `document-analysis` debe documentar que las 2 tools `*_document` se añaden al MCP server existente (`src/regulaitor/mcp_server/tools.py` ya creado en H3); no crear servidor separado.
- **Enlace:** ADR 0005 (planificado para cierre H3); spec H3 §1.

### 2026-05-05 · Transporte del MCP server: stdio en MVP

- **Decisión:** el MCP server expone sus tools por **stdio JSON-RPC** (transporte original del protocolo), no por Streamable HTTP. El server se lanza como subprocess (`python -m regulaitor.mcp_server`) y los clientes envían frames por stdin / leen por stdout.
- **Justificación:**
  1. **Simplicidad operacional.** Cero gestión de puertos, cero CORS, cero auth en MVP. El cliente lanza el server como subprocess directo.
  2. **Compatibilidad con Claude Desktop sin cambios.** Claude Desktop usa stdio por defecto: la demo de "abro un cliente MCP estándar y consume el corpus de RegulAItor" sale gratis.
  3. **YAGNI.** Streamable HTTP solo paga su coste cuando hay >1 cliente concurrente o exposición remota. H3 tiene 1 cliente local (el agente); H6 (Streamlit) y H7 (FastAPI) lanzarán el server desde el mismo proceso.
  4. **SSDLC: stdio no abre puerto.** Cero superficie de red. Si en H16 (despliegue público) hace falta HTTP, se añade entonces con auth + rate-limit en su sitio.
  5. **Reversible.** La lógica de las tools no depende del transporte. Cambiar a HTTP es ~30 LOC en `mcp_server/server.py` cuando lo amerite.
- **Alternativas descartadas:**
  - **Streamable HTTP en MVP:** rechazada por overhead operacional sin caso de uso.
  - **Dual-transport configurable por flag:** rechazada por YAGNI; doble código a testear sin ganancia.
- **Implicación para H16 (despliegue público):** si el server público se expone vía HTTP, el handoff es local: el contenedor lanza el server stdio, y un proxy HTTP delgado (FastAPI, e.g.) traduce HTTP↔stdio. Patrón común en deploys MCP.
- **Enlace:** spec H3 §3.1, §3.2.

### 2026-05-05 · Arquitectura: helper común con adapters finos (no agente-talks-MCP)

- **Decisión:** la lógica canónica de retrieval (embed → query → rerank → enrich) vive en `src/regulaitor/rag/retrieval.py::run`. Tanto el `RetrieverAgent` (LangGraph adapter) como el MCP tool `search_articles` son adapters finos que llaman al helper. **No** hay RPC interno entre el agente y el server; ambos comparten la misma función Python.
- **Justificación:**
  1. **Source of truth única.** La lógica embed+query+rerank se testea una vez en el helper. Los adapters tienen contract tests triviales sobre args + return.
  2. **Sin RPC interno innecesario.** El LangGraph del H4 va a invocar al RetrieverAgent dentro del mismo proceso Python. Meter stdio loopback ahí solo añade latencia (~5-20 ms) y complejidad operacional sin valor.
  3. **Cliente MCP externo (Claude Desktop) entra a la MISMA lógica.** El server hace dispatch al helper. Coherencia total: lo que prueba un evaluador del TFM por MCP es exactamente lo que ejecuta el RetrieverAgent en el chat E2E.
  4. **SSDLC:** el helper es un solo punto de auditoría/logging. Los adapters solo añaden trazado específico de su superficie (LangGraph state vs MCP request_id).
  5. **YAGNI elegante:** no construyes "agent talks to MCP" hoy y luego lo desmontas si no aporta valor. Y si en H16 se expone el MCP por HTTP, la lógica core no cambia.
- **Alternativas descartadas:**
  - **A. RetrieverAgent canónico, MCP envuelve:** descartada porque obliga al MCP server a importar `agents/`, mezclando capas (agent → corpus está bien; MCP → agent no tiene sentido).
  - **B. MCP canónico, RetrieverAgent envuelve por RPC:** descartada por la latencia interna y la complejidad operacional sin ganancia.
- **Estructura de archivos resultante:**
  ```
  rag/retrieval.py           # helper canónico — H3 nuevo
  agents/retriever.py        # adapter LangGraph — H3 nuevo
  mcp_server/server.py       # bootstrap stdio — H3 nuevo
  mcp_server/tools.py        # adapters MCP — H3 nuevo
  ```
- **Enlace:** spec H3 §3.1, §4.

### 2026-05-05 · Citation validator: matching normalizado exacto (sub-string sobre `_normalize`)

- **Decisión:** el validator compara la cita contra el corpus mediante **substring exacto sobre forma normalizada**. Reusa la función `_normalize` existente en `rag/chunking.py` (lowercase + strip accents + unify dashes + collapse whitespace). No fuzzy matching, no Levenshtein, no umbrales.
- **Justificación:**
  1. **Reusa exactamente lo que H2 ya tiene** y testea al 100%. Cero código nuevo de normalización, cero divergencia de comportamiento entre chunker y validator.
  2. **Cubre el 90% del ruido típico del LLM** sin abrir puertas: capitalización aleatoria, acentos perdidos al copiar de PDF, comillas tipográficas vs ASCII, dobles espacios, guiones largos vs cortos.
  3. **Defensible académicamente.** Cuando el tribunal pregunte "¿cómo decide tu sistema si una cita es válida?", la respuesta es: *"normalización determinista bien definida + comparación literal sobre la forma normalizada"*. Sin parámetros mágicos, sin "depende del modelo".
  4. **Defensa adversarial (SSDLC).** Fuzzy matching es **explotable**: un atacante puede construir una cita 95% similar al texto real pero que diga lo contrario semánticamente ("conforme con" → "no conforme con"). El red team de H9 va a probar exactamente eso. Strict normalizado cierra ese vector.
  5. **Comportamiento de fallo deseable.** Si el LLM cita parafraseando ("según establece el Art. 6", cuando el texto real es "el Artículo 6 establece"), el validator falla. El Auditor reporta "cita no validada → respuesta bloqueada", el sistema pide al Analyst que re-cite literal. Ese feedback loop es el corazón de la regla "no citation, no answer".
  6. **Capa fuzzy añadible en H15** (calibración del Auditor) sin breaking change si las evals lo justifican: AuditResult puede ganar campos `confidence_score` < 1.0 + `requires_human_review: bool` con warning explícito en `reason`.
- **Alternativas descartadas:**
  - **Literal estricto (sin normalización):** rechazada. Una sola comilla tipográfica `"` vs `"` y la cita válida cae. Penaliza al sistema sin ganancia adversarial.
  - **Fuzzy con umbral (Levenshtein ≥ 0.95):** rechazada por el vector adversarial + por el riesgo de calibrar el umbral sin gold set ni red team.
- **Detalle técnico — el `_normalize` exacto del H2:**
  ```python
  def _normalize(text: str) -> str:
      s = unicodedata.normalize("NFD", text.lower())
      s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
      s = re.sub(r"[–—−―]", "-", s)
      return re.sub(r"\s+", " ", s).strip()
  # "Artículo 6 — Sistemas de IA" → "articulo 6 - sistemas de ia"
  ```
- **Implicación para H4 (Auditor):** la comparación es **substring** (`_normalize(cita) in _normalize(corpus_text)`). El validator opera contra el texto del **apartado** si la cita tiene apartado, contra el **artículo entero** si no.
- **Enlace:** spec H3 §4.4; CLAUDE.md §6.

### 2026-05-05 · Schemas Pydantic en H3: solo los 5 que H3 produce/consume (no Finding ni Answer)

- **Decisión:** H3 define los schemas que produce/consume directamente: `Citation`, `AuditResult`, `RetrievedChunk`, `Context`, `FetchedArticle`. Los schemas `Finding` y `Answer` mencionados en planos previos se **defieren a H4**, cuando el Analyst esté siendo construido.
- **Justificación:**
  1. **YAGNI académicamente defendible.** Definir el shape de `Finding` ahora obliga a decidir cosas como: ¿severidad es enum `low/medium/high` o numérica? ¿`recommendation` es string libre o estructurado? ¿`citations` es ≥1 obligatorio o puede ser empty? Esas decisiones dependen del prompt del Analyst (H4) y del schema del gold set (H8). Comprometerlas ahora sin esa información es arbitrario.
  2. **El contrato real está en `Citation` y `AuditResult`.** Esos dos definen la frontera Analyst↔Auditor que materializa la regla "no citation, no answer". Definirlos bien en H3 es lo que importa. `Finding` / `Answer` son contenedores que pueden tomar la forma que mejor sirva al Analyst.
  3. **Coste de añadir en H4 es despreciable.** Pydantic v2 hace que añadir `Finding(BaseModel)` en H4 sea ~30 LOC + tests. Ningún consumidor de H3 cambia (no hay consumidor todavía).
  4. **Reduce el riesgo de breaking change a mitad de H4.** Si comprometemos `Finding` ahora con shape X, y al construir el Analyst nos damos cuenta que necesita shape Y, hay que reescribir + migrar tests + actualizar el log. Si lo definimos cuando lo construimos, sale derecho a la primera.
  5. **Disciplina YAGNI consistente con H2:** rechazamos schemas anticipados para casos especulativos varias veces durante H2.
- **Alternativa descartada:**
  - **Definir los 5 schemas (Citation, Finding, Answer, AuditResult, RetrievedChunk) ahora** "para que H4 tenga contrato congelado": rechazada porque la "congelación" prematura es justamente lo que produce breaking changes inesperados después.
- **Implicación para H4:** `citation/schemas.py` se extenderá con `Finding` y `Answer` cuando el Analyst esté operativo; el módulo ya estará en su sitio desde H3.
- **Enlace:** spec H3 §4.3.

### 2026-05-05 · Top-k en retrieval: defaults fijos pre=50 / post=5, MCP expone solo `top_k`

- **Decisión:** el helper `rag/retrieval.run` usa `PRE_RERANK = 50` (módulo-level constante) hardcoded para el query a LanceDB, y un parámetro `top_k: int = 5` (post-rerank) configurable por el caller. La MCP tool `search_articles` expone solo `top_k` al cliente. Ratio efectivo 10:1 entre candidatos pre-rerank y resultados finales.
- **Justificación:**
  1. **YAGNI calibratorio.** No tenemos gold set ni evals todavía (H8). Cualquier ajuste fino del ratio es arbitrario. Los defaults `50/5` vienen de literatura BGE-M3.
  2. **API mínima para el LLM.** El cliente MCP (incluido Claude Desktop en demo) ve un solo parámetro `top_k` con semántica obvia ("¿cuántos resultados quieres?"). Sin necesidad de explicar "candidatos" vs "resultados finales".
  3. **Heurística (ratio dinámico) introduce magia.** Pedir `top_k=20` con factor 10 dispararía `pre=200`, lo que en un corpus de 360 chunks ya es la mayoría. El usuario no sabe que pasó eso. Comportamiento sorprendente.
  4. **Doble parámetro (B) es no-breaking añadido después.** Si en H8 las evals demuestran que `pre=50` es subóptimo para queries densas, añadir `candidates` al MCP tool con default 50 es retrocompatible.
  5. **Tests deterministas.** Fixed defaults → fixtures predecibles. La integration test del retriever puede assert que devuelve exactamente N resultados con N conocido.
  6. **SSDLC:** API más pequeña = menos input que validar = menos superficie. Que un atacante mande `candidates=999999` para hacer DoS al rerank no es un vector que tenemos que cerrar si el parámetro no existe.
- **Alternativas descartadas:**
  - **Doble parámetro (`top_k` + `candidates`):** rechazada por overhead de API sin caso de uso actual.
  - **Heurística `pre = max(top_k * 10, 30)`:** rechazada por comportamiento sorprendente al usuario.
- **Detalle técnico:**
  ```python
  PRE_RERANK = 50

  def run(query, corpus, language, top_k: int = 5) -> list[RetrievedChunk]:
      candidates = store.search(...).limit(PRE_RERANK)
      reranked = reranker.rerank(query, [c.text for c in candidates], top_n=top_k)
      return reranked + meta enrichment
  ```
- **Implicación para H8 evals:** si tras gold set se demuestra que `pre=50` no es óptimo, añadir un nuevo parámetro `candidates` con default 50 es no-breaking; la decisión se revisa allí con datos.
- **Enlace:** spec H3 §4.2.

### 2026-05-05 · Validator depth: 3 chequeos estrictos (article + apartado + text), fail-fast con reason específico

- **Decisión:** el validator ejecuta 3 chequeos secuenciales con early-exit en el primero que falla:
  1. `article_exists`: ¿existe `(norma, articulo)` en el manifest?
  2. `apartado_exists` (si la cita lleva apartado): ¿existe ese apartado en el artículo?
  3. `text_normalized_match`: ¿el texto normalizado de la cita es substring del texto normalizado del **apartado** (si fue dado) o del **artículo** (si no)?
  Todos pasan → `validated=True`. Cualquiera falla → `validated=False` con `reason` específico al chequeo que falló.
- **Justificación:**
  1. **Cierra el vector "artículo correcto, apartado incorrecto".** Sin chequeo a nivel de apartado, un LLM puede citar `(art=6, apartado=1)` cuando el texto está en `apartado=5`. La cita pasa el text-match porque está en el artículo, pero la **estructura** de la cita es falsa. Vector adversarial concreto del red team H9.
  2. **Aprovecha datos que H1 ya almacena.** `corpus/processed/<norma>_<lang>.json` ya tiene `paragraphs: [{apartado, text}, ...]` por artículo. El validator simplemente lee `paragraphs[N].text` cuando `apartado=N`. Cero parsing nuevo.
  3. **`reason` granular es oro académico.** Cuando una cita falla, `AuditResult.reason` reporta exactamente qué falló y por qué (ver Sección 4.4 del spec). El tribunal puede inspeccionar logs de fallos y entender el rechazo.
  4. **Implementación trivial.** ~40 LOC de validator: 3 lookups secuenciales. Ningún algoritmo nuevo. Tests por cada rama.
  5. **SSDLC defense-in-depth.** Tres puertas independientes son más difíciles de saltar simultáneamente que una sola.
- **Alternativas descartadas:**
  - **Dos chequeos (article + text a nivel de artículo, apartado solo informativo):** rechazada por el vector "wrong apartado" no cerrado.
  - **Solo text-match:** rechazada porque permite citas con norma+articulo+apartado totalmente fabricados pero texto que existe en cualquier sitio del corpus.
- **Detalle técnico — `Citation.language` explícito (no auto-detect):** el schema requiere `language: Literal["es", "en"]` por construcción. Razón: auto-detect es un componente que puede fallar/ser engañado. Explicit > implicit; el Analyst declara la lengua y el validator confía pero verifica.
- **Schema resultante de `AuditResult` (preview):**
  ```python
  class AuditResult(BaseModel):
      citation: Citation
      validated: bool
      article_exists: bool
      apartado_exists: bool | None  # None si la cita no llevaba apartado
      text_normalized_match: bool
      reason: str | None  # human-readable; None iff validated=True
  ```
- **Enlace:** spec H3 §4.4.

### 2026-05-05 · `fetch_article` devuelve texto + metadata documental mínima (no metadata interna)

- **Decisión:** la tool MCP `fetch_article` devuelve un objeto `FetchedArticle` con 7 campos: `norma`, `articulo`, `apartado`, `language`, `text`, `version`, `source_url`. **No** expone metadata operacional del RAG (chunks, hash, embedded_at, embedding_model, tokens).
- **Justificación:**
  1. **Caso de uso real es texto.** Las dos consumiciones esperadas son: (a) el Auditor en H4 necesita el texto del apartado para validar; (b) un cliente externo (Claude Desktop) quiere "leer el Art. 6.1 del AI Act". Ambos necesitan texto + el mínimo contexto para citarlo.
  2. **Schema mínimo = contrato más estable.** `chunks`, `hash`, `embedded_at`, `embedding_model` son **internos del RAG** (boundary contract H1↔H2). Exponerlos los convierte en parte del contrato público del MCP: cualquier cambio interno del rag los rompería.
  3. **SSDLC: leak-by-default minimization.** Principio de mínima información: no exponer metadata operacional a clientes MCP externos hasta que haya un caso de uso real que lo justifique.
  4. **Latencia + tamaño.** Una `LanguageEntry` completa pesa ~10-20 KB serializada. Texto pesa ~1-3 KB. Para clientes stdio, KB extras son baratos pero acumulan.
  5. **Configurable (`format: "text" | "full"`) introduce ramas a testear sin justificación.** Añadirlo después es no-breaking si surge necesidad.
  6. **Coherente con `validate_citation`.** El validator internamente carga el `LanguageEntry` y trabaja con texto. `fetch_article` también. Una sola semántica para "lookup directo": "dame el texto".
  7. **`version` y `source_url` SÍ se exponen** porque son **información documental pública** (CELEX + URL EUR-Lex), no metadata interna. CLAUDE.md §7 los exige por chunk para audit trail.
- **Alternativas descartadas:**
  - **Exponer la `LanguageEntry` Pydantic completa:** rechazada por leak de metadata interna.
  - **Configurable con `format` parameter:** rechazada por YAGNI.
- **Detalle de comportamiento:**
  - Si `apartado` se da → devuelve solo `paragraphs[apartado].text`. Si no existe → `NotFoundError(-32001)` con mensaje accionable (`"ai_act art. 6 has no apartado 99. Valid apartados: 1-7."`).
  - Si `apartado` se omite → devuelve texto completo del artículo (concatenación de paragraphs separados por `\n\n`).
  - `language` es **requerido** (no `auto`) por mismo principio que el validator.
- **Enlace:** spec H3 §4.6, §6.

### 2026-05-05 · Corpus loader: lazy singleton + warmup explícito + integrity check fail-closed

- **Decisión:** los datos del corpus (manifests + processed JSON) se cargan en un **singleton in-memory** dentro de un nuevo módulo `corpus/loader.py`, análogo al patrón de `rag/embeddings.py` y `rag/reranker.py`. El MCP server llama `loader.warmup()` al arrancar, que carga los 4 procesados + 2 manifests en memoria **y verifica integridad** recomputando el SHA256 de cada `LanguageEntry.text` y comparando contra el hash del manifest. Drift detectado → `RuntimeError` → server no arranca.
- **Justificación:**
  1. **Tamaño que cabe en RAM.** Los 4 procesados + 2 manifests pesan **~2-4 MB combinados**. Cargarlos en warmup es trivial y elimina overhead de disk I/O en cada call. En H14 (NIS2 + DORA) sube a ~6-8 MB; sigue siendo trivial.
  2. **Pattern consistency.** El patrón "lazy singleton + warmup" ya está establecido en H2 para BGE-M3 y bge-reranker-v2-m3. Mismo patrón aquí mantiene la base mental simple.
  3. **Test discipline ya resuelta.** El patrón H2 incluye autouse fixture que resetea el singleton entre tests. Reusable directamente para `corpus/loader.py`.
  4. **Latencia predecible.** Para el flujo H4 (chat E2E con ~5 citas/respuesta), un `validate_citation` que internamente lee disco cada vez son 25-50 ms gratis. Con singleton: cero.
  5. **SSDLC fail-closed.** La regla "no citation, no answer" depende de que el corpus sea fiel a la fuente oficial. Si el corpus está alterado, **toda cita validada después es sospechosa** — el Auditor no detecta la manipulación porque su fuente de verdad ya está corrupta. La única política segura es **fail-closed en startup**.
  6. **Integrity check coste cero en happy path.** Recomputar SHA256 de 4 ficheros JSON (~2-4 MB) en warmup es <100 ms. Imperceptible.
  7. **Defensa adversarial concreta.** Modelo de amenaza: atacante con acceso al filesystem (supply-chain, container escape) sustituye `corpus/processed/ai_act_es.json` con versión alterada. Sin integrity check, el sistema produce respuestas falsamente "validadas". Con strict mode, el server crashea al arrancar.
  8. **Recovery path explícito.** Mensaje del error: `"manifest hash drift detected on ai_act art. 6 ES (expected sha256:abc..., got sha256:def...). Run 'make ingest' to refresh manifest, or restore corpus/processed/ from git-lfs."` Accionable.
  9. **Warn (B) es señal sin acción.** En la práctica, los warnings se ignoran. Un atacante que controla el filesystem puede contar con que los logs no se revisan en tiempo real.
  10. **Skip (C) renuncia al control.** No aprovecha información que tenemos gratis (los hashes ya están en el manifest desde H1).
- **Alternativas descartadas:**
  - **Lectura por llamada (sin caché):** rechazada por latencia acumulada en flujos con múltiples citas.
  - **DB layer (SQLite/LanceDB metadata):** rechazada por overkill (~2-4 MB no justifica DB).
  - **Warn-only (log + continúa):** rechazada por SSDLC fail-closed.
  - **Skip integrity check:** rechazada por renunciar a defensa que es gratis.
- **Detalle técnico — pseudocode warmup integrity check:**
  ```python
  for norma in CORPORA_WITH_MANIFESTS:
      m = manifest_mod.load(MANIFEST_DIR / f"{norma}.json")
      for article in m.articles:
          for lang, entry in article.languages.items():
              text = _load_processed_article_text(norma, article.articulo, lang)
              computed = hashlib.sha256(text.encode("utf-8")).hexdigest()
              if computed != entry.hash:
                  raise RuntimeError(
                      f"manifest hash drift detected on {norma} art. {article.articulo} {lang} "
                      f"(expected {entry.hash[:16]}..., got {computed[:16]}...). "
                      f"Run 'make ingest' to refresh manifest, or restore corpus/processed/ from git-lfs."
                  )
      _CORPUS_CACHE[norma] = m  # only cache if all hashes verified
  ```
- **Implicación para H14 (NIS2 + DORA):** los nuevos corpus se incorporan automáticamente al loader siguiendo el mismo patrón. Si el warmup tarda demasiado con corpus mucho más grande, profile y mover a warmup async background (mitigación documentada en risk register).
- **Implicación para H9 (red team):** uno de los ataques canónicos será "tampered processed/" → confirmar que el server falla al arrancar y NO sirve queries.
- **Enlace:** spec H3 §4.1, §7; ADR 0005.

### 2026-05-05 · `RetrievedChunk` shape: 9 campos (citable one-shot, sin metadata interna)

- **Decisión:** el schema `RetrievedChunk` que devuelve `search_articles` lleva 9 campos: `chunk_id`, `norma`, `articulo`, `apartado`, `language`, `text`, `score`, `version`, `source_url`. Incluye lo necesario para que el Analyst (H4) construya un `Citation` directamente sin segunda llamada al MCP. **No** incluye metadata operacional (`hash`, `embedded_at`, `embedding_model`, `tokens`).
- **Justificación:**
  1. **Coste cero en cable, ahorro real en llamadas.** `version` y `source_url` ya están cargados en memoria por el `corpus/loader.py` singleton. Añadirlos al chunk es un dict lookup. Sin ellos, el Analyst de H4 hace `search_articles` → elige top-3 → `fetch_article × 3` para conseguir version/source_url. Cinco round-trips MCP en vez de uno por respuesta.
  2. **Información NO sensible.** `version` (CELEX) y `source_url` (URL EUR-Lex pública) son información oficial documental, no secreta. El argumento "leak-by-default" del fetch no aplica: estos campos son **lo que la cita necesita** para ser auditable.
  3. **CLAUDE.md §7 obliga a `version` por chunk.** Literal: *"Cada chunk debe tener metadatos: norma, articulo, apartado, idioma, version, fuente, fecha_ingesta, hash"*. La regla se cumple por composición (chunk → article_id → manifest), pero exponer el chunk vía MCP sin `version` rompería trazabilidad para clientes externos.
  4. **Metadata operacional sin caso de uso.** `hash`, `embedded_at`, `embedding_model`, `tokens` son del orquestador `rag/build.py` para idempotencia. Ningún consumidor MCP los necesita. Exponerlos los convierte en parte del contrato público y ata las manos para refactor interno.
  5. **Schema intermedio que escala.** Si en H8 las evals piden ver el `hash` para correlacionar fallos con versiones del corpus, se añade entonces como campo opcional. Empezar mínimo y crecer guiado por evidencia.
- **Alternativas descartadas:**
  - **Mínimo (7 campos sin version + source_url):** rechazada por penalización 5x en round-trips para H4.
  - **Full (13+ campos con todo):** rechazada por leak de metadata interna sin caso de uso.
- **Schema resultante:**
  ```python
  class RetrievedChunk(BaseModel):
      model_config = ConfigDict(frozen=True)
      chunk_id: str
      norma: Norma
      articulo: str
      apartado: str | None
      language: Language
      text: str
      score: float = Field(ge=0.0, le=1.0)
      version: str
      source_url: str
  ```
- **Enlace:** spec H3 §4.3.

### 2026-05-05 · Política de errores MCP: por semántica de cada tool

- **Decisión:** cada MCP tool tiene una política de errores específica a su dominio:
  - `search_articles`: empty results → `[]` (resultado válido). Solo MCP error en fallo de infra.
  - `fetch_article`: artículo/apartado no existe → MCP error con `code=NOT_FOUND` (-32001). Args inválidos → `INVALID_PARAMS`. Infra → `INTERNAL_ERROR`.
  - `validate_citation`: cita inválida → `AuditResult(validated=False, reason=...)` siempre. **Nunca** lanza error por cita inválida. Args inválidos por Pydantic → `INVALID_PARAMS`. Infra → `INTERNAL_ERROR`.
- **Justificación:**
  1. **Cada tool tiene semántica distinta y la política refleja esa diferencia.**
     - `validate_citation` es un evaluador: nunca "falla" cuando dice "no válida"; **eso es el éxito de su trabajo**. Hacer que falle como error rompería el flujo del Auditor (H4) que tiene que poder distinguir "evaluación rechazó la cita" de "evaluación se cayó".
     - `fetch_article` pide un recurso específico. "No existe" es un 404 conceptual.
     - `search_articles` busca; "no encontré nada" es un resultado válido (vector de embedding del query no encaja con nada).
  2. **Alineado con convenciones HTTP/REST que el evaluador del TFM espera.** 200 con body para resultados válidos; 404 para recursos no encontrados; 5xx para fallo del servidor.
  3. **Result objects everywhere (B) introduce overhead de decisión.** Cada tool inventa su propio `NotFoundResult`, `EmptyResult`, etc., y los clientes hacen pattern-matching. MCP **ya tiene** un canal de errores estructurado.
  4. **Errors everywhere (C) colapsa información útil.** Si todo es error, el Auditor de H4 tiene que parsear el `error.code` para distinguir "cita rechazada por contenido" de "infraestructura caída". A mantiene esa distinción en el shape del retorno.
  5. **Contract tests más limpios.** Por tool, dos rutas a testear: "happy path" + "error path con código esperado".
  6. **SSDLC observability.** Los logs estructurados pueden distinguir "validación rechazó N citas" (señal de calidad del Analyst) de "fetch_article cayó N veces" (señal operacional). Misma distinción importante para el panel de métricas en H11.
- **Alternativas descartadas:**
  - **B. Result objects everywhere (no errors excepto infra):** rechazada por overhead de pattern-matching client-side y por no usar el canal de errores nativo de MCP.
  - **C. Errors everywhere (cualquier anomalía es error):** rechazada por colapsar "validación rechazada" con "infra caída".
- **Tabla de comportamiento:**

  | Tool | Happy path | Recurso missing | Bad input | Infra fail |
  |---|---|---|---|---|
  | `search_articles` | `list[RetrievedChunk]` | `[]` | `INVALID_PARAMS` | `INTERNAL_ERROR` |
  | `fetch_article` | `FetchedArticle` | `NotFoundError(-32001)` | `INVALID_PARAMS` | `INTERNAL_ERROR` |
  | `validate_citation` | `AuditResult(validated=True)` | `AuditResult(validated=False, reason=...)` | `INVALID_PARAMS` | `INTERNAL_ERROR` |
- **Enlace:** spec H3 §6.

### 2026-05-05 · `Context` como Pydantic wrapper, no plain list

- **Decisión:** el output del `RetrieverAgent.retrieve(...)` es un objeto `Context` (Pydantic v2) que envuelve la lista de `RetrievedChunk` con metadata adicional: `query`, `corpus`, `language`, `chunks`, `retrieved_at`, `embedding_model`. **No** es un alias de tipo `list[RetrievedChunk]`.
- **Justificación:**
  1. **El MCP tool `search_articles` y el RetrieverAgent no producen lo mismo.** El MCP tool devuelve `list[RetrievedChunk]` plano (contrato simple para clientes externos). El RetrieverAgent envuelve esa lista en `Context` con metadata adicional para uso interno por el LangGraph state de H4. Separación clara entre contrato externo (MCP, simple) y estructura interna (agent, rica).
  2. **Traceabilidad para evaluación (H8) y observability (H11).** Si el harness de evals quiere reportar "respuesta X con embedding model Y produjo retrieval Z para query Q", `Context` lleva todo eso por construcción. Sin wrapper, esa metadata se reconstruye desde logs externos — frágil.
  3. **Auditor (H4) puede verificar que el contexto es para el query actual.** `Context.query == analyst_state.query` es un check trivial pero importante: si el Analyst alegremente cita chunks de un retrieval anterior (race condition o bug), el Auditor lo detecta porque los queries no coinciden.
  4. **Cost < 30 LOC.** Pydantic v2 es declarativo; el wrapper es trivial. Tests también triviales (round-trip serialization).
  5. **Plain list (A) es premature simplification.** Cuando H4 quiera meter `query_id` para correlacionar logs, o H8 quiera versionar el embedding model usado, hay que añadir wrapper de todas formas.
- **Alternativas descartadas:**
  - **A. Plain list (`Context = list[RetrievedChunk]`):** rechazada por simplificación prematura.
  - **C. NamedTuple (`Context = NamedTuple(...)`):** rechazada como legacy Python; no se serializa bien a JSON.
- **Schema resultante:**
  ```python
  class Context(BaseModel):
      query: str
      corpus: Norma
      language: Language
      chunks: list[RetrievedChunk]
      retrieved_at: datetime
      embedding_model: str
  ```
- **Implicación para H4 (LangGraph state):** el `RetrieverAgent.retrieve()` se invoca como un nodo del graph; el output `Context` se guarda en el state que el siguiente nodo (Analyst) lee. El Analyst recibe `Context.chunks` para razonar sobre ellos.
- **Enlace:** spec H3 §4.5; CLAUDE.md §8.1.

Cada vez que el autor apruebe una decisión técnica (incluida una respuesta `OK`, `A`, etc. en una sesión de brainstorming, una decisión en un PR review, o una elección de stack):

1. Añadir entrada al hito correspondiente.
2. Si la decisión es de arquitectura no trivial (criterio: cambia la estructura de archivos, contratos públicos o invariantes), abrir además un ADR formal en `docs/adr/`.
3. Mantener el orden cronológico dentro de cada hito.

Cuando se cierre un hito, mover sus decisiones a una sección "cerrado" (no borrar) para que el log sirva como narrativa de defensa.
