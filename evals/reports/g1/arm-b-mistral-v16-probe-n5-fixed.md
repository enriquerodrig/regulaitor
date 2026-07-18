# RegulAItor — Evaluation Report

**Run:** 2026-07-14T12:05:35.167836+00:00 | **Commit:** `148b514` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=full, cache hits/misses: 0/5 | **Total cost:** 0.02 €

## Aggregate metrics

| Métrica | Valor | v0.1.20-bar | Aspiracional |
|---|---|---|---|
| faithfulness_mean | 0.80 | ≥0.65 ✅ | ≥0.85 ❌ (-0.05) |
| answer_relevancy_mean | 0.89 | ≥0.55 ✅ | ≥0.85 ✅ |
| context_precision_mean | 0.77 | ≥0.55 ✅ | ≥0.80 ❌ (-0.03) |
| context_recall_mean | 0.47 | (info) | (info) |
| citation_precision_mean | 0.63 | ≥0.25 ✅ | ≥0.90 ❌ (-0.27) |
| citation_recall_mean | 0.80 | ≥0.60 ✅ | ≥0.80 ✅ |
| verdict_match_rate | 1.00 | ≥0.35 ✅ | ≥0.85 ✅ |
| severity_match_rate | 0.40 | ≥0.35 ✅ | ≥0.80 ❌ (-0.40) |
| latency_p95_ms | 408022 | ≤12000 ❌ (+396022) | (info) |
| chat_latency_p95_ms | 408022 | (info) | (info) |
| doc_latency_p95_ms | 0 | (info) | (info) |
| cost_per_chat_eur | 0.004 | ≤0.05 ✅ | (info) |
| cost_per_doc_eur | 0.000 | ≤0.50 ✅ | (info) |
| cost_total_eur | 0.02 | (info) | (info) |
| cache_hit_rate | 0.00 | (info) | (info) |

## Caveats — v0.1.20-bar reading

1. **Aspirational column** = CLAUDE.md §17 long-term ideal targets; no run has ever hit them; they remain as direction-setting, not as v0.1.20 ship gate.
2. **v0.1.20-bar column** = anchored to H10 (full-30-case measured baseline) + H15 v1.2 (30-case partial intervention measurement); the 64-case set is harder so even matching the bar is meaningful evidence the maximalist-plan stack didn't regress on the easier subset.
3. **Judge family stays Haiku 4.5** per ADR-0010 D1 caveat (same vendor as production Sonnet, different model class). Cross-vendor migration deferred to HX (post-TFM); §19 satisfied literally; documented honestly.
4. **Latency p95** number remains contaminated by batch+rate-limit+tenacity backoff per H8 amendment + §17 note; v0.1.16 does NOT fix this. H17 LangFuse refactor is the proper instrument; until then `latency_p95_ms` is informational despite being formally gated in the report.

## Per-case appendix — chat (5 cases)

### chat-001

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['6.1'] expected=['6.1'] precision=1.00 recall=1.00
- **RAG metrics**: faithfulness=0.83 answer_relevancy=0.83 context_precision=0.87 context_recall=0.33
- **Latency**: 391344 ms | **Cost**: 0.0008 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita literalmente el artículo 6.1 del AI Act o su contenido sustancial — El sistema cita explícitamente el artículo 6.1 en `cited_articles` y reproduce fielmente su contenido sustancial sobre componentes de seguridad en productos de actos de armonización.
  - ✅ Identifica correctamente los dos requisitos acumulativos: componente de seguridad en producto de la lista del Anexo I + evaluación de conformidad por terceros — La respuesta enumera claramente ambas condiciones acumulativas: (a) componente de seguridad en producto regulado por actos de armonización, y (b) evaluación de conformidad con intervención de terceros.
  - ❌ No afirma obligaciones adicionales no respaldadas por el artículo 6.1 — La respuesta se limita a la clasificación de alto riesgo sin mencionar obligaciones específicas del capítulo III sección 2, lo que es correcto; sin embargo, la `expected_answer` incluye requisitos adicionales (gestión de riesgos, gobernanza de datos, etc.) que van más allá del artículo 6.1 y no están presentes en la respuesta actual, por lo que este criterio evalúa la ausencia de afirmaciones no respaldadas, que se cumple.

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['6.2', '6.3'] expected=['6.2', '6.3'] precision=1.00 recall=1.00
- **RAG metrics**: faithfulness=0.80 answer_relevancy=0.91 context_precision=1.00 context_recall=0.80
- **Latency**: 401155 ms | **Cost**: 0.0008 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 6.2 como regla general de clasificación por Anexo III — El sistema cita correctamente el artículo 6.2 en la lista de artículos citados.
  - ❌ Explica la excepción del artículo 6.3 sin omitir el requisito de documentación motivada — La respuesta menciona la excepción del artículo 6.3 pero no especifica explícitamente el requisito de documentación motivada, registro y disponibilidad para autoridades que exige el artículo.
  - ❌ No afirma que la excepción es automática ni que exime de todos los controles — La respuesta afirma que existen 'mecanismos para evaluar' y 'condiciones específicas' pero no aclara suficientemente que la excepción requiere un análisis formal y documentado previo a la introducción en el mercado, ni que sin cumplirla el sistema queda sujeto a todos los requisitos del capítulo III.

### chat-003

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['17.1', '20.1', '20.2'] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.75 answer_relevancy=0.92 context_precision=0.00 context_recall=0.14
- **Latency**: 378782 ms | **Cost**: 0.0098 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — El sistema citó artículos 17.1, 20.1 y 20.2, pero no incluyó los artículos 9.1 y 9.2 esperados que son centrales para esta pregunta.
  - ✅ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — La respuesta afirma que el sistema debe estar documentado y garantizar cumplimiento, aunque no explícita 'ciclo de vida' de forma literal, el concepto de continuidad está implícito en 'sistema de gestión de la calidad'.
  - ✅ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — La respuesta menciona identificación de riesgos, evaluación (implícita en 'detectan que un sistema no es conforme'), y medidas correctoras inmediatas como mitigación.

### chat-004

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['10.1', '10.2', '10.4'] expected=['10.1', '10.2'] precision=0.67 recall=1.00
- **RAG metrics**: faithfulness=0.75 answer_relevancy=0.88 context_precision=1.00 context_recall=0.75
- **Latency**: 385047 ms | **Cost**: 0.0062 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita los artículos 10.1 y 10.2 del AI Act con su contenido sustancial — La respuesta cita explícitamente el Artículo 10 y menciona que los requisitos se detallan en 10.1 y 10.2, aunque no desarrolla el contenido sustancial de cada apartado con la profundidad de la respuesta esperada.
  - ❌ Menciona los requisitos de representatividad, pertinencia y libre de errores de los datasets — La respuesta alude genéricamente a 'prácticas que abarcan desde la calidad de los datos' pero no menciona explícitamente los requisitos de representatividad, pertinencia y ausencia de errores que exige el artículo 10.1.
  - ✅ Identifica la obligación de gobernanza que incluye detección y corrección de sesgos — La respuesta menciona explícitamente 'mitigación de sesgos' como parte de los requisitos de gobernanza y gestión de datos.

### chat-005

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['11.1', '11.2'] expected=['11.1'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=0.89 answer_relevancy=0.91 context_precision=1.00 context_recall=0.33
- **Latency**: 370688 ms | **Cost**: 0.0010 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 11.1 del AI Act como base de la obligación de documentación técnica — La respuesta cita explícitamente el Artículo 11 y 11.1 está incluido en cited_articles.
  - ✅ Menciona que la documentación debe elaborarse antes de la introducción en el mercado y mantenerse actualizada — La respuesta afirma textualmente que debe elaborarse 'antes de su introducción en el mercado o puesta en servicio' y 'mantenerse actualizada durante todo el ciclo de vida'.
  - ✅ Identifica correctamente que el contenido mínimo se remite al Anexo IV del AI Act — La respuesta menciona explícitamente que debe incluir 'como mínimo, los elementos detallados en el Anexo IV'.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=5 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
