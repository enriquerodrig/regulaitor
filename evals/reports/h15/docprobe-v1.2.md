# RegulAItor — Evaluation Report

**Run:** 2026-05-19T06:16:17.264473+00:00 | **Commit:** `74efa27` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=full, cache hits/misses: 0/1 | **Total cost:** 0.00 €

## Aggregate metrics

| Métrica | Valor | Threshold | Pass |
|---|---|---|---|
| faithfulness_mean | 0.00 | ≥0.85 | ❌ (-0.85) |
| answer_relevancy_mean | 0.00 | ≥0.85 | ❌ (-0.85) |
| context_precision_mean | 0.00 | ≥0.80 | ❌ (-0.80) |
| context_recall_mean | 0.00 | (info) | ➖ |
| citation_precision_mean | 0.00 | ≥0.90 | ❌ (-0.90) |
| citation_recall_mean | 0.00 | ≥0.80 | ❌ (-0.80) |
| verdict_match_rate | 1.00 | ≥0.85 | ✅ |
| severity_match_rate | 0.00 | ≥0.80 | ❌ (-0.80) |
| latency_p95_ms | 345031 | ≤12000 | ❌ (+333031) |
| chat_latency_p95_ms | 0 | (info) | ➖ |
| doc_latency_p95_ms | 345031 | (info) | ➖ |
| cost_per_chat_eur | 0.000 | ≤0.05 | ✅ |
| cost_per_doc_eur | 0.000 | ≤0.50 | ✅ |
| cost_total_eur | 0.00 | (info) | ➖ |
| cache_hit_rate | 0.00 | (info) | ➖ |

## Per-case appendix — chat (0 cases)

## Per-case appendix — documents (1 cases)

### doc-001

- **Verdict**: actual=`requires_human_review` expected=`requires_human_review` ✅
- **Segments**: actual=0 expected=5 ❌
- **Findings citations**: emitted=[] expected=['6.1', '6.2', '9.1'] precision=0.00 recall=0.00
- **Faithfulness**: 0.00
- **Latency total**: 345031 ms | **Cost**: 0.0000 € | **Cache hit**: False
- **Criteria**:
  - ❌ Identifica la ausencia de clasificación formal de riesgo según el AI Act (artículo 6.1 / 6.2) para los sistemas listados — La respuesta está vacía; no identifica ninguna ausencia de clasificación de riesgo ni cita los artículos 6.1 o 6.2.
  - ❌ Cita el artículo 9.1 en hallazgos indicando la falta de sistema de gestión de riesgos documentado — La respuesta está vacía y no contiene cita alguna al artículo 9.1 ni hallazgo sobre gestión de riesgos.
  - ❌ Severidad reportada coherente con alto riesgo no gestionado (medium o high) — La respuesta está vacía; no hay severidad reportada ni evaluación de riesgo.

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=1 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
