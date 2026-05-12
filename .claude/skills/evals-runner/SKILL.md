---
name: evals-runner
description: Use this skill when running the H8 evaluation harness, reading `evals/reports/latest.md`, deciding whether to re-run, or extending the gold set. Activates from H8 onwards.
version: 1.0
---

# evals-runner

Procedimiento canónico para correr la evaluación de RegulAItor de forma reproducible y para leer el report sin malinterpretarlo.

## Cuándo invocarme

- Antes de correr `make eval` (validar que el budget Anthropic está disponible y que la gold set está estable).
- Después de modificar prompts del Analyst/Auditor, retriever config, o el sanitizer — para confirmar que las métricas no han regresado.
- Cuando el examinador pide "muéstrame los resultados" — el report committed en `main` es la respuesta canónica.
- Cuando se piensa extender el gold set (H10+ tendrá ≥60 casos con 40% modo documento).

## Procedimiento estándar

### 1. Verificar budget

```bash
test -n "$ANTHROPIC_API_KEY" && echo "OK" || echo "MISSING"
```
Una full run cuesta ~$3-5 (Sonnet 4.6 producción + Haiku 4.5 judge + Ragas internal). Verificar saldo en https://console.anthropic.com/billing antes de arrancar.

### 2. Run estratégico por tipo de cambio

| Cambio | Comando | Coste |
|---|---|---|
| Doc-only / report formatting | `make eval-from-cache` | €0 (cache hit en judge layer) |
| Harness logic, métricas, criterios | `make eval-subset` (~$0.30) → si OK, `make eval` (~$3-5) | total ~$3-5 |
| Prompts del Analyst / Auditor, retriever config, sanitizer | `make eval` directo (todas las llamadas a Sonnet/Ragas serán cache miss) | ~$3-5 |
| Gold set extension (añadir cases) | `make eval-subset` con `--subset` que cubra solo los nuevos | proporcional |

**Caveat crítico**: `make eval-from-cache` SOLO regenera el report a partir de los judge responses cacheados. Las llamadas H4 (chat graph) y H5 (document pipeline) producen sus propias llamadas Anthropic directas que NO pasan por `evals.cache.cache_call` y por tanto NO están cacheadas. En la práctica, `eval-from-cache` produce un report degradado (los chat/doc costs reportados son 0; solo el judge layer está cubierto). Para regeneración completa, re-correr `make eval`. Spec §6.4 documenta esta limitación.

### 3. Leer el report

`evals/reports/latest.md` tiene 5 secciones:
1. **Header**: fecha, commit SHA, modelos, settings, coste total.
2. **Aggregate metrics**: tabla con threshold + pass/fail por métrica.
3. **Per-case appendix**: una sección por caso (30 chat + 10 docs).
4. **Reproducibilidad**: comandos para regenerar.
5. **Caveats**: limitaciones del setup eval (judge same vendor, cost heuristic, partial cache).

Métricas críticas para gate H10 (CLAUDE.md §16.2 puntos 3 + 5 + §17):
- `citation_precision_mean` ≥ 0.85 (gate H10 fija 0.85; CLAUDE.md §17 fija 0.90 como objetivo).
- `faithfulness_mean` ≥ 0.85.
- `citation_recall_mean` ≥ 0.80.
- `verdict_match_rate` ≥ 0.85.

Si alguna falla, **NO es failure del harness** — es señal para H15 (calibración Auditor) o H10 (iteración pre-gate MVP).

### 4. Commit el report

`evals/reports/latest.md` SIEMPRE va committed cuando hay run nueva. Es el entregable visible que el tutor verá.

```bash
git add evals/reports/latest.md
git commit -m "docs(evals): re-run YYYY-MM-DD — <razón>"
```

## Anti-patterns

- **NO bypassear el cache**. Cualquier dev que invoque LLM en el harness debe ir por `evals.cache.cache_call`. Excepción documentada: H4/H5 backend graphs (spec §H8 prohíbe modificar backend, por eso esas llamadas no se cachean).
- **NO commitear `evals/cache/`** (gitignored).
- **NO ejecutar evals en CI** per-PR (Q4 H8 brainstorming, decision firme; $3-5 por PR es insostenible en budget MVP).
- **NO mezclar adversarial cases en gold set** — eso es H9 redteam (`redteam/attacks.jsonl`), separado per CLAUDE.md §18.
- **NO inventar números** si la run no se completó. Si Sonnet falla mid-run o se acaba el budget, el report queda incompleto: o bien commiteas el report parcial con caveat explícito de "ejecución incompleta — N/40 casos", o no commiteas en absoluto.
- **NO sustituir BGE-M3 por OpenAI embeddings** sin haber discutido la decisión. La métrica de answer_relevancy depende de embeddings; usar OpenAI cambiaría la semántica de la métrica y rompería continuidad temporal del benchmark.
- **NO modificar `faithfulness.v1.0.md`** sin bumpear a `v1.1.md` per prompt-versioning skill. Cualquier cambio en el prompt del judge invalida la cache (hash diferente) y obliga a re-correr full.

## Reproducibilidad

Cada `make eval-from-cache` debe producir EXACTAMENTE el mismo report en el judge-layer (modulo `run_date` header). Si diverge → bug en `evals.cache.cache_key`. Las métricas RAG (Ragas) y los chat/doc backend calls SÍ tienen variabilidad porque no se cachean — esa parte solo es reproducible al rerun completo.

## Referencias

- Spec H8: `docs/superpowers/specs/2026-05-10-h8-evaluation-harness-design.md`
- Plan H8: `docs/superpowers/plans/2026-05-10-h8-evaluation-harness.md`
- ADR 0010: `docs/adr/0010-evaluation-harness.md`
- Decisions log §H8: `docs/technical_decisions_log.md`
- Gold set: `evals/gold_set.jsonl` (30 chat cases) + `evals/document_cases/*.expected.json` (10 doc manifests).
- Judge prompt: `src/regulaitor/agents/prompts/judge/faithfulness.v1.0.md`.
