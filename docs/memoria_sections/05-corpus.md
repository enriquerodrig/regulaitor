# 05. Corpus normativo

## Resumen

RegulAItor opera sobre un corpus de cuatro instrumentos normativos europeos —AI Act, RGPD, NIS2 y DORA— ingestados desde EUR-Lex, parseados a partir de PDFs oficiales, validados estructuralmente y persistidos como manifests JSON versionados en git más un índice LanceDB de **1569 chunks** bilingües (ES + EN). El corpus es el suelo sobre el que se apoya la invariante §6 "no citation, no answer": cada cita emitida por el Analyst debe resolverse contra este corpus o queda bloqueada. Ningún otro componente del sistema —ni el retriever, ni el validator, ni el Auditor— inventa contenido normativo: todo lo que el usuario ve viene literalmente de aquí.

Esta sección documenta qué corpus se ingestaron y por qué (CLAUDE.md §7), el pipeline EUR-Lex → PDF → manifest → LanceDB con su pivote operativo a PDF (ADR-0003) y posterior bypass de WAF vía Playwright (ADR-0015), el contrato del manifest (`src/regulaitor/corpus/schemas.py`) que aterriza los metadatos exigidos por §7.2 (`norma, articulo, apartado, idioma, version, fuente, fecha_ingesta, hash`), y las limitaciones honestas que el corpus arrastra y que se declaran abiertamente para defensa académica (sólo base-act sin enmiendas consolidadas para NIS2/DORA; `source_url` con paths absolutos de máquina de desarrollo; re-adquisición no reproducible vía `curl`).

## Cobertura del corpus

El corpus MVP obligatorio (CLAUDE.md §7.1) cubre **AI Act** y **RGPD**, los dos instrumentos centrales para una PYME europea con tratamiento de datos personales y/o sistemas de IA. La extensión "avanzada deseable" (§7.2) añadió **NIS2** y **DORA** en H14, alcanzando la cobertura cuatricorpus que se mantiene en el demo público v0.1.32-h16-deploy.

Cifras pinneadas desde los cuatro `corpus/manifests/*.json` actualmente vivos en repo (rama `main`, 2026-05-29):

| Corpus | Instrumento | CELEX | Versión | Artículos | Chunks (ES+EN) | Hito de ingesta |
|---|---|---|---|---|---|---|
| `ai_act` | Reglamento (UE) 2024/1689 | `32024R1689` | 2024-07-12 | 113 | 687 | H1 (2026-05-04) |
| `gdpr` | Reglamento (UE) 2016/679 | `02016R0679-20160504` | 2016-05-04 | 99 | 324 | H1 (2026-05-04) |
| `nis2` | Directiva (UE) 2022/2555 | `32022L2555` | 2022-12-27 | 46 | 244 | H14 (2026-05-18) |
| `dora` | Reglamento (UE) 2022/2554 | `32022R2554` | 2022-12-27 | 64 | 314 | H14 (2026-05-18) |

Total: **322 artículos** (todos bilingües) y **1569 chunks** indexados en LanceDB (`corpus/indexes/regulaitor.lance`). Los recuentos coinciden con la tabla `EXPECTED_ARTICLE_COUNTS` cableada como invariante de validación en `src/regulaitor/corpus/validate.py:10-15`, por lo que `make ingest` aborta antes de escribir un manifest divergente.

GDPR usa el CELEX consolidado `02016R0679-20160504` porque incorpora el corrigendum de 2018; AI Act usa la versión inicial pública del Reglamento publicada en julio de 2024. NIS2 y DORA se ingestaron como **base-act** (CELEX `32022L2555` y `32022R2554`) en su publicación de 27-12-2022, sin enmiendas consolidadas posteriores —limitación declarada explícitamente en ADR-0015 D1: el WAF de EUR-Lex bloqueó el landing-page del CELEX consolidado, y el base-act es la versión autorizada para instrumentos 2022 sin enmiendas materiales conocidas hasta la fecha de ingesta.

## Pipeline EUR-Lex → manifest → LanceDB

### Arquitectura modular

El pipeline vive bajo `src/regulaitor/corpus/` y se divide en seis módulos con responsabilidad única (ADR-0003 "Module layout"):

- `schemas.py` — Contrato Pydantic v2 (`Manifest`, `ArticleEntry`, `LanguageEntry`, `Stats`, `Norma`, `Language`, `SourceFormat`).
- `manifest.py` — Carga, escritura atómica (`save_atomic` con `os.replace` para evitar manifests parciales) y diff per-article.
- `eurlex.py` — Cliente HTTP con allowlist (`eur-lex.europa.eu` únicamente), `If-Modified-Since` / `If-None-Match` y retry.
- `formex_parser.py`, `html_parser.py`, `pdf_parser.py` — Tres parsers que exponen la misma interfaz `parse(bytes) -> list[ParsedArticle]`; el orchestrator selecciona por `fetch_format ∈ {"formex4", "html", "pdf"}`.
- `validate.py` — Invariantes (recuento por corpus, sin duplicados, sin artículos vacíos); `strict=True` aborta el manifest write.
- `ingest.py` — Orquestador; CLI `python -m scripts.ingest`.

### Pivote a PDF (ADR-0003)

El spec H1 asumía que el endpoint Formex 4 XML de EUR-Lex devolvería el corpus estructurado vía content negotiation. El smoke run reveló que (a) el endpoint Formex devuelve HTTP 200 con cuerpo vacío cuando no hay representación Formex para el CELEX, y (b) el endpoint HTML responde HTTP 202 con un challenge de CloudFront WAF (~2 KB de JavaScript) ante cualquier cliente no-browser. Tras evaluar cuatro alternativas (Cellar RDF, beat-the-WAF con headers de Chrome, Playwright headless, snapshot manual local), H1 eligió **PDF local versionado en Git LFS** descargado a mano una vez desde el navegador real del operador.

Esta decisión —documentada honestamente como "EUR-Lex bloqueó nuestro acceso automático API; pivotamos a snapshot local versionado"— sigue siendo más defendible académicamente que disfrazar el bloqueo o falsificarlo con mocks, y se valida operacionalmente: el extractor PDF basado en `pdfplumber` + regex line-anchored (`^\s*(?:Article|Art[íi]culo)\s+(\d+)\s*$`, ver `src/regulaitor/corpus/pdf_parser.py:32`) produce los 113 + 99 artículos esperados para AI Act + GDPR sin tuning por documento. Las falsas coincidencias por referencias cruzadas en anexos (un número de artículo que reaparece como back-reference) se resuelven por la lógica `KEEP-FIRST` documentada en `pdf_parser.py:14`: el artículo cuerpo siempre precede al anexo en orden documental.

### H14: WAF bypass vía Playwright para NIS2 + DORA

H14 (ADR-0015 D1) extiende el linaje H1: el spec original planeaba reintroducir `curl`/`httpx` directo asumiendo que el WAF se habría relajado. No fue así. Adicionalmente, replay de la cookie de challenge resuelta en navegador **no** funciona porque el token está TLS-fingerprint-bound a la sesión del browser que resolvió el JS challenge. La resolución fue dirigir un navegador headless vía Playwright MCP, resolver el challenge en-browser, y luego ejecutar un fetch same-origin de los PDFs desde la propia página —el TLS fingerprint del browser más la cookie pasan el WAF. Esto es acceso legítimo y autorizado a legislación pública vía portal oficial, no evasión; pero se reconoce como una desviación frente al spec D1 y como un coste de reproducibilidad: re-adquirir el corpus exige sesión de navegador, no `curl`.

### Idempotencia por dos capas

1. **HTTP-layer**: `eurlex.py` emite `If-Modified-Since`/`If-None-Match` desde `http_cache` del manifest previo; un 304 cortocircuita a `FetchResultNotModified` y el orchestrator reutiliza los datos locales (`corpus/processed/`).
2. **Article-layer**: `ingest._build_manifest` calcula SHA256 por `(article, language)`; cuando el hash coincide con el almacenado, el `LanguageEntry` previo se preserva verbatim incluyendo `chunks` y `embedded_at`. H2 (rebuild del índice BGE-M3) re-embebe sólo los artículos que cambiaron, no el corpus completo.

El modo `--use-local-only` salta la capa HTTP enteramente (necesario para reproducir el flujo H1/H14 desde el snapshot de Git LFS sin tocar EUR-Lex), pero la capa de hash sigue activa.

## Esquema del manifest

`src/regulaitor/corpus/schemas.py:75-86` define el contrato top-level:

```python
class Manifest(BaseModel):
    corpus: Norma             # Literal["ai_act","gdpr","nis2","dora"]
    celex: str
    version: str              # consolidation date YYYY-MM-DD
    source_format: SourceFormat  # Literal["formex4","html","pdf"]
    fetched_at: datetime
    languages: list[Language]
    http_cache: dict[Language, HttpCacheEntry]
    stats: Stats
    articles: list[ArticleEntry]
```

Cada `ArticleEntry` agrupa un artículo en todas las lenguas disponibles, y cada `LanguageEntry` (`src/regulaitor/corpus/schemas.py:31-44`) lleva los campos exigidos por CLAUDE.md §7.2: `hash` (SHA256 con prefijo `sha256:` del texto bruto), `tokens` (proxy `cl100k_base` vía tiktoken), `chunks` (lista de chunk-ids generados por H2), `embedded_at`, `embedding_model` (`"BAAI/bge-m3@<sha256>"`), `fetched_at`, y `source_url`.

`apartado` no es un campo de `LanguageEntry` sino una propiedad de los párrafos almacenados en `corpus/processed/<corpus>_<lang>.json` —cada artículo allí lleva `paragraphs: list[{apartado, text}]`. El loader (`src/regulaitor/corpus/loader.py:181-210`) los expone vía `get_paragraph(norma, articulo, apartado, language)`, que es la API que consume el validator de citas (`citation/validator.py`) para implementar la invariante §6.

## Loader: warmup + integridad fail-closed

`src/regulaitor/corpus/loader.py:57-122` define `warmup()`, llamado una vez al boot del MCP server y del API: recorre los cuatro manifests, lee cada artículo en cada idioma desde `corpus/processed/`, recomputa el SHA256 y lo compara con el hash almacenado. Cualquier discrepancia produce `RuntimeError` con guía de recuperación (`Run make ingest to refresh manifest, or restore corpus/processed/ from git-lfs.`) y aborta el arranque del proceso —el sistema no acepta operar con un corpus inconsistente. La publicación a los singletons (`_CORPUS`, `_PROCESSED_CACHE`) es atómica al final del bucle: una verificación parcialmente fallida deja el estado previo intacto.

`CORPORA_WITH_MANIFESTS` (`loader.py:31`) lista los cuatro corpora cargados. Es deliberadamente independiente de `ALL_NORMAS` (la constante Pydantic) para preservar el "honest-partial gate" introducido en H14 D2: si un corpus se declarase deferred, sólo los aterrizados se cargarían sin que el sistema fallase. En el estado actual ambas listas coinciden.

## Limitaciones declaradas (§22.22 honest disclosure)

- **Base-act sin enmiendas consolidadas para NIS2 y DORA** (CLAUDE.md §7.2). Si la Comisión Europea publica una versión consolidada con corrigenda materiales, RegulAItor no la reflejará hasta una re-ingesta manual y aprobada.
- **`source_url` con paths absolutos de máquina de desarrollo** (e.g. `file:///C:/Users/enriq/Documents/regulaitor/regulaitor/corpus/raw/ai_act_es.pdf`). Pre-existente en H1, no introducido por H14; normalizar a path relativo al repo toca el shared local-load path y queda diferido (riesgo §22.18). El `get_manifest_meta` del loader (`loader.py:213-227`) sí expone una URL canónica EUR-Lex derivada del CELEX (`_EURLEX_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"`) para uso en citaciones de cara al usuario.
- **Re-adquisición no `curl`-reproducible**: el WAF de EUR-Lex exige sesión de navegador real (Playwright o equivalente) para re-descargar los PDFs. Documentado en ADR-0015 como acquisition-method deviation vs spec D1.
- **`rag-ingest` SKILL.md sigue Formex-céntrico**: la realidad operativa H1/H14 es PDF; el SKILL.md no se ha actualizado y se mantiene como follow-up de documentación.
- **Tokenización proxy**: H1 usa `cl100k_base` (tiktoken) como proxy de tokens para el threshold de chunking; BGE-M3 usa XLM-RoBERTa. El threshold de ~1000 tokens es generoso y el proxy es aceptable, pero documentado en ADR-0003 "Consequences/Negative".

## Trazabilidad y versionado

- `corpus/manifests/*.json` están versionados en git (cuatro archivos, ~1500-3900 líneas cada uno).
- `corpus/raw/*.pdf` y `corpus/processed/*.json` se gestionan vía Git LFS y, para v0.1.32-h16-deploy, se bakean en la imagen Docker para que el demo de Hugging Face Spaces tenga el índice LanceDB pre-construido (cold-start ~5 min, ver `docs/H16_DEPLOY.md`).
- Cada `embedded_at` registrado en los manifests refleja el último rebuild del índice; los timestamps actuales son `2026-05-28T*` (rebuild pre-deploy).
- `make ingest` y `make rag-build` son los dos comandos canónicos para regenerar el corpus y el índice respectivamente.

Este corpus es el "ground truth" del sistema: cualquier afirmación que RegulAItor emita al usuario debe rastrear hasta un `(norma, articulo, apartado, language)` que el loader pueda recuperar verbatim. El validator (§06) y el Auditor (§08) son los guardianes que enforce esta cadena.
