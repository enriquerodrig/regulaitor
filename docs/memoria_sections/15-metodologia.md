# 15. Metodología — §22.22 honest framing + ciclo científico

## 15.1 Tesis del capítulo

La contribución central del TFM no es el sistema RegulAItor en sí — ni el corpus, ni la arquitectura multi-agente, ni siquiera el invariante §6 "no citation, no answer". La contribución central es la **metodología** con la que se construyó: una disciplina de **encuadre honesto (honest framing, §22.22 de CLAUDE.md)** sostenida durante 13 hitos consecutivos y un **ciclo científico** explícito —*diagnosticar → intervenir → medir → refutar → revertir → documentar*— aplicado a través de dos capas distintas (Auditor en v0.1.23 y retrieval en v0.1.30). Dos resultados REVERT documentados con la misma exigencia que los CONFIRM. El invariante §6 sobrevivió intacto a ambos REVERTs y a las tres evoluciones interpretativas de la frontera de enforcement.

Esta sección describe (a) qué es §22.22 y por qué se adoptó, (b) el linaje de los 13 hitos consecutivos `v0.1.19` → `v0.1.32-h16-deploy`, (c) los dos REVERTs documentados con su mecanismo de refutación, (d) cómo §6 evolucionó de "byte-unchanged" a "arquitectura interpretativa de cuatro capas" sin perder garantías, y (e) el deep-review post-H16 que auto-aplicó la metodología sobre el propio sistema desplegado.

## 15.2 §22.22 honest framing — definición operativa

La regla §22.22 está enunciada de manera procedimental en CLAUDE.md y reforzada por la primera memoria persistente (`feedback_cost_estimation_discipline.md`). En esencia:

1. **Nunca presentar como medido lo que no se ha medido**. Cualquier afirmación numérica debe citar el archivo/run que la produjo; en ausencia, etiquetar `[medicion pendiente]` (CLAUDE.md §22.22).
2. **Nunca afirmar "X funciona" sin evidencia empírica reproducible**. Tests verdes son evidencia de invariante, no de eficacia funcional; la eficacia exige run pagado o $0 diagnostic con audit trail reproducible.
3. **Documentar todas las divergencias plan-vs-realidad en la propia closure narrative**, no en commits-fix posteriores. El catálogo de §22.22 disclosures en cada ADR es parte del entregable.
4. **Honrar tanto la dirección CONFIRM como la dirección REVERT**: el mismo ceremonial, la misma exigencia documental, la misma transparencia de coste. Un REVERT honesto vale más que un CONFIRM ambiguo.
5. **Cost-estimation discipline asociada** (consolidada tras el desastre H15.2 que perdió €2.43 por crash sin checkpoint): probes mínimos N=5, estimaciones expresadas como rangos `(low, expected, high = expected × 1.5)`, prohibición de autorizar runs pagados si el presupuesto < high-estimate, prohibición de runs pagados sin harness checkpoint per-case en disco.

La disciplina se introdujo formalmente en v0.1.19 (cuando se hizo evidente que las medidas A/B post-H10 estaban produciendo lecturas mixtas y que la única manera de no contaminar la narrativa académica era documentar las ambigüedades en lugar de suavizarlas). A partir de ahí se aplicó sin excepción en 13 milestones consecutivos.

## 15.3 El linaje de 13 milestones (v0.1.19 → v0.1.32-h16-deploy)

| Milestone | Etiqueta | Tipo | Hallazgo §22.22 dominante |
|---|---|---|---|
| v0.1.19 | `v0.1.19-council-binding` | Capability $0 | Council binding ON cierra deferral H13/H15; conservative-only (solo PASS→RHR en unánime BLOCK) |
| v0.1.20 | `v0.1.20-paid-validation` | Paid €7.83 | A/B v1.0 vs v1.4 → FLIP chat; doc retiene v1.0; wall-clock 14h fue 4× el estimado del plan (documentado, no escondido) |
| v0.1.21 | `v0.1.21-auditor-quorum-hard-constraints` | Capability $0 | Tier 1 RHR quorum + Tier 2 Capa A+B+C; bug Capa A en `additionalProperties=False` sobre `$defs` anidados shipped silently ~12h, descubierto y reparado durante v0.1.22 |
| v0.1.21.2 | `v0.1.21.2-tier2-flips` | Capability $0 | Retrieval defaults flip + chat refusal mock; ship sin paid pre-validación (medida acumulativa diferida) |
| v0.1.22 | `v0.1.22-paid-validation` | Paid €1.91 | CONDITIONAL CONFIRM; 10 disclosures verbatim en ADR-0029 (3 probes fallidos previos $0 + bug Capa A 12h silencioso + 1-arm vs cached trade-off + per-capability NO medido) |
| v0.1.22.1 | `v0.1.22.1-verdict-diagnostic` | Diagnostic $0 | H1 dominante 62.5% (validador strict vs eval-metric lenient); propone v0.1.23 — pero advierte sobre el riesgo de over-attribution |
| **v0.1.23** | `v0.1.23-auditor-lenient-quorum` | **REVERT** Paid €1.76 | Predicho +0.10 verdict_match; medido **-0.03**; 0/10 flips predichos; mecanismo Design B intervino en la capa equivocada |
| v0.1.24 | `v0.1.24-gold-alignment-decomposition` | Capability $0 | O1 `acceptable_verdicts` (+0.10 alignment) + O2 `failed_check` decomposition; primera evolución del invariante §6 ("byte-equivalent semantics + additive observability") |
| v0.1.24.1 | `v0.1.24.1-finding-path-diagnostic` | Diagnostic $0 | Path B (Strict-Answer partial routing) dominante 8/10 — corrige la capa que v0.1.23 había errado |
| v0.1.25 | `v0.1.25-auditor-partial-routing` | **CONFIRM** Paid €1.66 | Design H D2; verdict_match **+0.33** (mayor lift de todo el linaje); 9/10 flips H1 confirmados (antítesis empírica de v0.1.23) |
| v0.1.29 | `v0.1.29-chat-016-all-blocked-softening` | **CONFIRM** Paid €1.89 | Design D Mirror del D2; verdict_match **+0.08** on-forecast; reutiliza el helper de v0.1.25 |
| **v0.1.30** | `v0.1.30-title-augmented-embeddings` | **REVERT** Paid €0.65 | Doc-mode citation_recall 0.33 flat (vs target ≥0.38); doc-001 precision REGRESS 0.50→0.00; mecanismo over-citation 5x mediana |
| v0.1.32 | `v0.1.32-h16-deploy` | Deploy $0 | HF Spaces vivo; 12-round iteration documentada; 1569 rows via Git LFS; smoke OK con §6.1 architecture visible |

Los hitos v0.1.21.1, v0.1.21.3 y v0.1.26-v0.1.28 (mini-milestones decimales sin nuevo ADR) están registrados en CLAUDE.md §16.3 y `docs/technical_decisions_log.md` pero no se cuentan separadamente en el linaje §22.22 porque siguen el patrón "light" sin paid run.

### 15.3.1 Cadencia y costes

Coste pagado acumulado del linaje §22.22: aproximadamente €17.41 distribuidos en 8 runs pagados (v0.1.20 €7.83 + v0.1.22 €1.91 + v0.1.23 €1.76 + v0.1.25 €1.66 + v0.1.27 €0.16 + v0.1.28 €1.55 + v0.1.29 €1.89 + v0.1.30 €0.65). El resto de los 13 milestones es $0 (capability ships sin paid pre-validación, diagnósticos sobre caches existentes, deploy infrastructure). La disciplina cost-estimation evitó al menos un desastre análogo a H15.2: v0.1.30 saltó T7 main (~€1.40 estimado) cuando el probe T5 (€0.65) refutó estructuralmente el SHIP criterion, ahorrando ~$2 USD del budget restante.

## 15.4 El ciclo científico explícito

A partir de v0.1.22.1 cristalizó un patrón procedimental de seis pasos que se repite en cada milestone evidence-driven:

1. **Diagnosticar** ($0 sobre evidencia cacheada cuando es posible): aislar el mecanismo dominante de la regresión o gap. v0.1.17 diagnostic-first ya había anticipado esto al descubrir que el bug `no_answer_residual` tenía un 5º mecanismo (prose-without-findings) que un fix-first speculative habría errado.
2. **Intervenir** (mínimo surface change, máxima reversibilidad): preferir 1-line wirings sobre refactors; preferir helpers locales sobre cambios de schema; preferir aggregation layer sobre validator layer cuando el §6 risk surface lo permite.
3. **Medir** (paid run con probe gate per cost-estimation discipline): probe N=5 con SKIP/PROCEED explícito; main 25 cases si probe pasa; reportes cache-mining $0 sobre el probe ya pagado.
4. **Refutar o confirmar** (binary decision sobre flip protocol explícito en el ADR): CONFIRM si hard floor PASS + métrica predicha cumple; CONDITIONAL CONFIRM si hard floor PASS + mixed; REVERT si hard floor FAIL o regresión.
5. **Revertir** (atómico cuando aplica): cherry-pick del 1-line change; snapshot mv-back para corpus; tests retirados con el mismo squash; ADR amendado con sección §REVERT verbatim del razonamiento prospectivo preservado como registro científico.
6. **Documentar** (sin excepción, ambas direcciones): closure narrative en `docs/technical_decisions_log.md`; entrada en `CLAUDE.md §27 Hitos cerrados`; actualización de `docs/evidence_matrix.md`; rolling forward de la memoria persistente.

Este ciclo está descrito en abstracto en ADR-0030 §REVERT (la sección que documenta el primer REVERT) y se aplica de manera explícita en ADR-0032 §"Flip protocol summary" + ADR-0034 + ADR-0035. La continuidad procedimental cross-milestone es lo que permite que un REVERT como v0.1.23 no destruya el linaje, sino que lo refuerce.

## 15.5 Los dos REVERTs documentados

### 15.5.1 v0.1.23 — Auditor lenient quorum (Design B): la capa equivocada

**Hipótesis prospectiva** (ADR-0030 D1-D7, prerumiido por v0.1.22.1 diagnostic): el invariante "validador strict vs eval-metric lenient" causaba 10/16 = 62.5% de las RHR cases (atribuidas a H1). Design B introdujo un helper inline `_is_lenient_valid(result)` en `src/regulaitor/agents/auditor.py` y cambió 1 línea en el conteo Tier 1 quorum: `not r.validated` → `not _is_lenient_valid(r)`. §6 risk evaluado como LOW (validador byte-unchanged; intervención solo en aggregation layer).

**Medida empírica** (T6, paid €1.76 = ~$1.89 USD): verdict_match **0.30 → 0.27 (-0.03)** vs predicción **+0.10**. De 10 cases H1 predichos para flip RHR→PASS, **0 flipearon** como esperado; 8/10 permanecieron RHR; 2/10 (chat-016, chat-017) flipearon RHR→**BLOCK** (dirección opuesta).

**Atribución mecanística (3 root causes documentados en ADR-0030 §REVERT)**:

1. **API drift (~20%, 2/10 cases)**: gap de 2 días entre la baseline cacheada (v0.1.22-prod 2026-05-24) y el run fresco (v0.1.23 2026-05-26). La no-determinismo de Sonnet a temperature=0 produjo citas distintas para chat-016 y chat-017 → outputs distintos del validador → routing distinto del Auditor. El cache-based prediction era inválido para esos cases.
2. **Design B assumption invalid (~80%, 8/10 cases — DOMINANTE)**: el Tier 1 quorum **no era el bottleneck** para los H1 unchanged-RHR cases. Aun con conteo lenient, los 8 casos siguieron RHR. Capas upstream (Strict-Answer partial-Findings routing OR Finding-Lenient strict-text-match) son los gatekeepers reales que el quorum nunca alcanzó a ejecutar.
3. **Diagnostic measurement artifact**: el trail `per_citation_audits` de v0.1.21.1 D2 almacenaba `validated: bool` combinado sin enumerar los sub-checks 1/2/3. La atribución H1 de v0.1.22.1 contaba la cadena `text_not_in_apartado` como evidencia de Check 3, pero no podía separar fallos puros de Check 3 de fallos combinados con Check 1/2.

**Acción REVERT** (T-revert, 2026-05-26): cherry-pick de la línea modificada; 5 tests retirados; ADR-0030 amendado con sección §REVERT verbatim (~70 líneas; razonamiento prospectivo preservado). Tag `v0.1.23-auditor-lenient-quorum` se mantiene como registro semántico ("el experimento que se ejecutó y se revirtió; estado de producción restaurado a baseline v0.1.22.1").

**Lecciones (carry-forwards en `docs/adr/0030-auditor-lenient-quorum.md`)**: (a) la atribución diagnóstica requiere decomposición Check 1/2/3 — esto produjo v0.1.24 O2 `failed_check` decomposition field; (b) el bottleneck verdict_match estaba en Strict-Answer partial routing (Layer c) o en Finding-Lenient (Layer b), no en Tier 1 quorum — esto produjo v0.1.24.1 path-attribution diagnostic y v0.1.25 Design H D2 al layer correcto; (c) ~20% noise floor para comparaciones cross-day; (d) Designs A y C (validator-direct + schema field) son carry-forward HX si el verdict_match vuelve a ser crítico post-deploy.

### 15.5.2 v0.1.30 — Title-augmented corpus embeddings: la asimetría no obvia

**Hipótesis prospectiva** (ADR-0035 D1-D5): el query-side title-prepend de v0.1.28 T4-bis (que llevó citation_recall doc-mode 0→0.33) sugería que el mismo prefijo aplicado al corpus-side (re-embed con `f"Artículo {chunk.articulo} - {parsed.title}\n\n{chunk.text}"` en `src/regulaitor/rag/build.py`) cerraría parcialmente la brecha semántica descriptive-doc-segment ↔ obligation-corpus-article. §6 risk evaluado como LOW (`Chunk.text` byte-unchanged; solo el string pasado a `embeddings.embed()` cambia; validador unaffected).

**Medida empírica** (T5 probe, paid €0.65; T7 main SKIPPED por cost-discipline): doc-mode citation_recall **0.33 flat** (target ≥0.38; FAILS SHIP criterion D5); doc-001 precision **REGRESS 0.50→0.00**; expansion mediana de citas emitidas 5× (doc-001 1-2→12; doc-003 1→19).

**Atribución mecanística (§REVERT en ADR-0035)**: la intervención funcionó **as designed at the embedding level** (cosine sim 0.97 ≠ 1.0 vs snapshot pre-v0.1.30 confirma shift vectorial real); pero la **consecuencia downstream fue desfavorable**: los embeddings title-augmented surfacean significativamente más artículos topic-related → el prompt `document_analyst v1.6` (Finding-based refusal) emite Findings citando todos los surfaceados → precision se hunde porque los artículos gold-specific siguen sin dominar el set surfaceado, y la over-emission diluye la señal. **Este es el mismo mecanismo que el REVERT T4-extra α+β de v0.1.28** (ADR-0033 §22.22 #5: top_k=15 + max_chunks_per_norma=5 → context dilution → citation_precision 0.17→0.00). La over-citation es estructural a la combinación BGE-M3 + doc_analyst v1.6 cuando la breadth retrieval expande en cualquier capa.

**Acción REVERT** (T-revert, atómica): (1) index revert via `mv corpus/indexes/regulaitor.lance.pre-v0.1.30/ corpus/indexes/regulaitor.lance/`; (2) manifests revert via `git checkout HEAD -- corpus/manifests/`; (3) code revert de `rag/build.py` (remove `_text_to_embed` + restore `embeddings.embed([ch.text for ch in chunks])`); (4) 5 tests removed; (5) ADR-0035 amendado con sección §REVERT preservando D1-D5 + Alternatives A-D + 5 §22.22 disclosures verbatim.

**Asimetría no-obvia como hallazgo científico**: el mismo prefijo aplicado en query-side AYUDA (v0.1.28 T4-bis SHIPPED: citation_recall 0→0.33) y aplicado en corpus-side HIERE (v0.1.30 REVERT). Esto es un hallazgo no-trivial sobre la dinámica retrieval-vs-emission en `document_analyst v1.6`, documentado para H17 memoria como insight empírico sobre BGE-M3 + Finding-based-refusal prompts. Las alternatives HyDE (Alternative A), hybrid BM25 (B) y custom legal reranker (C) quedan como carry-forward HX informadas por tráfico real post-deploy.

### 15.5.3 Por qué los dos REVERTs fortalecen la narrativa

Ambos REVERTs comparten la propiedad fundamental: **el invariante §6 se mantuvo intacto durante toda la activación y toda la restauración**. En v0.1.23, `src/regulaitor/citation/validator.py` + `src/regulaitor/citation/schemas.py` quedaron byte-unchanged en T1+T2 (activación) y en T-revert (restauración), verificado por `git diff main -- src/regulaitor/citation/` vacío en ambos puntos; Finding-Lenient layer se mantuvo strict; redteam-smoke 0.92 carry. En v0.1.30, las capas (a), (b), (c) y (d) del §6 quedaron byte-unchanged; el único archivo `src/` modificado fue `rag/build.py` (revertido cleanly); 0 fabricaciones detectadas en T5 probe; redteam-smoke 0.92 carry por construcción.

La asimetría entre los dos REVERTs es instructiva: v0.1.23 erró la **capa** (intervino en Tier 1 quorum cuando el bottleneck estaba en Strict-Answer partial routing); v0.1.30 erró el **side** del retrieval (intervino corpus-side cuando el sweet spot estaba en query-side). En ambos casos, el ciclo científico permitió ship-then-measure-then-revert sin contaminar el estado de producción, y produjo carry-forwards accionables (v0.1.24 O2 + v0.1.25 D2 al layer correcto; HyDE/hybrid carry-forward HX para retrieval).

## 15.6 Evolución interpretativa del invariante §6

El invariante "no citation, no answer" (CLAUDE.md §6) **nunca se debilitó** a lo largo de las 35 ADRs y los 13 milestones §22.22. Lo que sí evolucionó es la **interpretación arquitectural** del enforcement boundary, en tres pasos explícitamente documentados (CLAUDE.md §6.1):

- **Capa (a) — per-citation validator** (`src/regulaitor/citation/validator.py`): tres checks STRICT (`article_exists`, `apartado_exists`, `text_normalized_match`). **BYTE-EQUIVALENT desde H4**. En v0.1.24 ADR-0031 se añadió el campo aditivo `failed_check: Literal[1, 2, 3] | None` (observabilidad pura; NO está en el decision path).
- **Capa (b) — Finding-Lenient aggregation** (`src/regulaitor/agents/auditor.py:65` `any(r.validated for r in this_finding_results)`): un Finding pasa si ≥1 de sus citations valida STRICTLY. **BYTE-UNCHANGED desde v0.1.21**. Es la segunda línea de defensa contra fabricación.
- **Capa (c) — Turn-level aggregation policy** (`auditor.py`, branches del `audit()`): combina per-Finding verdicts en un veredicto turn-level. Modificada en (1) v0.1.21 ADR-0027 D1 (Tier 1 quorum `n_invalid_citations >= 2` → RHR); (2) v0.1.25 ADR-0032 D2 (partial-Findings routing softening cuando helper True); (3) v0.1.29 ADR-0034 D Mirror (all-blocked routing softening con la MISMA condición helper). Las modificaciones son aditivas y gated en una condición binaria: el helper `_all_blocked_findings_paraphrase_only` retorna True solo cuando TODA citation invalid tiene `failed_check==3`, garantizando por construcción que cualquier Check 1 o Check 2 (fabricación real de artículo o apartado) preserva el routing original BLOCK/RHR.
- **Capa (d) — prompt-level explicit forbid** (`src/regulaitor/agents/prompts/analyst/system.v1.5.md` + `prompts/document_analyst/system.v1.6.md`): Hard rule 4 inviolable "Never emit placeholder citation strings (UNKNOWN/N/A/TBD)" + Rule 2 Finding-based refusal cuando contexto insuficiente. NUEVA en v0.1.28 ADR-0033 como defense-in-depth model-side complementando el enforcement validator-side.

La enunciación del invariante §6 evolucionó así de **"byte-unchanged en validator + Auditor"** (H4-v0.1.18) a **"byte-equivalent validation semantics + additive observability"** (v0.1.24, primera evolución interpretativa) a **"three-layer architecture: validator + Finding-Lenient BYTE-UNCHANGED + Turn-level aggregation policy MODIFIED at Layer (c) with binary §6-safe condition"** (v0.1.25, segunda evolución) a **"four-layer architecture incluyendo Layer (d) prompt-level forbid as defense-in-depth"** (v0.1.28, tercera evolución). El contrato se fortalece, no se debilita, con cada precisión interpretativa: la garantía de que la fabricación nunca es PASS está documentada en CLAUDE.md §6.1: "el helper compartido sólo retorna True si TODA citation invalid tiene `failed_check==3`; cualquier Check 1 o Check 2 retorna False → preserva BLOCK/RHR routing original. **Por construcción, fabricación nunca es PASS.**"

## 15.7 Deep-review post-H16: la metodología auto-aplicada

Después del deploy a Hugging Face Spaces en v0.1.32, el proyecto sometió el sistema desplegado a un deep-review estructurado (61-agent ultracode workflow `wf_dc377549-4c0`). El review produjo 42 findings verificadas tras adversarial verify pass (3 critical, 10 important, 19 minor, 10 informational). **El finding C1 — un edge case de whitespace en el normalizador de citas (`Citation(text=" ")` pasaba como §6 PASS vía `_normalize(" ") == ""` luego `"" in any_string == True`) — se reparó el mismo día tras la entrega del review** (commit `549b718`, 2026-05-29), manteniendo el invariante §6 (de hecho **estrictamente endurecido**, nunca relajado: schema-level `@field_validator` + defense-in-depth en validator.py) y la trazabilidad de la corrección (3 nuevos regression tests + actualización del registro `§v0.1.32-post` en `docs/technical_decisions_log.md`) bajo el mismo ceremonial §22.22 que cualquier milestone anterior.

Este episodio cierra el ciclo metodológico: el sistema desplegado no es un artefacto congelado sino un objeto sujeto a la misma disciplina diagnóstico-intervención-medida-documentación. La metodología **se auto-aplica** sin distinción entre "milestones de pre-deploy" y "operación post-deploy". Esto es consistente con la posición §15.1: la metodología es la contribución; el sistema es el vehículo.

## 15.8 Implicaciones para la defensa del TFM

Tres puntos resumen la posición defensiva:

1. **Honestidad como ventaja, no como debilidad**. Los 13 milestones consecutivos con §22.22 framing — incluyendo dos REVERTs documentados verbatim — producen una evidence chain reproducible y auditable. Un evaluador puede revisar `evals/reports/v0.1.23/` y `evals/reports/v0.1.30/probe.md` y verificar que la refutación está sustantiva, que el invariante §6 se mantuvo, y que las carry-forwards están registradas. Esto es preferible a un resultado pulido pero opaco.
2. **El invariante §6 sobrevive a la evolución interpretativa**. Las tres evoluciones (additive observability v0.1.24; three-layer architecture v0.1.25; four-layer architecture v0.1.28) no debilitan la garantía "no citation, no answer" — la precisan. Por construcción del helper compartido `_all_blocked_findings_paraphrase_only` en `auditor.py:20-48`, fabricación nunca pasa a PASS. El TFM puede defender que el sistema preserva su invariante de seguridad bajo refinamientos de aggregation policy.
3. **El ciclo científico es la unidad de trabajo, no el commit**. Cada milestone es un ciclo completo (spec + plan + implementation + paid validation o $0 diagnostic + ADR + closure docs); cada ADR contiene su sección §22.22 disclosures + flip protocol + Alternatives + References. Esta estructura procedimental es lo que permite que 13 milestones consecutivos mantengan la coherencia narrativa y la trazabilidad académica.

La sección 16 (Resultados) detalla las métricas; la sección 17 (Discusión) interpreta el techo system-level (el verdadero limit no es la elección de modelo, es la cadena retriever + Auditor + prompt); la sección 18 (Limitaciones) enumera explícitamente las carry-forwards HX. Esta sección 15 establece el aparato metodológico que hace posibles las otras tres.

## 15.9 Referencias internas

- **CLAUDE.md** §6 (invariante "no citation, no answer"), §6.1 (arquitectura cuatro capas), §22.22 (honest framing rule), §16.3 (línea temporal H0→v0.1.32), §27 (hitos cerrados; referencia exhaustiva por milestone).
- **docs/technical_decisions_log.md** (>5300 líneas; closure narratives detalladas de cada milestone incluyendo §22.22 disclosures verbatim).
- **docs/adr/0023-no-answer-fix.md** … **docs/adr/0035-title-augmented-corpus-embeddings.md** (13 ADRs del linaje §22.22; ADR-0030 §REVERT y ADR-0035 §REVERT son los registros canónicos de los dos REVERTs).
- **evals/reports/v0.1.22/** … **evals/reports/v0.1.30/** (paid run evidence + $0 cache-mining diagnostics; los comparison reports + per-citation-mechanism reports + verdict-flip-review reports son la auditabilidad reproducible de las afirmaciones empíricas).
- **memory/feedback_cost_estimation_discipline.md** (las 4 hard rules cost-estimation consolidadas tras el desastre v0.1.15.2).
- **src/regulaitor/citation/validator.py** (Layer a §6 guardian; BYTE-EQUIVALENT semantics desde H4).
- **src/regulaitor/agents/auditor.py:20-48** (helper compartido `_all_blocked_findings_paraphrase_only` — garantía estructural de que fabricación nunca pasa a PASS).
- **src/regulaitor/agents/prompts/analyst/system.v1.5.md** + **prompts/document_analyst/system.v1.6.md** (Layer d defense-in-depth prompt-level forbid).
