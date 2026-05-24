# RegulAItor — Evaluation Report

**Run:** 2026-05-23T08:32:01.770978+00:00 | **Commit:** `160854b` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=full, cache hits/misses: 0/5 | **Total cost:** 0.31 €

## Aggregate metrics

| Métrica | Valor | v0.1.20-bar | Aspiracional |
|---|---|---|---|
| faithfulness_mean | 0.76 | ≥0.65 ✅ | ≥0.85 ❌ (-0.09) |
| answer_relevancy_mean | 0.68 | ≥0.55 ✅ | ≥0.85 ❌ (-0.17) |
| context_precision_mean | 0.77 | ≥0.55 ✅ | ≥0.80 ❌ (-0.03) |
| context_recall_mean | 0.48 | (info) | (info) |
| citation_precision_mean | 0.31 | ≥0.25 ✅ | ≥0.90 ❌ (-0.59) |
| citation_recall_mean | 0.80 | ≥0.60 ✅ | ≥0.80 ✅ |
| verdict_match_rate | 0.60 | ≥0.35 ✅ | ≥0.85 ❌ (-0.25) |
| severity_match_rate | 0.20 | ≥0.35 ❌ (-0.15) | ≥0.80 ❌ (-0.60) |
| latency_p95_ms | 436052 | ≤12000 ❌ (+424052) | (info) |
| chat_latency_p95_ms | 436052 | (info) | (info) |
| doc_latency_p95_ms | 0 | (info) | (info) |
| cost_per_chat_eur | 0.062 | ≤0.05 ❌ (+0.012) | (info) |
| cost_per_doc_eur | 0.000 | ≤0.50 ✅ | (info) |
| cost_total_eur | 0.31 | (info) | (info) |
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
- **RAG metrics**: faithfulness=0.78 answer_relevancy=0.80 context_precision=1.00 context_recall=0.33
- **Latency**: 433406 ms | **Cost**: 0.0499 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita literalmente el artículo 6.1 del AI Act o su contenido sustancial — La respuesta cita explícitamente el Artículo 6, apartado 1 y describe su contenido sustancial de forma precisa.
  - ✅ Identifica correctamente los dos requisitos acumulativos: componente de seguridad en producto de la lista del Anexo I + evaluación de conformidad por terceros — La respuesta identifica claramente ambos requisitos acumulativos: (1) sistema de IA como componente de seguridad de producto en Anexo I, y (2) evaluación de conformidad por terceros requerida.
  - ❌ No afirma obligaciones adicionales no respaldadas por el artículo 6.1 — La respuesta introduce obligaciones del Capítulo III, Sección 2 (gestión de riesgos, gobernanza de datos, documentación técnica, supervisión humana, exactitud y ciberseguridad) que van más allá de lo establecido en el artículo 6.1, que solo define la clasificación como alto riesgo.

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['6.2', '6.3', '6.4', '80'] expected=['6.2', '6.3'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.87 context_precision=0.83 context_recall=1.00
- **Latency**: 395969 ms | **Cost**: 0.0519 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 6.2 como regla general de clasificación por Anexo III — El artículo 6.2 aparece en la lista de artículos citados y la respuesta implícitamente reconoce que los sistemas del Anexo III se clasifican como de alto riesgo.
  - ✅ Explica la excepción del artículo 6.3 sin omitir el requisito de documentación motivada — La respuesta menciona explícitamente que la excepción requiere documentación de la evaluación antes de poner en el mercado y obligaciones de registro.
  - ✅ No afirma que la excepción es automática ni que exime de todos los controles — La respuesta aclara que la excepción tiene límites (elaboración de perfiles siempre es alto riesgo) y que las autoridades pueden revisar la clasificación e imponer multas.

### chat-003

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`None` expected=`high` ❌
- **Citations**: emitted=[] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.00 answer_relevancy=0.00 context_precision=0.00 context_recall=0.00
- **Latency**: 429625 ms | **Cost**: 0.0901 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — La respuesta actual está vacía; no cita ningún artículo ni proporciona contenido sustancial.
  - ❌ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — La respuesta actual está vacía; no contiene información sobre el carácter continuo o el ciclo de vida.
  - ❌ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — La respuesta actual está vacía; no identifica ninguno de los elementos obligatorios requeridos.

### chat-004

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['10.1', '10.2', '10.3', '42.1'] expected=['10.1', '10.2'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.76 context_precision=1.00 context_recall=0.75
- **Latency**: 408093 ms | **Cost**: 0.0482 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita los artículos 10.1 y 10.2 del AI Act con su contenido sustancial — La respuesta cita explícitamente el Artículo 10 y describe el contenido sustancial de 10.1 (datos pertinentes, representativos, libres de errores) y 10.2 (prácticas de gobernanza con decisiones de diseño, recogida, evaluación de sesgos).
  - ✅ Menciona los requisitos de representatividad, pertinencia y libre de errores de los datasets — La respuesta explícitamente menciona que los datos deben ser 'adecuados, representativos y estén libres de errores en la mayor medida posible', cubriendo los tres requisitos solicitados.
  - ✅ Identifica la obligación de gobernanza que incluye detección y corrección de sesgos — La respuesta identifica claramente la evaluación de sesgos y la 'detección y subsanación de deficiencias en los datos' como parte de las prácticas de gobernanza obligatorias.

### chat-005

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['11.1', '11.2', '11.3', '23.1', '72.3'] expected=['11.1'] precision=0.20 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.94 context_precision=1.00 context_recall=0.33
- **Latency**: 414015 ms | **Cost**: 0.0680 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 11.1 del AI Act como base de la obligación de documentación técnica — El artículo 11.1 está incluido en la lista de artículos citados por el sistema.
  - ✅ Menciona que la documentación debe elaborarse antes de la introducción en el mercado y mantenerse actualizada — La respuesta afirma explícitamente que la documentación debe elaborarse 'antes de introducir el sistema en el mercado o ponerlo en servicio' y 'mantenerse actualizada'.
  - ✅ Identifica correctamente que el contenido mínimo se remite al Anexo IV del AI Act — La respuesta menciona que 'el contenido mínimo de la documentación técnica viene determinado por el Anexo IV del AI Act'.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=5 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
