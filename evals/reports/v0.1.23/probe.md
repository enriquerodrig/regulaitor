# RegulAItor — Evaluation Report

**Run:** 2026-05-25T22:24:05.689977+00:00 | **Commit:** `fac612e` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=full, cache hits/misses: 0/5 | **Total cost:** 0.31 €

## Aggregate metrics

| Métrica | Valor | v0.1.20-bar | Aspiracional |
|---|---|---|---|
| faithfulness_mean | 0.92 | ≥0.65 ✅ | ≥0.85 ✅ |
| answer_relevancy_mean | 0.89 | ≥0.55 ✅ | ≥0.85 ✅ |
| context_precision_mean | 0.83 | ≥0.55 ✅ | ≥0.80 ✅ |
| context_recall_mean | 0.52 | (info) | (info) |
| citation_precision_mean | 0.32 | ≥0.25 ✅ | ≥0.90 ❌ (-0.58) |
| citation_recall_mean | 0.80 | ≥0.60 ✅ | ≥0.80 ✅ |
| verdict_match_rate | 0.60 | ≥0.35 ✅ | ≥0.85 ❌ (-0.25) |
| severity_match_rate | 0.40 | ≥0.35 ✅ | ≥0.80 ❌ (-0.40) |
| latency_p95_ms | 352806 | ≤12000 ❌ (+340806) | (info) |
| chat_latency_p95_ms | 352806 | (info) | (info) |
| doc_latency_p95_ms | 0 | (info) | (info) |
| cost_per_chat_eur | 0.062 | ≤0.05 ❌ (+0.012) | (info) |
| cost_per_doc_eur | 0.000 | ≤0.50 ✅ | (info) |
| cost_total_eur | 0.31 | (info) | (info) |
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
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.87 context_precision=1.00 context_recall=0.33
- **Latency**: 351921 ms | **Cost**: 0.0584 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita literalmente el artículo 6.1 del AI Act o su contenido sustancial — El sistema cita explícitamente 'artículo 6, apartado 1' y lo incluye en cited_articles como '6.1'.
  - ❌ Identifica correctamente los dos requisitos acumulativos: componente de seguridad en producto de la lista del Anexo I + evaluación de conformidad por terceros — La respuesta menciona 'dos condiciones acumulativas' pero no especifica explícitamente la segunda condición (evaluación de conformidad por terceros); solo alude vagamente a 'sección A o B del Anexo I'.
  - ❌ No afirma obligaciones adicionales no respaldadas por el artículo 6.1 — La respuesta introduce obligaciones del capítulo III (gestión de riesgos, gobernanza de datos, etc.) que van más allá del contenido sustancial del artículo 6.1 citado, sin aclarar que provienen de otras disposiciones.

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['6.2', '6.3', '6.4', '80'] expected=['6.2', '6.3'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=0.92 answer_relevancy=0.90 context_precision=0.83 context_recall=1.00
- **Latency**: 344860 ms | **Cost**: 0.0580 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 6.2 como regla general de clasificación por Anexo III — La respuesta cita explícitamente el artículo 6.2 y lo identifica como la regla que establece que los sistemas del Anexo III se consideran de alto riesgo.
  - ✅ Explica la excepción del artículo 6.3 sin omitir el requisito de documentación motivada — La respuesta detalla la excepción del artículo 6.3, menciona explícitamente que el proveedor debe documentar su evaluación, y enumera las condiciones específicas que permiten la exclusión.
  - ✅ No afirma que la excepción es automática ni que exime de todos los controles — La respuesta aclara que la excepción requiere cumplir condiciones específicas y que el sistema sigue sujeto a supervisión de autoridades, evitando presentarla como automática o eximente total.

### chat-003

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['16', '17.1', '17.2', '25.1'] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.93 context_precision=0.33 context_recall=0.17
- **Latency**: 345952 ms | **Cost**: 0.0695 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — El sistema citó artículos 16, 17.1, 17.2 y 25.1, pero no incluyó los artículos 9.1 ni 9.2 que son los centrales para esta pregunta.
  - ✅ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — La respuesta afirma explícitamente que el sistema de gestión de riesgos debe 'integrar' y funcionar 'a lo largo de todo el ciclo de vida del sistema'.
  - ✅ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — La respuesta menciona 'identificación y análisis de riesgos', 'estimación y evaluación de los riesgos' y 'adopción de medidas de gestión apropiadas'.

### chat-004

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['10.1', '10.2', '10.3', '42.1'] expected=['10.1', '10.2'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=0.69 answer_relevancy=0.84 context_precision=1.00 context_recall=0.75
- **Latency**: 349141 ms | **Cost**: 0.0581 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita los artículos 10.1 y 10.2 del AI Act con su contenido sustancial — La respuesta cita explícitamente los artículos 10.1 y 10.2 y describe su contenido sustancial: requisitos de calidad de datos y prácticas de gobernanza respectivamente.
  - ✅ Menciona los requisitos de representatividad, pertinencia y libre de errores de los datasets — La respuesta identifica explícitamente los tres criterios de calidad intrínseca: pertinencia, representatividad y ausencia de errores.
  - ✅ Identifica la obligación de gobernanza que incluye detección y corrección de sesgos — La respuesta menciona claramente que las prácticas de gobernanza incluyen 'detección de sesgos' y que el eje (2) cubre 'prácticas adecuadas de gobernanza, cubriendo desde el diseño hasta la detección de sesgos'.

### chat-005

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['11.1', '11.2', '23.1', '72.3'] expected=['11.1'] precision=0.25 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.90 context_precision=1.00 context_recall=0.33
- **Latency**: 350656 ms | **Cost**: 0.0681 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 11.1 del AI Act como base de la obligación de documentación técnica — El artículo 11.1 está incluido en cited_articles y la respuesta se refiere explícitamente al AI Act como fuente de la obligación.
  - ✅ Menciona que la documentación debe elaborarse antes de la introducción en el mercado y mantenerse actualizada — La respuesta afirma textualmente que debe elaborarse 'antes de la introducción en el mercado o puesta en servicio del sistema, mantenerse actualizada'.
  - ✅ Identifica correctamente que el contenido mínimo se remite al Anexo IV del AI Act — La respuesta menciona explícitamente que 'Su contenido mínimo se recoge en el Anexo IV del Reglamento'.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=5 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
