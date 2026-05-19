# RegulAItor — Evaluation Report

**Run:** 2026-05-18T21:05:43.002611+00:00 | **Commit:** `b0e6842` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=first 3, cache hits/misses: 0/3 | **Total cost:** 0.16 €

## Aggregate metrics

| Métrica | Valor | Threshold | Pass |
|---|---|---|---|
| faithfulness_mean | 0.97 | ≥0.85 | ✅ |
| answer_relevancy_mean | 0.87 | ≥0.85 | ✅ |
| context_precision_mean | 0.61 | ≥0.80 | ❌ (-0.19) |
| context_recall_mean | 0.50 | (info) | ➖ |
| citation_precision_mean | 0.28 | ≥0.90 | ❌ (-0.62) |
| citation_recall_mean | 0.67 | ≥0.80 | ❌ (-0.13) |
| verdict_match_rate | 0.67 | ≥0.85 | ❌ (-0.18) |
| severity_match_rate | 0.33 | ≥0.80 | ❌ (-0.47) |
| latency_p95_ms | 361230 | ≤12000 | ❌ (+349230) |
| chat_latency_p95_ms | 361230 | (info) | ➖ |
| doc_latency_p95_ms | 0 | (info) | ➖ |
| cost_per_chat_eur | 0.052 | ≤0.05 | ❌ (+0.002) |
| cost_per_doc_eur | 0.000 | ≤0.50 | ✅ |
| cost_total_eur | 0.16 | (info) | ➖ |
| cache_hit_rate | 0.00 | (info) | ➖ |

## Per-case appendix — chat (3 cases)

### chat-001

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['2.2', '25.3', '6.1'] expected=['6.1'] precision=0.33 recall=1.00
- **RAG metrics**: faithfulness=0.91 answer_relevancy=0.79 context_precision=1.00 context_recall=0.33
- **Latency**: 358406 ms | **Cost**: 0.0493 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita literalmente el artículo 6.1 del AI Act o su contenido sustancial — La respuesta cita explícitamente el artículo 6.1 y describe su contenido sustancial de forma precisa.
  - ✅ Identifica correctamente los dos requisitos acumulativos: componente de seguridad en producto de la lista del Anexo I + evaluación de conformidad por terceros — La respuesta identifica claramente ambas condiciones acumulativas: integración como componente de seguridad en producto del Anexo I y sometimiento a evaluación de conformidad por terceros.
  - ❌ No afirma obligaciones adicionales no respaldadas por el artículo 6.1 — La respuesta introduce obligaciones del capítulo III sección 2 (gestión de riesgos, gobernanza de datos, documentación técnica, supervisión humana, exactitud y ciberseguridad) que van más allá del contenido del artículo 6.1, que solo establece criterios de clasificación, no requisitos operativos específicos.

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['6.2', '6.3', '6.4', '80'] expected=['6.2', '6.3'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.88 context_precision=0.83 context_recall=1.00
- **Latency**: 354875 ms | **Cost**: 0.0511 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 6.2 como regla general de clasificación por Anexo III — La respuesta establece claramente que el AI Act considera de alto riesgo los sistemas del Anexo III como regla general, aunque no cita explícitamente '6.2' en el texto, sí lo hace implícitamente al referirse a la regla general y el artículo 6.3 como excepción.
  - ✅ Explica la excepción del artículo 6.3 sin omitir el requisito de documentación motivada — La respuesta explica detalladamente la excepción del artículo 6.3, incluye las cuatro condiciones alternativas, y subraya explícitamente que 'el proveedor tiene la obligación de documentar su evaluación antes de comercializar o poner en servicio el sistema'.
  - ✅ No afirma que la excepción es automática ni que exime de todos los controles — La respuesta enfatiza que 'no se trata de una clasificación automática e inamovible', aclara que la excepción requiere acreditación y documentación, y advierte sobre la revisión de autoridades y posibles multas por elusión de requisitos.

### chat-003

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['16', '17.1', '17.2'] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.94 context_precision=0.00 context_recall=0.17
- **Latency**: 350390 ms | **Cost**: 0.0564 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — El sistema citó los artículos 16 y 17, pero no citó los artículos 9.1 ni 9.2 que son centrales para responder la pregunta sobre gestión de riesgos.
  - ❌ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — La respuesta no menciona explícitamente que el sistema de gestión de riesgos debe funcionar a lo largo de todo el ciclo de vida del sistema de IA.
  - ❌ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — Aunque la respuesta menciona gestión de riesgos, no detalla explícitamente los tres elementos obligatorios: identificación de riesgos, evaluación de riesgos y adopción de medidas de mitigación.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=3 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
