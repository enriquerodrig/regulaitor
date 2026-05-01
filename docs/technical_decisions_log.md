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

---

## Convención de actualización

Cada vez que el autor apruebe una decisión técnica (incluida una respuesta `OK`, `A`, etc. en una sesión de brainstorming, una decisión en un PR review, o una elección de stack):

1. Añadir entrada al hito correspondiente.
2. Si la decisión es de arquitectura no trivial (criterio: cambia la estructura de archivos, contratos públicos o invariantes), abrir además un ADR formal en `docs/adr/`.
3. Mantener el orden cronológico dentro de cada hito.

Cuando se cierre un hito, mover sus decisiones a una sección "cerrado" (no borrar) para que el log sirva como narrativa de defensa.
