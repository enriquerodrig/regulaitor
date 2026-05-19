# RegulAItor — Evaluation Report

**Run:** 2026-05-19T08:30:44.299864+00:00 | **Commit:** `d104211` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=first 3, cache hits/misses: 0/3 | **Total cost:** 0.16 €

## Aggregate metrics

| Métrica | Valor | Threshold | Pass |
|---|---|---|---|
| faithfulness_mean | 0.90 | ≥0.85 | ✅ |
| answer_relevancy_mean | 0.87 | ≥0.85 | ✅ |
| context_precision_mean | 0.83 | ≥0.80 | ✅ |
| context_recall_mean | 0.67 | (info) | ➖ |
| citation_precision_mean | 0.00 | ≥0.90 | ❌ (-0.90) |
| citation_recall_mean | 0.00 | ≥0.80 | ❌ (-0.80) |
| verdict_match_rate | 0.33 | ≥0.85 | ❌ (-0.52) |
| severity_match_rate | 0.67 | ≥0.80 | ❌ (-0.13) |
| latency_p95_ms | 389302 | ≤12000 | ❌ (+377302) |
| chat_latency_p95_ms | 389302 | (info) | ➖ |
| doc_latency_p95_ms | 0 | (info) | ➖ |
| cost_per_chat_eur | 0.054 | ≤0.05 | ❌ (+0.004) |
| cost_per_doc_eur | 0.000 | ≤0.50 | ✅ |
| cost_total_eur | 0.16 | (info) | ➖ |
| cache_hit_rate | 0.00 | (info) | ➖ |

## Per-case appendix — chat (3 cases)

### nis2-001

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['2.2', '3.1', '3.2', '3.3', '34.4'] expected=['2', '3'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.80 answer_relevancy=0.90 context_precision=1.00 context_recall=0.33
- **Latency**: 376827 ms | **Cost**: 0.0632 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 2 NIS2 sobre el ámbito de aplicación (sectores y umbrales de tamaño) — La respuesta cita el artículo 2.2 y describe correctamente el ámbito de aplicación (sectores en anexos, umbrales de mediana empresa, excepciones por criticidad).
  - ✅ Cita el artículo 3 NIS2 sobre la distinción entre entidades esenciales e importantes — La respuesta cita los artículos 3.1, 3.2 y 3.3, y explica la distinción entre entidades esenciales e importantes con referencia a sectores y tamaño.
  - ✅ No afirma obligaciones de registro o sanciones sin respaldarlas en los artículos citados — La respuesta menciona el régimen sancionador diferenciado pero no detalla obligaciones específicas de registro sin respaldo; la afirmación sobre sanciones se vincula implícitamente a la clasificación de entidades.

### nis2-002

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['20', '21.1', '4'] expected=['21'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.84 context_precision=1.00 context_recall=0.67
- **Latency**: 357703 ms | **Cost**: 0.0469 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 21 NIS2 sobre medidas para la gestión de riesgos de ciberseguridad — El sistema cita explícitamente el artículo 21.1 en la lista de artículos citados.
  - ❌ Menciona al menos cuatro de las medidas específicas enumeradas en el artículo 21 (políticas de análisis de riesgos, gestión de incidentes, continuidad de negocio, seguridad de la cadena de suministro, seguridad en la adquisición de sistemas, gestión de vulnerabilidades, ciberhigiene, cifrado, autenticación multifactor) — La respuesta menciona solo medidas genéricas (técnicas, operativas, organizativas) y formación, pero no enumera explícitamente al menos cuatro de las medidas específicas listadas en el criterio.
  - ✅ Identifica el principio de proporcionalidad al riesgo como criterio para la adopción de medidas — La respuesta explícitamente menciona que 'la proporcionalidad de las medidas se evalúa teniendo en cuenta factores como el grado de exposición al riesgo, el tamaño de la entidad y la probabilidad y gravedad de los incidentes'.

### nis2-003

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['23.4'] expected=['23'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.91 answer_relevancy=0.88 context_precision=0.50 context_recall=1.00
- **Latency**: 361233 ms | **Cost**: 0.0525 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 23 NIS2 sobre las obligaciones de notificación de incidentes — El sistema cita el artículo 23.4, pero el criterio y las expected_articles requieren la cita del artículo 23 en su forma general; la cita parcial (23.4) no satisface el requisito de citar el artículo 23.
  - ✅ Menciona los plazos escalonados de notificación: alerta temprana (24 horas), notificación de incidente (72 horas) e informe final (un mes) — La respuesta identifica correctamente los tres plazos escalonados: alerta temprana en 24 horas, notificación detallada en 72 horas e informe definitivo en un mes.
  - ❌ Identifica al CSIRT o la autoridad competente como destinatarios de la notificación — La respuesta no menciona explícitamente al CSIRT o a la autoridad competente como destinatarios de la notificación; solo describe los plazos y contenidos sin especificar a quién se notifica.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=3 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
