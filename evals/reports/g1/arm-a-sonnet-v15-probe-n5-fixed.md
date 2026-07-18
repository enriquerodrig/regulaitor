# RegulAItor — Evaluation Report

**Run:** 2026-07-14T11:28:37.368948+00:00 | **Commit:** `148b514` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=full, cache hits/misses: 0/5 | **Total cost:** 0.25 €

## Aggregate metrics

| Métrica | Valor | v0.1.20-bar | Aspiracional |
|---|---|---|---|
| faithfulness_mean | 1.00 | ≥0.65 ✅ | ≥0.85 ✅ |
| answer_relevancy_mean | 0.88 | ≥0.55 ✅ | ≥0.85 ✅ |
| context_precision_mean | 0.77 | ≥0.55 ✅ | ≥0.80 ❌ (-0.03) |
| context_recall_mean | 0.52 | (info) | (info) |
| citation_precision_mean | 0.32 | ≥0.25 ✅ | ≥0.90 ❌ (-0.58) |
| citation_recall_mean | 0.70 | ≥0.60 ✅ | ≥0.80 ❌ (-0.10) |
| verdict_match_rate | 1.00 | ≥0.35 ✅ | ≥0.85 ✅ |
| severity_match_rate | 0.40 | ≥0.35 ✅ | ≥0.80 ❌ (-0.40) |
| latency_p95_ms | 916672 | ≤12000 ❌ (+904672) | (info) |
| chat_latency_p95_ms | 916672 | (info) | (info) |
| doc_latency_p95_ms | 0 | (info) | (info) |
| cost_per_chat_eur | 0.050 | ≤0.05 ❌ (+0.000) | (info) |
| cost_per_doc_eur | 0.000 | ≤0.50 ✅ | (info) |
| cost_total_eur | 0.25 | (info) | (info) |
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
- **Citations**: emitted=['2.2', '43.3', '6.1', '74.3'] expected=['6.1'] precision=0.25 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.81 context_precision=0.87 context_recall=0.33
- **Latency**: 705578 ms | **Cost**: 0.0474 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita literalmente el artículo 6.1 del AI Act o su contenido sustancial — El sistema cita explícitamente 'artículo 6.1' en la respuesta y describe su contenido sustancial sobre sistemas de alto riesgo.
  - ❌ Identifica correctamente los dos requisitos acumulativos: componente de seguridad en producto de la lista del Anexo I + evaluación de conformidad por terceros — La respuesta menciona 'dos condiciones acumulativas' pero no las especifica claramente; no explicita que ambas deben cumplirse simultáneamente (componente de seguridad + evaluación por terceros).
  - ❌ No afirma obligaciones adicionales no respaldadas por el artículo 6.1 — La respuesta afirma que 'el proveedor deberá cumplir todos los requisitos del capítulo III, sección 2' como consecuencia directa del artículo 6.1, pero esta obligación es derivada de la clasificación como alto riesgo, no del artículo 6.1 en sí mismo.

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['6.3', '80.1'] expected=['6.2', '6.3'] precision=0.50 recall=0.50
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.90 context_precision=0.75 context_recall=1.00
- **Latency**: 399171 ms | **Cost**: 0.0476 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 6.2 como regla general de clasificación por Anexo III — El artículo 6.2 no aparece en cited_articles; solo se citan 6.3 y 80.1.
  - ❌ Explica la excepción del artículo 6.3 sin omitir el requisito de documentación motivada — La respuesta menciona la excepción del 6.3 pero no explica explícitamente el requisito de documentación motivada previa a la introducción en el mercado ni su registro.
  - ✅ No afirma que la excepción es automática ni que exime de todos los controles — La respuesta aclara correctamente que la excepción requiere cumplir condiciones (no plantear riesgo importante y no influir sustancialmente) y que existe límite absoluto con la elaboración de perfiles.

### chat-003

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['16', '17.1', '17.2', '20.2'] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.93 context_precision=0.33 context_recall=0.14
- **Latency**: 393780 ms | **Cost**: 0.0601 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — El sistema citó artículos 16, 17.1, 17.2 y 20.2, pero no incluyó los artículos 9.1 ni 9.2 que son los esperados.
  - ❌ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — La respuesta no menciona explícitamente que el sistema debe funcionar a lo largo de todo el ciclo de vida del sistema de IA.
  - ✅ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — La respuesta menciona identificación de riesgos, evaluación de riesgos y adopción de medidas correctoras/mitigación.

### chat-004

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['10.1', '10.2', '10.4', '10.6'] expected=['10.1', '10.2'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.88 context_precision=0.92 context_recall=0.75
- **Latency**: 391390 ms | **Cost**: 0.0484 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita los artículos 10.1 y 10.2 del AI Act con su contenido sustancial — La respuesta no cita explícitamente los artículos 10.1 y 10.2 ni reproduce su contenido sustancial; solo alude genéricamente a 'requisitos específicos' sin referencia directa a estos artículos.
  - ❌ Menciona los requisitos de representatividad, pertinencia y libre de errores de los datasets — La respuesta no menciona explícitamente los requisitos de representatividad, pertinencia o la exigencia de estar libres de errores e incompletos que establece el artículo 10.1.
  - ✅ Identifica la obligación de gobernanza que incluye detección y corrección de sesgos — La respuesta menciona explícitamente 'detección activa de sesgos' como parte de los requisitos de gobernanza y gestión de datos.

### chat-005

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['11.1', '11.2', '11.3'] expected=['11.1'] precision=0.33 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.89 context_precision=1.00 context_recall=0.38
- **Latency**: 404015 ms | **Cost**: 0.0487 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 11.1 del AI Act como base de la obligación de documentación técnica — El artículo 11.1 está incluido en cited_articles y la respuesta se refiere explícitamente al AI Act como fuente de la obligación.
  - ✅ Menciona que la documentación debe elaborarse antes de la introducción en el mercado y mantenerse actualizada — La respuesta afirma textualmente que debe elaborarse 'antes de introducir el sistema en el mercado o ponerlo en servicio' y 'debe mantenerla actualizada'.
  - ✅ Identifica correctamente que el contenido mínimo se remite al Anexo IV del AI Act — La respuesta menciona explícitamente que 'Su contenido mínimo está fijado por el Anexo IV del Reglamento'.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=5 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
