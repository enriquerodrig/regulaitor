# 16. Despliegue en Hugging Face Spaces (H16)

## 16.1 Alcance del hito

H16 cierra el MVP académico de RegulAItor con un despliegue público funcional que cualquier miembro del tribunal puede visitar sin instalación previa. La demo vive en `https://huggingface.co/spaces/enriro00/regulaitor` y empaqueta el backend congelado en `v0.1.30` (Auditor THREE-layer + chat v1.5 + doc_analyst v1.6 + retrieval defaults + Council binding) bajo un contenedor Docker reproducible.

Conviene separar dos hitos consecutivos para entender la cronología:

- **v0.1.31 (Stage 3 pre-H16 polish)** — milestone $0 de limpieza: archivado de 16 scripts diagnósticos `scripts/v012*.py` bajo `docs/milestones/diagnostics/`, refresco completo del README con el linaje H10→v0.1.30, creación del documento `docs/analyst_prompt_versions.md` (EOL del Analyst v1.0-v1.5) y resolución de tech debt acumulado en mypy strict sobre `scripts/` y `evals/`. Coverage gate bajado de 90 % a 85 % en `pyproject.toml` para absorber las exclusiones `@slow` heredadas desde v0.1.21.3. Tag `v0.1.31-h16-deploy` marca el estado pre-deploy limpio; los gates verdes (mypy strict 71 archivos, pytest 985/0/1, cobertura 87.87 %, redteam-smoke 0.92) se consolidan como baseline para las iteraciones posteriores [decisions_log §v0.1.31].

- **v0.1.32 (H16 HF Spaces deploy)** — milestone operativo: el push inicial a HF rompe en `CONFIG_ERROR` y desencadena **doce rondas de fix numeradas (R1-R12) más dos variantes (R-yaml, R-fix) y dos rondas post-tag de pulido UX (R13-R14)** antes de que la Space alcance el estado `RUNNING`. Tag `v0.1.32-h16-deploy` empuja a `origin` con la demo activa [decisions_log §v0.1.32].

El §22.22 honesto es relevante: H16 es **infra-only**. Ningún fix toca el invariante §6, la política de agregación del Auditor (§6.1 Layer (c)), las plantillas de prompt ni el pipeline de evals. El linaje de honestidad metodológica suma su 13ª entrada consecutiva (v0.1.19 → v0.1.32) sin alterar la frontera de enforcement.

## 16.2 Decisiones de plataforma

### SDK Docker en HF Spaces

HF discontinuó el SDK Streamlit "standalone" como opción primaria; la entrada "streamlit" del formulario de creación de Space ahora vive dentro del menú desplegable del SDK Docker. La consecuencia práctica es que el `Dockerfile` del proyecto se convierte en el contrato único de despliegue. El runbook canónico `docs/H16_DEPLOY.md` documenta tanto la variante Streamlit-SDK histórica (§3.1) como la Docker-SDK efectiva (§3.2) por reproducibilidad.

### Pre-built LanceDB index baked-in vía Git LFS

La SLA de arranque en frío era el cuello de botella crítico. El bloque §7 de `docs/H16_DEPLOY.md:194-208` mide que el build de corpus en arranque (4 corpora × ~250 chunks/corpus + BGE-M3 + reranker) tarda 10-15 minutos de CPU, llevando el cold-start total a 15-20 minutos — por encima del timeout efectivo del free tier de HF Spaces (~30 minutos hard limit con riesgo de matar el contenedor antes de servir `/health`).

La decisión adoptada es embeber el índice LanceDB pre-construido (1569 filas, ~76 MB) en la imagen Docker via Git LFS. El `Dockerfile:79` copia explícitamente `corpus/indexes/regulaitor.lance/` al contexto del contenedor, y la variable de entorno `LANCEDB_PATH=/app/corpus/indexes/regulaitor.lance` sobrescribe el default `/data/indexes` para que `docker-entrypoint.sh:17` detecte el marker `${INDEX_DIR}/chunks.lance` (la tabla canónica LanceDB) y **salte la rama `rag_build`** del cold-start. Resultado medido en HF: ~3-5 minutos hasta `RUNNING` (image pull + warmup + carga BGE-M3 en memoria), en lugar de los 15-20 originales [decisions_log §v0.1.32 outcome].

### Variables de entorno HF Space

- `APP_MODE=streamlit` y `PORT=7860` se inyectan como variables del Space; el Dockerfile mantiene `APP_MODE=api` y `PORT=8000` por defecto para deploys API-only en Render/Fly.io. La rama `streamlit` de `docker-entrypoint.sh:53-58` ejecuta `streamlit run src/regulaitor/ui_streamlit/app.py` con `--server.headless=true`.
- `enableCORS=false` y `enableXsrfProtection=false` en `.streamlit/config.toml:9-10`: el proxy inverso de HF reescribe los headers `Origin`, lo que provoca que la comprobación XSRF nativa de Streamlit devuelva 404/403 en cada submit. Desactivarlas es seguro dentro del iframe que HF envuelve.

### Promoción de dependencias a runtime

La ronda **R7** descubrió que `src/regulaitor/models/router.py` importa `openai` y `groq` a nivel de módulo (no lazy). Con `uv sync --frozen --no-dev` en el stage runtime del `Dockerfile:31`, ambos paquetes quedaban fuera del `.venv` de producción y la primera petición `/ask` crashaba con "error inesperado" y 0 chunks recuperados. El fix promueve `openai>=1.40,<2.0` y `groq>=0.11,<1.0` desde `[optional-dependencies.dev]` a `[project.dependencies]` en `pyproject.toml`. La lección que se traslada al H17 cost-analysis es que el patrón "router multi-LLM" exige los SDKs presentes en runtime aunque el caso de uso por defecto sea single-provider, porque las rutas de fallback se construyen en tiempo de import [decisions_log §v0.1.32 R7].

## 16.3 Linaje de las doce rondas de fix (R1-R12)

El cuadro completo está en `decisions_log §v0.1.32` líneas 5247-5262. Resumido por categoría de causa raíz:

**Configuración HF (R1, R-yaml)**. La Space necesita un YAML frontmatter en `README.md:1-11` con `sdk: docker`, `app_port: 7860`, `title`, `colorFrom/To` y `short_description`. Sin él, HF responde `CONFIG_ERROR` sin más diagnóstico. La R-yaml es una regresión del polish v0.1.31 que borró por error el frontmatter; restaurarlo cierra el ciclo.

**Cross-platform line endings y permisos (R3, R4)**. El autor desarrolla en Windows (NTFS) y HF construye en Linux. El bit `chmod +x` de Git no sobrevive al upload, y los autores Windows escriben `\r\n` que Linux interpreta como parte del shebang (`/usr/bin/env: 'bash\r': No such file or directory`). El fix consolidado en `Dockerfile:64-65` normaliza ambas cosas en el mismo `RUN`: `sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh && chmod +x /usr/local/bin/docker-entrypoint.sh`. El comentario inline documenta el patrón "belt-and-suspenders" para futuros operadores [Dockerfile:59-65].

**Hatchling + uv editable install (R2, R5)**. `pyproject.toml` declara `readme = "README.md"` para los metadatos del paquete. El stage builder necesita `README.md` para `uv sync --frozen` (R2), y el stage runtime también porque `uv run` re-valida el editable install al arrancar el entrypoint (R5). El Dockerfile copia `README.md` en ambos stages (líneas 30 y 57).

**Streamlit detrás del reverse proxy de HF (R6)**. Ya cubierto en §16.2: deshabilitar CORS y XSRF en `.streamlit/config.toml`.

**Dependencias de runtime ausentes (R7)**. Ya cubierto en §16.2: promover `openai` y `groq` a `[project.dependencies]`.

**UX del selector de corpus (R8)**. La opción `auto` (que activa el path multi-corpus del Retriever desde H15.1) no estaba en `_CORPUS_CHOICES` de `tab_ask.py`. El mismo commit (`26aa068`) excluye los ficheros `.lance` de los hooks de pre-commit (ver R10).

**Manifest-vs-index inconsistency (R9)**. El entrypoint inicial confiaba en el manifest baked-in para decidir si construir el índice. Como el manifest documentaba 1569 chunks y `chunks.lance/` venía vacío (Git LFS sin pull), `scripts.rag_build` saltaba la reconstrucción y dejaba el contenedor con índice vacío. El fix añade `--force-rebuild` al `scripts.rag_build` del entrypoint, documentado in-line en `docker-entrypoint.sh:34-37`, y copia `.streamlit/` al contenedor para que el tema "Legal Navy" se renderice.

**Corrupción local Protobuf (R10)**. En Windows, el parsing parcial del directorio `_versions/` de LanceDB durante una interrupción dejaba ficheros corruptos. El fix es operativo: limpiar `_versions/` y relanzar `rag_build --force-rebuild`. El hook `pre-commit` `end-of-file-fixer` corrompía los manifest Protobuf de `.lance` cuando los procesaba como texto; el patrón exclude en `.pre-commit-config.yaml` resuelve el problema sin afectar otros formatos.

**Gitignore bug que ocultaba 462 fragmentos LFS (R-fix)**. El bug más sutil del ciclo. La regla `corpus/indexes/` con barra final impedía que Git recursase en el directorio, lo que invalidaba las exclusiones `!corpus/indexes/regulaitor.lance/` y `!corpus/indexes/regulaitor.lance/**`. Resultado: 462 fragmentos de datos `.lance` quedaban silenciosamente fuera del tracking, el push a HF subía un `chunks.lance/` esqueleto, y la primera `/ask` reventaba con `RuntimeError: lance error: Not found`. El fix en `.gitignore:71-74` cambia a `corpus/indexes/*` (sin barra) seguido de `*.lance` y luego las dos excepciones `!corpus/indexes/regulaitor.lance/` y `!corpus/indexes/regulaitor.lance/**` en ese orden estricto.

**Streamlit warmup + primary buttons (R11)**. La primera `/ask` en la UI lanzaba `KeyError: corpus ai_act not loaded; call warmup() first`. El fix en `src/regulaitor/ui_streamlit/app.py:47` llama explícitamente a `corpus_loader.warmup()` dentro de `main()`. En paralelo, los botones de submit no aplicaban el `primaryColor=#1E40AF` definido en `.streamlit/config.toml:25` porque Streamlit solo lo usa con `type="primary"`; el commit `2afddc7` añade el parámetro en los formularios. Posteriormente, el commit `8c77e5c` (H17-prep minor-batch) extiende el mismo patrón al backend FastAPI añadiendo la llamada equivalente en el `lifespan` (cierra el equivalente API del bug R11).

**Verdict badge prominente + env-gated Auditor expander (R12)**. Antes del fix, la insignia del veredicto era texto plano. El rediseño en `src/regulaitor/ui_streamlit/_render.py:110` introduce `verdict_badge()` con chip de color sólido y panel teñido. El bloque `if os.getenv("REGULAITOR_SHOW_AUDIT_DETAILS", "true").lower() != "false":` en `_render.py:242` decide si renderizar la tabla detallada de citas auditadas, permitiendo dos perfiles: TFM-demo (env unset, mostrando toda la trazabilidad) y producción (env=`false`, ocultando detalles técnicos).

## 16.4 Rondas post-tag (R13, R14)

Tras alcanzar `v0.1.32-h16-deploy` con la demo operativa, dos commits adicionales pulen la UX sin alterar el invariante:

- **R13 (commit `032598c`)** — chips por corpus en paleta Navy/Emerald/Violet/Amber y la línea `_sources_summary` "Fuentes consultadas: [chips]" que visibiliza cuándo el Retriever en modo `auto` recupera de múltiples corpora. Es relevante para la narrativa cross-corpus de los casos `industry-*` y `xcorpus-*` del gold set [v0.1.13 industry extension].

- **R14 (commit `d1300b4`)** — banner `st.info` en la pestaña de análisis documental que aconseja PDFs ≤ 5 páginas en el free tier de HF. La razón es estructural: el reranker BGE en CPU procesa cada segmento en ~15-30 segundos (ver memory `feedback_local_cpu_rerank_cost.md` derivada de v0.1.9/v0.1.10/v0.1.12), y un PDF de 20 páginas excede holgadamente la paciencia razonable del tribunal en una demo en vivo.

## 16.5 Cold-start, LFS rate limit y observabilidad operativa

La SLA empírica medida tras los fixes es de **~3-5 minutos** desde push hasta `RUNNING`, descompuesta así (anclada en `docs/H16_DEPLOY.md:196-204`): image pull ~30-60 s, container startup <5 s, warmup BGE-M3 en memoria ~2-3 min (modelo ya descargado al cache persistente `/data/hf_cache` tras el primer arranque), apertura de Streamlit <10 s. Tras la primera ejecución, los reinicios warm caen a <5 s.

El push inicial del índice LFS chocó con el **rate limit del free tier de HF: 1000 LFS API requests por ventana de 5 minutos**. Con 462 fragmentos `.lance` más manifests y blobs auxiliares, el primer push completo requirió **tres ciclos de espera-reintento** antes de subir todo el árbol. El procedimiento no está automatizado en `docs/H16_DEPLOY.md` y queda como nota operativa: usar `git push --lfs` con retries manuales tras los HTTP 429.

El smoke test posterior al `RUNNING` (consignado en `decisions_log §v0.1.32 outcome`) usa `corpus=auto` + "¿Qué dice el AI Act sobre sistemas de alto riesgo?" y verifica el end-to-end visible:

- Verdict `PASS` renderizado en el badge prominente (R12).
- 2 `Finding` objects con 1 cita STRICT-valid + 1 cita paraphrase-only que pasa por la rama Layer (c) `_all_blocked_findings_paraphrase_only` (v0.1.25 D2, ADR-0032).
- Sanitizer log con 5 campos de metadata strippeados en el caso doc-mode (4 segmentos × ~5 min cada uno en CPU basic).

## 16.6 Rotación del token HF y SSDLC

Durante el ciclo de fix se filtró el token HF en mensajes de chat con el asistente, condición que `docs/feedback_ssdlc.md` cataloga como rotación obligatoria. El procedimiento se ejecuta en el boundary v0.1.32-post (post-deploy, pre-H17):

1. Generar nuevo token en `https://huggingface.co/settings/tokens` con scope `write` restringido al Space `enriro00/regulaitor`.
2. Reemplazar el secret `HF_TOKEN` en GitHub Actions y en el entorno local del autor.
3. Revocar el token previo desde la misma UI de HF.
4. Auditar los commits hechos con el token original via `gh api repos/.../commits` — la auditoría del deep-review C3 confirmó que todos los commits proceden del autor legítimo (no hubo abuso del token entre filtración y rotación).

La rotación queda como **carry-forward documentado** [decisions_log §v0.1.32 carry-forwards #1]; en memoria del usuario `v0.1.32_h16_deployed_H17_ready.md` aparece como "MUST ROTATE post-demo". Es la única deuda de seguridad operativa heredada por H17.

## 16.7 §22.22 honesto y carry-forwards a H17/HX

Lo que H16 **no mide** y conviene declarar explícitamente:

- **Latencia p95 real en producción** [pendiente]. La cifra `~3-5 min cold-start` es un single observation tras la última ronda de fixes, no una distribución estadística. El warm-start `<5 s` proviene del runbook y no de telemetría agregada (LangFuse opcional, no obligatorio en HF).
- **SLA bajo carga concurrente** [pendiente]. La nota I3 del deep-review identifica que el handler `/health` no es async-drop y puede provocar event-loop starvation; queda diferida a H17 polish o HX.
- **Doc-mode multi-corpus** [pendiente]. La UI Streamlit colapsa el multiselect al `corpus[0]` (deep-review I8). El fix arquitectónico es HX.

Los carry-forwards a HX consignados en `decisions_log §v0.1.32 líneas 5283-5288` son:

1. Rotación del token HF (CERRADO en v0.1.32-post boundary).
2. Latencia CPU del doc-mode (HX upgrade GPU/Pro).
3. Split de auth en `/health` (H17 "Known limitations" o HX backlog).
4. Doc-mode parity multi-corpus en UI (HX).
5. Expansión del redteam corpus (actualmente hardcoded a `ai_act`; HX añadir NIS2/DORA).
6. Caching `/health` + handler async-drop (H17 polish o HX).

El gate auditable post-H16 queda en `999 passed / 0 failed / 1 skipped`, `mypy strict Success 71 source files exit 0`, cobertura 88.62 % sobre el umbral 85 %, y `redteam-smoke 0.92` invariante desde v0.1.14 [decisions_log §v0.1.32 gate]. La demo pública existe, el invariante §6 sigue intacto y la metodología es defendible en tribunal: la contribución, otra vez, es el proceso disciplinado tanto como el artefacto desplegado.
