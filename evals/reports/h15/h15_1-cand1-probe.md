# RegulAItor — Evaluation Report

**Run:** 2026-05-19T17:39:44.633336+00:00 | **Commit:** `1e5d82f` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=first 3, cache hits/misses: 0/3 | **Total cost:** 0.16 €

## Aggregate metrics

| Métrica | Valor | Threshold | Pass |
|---|---|---|---|
| faithfulness_mean | 0.89 | ≥0.85 | ✅ |
| answer_relevancy_mean | 0.88 | ≥0.85 | ✅ |
| context_precision_mean | 0.72 | ≥0.80 | ❌ (-0.08) |
| context_recall_mean | 0.50 | (info) | ➖ |
| citation_precision_mean | 0.28 | ≥0.90 | ❌ (-0.62) |
| citation_recall_mean | 0.67 | ≥0.80 | ❌ (-0.13) |
| verdict_match_rate | 0.67 | ≥0.85 | ❌ (-0.18) |
| severity_match_rate | 0.33 | ≥0.80 | ❌ (-0.47) |
| latency_p95_ms | 439380 | ≤12000 | ❌ (+427380) |
| chat_latency_p95_ms | 439380 | (info) | ➖ |
| doc_latency_p95_ms | 0 | (info) | ➖ |
| cost_per_chat_eur | 0.054 | ≤0.05 | ❌ (+0.004) |
| cost_per_doc_eur | 0.000 | ≤0.50 | ✅ |
| cost_total_eur | 0.16 | (info) | ➖ |
| cache_hit_rate | 0.00 | (info) | ➖ |

## Per-case appendix — chat (3 cases)

### chat-001

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['2.2', '25.3', '6.1'] expected=['6.1'] precision=0.33 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.81 context_precision=1.00 context_recall=0.33
- **Latency**: 426968 ms | **Cost**: 0.0498 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita literalmente el artículo 6.1 del AI Act o su contenido sustancial — El artículo 6.1 aparece en la lista de artículos citados y su contenido sustancial se reproduce en la respuesta.
  - ✅ Identifica correctamente los dos requisitos acumulativos: componente de seguridad en producto de la lista del Anexo I + evaluación de conformidad por terceros — La respuesta explícitamente enumera ambas condiciones acumulativas: ser componente de seguridad de producto en Anexo I y estar sujeto a evaluación de conformidad por terceros.
  - ❌ No afirma obligaciones adicionales no respaldadas por el artículo 6.1 — La respuesta introduce obligaciones del artículo 16 y requisitos del capítulo III sección 2 que van más allá del alcance del artículo 6.1, que solo establece la clasificación como alto riesgo.

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['6.2', '6.3', '6.4', '80'] expected=['6.2', '6.3'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=0.89 answer_relevancy=0.90 context_precision=0.83 context_recall=1.00
- **Latency**: 407547 ms | **Cost**: 0.0503 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 6.2 como regla general de clasificación por Anexo III — La respuesta cita explícitamente el artículo 6.2 y establece que los sistemas del Anexo III se consideran de alto riesgo como regla general.
  - ✅ Explica la excepción del artículo 6.3 sin omitir el requisito de documentación motivada — La respuesta detalla la excepción del artículo 6.3, menciona explícitamente que el proveedor debe documentar la evaluación antes de comercializar, y especifica las condiciones alternativas que permiten la exclusión.
  - ✅ No afirma que la excepción es automática ni que exime de todos los controles — La respuesta aclara que la excepción requiere documentación previa, que las autoridades pueden revisar la clasificación, y que existen límites absolutos (como el caso de elaboración de perfiles), evitando presentarla como automática o eximente total.

### chat-003

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['16', '17.1', '17.2', '25.1'] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.78 answer_relevancy=0.93 context_precision=0.33 context_recall=0.17
- **Latency**: 411453 ms | **Cost**: 0.0613 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — El sistema citó los artículos 16, 17.1, 17.2 y 25.1, pero no incluyó los artículos 9.1 ni 9.2 que son centrales para responder la pregunta.
  - ❌ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — La respuesta no menciona explícitamente que el sistema debe funcionar a lo largo de todo el ciclo de vida del sistema de IA.
  - ❌ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — Aunque menciona 'identificación y análisis de riesgos' de forma genérica, no detalla explícitamente los tres elementos obligatorios (identificación, evaluación y medidas de mitigación) como componentes estructurados del sistema de gestión de riesgos.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=3 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
