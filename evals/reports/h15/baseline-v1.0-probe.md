# RegulAItor — Evaluation Report

**Run:** 2026-05-18T19:55:44.343893+00:00 | **Commit:** `b0e6842` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=first 3, cache hits/misses: 0/3 | **Total cost:** 0.23 €

## Aggregate metrics

| Métrica | Valor | Threshold | Pass |
|---|---|---|---|
| faithfulness_mean | 0.67 | ≥0.85 | ❌ (-0.18) |
| answer_relevancy_mean | 0.54 | ≥0.85 | ❌ (-0.31) |
| context_precision_mean | 0.61 | ≥0.80 | ❌ (-0.19) |
| context_recall_mean | 0.44 | (info) | ➖ |
| citation_precision_mean | 0.25 | ≥0.90 | ❌ (-0.65) |
| citation_recall_mean | 0.67 | ≥0.80 | ❌ (-0.13) |
| verdict_match_rate | 0.33 | ≥0.85 | ❌ (-0.52) |
| severity_match_rate | 0.00 | ≥0.80 | ❌ (-0.80) |
| latency_p95_ms | 1320002 | ≤12000 | ❌ (+1308002) |
| chat_latency_p95_ms | 1320002 | (info) | ➖ |
| doc_latency_p95_ms | 0 | (info) | ➖ |
| cost_per_chat_eur | 0.078 | ≤0.05 | ❌ (+0.028) |
| cost_per_doc_eur | 0.000 | ≤0.50 | ✅ |
| cost_total_eur | 0.23 | (info) | ➖ |
| cache_hit_rate | 0.00 | (info) | ➖ |

## Per-case appendix — chat (3 cases)

### chat-001

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['105', '2.2', '25.3', '6.1'] expected=['6.1'] precision=0.25 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.75 context_precision=1.00 context_recall=0.33
- **Latency**: 1290938 ms | **Cost**: 0.0523 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita literalmente el artículo 6.1 del AI Act o su contenido sustancial — La respuesta cita explícitamente 'Artículo 6.1' y reproduce su contenido sustancial sobre la clasificación de alto riesgo.
  - ✅ Identifica correctamente los dos requisitos acumulativos: componente de seguridad en producto de la lista del Anexo I + evaluación de conformidad por terceros — La respuesta enumera claramente las dos condiciones acumulativas: (1) componente de seguridad en producto del Anexo I, y (2) evaluación de conformidad por terceros.
  - ❌ No afirma obligaciones adicionales no respaldadas por el artículo 6.1 — La respuesta menciona 'obligaciones aplican' y variaciones según secciones A/B del Anexo I sin citar artículos específicos que respalden estas afirmaciones adicionales más allá del 6.1.

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['6.2', '6.3', '6.4', '80'] expected=['6.2', '6.3'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.87 context_precision=0.83 context_recall=1.00
- **Latency**: 1254608 ms | **Cost**: 0.0918 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 6.2 como regla general de clasificación por Anexo III — El sistema cita el artículo 6.2 en la lista de artículos citados y lo menciona implícitamente al referirse a la clasificación automática de sistemas del Anexo III como de alto riesgo.
  - ✅ Explica la excepción del artículo 6.3 sin omitir el requisito de documentación motivada — La respuesta explica la excepción del artículo 6.3, detalla las condiciones para acogerse a ella, y subraya explícitamente que 'debe documentar formalmente esa evaluación antes de comercializar o poner en servicio el sistema'.
  - ✅ No afirma que la excepción es automática ni que exime de todos los controles — La respuesta aclara que 'no implica automáticamente' y que existe un 'límite absoluto' (elaboración de perfiles), además de mencionar obligaciones de registro y supervisión por autoridades.

### chat-003

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`None` expected=`high` ❌
- **Citations**: emitted=[] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.00 answer_relevancy=0.00 context_precision=0.00 context_recall=0.00
- **Latency**: 641125 ms | **Cost**: 0.0899 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — La respuesta actual está vacía; no cita ningún artículo ni proporciona contenido sustancial.
  - ❌ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — La respuesta actual está vacía; no contiene información sobre el carácter continuo o el ciclo de vida.
  - ❌ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — La respuesta actual está vacía; no identifica ninguno de los elementos obligatorios requeridos.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=3 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
