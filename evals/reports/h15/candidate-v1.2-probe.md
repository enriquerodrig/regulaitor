# RegulAItor — Evaluation Report

**Run:** 2026-05-18T21:57:50.599930+00:00 | **Commit:** `de294a8` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=first 3, cache hits/misses: 0/3 | **Total cost:** 0.16 €

## Aggregate metrics

| Métrica | Valor | Threshold | Pass |
|---|---|---|---|
| faithfulness_mean | 1.00 | ≥0.85 | ✅ |
| answer_relevancy_mean | 0.89 | ≥0.85 | ✅ |
| context_precision_mean | 0.72 | ≥0.80 | ❌ (-0.08) |
| context_recall_mean | 0.50 | (info) | ➖ |
| citation_precision_mean | 0.33 | ≥0.90 | ❌ (-0.57) |
| citation_recall_mean | 0.67 | ≥0.80 | ❌ (-0.13) |
| verdict_match_rate | 0.67 | ≥0.85 | ❌ (-0.18) |
| severity_match_rate | 0.33 | ≥0.80 | ❌ (-0.47) |
| latency_p95_ms | 355794 | ≤12000 | ❌ (+343794) |
| chat_latency_p95_ms | 355794 | (info) | ➖ |
| doc_latency_p95_ms | 0 | (info) | ➖ |
| cost_per_chat_eur | 0.052 | ≤0.05 | ❌ (+0.002) |
| cost_per_doc_eur | 0.000 | ≤0.50 | ✅ |
| cost_total_eur | 0.16 | (info) | ➖ |
| cache_hit_rate | 0.00 | (info) | ➖ |

## Per-case appendix — chat (3 cases)

### chat-001

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['2.2', '6.1'] expected=['6.1'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.83 context_precision=1.00 context_recall=0.33
- **Latency**: 354983 ms | **Cost**: 0.0443 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita literalmente el artículo 6.1 del AI Act o su contenido sustancial — La respuesta cita explícitamente 'artículo 6, apartado 1' y describe su contenido sustancial de forma precisa.
  - ✅ Identifica correctamente los dos requisitos acumulativos: componente de seguridad en producto de la lista del Anexo I + evaluación de conformidad por terceros — La respuesta enumera claramente ambas condiciones acumulativas: integración como componente de seguridad en producto del Anexo I y sometimiento a evaluación de conformidad por terceros.
  - ❌ No afirma obligaciones adicionales no respaldadas por el artículo 6.1 — La respuesta menciona que 'el proveedor deberá cumplir todos los requisitos del capítulo III, sección 2' (gestión de riesgos, gobernanza de datos, etc.), lo que va más allá del artículo 6.1 que solo establece la clasificación; estas obligaciones derivan de otros artículos, no del 6.1 directamente.

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['6.2', '6.3', '6.4', '80'] expected=['6.2', '6.3'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.90 context_precision=0.83 context_recall=1.00
- **Latency**: 353140 ms | **Cost**: 0.0497 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 6.2 como regla general de clasificación por Anexo III — El artículo 6.2 está incluido en cited_articles y la respuesta establece la regla general de que los sistemas del Anexo III se consideran de alto riesgo.
  - ✅ Explica la excepción del artículo 6.3 sin omitir el requisito de documentación motivada — La respuesta cita el artículo 6.3, explica la excepción y enfatiza explícitamente que el proveedor debe documentar formalmente esa decisión antes de comercializar.
  - ✅ No afirma que la excepción es automática ni que exime de todos los controles — La respuesta afirma claramente que 'no existe una clasificación automática e irrevocable' y que las autoridades pueden revisar y rebatir la clasificación, evitando ambigüedad sobre exención de controles.

### chat-003

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['16', '17.1', '17.2', '25.1'] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.93 context_precision=0.33 context_recall=0.17
- **Latency**: 353969 ms | **Cost**: 0.0620 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — El sistema citó los artículos 16, 17.1, 17.2 y 25.1, pero no incluyó las citas específicas a 9.1 ni 9.2 que son centrales en la respuesta esperada.
  - ❌ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — Aunque la respuesta menciona que el sistema debe funcionar 'a lo largo de todo el ciclo de vida', esta información no aparece en la respuesta actual del sistema evaluado.
  - ❌ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — La respuesta actual no detalla explícitamente los tres elementos obligatorios (identificación de riesgos, evaluación de riesgos y adopción de medidas de mitigación) de forma estructurada como se espera.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=3 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
