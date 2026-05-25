# RegulAItor — Evaluation Report

**Run:** 2026-05-25T15:11:34.224712+00:00 | **Commit:** `f2d10eb` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=full, cache hits/misses: 0/5 | **Total cost:** 0.32 €

## Aggregate metrics

| Métrica | Valor | v0.1.20-bar | Aspiracional |
|---|---|---|---|
| faithfulness_mean | 0.97 | ≥0.65 ✅ | ≥0.85 ✅ |
| answer_relevancy_mean | 0.87 | ≥0.55 ✅ | ≥0.85 ✅ |
| context_precision_mean | 0.77 | ≥0.55 ✅ | ≥0.80 ❌ (-0.03) |
| context_recall_mean | 0.52 | (info) | (info) |
| citation_precision_mean | 0.28 | ≥0.25 ✅ | ≥0.90 ❌ (-0.62) |
| citation_recall_mean | 0.70 | ≥0.60 ✅ | ≥0.80 ❌ (-0.10) |
| verdict_match_rate | 0.60 | ≥0.35 ✅ | ≥0.85 ❌ (-0.25) |
| severity_match_rate | 0.40 | ≥0.35 ✅ | ≥0.80 ❌ (-0.40) |
| latency_p95_ms | 407740 | ≤12000 ❌ (+395740) | (info) |
| chat_latency_p95_ms | 407740 | (info) | (info) |
| doc_latency_p95_ms | 0 | (info) | (info) |
| cost_per_chat_eur | 0.063 | ≤0.05 ❌ (+0.013) | (info) |
| cost_per_doc_eur | 0.000 | ≤0.50 ✅ | (info) |
| cost_total_eur | 0.32 | (info) | (info) |
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
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.76 context_precision=1.00 context_recall=0.33
- **Latency**: 383688 ms | **Cost**: 0.0582 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita literalmente el artículo 6.1 del AI Act o su contenido sustancial — El sistema cita explícitamente el artículo 6.1 en la lista de artículos citados y su respuesta refleja el contenido sustancial del requisito de alto riesgo para componentes de seguridad.
  - ✅ Identifica correctamente los dos requisitos acumulativos: componente de seguridad en producto de la lista del Anexo I + evaluación de conformidad por terceros — La respuesta identifica claramente ambas condiciones acumulativas: (1) componente de seguridad en producto del Anexo I, y (2) evaluación de conformidad de terceros requerida.
  - ❌ No afirma obligaciones adicionales no respaldadas por el artículo 6.1 — La respuesta menciona que 'el régimen de obligaciones aplicable puede variar dependiendo de si el producto está recogido en la sección A o la sección B del Anexo I', lo cual introduce una distinción no explícita en el artículo 6.1 y va más allá de lo que ese artículo establece.

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['6.3', '6.4', '80.1'] expected=['6.2', '6.3'] precision=0.33 recall=0.50
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.88 context_precision=0.83 context_recall=1.00
- **Latency**: 339390 ms | **Cost**: 0.0546 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 6.2 como regla general de clasificación por Anexo III — El artículo 6.2 no aparece en cited_articles; solo se citan 6.3, 6.4 y 80.1.
  - ✅ Explica la excepción del artículo 6.3 sin omitir el requisito de documentación motivada — La respuesta menciona explícitamente que la excepción requiere 'documentación adecuada' y que debe 'documentarse' la evaluación, cumpliendo el requisito de documentación motivada.
  - ✅ No afirma que la excepción es automática ni que exime de todos los controles — La respuesta afirma claramente que 'esta clasificación no es automática e irrefutable' y que 'la excepción no es automática', evitando ambas afirmaciones prohibidas.

### chat-003

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['16', '17.1', '17.2', '25.1'] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.91 answer_relevancy=0.93 context_precision=0.00 context_recall=0.17
- **Latency**: 349327 ms | **Cost**: 0.0711 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — El sistema citó los artículos 16, 17.1, 17.2 y 25.1, pero no incluyó los artículos 9.1 ni 9.2 que son centrales para responder la pregunta sobre gestión de riesgos.
  - ✅ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — La respuesta afirma explícitamente que el sistema de gestión de riesgos debe 'integrar' y funcionar 'a lo largo de todo el ciclo de vida del sistema de IA'.
  - ✅ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — La respuesta menciona 'identificación y análisis de riesgos', 'estimación y evaluación de los riesgos' y 'adopción de medidas de gestión apropiadas', cubriendo los tres elementos.

### chat-004

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['10.1', '10.2', '10.3', '42.1'] expected=['10.1', '10.2'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=0.94 answer_relevancy=0.88 context_precision=1.00 context_recall=0.75
- **Latency**: 342889 ms | **Cost**: 0.0615 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita los artículos 10.1 y 10.2 del AI Act con su contenido sustancial — La respuesta cita explícitamente los artículos 10.1 y 10.2 y describe su contenido sustancial: requisitos de calidad de datos y prácticas de gobernanza.
  - ✅ Menciona los requisitos de representatividad, pertinencia y libre de errores de los datasets — La respuesta enumera explícitamente que los conjuntos deben ser 'pertinentes, suficientemente representativos, libres de errores en la mayor medida posible'.
  - ✅ Identifica la obligación de gobernanza que incluye detección y corrección de sesgos — La respuesta menciona claramente 'el examen de posibles sesgos' y 'las medidas para mitigar dichos sesgos' como parte de las prácticas de gobernanza requeridas.

### chat-005

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['11.1', '11.2', '23.1', '72.3'] expected=['11.1'] precision=0.25 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.90 context_precision=1.00 context_recall=0.33
- **Latency**: 345921 ms | **Cost**: 0.0703 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 11.1 del AI Act como base de la obligación de documentación técnica — El artículo 11.1 está presente en la lista de artículos citados por el sistema.
  - ✅ Menciona que la documentación debe elaborarse antes de la introducción en el mercado y mantenerse actualizada — La respuesta afirma explícitamente que la documentación 'debe elaborarse antes de la introducción en el mercado o puesta en servicio del sistema y mantenerse actualizada'.
  - ✅ Identifica correctamente que el contenido mínimo se remite al Anexo IV del AI Act — La respuesta menciona que 'El contenido mínimo está determinado por el Anexo IV del Reglamento'.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=5 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
