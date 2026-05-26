# RegulAItor — Evaluation Report

**Run:** 2026-05-26T12:56:40.232659+00:00 | **Commit:** `01ef316` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=full, cache hits/misses: 0/5 | **Total cost:** 0.30 €

## Aggregate metrics

| Métrica | Valor | v0.1.20-bar | Aspiracional |
|---|---|---|---|
| faithfulness_mean | 0.90 | ≥0.65 ✅ | ≥0.85 ✅ |
| answer_relevancy_mean | 0.88 | ≥0.55 ✅ | ≥0.85 ✅ |
| context_precision_mean | 0.77 | ≥0.55 ✅ | ≥0.80 ❌ (-0.03) |
| context_recall_mean | 0.52 | (info) | (info) |
| citation_precision_mean | 0.28 | ≥0.25 ✅ | ≥0.90 ❌ (-0.62) |
| citation_recall_mean | 0.70 | ≥0.60 ✅ | ≥0.80 ❌ (-0.10) |
| verdict_match_rate | 1.00 | ≥0.35 ✅ | ≥0.85 ✅ |
| severity_match_rate | 0.40 | ≥0.35 ✅ | ≥0.80 ❌ (-0.40) |
| latency_p95_ms | 2568235 | ≤12000 ❌ (+2556235) | (info) |
| chat_latency_p95_ms | 2568235 | (info) | (info) |
| doc_latency_p95_ms | 0 | (info) | (info) |
| cost_per_chat_eur | 0.060 | ≤0.05 ❌ (+0.010) | (info) |
| cost_per_doc_eur | 0.000 | ≤0.50 ✅ | (info) |
| cost_total_eur | 0.30 | (info) | (info) |
| cache_hit_rate | 0.00 | (info) | (info) |

## Caveats — v0.1.20-bar reading

1. **Aspirational column** = CLAUDE.md §17 long-term ideal targets; no run has ever hit them; they remain as direction-setting, not as v0.1.20 ship gate.
2. **v0.1.20-bar column** = anchored to H10 (full-30-case measured baseline) + H15 v1.2 (30-case partial intervention measurement); the 64-case set is harder so even matching the bar is meaningful evidence the maximalist-plan stack didn't regress on the easier subset.
3. **Judge family stays Haiku 4.5** per ADR-0010 D1 caveat (same vendor as production Sonnet, different model class). Cross-vendor migration deferred to HX (post-TFM); §19 satisfied literally; documented honestly.
4. **Latency p95** number remains contaminated by batch+rate-limit+tenacity backoff per H8 amendment + §17 note; v0.1.16 does NOT fix this. H17 LangFuse refactor is the proper instrument; until then `latency_p95_ms` is informational despite being formally gated in the report.

## Per-case appendix — chat (5 cases)

### chat-001

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['2.2', '25.3', '6.1'] expected=['6.1'] precision=0.33 recall=1.00
- **RAG metrics**: faithfulness=0.80 answer_relevancy=0.89 context_precision=1.00 context_recall=0.33
- **Latency**: 1179985 ms | **Cost**: 0.0580 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita literalmente el artículo 6.1 del AI Act o su contenido sustancial — El sistema cita explícitamente 'artículo 6, apartado 1' y lo identifica como la norma que establece la clasificación de alto riesgo.
  - ❌ Identifica correctamente los dos requisitos acumulativos: componente de seguridad en producto de la lista del Anexo I + evaluación de conformidad por terceros — La respuesta menciona 'dos condiciones acumulativas' pero no las especifica explícitamente; no detalla que la segunda condición es la evaluación de conformidad por terceros, solo alude a 'limitación de obligaciones' para productos de la sección B del anexo I.
  - ❌ No afirma obligaciones adicionales no respaldadas por el artículo 6.1 — La respuesta afirma que el proveedor 'deberá cumplir todos los requisitos del capítulo III, sección 2' (gestión de riesgos, gobernanza de datos, etc.), pero el artículo 6.1 solo clasifica como alto riesgo; las obligaciones específicas derivan de otros artículos, no del 6.1 directamente.

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['6.3', '6.4', '80'] expected=['6.2', '6.3'] precision=0.33 recall=0.50
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.88 context_precision=0.83 context_recall=1.00
- **Latency**: 1211718 ms | **Cost**: 0.0531 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 6.2 como regla general de clasificación por Anexo III — El artículo 6.2 no aparece en cited_articles; la respuesta menciona 'regla general' pero no cita explícitamente 6.2.
  - ✅ Explica la excepción del artículo 6.3 sin omitir el requisito de documentación motivada — La respuesta cita 6.3, explica la excepción y menciona explícitamente la documentación de la evaluación antes de poner en mercado.
  - ✅ No afirma que la excepción es automática ni que exime de todos los controles — La respuesta aclara que la excepción requiere acreditación y documentación, y que las autoridades pueden revisar la clasificación; no la presenta como automática.

### chat-003

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['16', '17.1', '17.2', '25.1'] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.82 answer_relevancy=0.93 context_precision=0.00 context_recall=0.17
- **Latency**: 2316968 ms | **Cost**: 0.0647 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — El sistema citó el artículo 9 de forma genérica, pero no incluyó en cited_articles los artículos 9.1 ni 9.2 específicamente; además, los artículos citados (16, 17.1, 17.2, 25.1) no coinciden con los esperados (9.1, 9.2).
  - ❌ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — Aunque la respuesta menciona 'a lo largo de todo el ciclo de vida' en la respuesta esperada, la respuesta actual del sistema no incluye explícitamente esta caracterización de continuidad o ciclo de vida.
  - ✅ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — La respuesta actual menciona procedimientos de diseño, verificación, gestión de datos, vigilancia poscomercialización e incidentes graves, que cubren identificación, evaluación y mitigación de riesgos.

### chat-004

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['10.1', '10.2', '10.3', '42.1'] expected=['10.1', '10.2'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=0.86 answer_relevancy=0.82 context_precision=1.00 context_recall=0.75
- **Latency**: 1958015 ms | **Cost**: 0.0553 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita los artículos 10.1 y 10.2 del AI Act con su contenido sustancial — La respuesta cita explícitamente los artículos 10.1 y 10.2 y describe su contenido sustancial: requisitos de calidad de datos y prácticas de gobernanza respectivamente.
  - ✅ Menciona los requisitos de representatividad, pertinencia y libre de errores de los datasets — La respuesta enumera explícitamente estos tres criterios de calidad intrínseca: 'pertinencia, representatividad, ausencia de errores y completitud'.
  - ✅ Identifica la obligación de gobernanza que incluye detección y corrección de sesgos — La respuesta menciona en el nivel (2) la 'detección de sesgos' y en el nivel (3) implícitamente medidas correctivas como parte del marco de gobernanza.

### chat-005

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['11.1', '11.2', '23.1', '72.3'] expected=['11.1'] precision=0.25 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.90 context_precision=1.00 context_recall=0.33
- **Latency**: 358734 ms | **Cost**: 0.0675 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 11.1 del AI Act como base de la obligación de documentación técnica — El artículo 11.1 está incluido en la lista de artículos citados por el sistema.
  - ✅ Menciona que la documentación debe elaborarse antes de la introducción en el mercado y mantenerse actualizada — La respuesta afirma explícitamente que la documentación 'debe elaborarse antes de su introducción en el mercado o puesta en servicio, y mantenerse actualizada'.
  - ✅ Identifica correctamente que el contenido mínimo se remite al Anexo IV del AI Act — La respuesta menciona que 'El contenido mínimo está determinado por el Anexo IV del Reglamento'.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=5 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
