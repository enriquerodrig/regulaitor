# RegulAItor Operational Runbook

Audiencia: desarrollador o operador que ejecuta RegulAItor en local, en CI o en
despliegue público. Versión consolidada post-H16 (v0.1.32 deploy a Hugging Face
Spaces vivo en https://huggingface.co/spaces/enriro00/regulaitor) que absorbe el
runbook H11 LangFuse original y los aprendizajes de las 12+ rondas de iteración
del deploy (R1-R12 + R13-R14 polish). Para el procedimiento de despliegue
detallado por plataforma seguir vigente `docs/H16_DEPLOY.md`; este documento
añade lo no cubierto allí (rotación de tokens, debug de cold-start por etapa,
backup/restore, post-mortems, gate de cobertura).

---

## 1. Setup local de desarrollo

### 1.1 Prerrequisitos

- Python 3.11 (no 3.12+; FlagEmbedding + lance binding pinned a 3.11).
- `uv` >= 0.4.18 (`pip install uv==0.4.18` o `winget install astral-sh.uv`).
- Git con LFS (`git lfs install`; el índice LanceDB `corpus/indexes/regulaitor.lance/`
  pesa ~76 MB y vive en LFS desde v0.1.32).
- Windows users: ver §1.4 (sin `make` nativo + bug Protobuf lance + SSL CRL).
- Disco: ~4 GB libres (BGE-M3 ~2 GB + reranker ~600 MB + lance + venv).

### 1.2 Bootstrap reproducible (gate §16.2 #1)

```bash
git clone https://github.com/enriro00/regulaitor
cd regulaitor
git lfs pull                  # baja chunks.lance + manifests binarios
make setup                    # uv sync --extra dev + pre-commit install
```

`.env` se crea a mano (regla dura: NO existe `.env.example` per
`feedback_no_env_example.md`; el usuario lo flageó en H6 y H8). Variables
mínimas para desarrollo local:

```bash
ANTHROPIC_API_KEY=sk-ant-...
REGULAITOR_API_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
# Opcional según superficie a probar:
# OPENAI_API_KEY=...                              # router fallback (H12)
# GROQ_API_KEY=...                                # Llama-3.3-70b judge (H13)
# LANGFUSE_PUBLIC_KEY=...                         # observabilidad (H11)
# LANGFUSE_SECRET_KEY=...
# LANGFUSE_HOST=https://cloud.langfuse.com
# REGULAITOR_API_CORS_ORIGINS=https://app.example
# LANCEDB_PATH=./corpus/indexes/regulaitor.lance  # ver §3 post-mortem
```

### 1.3 Ingesta corpus + build RAG (solo si LFS no trajo el índice)

Si `git lfs pull` resolvió correctamente, `corpus/indexes/regulaitor.lance/chunks.lance/`
ya existe (1569 chunks: ai_act 687 + gdpr 324 + nis2 244 + dora 314) y puedes
saltar este paso. Si no:

```bash
make ingest      # parsea PDFs corpus/raw/*.pdf -> corpus/processed/*.json
make rag-build   # chunk + embed BGE-M3 + warmup reranker + upsert LanceDB
```

Tiempo: ~10-15 min CPU (descarga BGE-M3 ~2 GB + reranker ~600 MB en primera
ejecución; cached a `~/.cache/huggingface/` luego). Idempotente: ejecutar dos
veces no duplica chunks (`scripts.rag_build` lee manifests + omite por hash).

### 1.4 Quirks Windows

- `make` no viene con Git for Windows. Opciones: `scoop install make` /
  `choco install make` / ejecutar `uv run ...` directamente (cada target del
  Makefile es una línea).
- Pre-commit hook `gitleaks` falla en Windows (Go toolchain ausente). Patrón
  de commit aprobado: `$env:SKIP = "gitleaks"; git commit -m "msg"`. CI Linux
  ejecuta gitleaks v8.21.2 como gate vinculante (`.github/workflows/ci.yml:188-192`).
  **Nunca usar `--no-verify`** (regla dura `feedback_resume_verify_state.md` +
  precedente CLAUDE.md §22).
- SSL Windows + CryptoAPI CRL: `truststore.inject_into_ssl()` necesario para
  Anthropic + HuggingFace (CRYPT_E_NO_REVOCATION_CHECK 0x80092012). Promovido
  a dependencia `main` en v0.1.26 (`pyproject.toml`). Si reaparece en scripts
  ad-hoc, importar `truststore` antes que `anthropic` / `huggingface_hub`. Ver
  ADR-0029 §22.22 #2 para el post-mortem completo.
- Lance Protobuf rebuild bug: ver §7.

### 1.5 Comandos canónicos (gate §16.2 #1)

```bash
make lint              # ruff + black --check + mypy
make test              # pytest (gate cov 85%; 999 passed / 0 failed / 1 skipped)
make eval              # ~$2.50 Anthropic; popula cache judge
make redteam-smoke     # $0 ~30s; gate §16.2 #4 block_rate >= 0.90
make serve             # Streamlit http://localhost:8501
make serve-api         # FastAPI http://localhost:8000 (requiere REGULAITOR_API_TOKEN)
```

---

## 2. Despliegue a HF Spaces — lecciones de R1-R14

Procedimiento base en `docs/H16_DEPLOY.md` §3. Esta sección añade los gotchas
descubiertos durante las 12+ rondas de iteración del v0.1.32 deploy
(2026-05-27 a 2026-05-28). Cada item es un fallo real reproducido + el fix
canónico que evita repetirlo.

### 2.1 Cross-platform Windows → Linux container

- **R-fix CRLF → LF en `docker-entrypoint.sh`**: Windows escribe `#!/usr/bin/env bash\r`;
  Linux ejecuta `bash\r` como binario inexistente → "No such file or directory".
  Solución en `Dockerfile:64`: `sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh`
  ANTES del `chmod +x`. Belt-and-suspenders.
- **R-fix `chmod +x` explícito**: git mode bits no sobreviven uploads cross-plat
  (Windows NTFS → HF Spaces). El `RUN chmod +x` en el Dockerfile es obligatorio
  aunque el git diff muestre el bit. Línea `Dockerfile:65`.
- **R-fix README.md en runtime stage**: hatchling re-valida el editable install
  al startup → necesita `README.md` en CWD o falla. Copiar también en stage 2
  (`Dockerfile:57`), no solo en builder.

### 2.2 YAML frontmatter + Hugging Face SDK detection

- **R-fix frontmatter en README.md** raíz: HF Spaces requiere YAML frontmatter
  `title:`, `emoji:`, `sdk: docker`, `app_port: 7860`. Sin él, la Space queda
  en estado CONFIG_ERROR sin logs útiles. README.md ya está extendido con este
  bloque desde v0.1.32.
- **R-fix `.streamlit/config.toml` COPY**: sin él, Streamlit cae a tema default
  + falla detrás del reverse proxy de HF por enableCORS/enableXsrfProtection.
  Valores deploy: `enableCORS = false`, `enableXsrfProtection = false`. Línea
  `Dockerfile:70`.

### 2.3 LFS, gitignore y baked-in index

- **R-fix bug recursivo `.gitignore`**: el patrón previo `corpus/indexes/*`
  ignoraba silenciosamente los fragmentos de datos lance que no estaban
  trackeados explícitamente. Resultado: rebuild bajaba sólo el manifest
  Protobuf, LanceDB encontraba el directorio + manifest pero 0 filas → BLOCK
  con `cited_articles=[]`. Fix: cambiar `.gitignore` a `corpus/indexes/*` con
  excepción explícita para `!corpus/indexes/regulaitor.lance/` +
  `!corpus/indexes/regulaitor.lance/**` (ver `.gitignore:71-74`); verificar
  con `git lfs ls-files | grep "\.lance" | wc -l` antes del push (baseline
  actual ~4510 archivos LFS lance trackeados; [carry-forward HX:
  cifra exacta puede variar tras rebuilds]).
- **R-fix LFS rate limit 1000 req / 5 min**: durante el primer push pleno
  HF responde 429 cuando la cola supera el límite. Patrón bash de retry:

  ```bash
  until git push -f hf main; do
    echo "LFS rate limit; sleeping 300s..."
    sleep 300
  done
  ```

- **R-fix `--force-rebuild` en entrypoint**: si el operador hace cold-start
  con `LANCEDB_PATH=/data/indexes` (no la baked-in path), los manifests baked-in
  declaran chunks ya construidos → `scripts.rag_build` omite por defecto → el
  índice persistente queda vacío. Fix: pasar `--force-rebuild` siempre en el
  entrypoint (`docker-entrypoint.sh:38`).
- **R-fix dependencias `groq` + `openai` en `[project.dependencies]`**: antes
  estaban bajo `[optional-dependencies.dev]` (heredado de pre-H12 cuando el
  router era stub). El `uv sync --no-dev` del builder las omitía → `import openai`
  en `models/router.py` fallaba al primer request. Movidas a main + import
  top-level en `router.py` para forzar clasificación.

### 2.4 Warmup + UX polish

- **R-fix `corpus_loader.warmup()` en `app.py main()`**: sin ello, el primer
  request tiraba `KeyError("ai_act")` porque el corpus loader lazy-init no se
  había disparado todavía (el primer hit a `/ask` ocurría antes que el reranker
  estuviera cargado en RAM). Línea `src/regulaitor/ui_streamlit/app.py` en
  el lifespan/main.
- **R13/R14 UX polish**: corpus chips visibles, cross-corpus indicator, doc-mode
  advisory de latencia CPU (BGE-M3 reranker en cpu-basic ~15-30s/segmento;
  documento 80 segmentos ~1h). Recomendación a usuarios públicos: PDFs ≤ 5
  páginas. Fix real está en HX (GPU upgrade o reranker destilado).

---

## 3. Debug de cold-start por etapa

Cuando la Space queda en estado de error o `/health` no responde, la
clasificación por etapa permite ir directo al log relevante:

| Síntoma observable | Etapa | Log a inspeccionar | Causa típica |
|---|---|---|---|
| Space en `CONFIG_ERROR`, sin build iniciado | Configuración | HF Space Settings | YAML frontmatter ausente o `sdk:` incorrecto en README.md (§2.2) |
| Build falla durante `RUN uv sync` | Builder Docker | `Build logs` tab en HF | Network falla bajando wheels; `truststore` ausente; CRLF en entrypoint |
| Build OK pero contenedor reinicia loop | Entrypoint | `Run logs` tab | `chmod +x` faltante; CRLF; APP_MODE inválido (no `api`/`streamlit`) |
| `/health` 503 + log `Not found: /data/indexes/chunks.lance` | LanceDB cold-start | `Run logs` `[entrypoint] FATAL` | gitignore recursivo (§2.3) o `LANCEDB_PATH` apuntando a directorio padre vacío |
| `/ask` tira `KeyError corpus not loaded` | Warmup | `Run logs` traceback | `corpus_loader.warmup()` ausente del lifespan (§2.4) |
| Findings con `articulo="<UNKNOWN>"` + BLOCK 100% | Analyst prompt | trace Anthropic | v1.0 doc_analyst en lugar de v1.6 → ver ADR-0033; verificar `REGULAITOR_ANALYST_PROMPT_VERSION` no fuerza v1.0 |

### 3.1 Post-mortem `LANCEDB_PATH` apuntando a directorio padre

Descubierto en v0.1.29 T5 probe 1 (€0.14 sunk antes del fix). v0.1.26
deploy-prep añadió env-reading a `rag/store.py`; un `.env` con
`LANCEDB_PATH=./corpus/indexes` (sin el sufijo `regulaitor.lance`) provocaba
que LanceDB creara una tabla nueva vacía `chunks.lance/` dentro del directorio
padre → 0 filas retrieved → Sonnet refusal → citas `UNKNOWN` por contrato del
prompt v1.0. Fix: el valor correcto incluye el sufijo
`./corpus/indexes/regulaitor.lance` Y borrar la tabla espuria que se creó
en el run fallido. Documentado en CLAUDE.md §27 entrada v0.1.29 + Stage 1
cleanup commit que incluyó esta entrada del runbook.

---

## 4. Rotación del token HF (security hygiene)

Pendiente activo: el token `hf_***REVOKED-2026-05-29***` fue leaked
en chat durante el deploy de v0.1.32. El usuario aplazó la rotación al post-demo
(memory `v0.1.32_h16_deployed_H17_ready.md`).

Procedimiento canónico:

```bash
# 1. Revocar token comprometido vía UI: https://huggingface.co/settings/tokens
#    Click 'Revoke' en el token actual. Auditar accesos antes de revocar:
#    https://huggingface.co/settings/access-logs
# 2. Crear nuevo token con scope write limitado al Space:
#    Create new token -> Type: write -> Permissions: scope al repo enriro00/regulaitor
# 3. Actualizar remote local:
git remote set-url hf https://enriro00:hf_NEW_TOKEN@huggingface.co/spaces/enriro00/regulaitor
# 4. Verificar:
git push hf main --dry-run
# 5. Auditar commits del Space para confirmar que ningún tercero pusheó con el
#    token comprometido en ventana de exposición:
#    GET https://huggingface.co/api/spaces/enriro00/regulaitor/commits
# 6. Si hay commits sospechosos, revertir + repushear desde main GitHub limpio.
# 7. Borrar la entrada leaked en el chat history si la plataforma lo permite.
```

---

## 5. Backup + restore corpus

El corpus de RegulAItor tiene tres capas con políticas distintas:

| Capa | Path | Backup | Restore |
|---|---|---|---|
| Manifests JSON | `corpus/manifests/*.json` | git-tracked | `git checkout` |
| Processed JSON | `corpus/processed/*.json` | git-tracked | `git checkout` |
| Índice LanceDB | `corpus/indexes/regulaitor.lance/chunks.lance/` | git LFS | `git lfs pull` |

Si el LFS se corrompe (ej. push interrumpido), restore desde origen autoritativo:

```bash
# Opción A: re-clonar desde origen GitHub
rm -rf corpus/indexes/regulaitor.lance/
git lfs pull --include="corpus/indexes/**"

# Opción B: regenerar desde processed/ (~10-15 min CPU)
make rag-build  # rehace embeddings + repuebla chunks.lance/

# Opción C (worst case): re-ingest desde corpus/raw/*.pdf
make ingest && make rag-build
```

Verificación post-restore (gate de integridad):

```bash
uv run python -c "
import lancedb
db = lancedb.connect('corpus/indexes/regulaitor.lance')
print('rows:', db.open_table('chunks').count_rows())
"
# Expected: 1569
```

---

## 6. Render / Fly.io como alternativas a HF

Si la Space supera el free tier de HF (Pro €9/mo + GPU t4-medium ~€0.40/h):

- **Render**: ver `docs/H16_DEPLOY.md` §4 (Dockerfile + render.yaml ya provistos;
  disk 10 GB en /data; sleep tras 15 min idle; wake ~30s).
- **Fly.io**: ver `docs/H16_DEPLOY.md` §5 (fly.toml + volume; `fly secrets set`;
  región `mad` para latencia EU).

Ambos consumen el mismo Dockerfile multi-stage; cambia sólo el manifest IaC +
secrets manager + healthcheck path (`/health` en ambos).

---

## 7. Post-mortem Windows lance Protobuf rebuild

Reproducido localmente durante v0.1.30 corpus rebuild. Síntoma: tras
`rm -rf` parcial del índice lance (estado `_versions/` huérfano), un
`scripts.rag_build` reusa lectura de `_transactions/` + reescribe `_versions/`
con offsets inconsistentes → `DataFusionError: Internal error: ProtobufError`.

Workaround:

```bash
# Borrar índice completo (no parcial)
rm -rf corpus/indexes/regulaitor.lance/
mkdir -p corpus/indexes/regulaitor.lance/
make rag-build  # rebuild limpio
```

Si reproduce: ejecutar el rebuild dentro de WSL2 (lance Python binding ARM/x86
en native Linux es estable; Windows binding 0.10.x tiene este edge case
conocido). No documentado upstream todavía; pendiente report al repo lance.

---

## 8. Gate de cobertura 85% — racional y camino a 90%

`.github/workflows/ci.yml:70` aplica `--cov-fail-under=85`. La medición
autoritativa actual es 88.62% (gate baseline desde v0.1.29). La elección de
85% (vs los 90% históricos pre-v0.1.21.3) es trade-off operativo documentado:

- Path offline-SSL en `models/router.py` no cubre ramas Anthropic/OpenAI bajo
  CRYPT_E CRL block sin truststore inyectado. Tests del path completo
  necesitan red real → marcados `@pytest.mark.slow` y excluidos del gate
  `-m "not slow"`. Resultado: cobertura aggregate ~88.5-88.6%.
- Camino a 90%: (a) añadir suite offline-SSL en `tests/integration/` (path
  propuesto, archivo aún no creado) con `truststore` y fakes anthropic/openai/groq
  que ejerciten las ramas no cubiertas; (b) o relajar gate a 85% como trade-off
  perpetuo (decisión actual).

Carry-forward a HX post-TFM cuando la prioridad esté en endurecer el gate.
No bloquea H16 ni H17.

---

## 9. Procedimientos operacionales heredados (H11)

Las tres condiciones de alerta más comunes — drop `block_rate < 0.90`,
subida latencia p95, spikes de coste — quedan documentadas con el detalle
canónico H11 en commit `8378015`. Esos procedimientos siguen vigentes; el
único cambio post-H11 es que LangFuse ahora se enchufa también al Space
público (las trazas aparecen automáticamente cuando los tres `LANGFUSE_*`
secrets están seteados en HF Settings → Variables and secrets). Para la
interpretación de latencia (per-query vs batch eval p95 = 572s artifact) y
el contrato no-op de LangFuse sin las env vars, consultar también
`docs/H16_DEPLOY.md` §8 + ADR-0012 H11.

---

**Fin del runbook RegulAItor (post-v0.1.32 H16 deploy).**
