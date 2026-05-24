# RegulAItor — Evaluation Report

**Run:** 2026-05-23T09:17:04.946736+00:00 | **Commit:** `d3e40ca` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=full, cache hits/misses: 0/5 | **Total cost:** 0.29 €

## Aggregate metrics

| Métrica | Valor | v0.1.20-bar | Aspiracional |
|---|---|---|---|
| faithfulness_mean | 0.85 | ≥0.65 ✅ | ≥0.85 ❌ (-0.00) |
| answer_relevancy_mean | 0.86 | ≥0.55 ✅ | ≥0.85 ✅ |
| context_precision_mean | 0.83 | ≥0.55 ✅ | ≥0.80 ✅ |
| context_recall_mean | 0.52 | (info) | (info) |
| citation_precision_mean | 0.28 | ≥0.25 ✅ | ≥0.90 ❌ (-0.62) |
| citation_recall_mean | 0.70 | ≥0.60 ✅ | ≥0.80 ❌ (-0.10) |
| verdict_match_rate | 0.80 | ≥0.35 ✅ | ≥0.85 ❌ (-0.05) |
| severity_match_rate | 0.40 | ≥0.35 ✅ | ≥0.80 ❌ (-0.40) |
| latency_p95_ms | 431356 | ≤12000 ❌ (+419356) | (info) |
| chat_latency_p95_ms | 431356 | (info) | (info) |
| doc_latency_p95_ms | 0 | (info) | (info) |
| cost_per_chat_eur | 0.059 | ≤0.05 ❌ (+0.009) | (info) |
| cost_per_doc_eur | 0.000 | ≤0.50 ✅ | (info) |
| cost_total_eur | 0.29 | (info) | (info) |
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
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.89 context_precision=1.00 context_recall=0.33
- **Latency**: 416000 ms | **Cost**: 0.0549 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita literalmente el artículo 6.1 del AI Act o su contenido sustancial — El sistema cita explícitamente 'artículo 6, apartado 1' y menciona la integración como componente de seguridad en productos de legislación de armonización.
  - ❌ Identifica correctamente los dos requisitos acumulativos: componente de seguridad en producto de la lista del Anexo I + evaluación de conformidad por terceros — La respuesta menciona 'dos condiciones acumulativas' pero no especifica explícitamente la evaluación de conformidad por terceros como segundo requisito; solo alude vagamente a 'variación según sección A o B del Anexo I'.
  - ❌ No afirma obligaciones adicionales no respaldadas por el artículo 6.1 — La respuesta no detalla obligaciones específicas del capítulo III sección 2 (gestión de riesgos, gobernanza de datos, etc.), pero tampoco las afirma como derivadas directamente del art. 6.1; sin embargo, la mención de 'régimen normativo aplicable puede variar' es imprecisa y potencialmente contradice la clasificación uniforme de alto riesgo.

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['6.3', '6.4', '80'] expected=['6.2', '6.3'] precision=0.33 recall=0.50
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.89 context_precision=0.83 context_recall=1.00
- **Latency**: 390530 ms | **Cost**: 0.0522 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 6.2 como regla general de clasificación por Anexo III — El artículo 6.2 no aparece en la lista de artículos citados (6.3, 6.4, 80); la respuesta no cita explícitamente la regla general del 6.2.
  - ✅ Explica la excepción del artículo 6.3 sin omitir el requisito de documentación motivada — La respuesta explica la excepción del 6.3, detalla las condiciones alternativas y menciona explícitamente la documentación de la evaluación antes de comercializar y su registro conforme al artículo 49.2.
  - ✅ No afirma que la excepción es automática ni que exime de todos los controles — La respuesta deja claro que la excepción requiere que el proveedor 'concluya' y 'documente' su evaluación, y que queda sujeto a supervisión; no la presenta como automática ni eximente.

### chat-003

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['16', '17.1', '17.2'] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.83 answer_relevancy=0.93 context_precision=0.33 context_recall=0.17
- **Latency**: 390188 ms | **Cost**: 0.0612 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — La respuesta cita los artículos 16 y 17, pero no cita los artículos 9.1 y 9.2 que son los directamente aplicables a la gestión de riesgos.
  - ❌ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — La respuesta no menciona explícitamente que el sistema debe funcionar a lo largo de todo el ciclo de vida del sistema de IA.
  - ❌ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — Aunque la respuesta menciona genéricamente 'sistema de gestión de riesgos', no detalla los elementos específicos de identificación, análisis, estimación y evaluación de riesgos, ni la ponderación de medidas con beneficios.

### chat-004

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['10.1', '10.2', '10.3', '42.1'] expected=['10.1', '10.2'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=0.50 answer_relevancy=0.88 context_precision=1.00 context_recall=0.75
- **Latency**: 389358 ms | **Cost**: 0.0550 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita los artículos 10.1 y 10.2 del AI Act con su contenido sustancial — La respuesta cita explícitamente los artículos 10.1 y 10.2, y describe su contenido sustancial: requisitos de calidad intrínseca (art. 10.1) y prácticas de gobernanza y gestión de datos (art. 10.2).
  - ❌ Menciona los requisitos de representatividad, pertinencia y libre de errores de los datasets — La respuesta no menciona explícitamente los requisitos de representatividad, pertinencia y libre de errores; solo alude genéricamente a 'estándares de calidad intrínseca' sin detallar estos elementos concretos.
  - ❌ Identifica la obligación de gobernanza que incluye detección y corrección de sesgos — La respuesta menciona 'prácticas de gestión y gobernanza de datos' pero no especifica explícitamente la evaluación de sesgos ni las medidas de corrección como componentes de esa gobernanza.

### chat-005

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['11.1', '11.2', '11.3', '72.3'] expected=['11.1'] precision=0.25 recall=1.00
- **RAG metrics**: faithfulness=0.90 answer_relevancy=0.71 context_precision=1.00 context_recall=0.33
- **Latency**: 394062 ms | **Cost**: 0.0717 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 11.1 del AI Act como base de la obligación de documentación técnica — La respuesta cita explícitamente el artículo 11 y la lista de artículos citados incluye 11.1.
  - ✅ Menciona que la documentación debe elaborarse antes de la introducción en el mercado y mantenerse actualizada — La respuesta afirma textualmente que la documentación 'debe elaborarse antes de la introducción en el mercado o puesta en servicio del sistema, mantenerse actualizada'.
  - ✅ Identifica correctamente que el contenido mínimo se remite al Anexo IV del AI Act — La respuesta menciona explícitamente que la documentación debe 'contener como mínimo los elementos del Anexo IV'.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=5 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
