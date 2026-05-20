# RegulAItor — Evaluation Report

**Run:** 2026-05-20T10:26:35.475855+00:00 | **Commit:** `ee75033` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=first 3, cache hits/misses: 0/3 | **Total cost:** 0.19 €

## Aggregate metrics

| Métrica | Valor | Threshold | Pass |
|---|---|---|---|
| faithfulness_mean | 0.98 | ≥0.85 | ✅ |
| answer_relevancy_mean | 0.86 | ≥0.85 | ✅ |
| context_precision_mean | 0.72 | ≥0.80 | ❌ (-0.08) |
| context_recall_mean | 0.50 | (info) | ➖ |
| citation_precision_mean | 0.33 | ≥0.90 | ❌ (-0.57) |
| citation_recall_mean | 0.67 | ≥0.80 | ❌ (-0.13) |
| verdict_match_rate | 0.67 | ≥0.85 | ❌ (-0.18) |
| severity_match_rate | 0.33 | ≥0.80 | ❌ (-0.47) |
| latency_p95_ms | 662591 | ≤12000 | ❌ (+650591) |
| chat_latency_p95_ms | 662591 | (info) | ➖ |
| doc_latency_p95_ms | 0 | (info) | ➖ |
| cost_per_chat_eur | 0.062 | ≤0.05 | ❌ (+0.012) |
| cost_per_doc_eur | 0.000 | ≤0.50 | ✅ |
| cost_total_eur | 0.19 | (info) | ➖ |
| cache_hit_rate | 0.00 | (info) | ➖ |

## Per-case appendix — chat (3 cases)

### chat-001

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['2.2', '6.1'] expected=['6.1'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.76 context_precision=0.98 context_recall=0.33
- **Latency**: 612953 ms | **Cost**: 0.0520 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita literalmente el artículo 6.1 del AI Act o su contenido sustancial — La respuesta cita explícitamente 'artículo 6, apartado 1' y describe su contenido sustancial de forma precisa.
  - ✅ Identifica correctamente los dos requisitos acumulativos: componente de seguridad en producto de la lista del Anexo I + evaluación de conformidad por terceros — La respuesta identifica ambos requisitos acumulativos con claridad: integración como componente de seguridad en producto del Anexo I y evaluación de conformidad por terceros.
  - ❌ No afirma obligaciones adicionales no respaldadas por el artículo 6.1 — La respuesta menciona un régimen específico para la sección B del Anexo I sin citar artículo que lo respalde, y el artículo 6.1 no diferencia entre secciones del Anexo I.

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['6.2', '6.3', '6.4', '80'] expected=['6.2', '6.3'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=0.95 answer_relevancy=0.90 context_precision=0.83 context_recall=1.00
- **Latency**: 640530 ms | **Cost**: 0.0664 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 6.2 como regla general de clasificación por Anexo III — La respuesta cita explícitamente el artículo 6.2 y establece que los sistemas del Anexo III se consideran de alto riesgo con carácter general.
  - ✅ Explica la excepción del artículo 6.3 sin omitir el requisito de documentación motivada — La respuesta detalla la excepción del artículo 6.3, menciona explícitamente que requiere documentación antes de comercializar, y enumera las condiciones específicas que permiten la exclusión.
  - ✅ No afirma que la excepción es automática ni que exime de todos los controles — La respuesta aclara que la excepción no es automática, requiere evaluación documentada, y subraya que las autoridades pueden revisar la clasificación y exigir medidas correctoras.

### chat-003

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['16', '17.1', '17.2', '20.2', '72.2'] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.93 context_precision=0.33 context_recall=0.17
- **Latency**: 605750 ms | **Cost**: 0.0668 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — El sistema citó artículos 16, 17.1, 17.2, 20.2 y 72.2, pero no incluyó los artículos 9.1 ni 9.2 que son centrales para esta pregunta.
  - ✅ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — La respuesta afirma explícitamente que el sistema debe funcionar 'durante toda su vida útil' y describe un 'proceso continuo de identificación y análisis de riesgos'.
  - ✅ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — La respuesta menciona la identificación de riesgos, la evaluación/estimación de riesgos y la adopción de medidas correctoras/mitigación de forma clara.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=3 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
