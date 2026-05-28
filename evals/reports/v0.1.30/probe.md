# RegulAItor — Evaluation Report

**Run:** 2026-05-28T05:56:32.952257+00:00 | **Commit:** `e91a690` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=full, cache hits/misses: 0/6 | **Total cost:** 0.65 €

## Aggregate metrics

| Métrica | Valor | v0.1.20-bar | Aspiracional |
|---|---|---|---|
| faithfulness_mean | 0.69 | ≥0.65 ✅ | ≥0.85 ❌ (-0.16) |
| answer_relevancy_mean | 0.91 | ≥0.55 ✅ | ≥0.85 ✅ |
| context_precision_mean | 0.61 | ≥0.55 ✅ | ≥0.80 ❌ (-0.19) |
| context_recall_mean | 0.50 | (info) | (info) |
| citation_precision_mean | 0.14 | ≥0.25 ❌ (-0.11) | ≥0.90 ❌ (-0.76) |
| citation_recall_mean | 0.33 | ≥0.60 ❌ (-0.27) | ≥0.80 ❌ (-0.47) |
| verdict_match_rate | 0.67 | ≥0.35 ✅ | ≥0.85 ❌ (-0.18) |
| severity_match_rate | 0.33 | ≥0.35 ❌ (-0.02) | ≥0.80 ❌ (-0.47) |
| latency_p95_ms | 1819099 | ≤12000 ❌ (+1807099) | (info) |
| chat_latency_p95_ms | 372913 | (info) | (info) |
| doc_latency_p95_ms | 1822252 | (info) | (info) |
| cost_per_chat_eur | 0.059 | ≤0.05 ❌ (+0.009) | (info) |
| cost_per_doc_eur | 0.157 | ≤0.50 ✅ | (info) |
| cost_total_eur | 0.65 | (info) | (info) |
| cache_hit_rate | 0.00 | (info) | (info) |

## Caveats — v0.1.20-bar reading

1. **Aspirational column** = CLAUDE.md §17 long-term ideal targets; no run has ever hit them; they remain as direction-setting, not as v0.1.20 ship gate.
2. **v0.1.20-bar column** = anchored to H10 (full-30-case measured baseline) + H15 v1.2 (30-case partial intervention measurement); the 64-case set is harder so even matching the bar is meaningful evidence the maximalist-plan stack didn't regress on the easier subset.
3. **Judge family stays Haiku 4.5** per ADR-0010 D1 caveat (same vendor as production Sonnet, different model class). Cross-vendor migration deferred to HX (post-TFM); §19 satisfied literally; documented honestly.
4. **Latency p95** number remains contaminated by batch+rate-limit+tenacity backoff per H8 amendment + §17 note; v0.1.16 does NOT fix this. H17 LangFuse refactor is the proper instrument; until then `latency_p95_ms` is informational despite being formally gated in the report.

## Per-case appendix — chat (3 cases)

### chat-001

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['2.2', '25', '6.1'] expected=['6.1'] precision=0.33 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.90 context_precision=1.00 context_recall=0.33
- **Latency**: 370250 ms | **Cost**: 0.0576 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita literalmente el artículo 6.1 del AI Act o su contenido sustancial — El artículo 6.1 aparece en la lista de artículos citados y la respuesta refleja su contenido sustancial sobre clasificación de alto riesgo.
  - ✅ Identifica correctamente los dos requisitos acumulativos: componente de seguridad en producto de la lista del Anexo I + evaluación de conformidad por terceros — La respuesta explícitamente enumera las dos condiciones acumulativas: (1) componente de seguridad en producto del Anexo I, y (2) evaluación de conformidad por terceros.
  - ❌ No afirma obligaciones adicionales no respaldadas por el artículo 6.1 — La respuesta menciona variación según Sección A o B del Anexo I sin respaldo explícito en el artículo 6.1, y no desarrolla obligaciones del capítulo III que sí están respaldadas pero van más allá del criterio de clasificación.

### chat-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['6.2', '6.3', '6.4', '80'] expected=['6.2', '6.3'] precision=0.50 recall=1.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.90 context_precision=0.83 context_recall=1.00
- **Latency**: 360157 ms | **Cost**: 0.0544 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 6.2 como regla general de clasificación por Anexo III — El artículo 6.2 está presente en cited_articles y la respuesta establece que los sistemas del Anexo III se consideran de alto riesgo en principio.
  - ✅ Explica la excepción del artículo 6.3 sin omitir el requisito de documentación motivada — La respuesta menciona explícitamente que el proveedor debe documentar la evaluación antes de la comercialización y que puede ser revisado por autoridades.
  - ✅ No afirma que la excepción es automática ni que exime de todos los controles — La respuesta aclara que la excepción no es automática, requiere evaluación formal, y subraya que si no se cumple, el sistema queda sujeto a todos los requisitos del capítulo III.

### chat-003

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['16', '17.1', '17.2'] expected=['9.1', '9.2'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.70 answer_relevancy=0.93 context_precision=0.00 context_recall=0.17
- **Latency**: 366921 ms | **Cost**: 0.0657 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 9.1 y 9.2 del AI Act con su contenido sustancial — El sistema citó los artículos 16, 17.1 y 17.2, pero no incluyó las citas esperadas a los artículos 9.1 y 9.2 que son centrales para responder la pregunta.
  - ❌ Menciona el carácter continuo del sistema de gestión de riesgos (ciclo de vida) — La respuesta no menciona explícitamente que el sistema de gestión de riesgos debe funcionar a lo largo de todo el ciclo de vida del sistema de IA.
  - ❌ Identifica correctamente los elementos obligatorios: identificación, evaluación y medidas de mitigación — Aunque la respuesta menciona evaluación de conformidad y medidas correctoras, no detalla específicamente los tres elementos obligatorios (identificación de riesgos, evaluación de riesgos y medidas de mitigación) como exige el artículo 9.

## Per-case appendix — documents (3 cases)

### doc-001

- **Verdict**: actual=`pass` expected=`requires_human_review` ❌
- **Segments**: actual=5 expected=5 ✅
- **Findings citations**: emitted=['1', '112.1', '26.11', '26.7', '26.9', '3.1', '43.3', '6.3', '74.12', '79.6', '80', '9.5'] expected=['6.1', '6.2', '9.1'] precision=0.00 recall=0.00
- **Faithfulness**: 0.57
- **Latency total**: 1784420 ms | **Cost**: 0.1694 € | **Cache hit**: False
- **Criteria**:
  - ❌ Identifica la ausencia de clasificación formal de riesgo según el AI Act (artículo 6.1 / 6.2) para los sistemas listados — La respuesta identifica la ausencia de clasificación formal de riesgo, pero los artículos 6.1 y 6.2 no aparecen en cited_articles; se citan otros artículos (1, 43.3, 74.12) pero no los esperados.
  - ❌ Cita el artículo 9.1 en hallazgos indicando la falta de sistema de gestión de riesgos documentado — El artículo 9.1 no aparece en cited_articles; se cita 9.5 pero no 9.1, que es el esperado para gestión de riesgos.
  - ✅ Severidad reportada coherente con alto riesgo no gestionado (medium o high) — La respuesta describe múltiples brechas de alto riesgo, incumplimientos significativos y exposición a sanciones, reflejando severidad alta coherente con riesgo no gestionado.

### doc-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Segments**: actual=4 expected=4 ✅
- **Findings citations**: emitted=['1', '10.2', '10.5', '113.1', '113.3', '113.6', '50.5'] expected=['13.1', '50.1'] precision=0.00 recall=0.00
- **Faithfulness**: 0.50
- **Latency total**: 1416343 ms | **Cost**: 0.1150 € | **Cache hit**: False
- **Criteria**:
  - ❌ Identifica la ausencia de información al usuario sobre la naturaleza de IA del chatbot (artículo 50.1 del AI Act) — La respuesta cita el artículo 50.5 pero no cita el artículo 50.1 esperado; aunque identifica la brecha de transparencia, no lo hace bajo el artículo específico requerido.
  - ❌ Cita el artículo 13.1 del AI Act en hallazgos sobre falta de instrucciones de uso y transparencia — El artículo 13.1 no aparece en la lista de artículos citados; la respuesta no lo menciona explícitamente.
  - ❌ Severidad reportada como low o medium coherente con incumplimiento de transparencia — La respuesta no reporta explícitamente un nivel de severidad (low, medium, high); describe las brechas como 'graves' pero sin clasificación formal de severidad.

### doc-003

- **Verdict**: actual=`block` expected=`pass` ❌
- **Segments**: actual=6 expected=6 ✅
- **Findings citations**: emitted=['12.2', '13.1', '14.3', '14.4', '17.1', '18.1', '26.11', '26.2', '26.5', '6.1', '6.5', '73.1', '73.2', '73.6', '9.1', '9.2', '9.5', '9.6', '9.8'] expected=['14.1', '14.2'] precision=0.00 recall=0.00
- **Faithfulness**: 0.39
- **Latency total**: 1805438 ms | **Cost**: 0.1857 € | **Cache hit**: False
- **Criteria**:
  - ✅ Identifica la ausencia de mecanismos de supervisión humana efectiva (artículo 14.1 del AI Act) — La respuesta identifica explícitamente brechas en supervisión humana efectiva y menciona el artículo 14 en el contexto de obligaciones incumplidas.
  - ❌ Cita el artículo 14.2 en hallazgos sobre la falta de protocolo de intervención humana para resultados de baja confiabilidad — El artículo 14.2 no aparece en la lista de artículos citados; solo se cita 14.3 y 14.4.
  - ❌ Severidad reportada como high coherente con el riesgo de decisiones automatizadas sin supervisión — La respuesta no reporta explícitamente una severidad clasificada como 'high'; describe brechas graves pero sin asignar un nivel de severidad formal.

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=6 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
