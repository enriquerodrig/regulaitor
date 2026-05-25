# RegulAItor — Evaluation Report

**Run:** 2026-05-24T22:30:03.097559+00:00 | **Commit:** `f2d10eb` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=full, cache hits/misses: 0/5 | **Total cost:** 0.00 €

## Aggregate metrics

| Métrica | Valor | v0.1.20-bar | Aspiracional |
|---|---|---|---|
| faithfulness_mean | 0.00 | ≥0.65 ❌ (-0.65) | ≥0.85 ❌ (-0.85) |
| answer_relevancy_mean | 0.00 | ≥0.55 ❌ (-0.55) | ≥0.85 ❌ (-0.85) |
| context_precision_mean | 0.00 | ≥0.55 ❌ (-0.55) | ≥0.80 ❌ (-0.80) |
| context_recall_mean | 0.00 | (info) | (info) |
| citation_precision_mean | 0.00 | ≥0.25 ❌ (-0.25) | ≥0.90 ❌ (-0.90) |
| citation_recall_mean | 0.00 | ≥0.60 ❌ (-0.60) | ≥0.80 ❌ (-0.80) |
| verdict_match_rate | 0.00 | ≥0.35 ❌ (-0.35) | ≥0.85 ❌ (-0.85) |
| severity_match_rate | 0.00 | ≥0.35 ❌ (-0.35) | ≥0.80 ❌ (-0.80) |
| latency_p95_ms | 396137 | ≤12000 ❌ (+384137) | (info) |
| chat_latency_p95_ms | 396137 | (info) | (info) |
| doc_latency_p95_ms | 0 | (info) | (info) |
| cost_per_chat_eur | 0.000 | ≤0.05 ✅ | (info) |
| cost_per_doc_eur | 0.000 | ≤0.50 ✅ | (info) |
| cost_total_eur | 0.00 | (info) | (info) |
| cache_hit_rate | 0.00 | (info) | (info) |

## Caveats — v0.1.20-bar reading

1. **Aspirational column** = CLAUDE.md §17 long-term ideal targets; no run has ever hit them; they remain as direction-setting, not as v0.1.20 ship gate.
2. **v0.1.20-bar column** = anchored to H10 (full-30-case measured baseline) + H15 v1.2 (30-case partial intervention measurement); the 64-case set is harder so even matching the bar is meaningful evidence the maximalist-plan stack didn't regress on the easier subset.
3. **Judge family stays Haiku 4.5** per ADR-0010 D1 caveat (same vendor as production Sonnet, different model class). Cross-vendor migration deferred to HX (post-TFM); §19 satisfied literally; documented honestly.
4. **Latency p95** number remains contaminated by batch+rate-limit+tenacity backoff per H8 amendment + §17 note; v0.1.16 does NOT fix this. H17 LangFuse refactor is the proper instrument; until then `latency_p95_ms` is informational despite being formally gated in the report.

## Per-case appendix — chat (5 cases)

### chat-001

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`None` expected=`medium` ❌
- **Citations**: emitted=[] expected=['6.1'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.00 answer_relevancy=0.00 context_precision=0.00 context_recall=0.00
- **Latency**: 372578 ms | **Cost**: 0.0000 € | **Cache hit**: False
- **Criteria**:

### chat-002

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`None` expected=`medium` ❌
- **Citations**: emitted=[] expected=['6.2', '6.3'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.00 answer_relevancy=0.00 context_precision=0.00 context_recall=0.00
- **Latency**: 333390 ms | **Cost**: 0.0000 € | **Cache hit**: False
- **Criteria**:

### chat-003

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`None` expected=`high` ❌
- **Citations**: emitted=[] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.00 answer_relevancy=0.00 context_precision=0.00 context_recall=0.00
- **Latency**: 331547 ms | **Cost**: 0.0000 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — La respuesta actual está vacía; no cita ningún artículo ni proporciona contenido sustancial.
  - ❌ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — La respuesta actual está vacía; no contiene información sobre el carácter continuo o el ciclo de vida.
  - ❌ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — La respuesta actual está vacía; no identifica ninguno de los elementos obligatorios requeridos.

### chat-004

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`None` expected=`high` ❌
- **Citations**: emitted=[] expected=['10.1', '10.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.00 answer_relevancy=0.00 context_precision=0.00 context_recall=0.00
- **Latency**: 336030 ms | **Cost**: 0.0000 € | **Cache hit**: False
- **Criteria**:

### chat-005

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`None` expected=`medium` ❌
- **Citations**: emitted=[] expected=['11.1'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.00 answer_relevancy=0.00 context_precision=0.00 context_recall=0.00
- **Latency**: 338922 ms | **Cost**: 0.0000 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 11.1 del AI Act como base de la obligación de documentación técnica — La respuesta está vacía; no cita ningún artículo.
  - ❌ Menciona que la documentación debe elaborarse antes de la introducción en el mercado y mantenerse actualizada — La respuesta está vacía; no contiene información sobre cuándo debe elaborarse la documentación.
  - ❌ Identifica correctamente que el contenido mínimo se remite al Anexo IV del AI Act — La respuesta está vacía; no menciona el Anexo IV ni sus contenidos.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=5 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
