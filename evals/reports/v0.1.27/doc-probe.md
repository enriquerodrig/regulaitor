# RegulAItor — Evaluation Report

**Run:** 2026-05-27T08:13:37.962948+00:00 | **Commit:** `58353b0` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=full, cache hits/misses: 0/3 | **Total cost:** 0.16 €

## Aggregate metrics

| Métrica | Valor | v0.1.20-bar | Aspiracional |
|---|---|---|---|
| faithfulness_mean | 0.17 | ≥0.65 ❌ (-0.48) | ≥0.85 ❌ (-0.68) |
| answer_relevancy_mean | 0.00 | ≥0.55 ❌ (-0.55) | ≥0.85 ❌ (-0.85) |
| context_precision_mean | 0.00 | ≥0.55 ❌ (-0.55) | ≥0.80 ❌ (-0.80) |
| context_recall_mean | 0.00 | (info) | (info) |
| citation_precision_mean | 0.00 | ≥0.25 ❌ (-0.25) | ≥0.90 ❌ (-0.90) |
| citation_recall_mean | 0.00 | ≥0.60 ❌ (-0.60) | ≥0.80 ❌ (-0.80) |
| verdict_match_rate | 0.00 | ≥0.35 ❌ (-0.35) | ≥0.85 ❌ (-0.85) |
| severity_match_rate | 0.00 | ≥0.35 ❌ (-0.35) | ≥0.80 ❌ (-0.80) |
| latency_p95_ms | 80339 | ≤12000 ❌ (+68339) | (info) |
| chat_latency_p95_ms | 0 | (info) | (info) |
| doc_latency_p95_ms | 80339 | (info) | (info) |
| cost_per_chat_eur | 0.000 | ≤0.05 ✅ | (info) |
| cost_per_doc_eur | 0.053 | ≤0.50 ✅ | (info) |
| cost_total_eur | 0.16 | (info) | (info) |
| cache_hit_rate | 0.00 | (info) | (info) |

## Caveats — v0.1.20-bar reading

1. **Aspirational column** = CLAUDE.md §17 long-term ideal targets; no run has ever hit them; they remain as direction-setting, not as v0.1.20 ship gate.
2. **v0.1.20-bar column** = anchored to H10 (full-30-case measured baseline) + H15 v1.2 (30-case partial intervention measurement); the 64-case set is harder so even matching the bar is meaningful evidence the maximalist-plan stack didn't regress on the easier subset.
3. **Judge family stays Haiku 4.5** per ADR-0010 D1 caveat (same vendor as production Sonnet, different model class). Cross-vendor migration deferred to HX (post-TFM); §19 satisfied literally; documented honestly.
4. **Latency p95** number remains contaminated by batch+rate-limit+tenacity backoff per H8 amendment + §17 note; v0.1.16 does NOT fix this. H17 LangFuse refactor is the proper instrument; until then `latency_p95_ms` is informational despite being formally gated in the report.

## Per-case appendix — chat (0 cases)

## Per-case appendix — documents (3 cases)

### doc-001

- **Verdict**: actual=`block` expected=`requires_human_review` ❌
- **Segments**: actual=5 expected=5 ✅
- **Findings citations**: emitted=['<UNKNOWN>', 'N/A', 'UNKNOWN'] expected=['6.1', '6.2', '9.1'] precision=0.00 recall=0.00
- **Faithfulness**: 0.14
- **Latency total**: 63203 ms | **Cost**: 0.0580 € | **Cache hit**: False
- **Criteria**:
  - ❌ Identifica la ausencia de clasificación formal de riesgo según el AI Act (artículo 6.1 / 6.2) para los sistemas listados — La respuesta menciona ausencia de verificación de conformidad pero no cita explícitamente los artículos 6.1 o 6.2, y `cited_articles` contiene solo valores inválidos (<UNKNOWN>, N/A, UNKNOWN).
  - ❌ Cita el artículo 9.1 en hallazgos indicando la falta de sistema de gestión de riesgos documentado — El artículo 9.1 no aparece en `cited_articles`; la respuesta reconoce la falta de gestión de riesgos pero no proporciona cita literal del artículo 9.1.
  - ❌ Severidad reportada coherente con alto riesgo no gestionado (medium o high) — La respuesta no reporta ningún nivel de severidad (medium, high, etc.); solo declara que no es posible emitir hallazgos sin contexto normativo.

### doc-002

- **Verdict**: actual=`block` expected=`pass` ❌
- **Segments**: actual=4 expected=4 ✅
- **Findings citations**: emitted=['22', '5', '50', 'N/A'] expected=['13.1', '50.1'] precision=0.00 recall=0.00
- **Faithfulness**: 0.17
- **Latency total**: 34375 ms | **Cost**: 0.0448 € | **Cache hit**: False
- **Criteria**:
  - ✅ Identifica la ausencia de información al usuario sobre la naturaleza de IA del chatbot (artículo 50.1 del AI Act) — La respuesta identifica explícitamente que 'no se informa al usuario de que está interactuando con un sistema automatizado' y reconoce esta ausencia de transparencia como potencialmente relevante para el AI Act.
  - ❌ Cita el artículo 13.1 del AI Act en hallazgos sobre falta de instrucciones de uso y transparencia — El artículo 13.1 no aparece en la lista de artículos citados (cited_articles contiene '22', '5', '50', 'N/A'); la respuesta menciona el AI Act genéricamente pero no cita 13.1 de forma explícita.
  - ❌ Severidad reportada como low o medium coherente con incumplimiento de transparencia — La respuesta no reporta ningún nivel de severidad (low, medium, high); se limita a describir la ausencia de contexto regulatorio sin emitir hallazgos con severidad asignada.

### doc-003

- **Verdict**: actual=`block` expected=`pass` ❌
- **Segments**: actual=6 expected=6 ✅
- **Findings citations**: emitted=['<UNKNOWN>', 'N/A'] expected=['14.1', '14.2'] precision=0.00 recall=0.00
- **Faithfulness**: 0.21
- **Latency total**: 41782 ms | **Cost**: 0.0560 € | **Cache hit**: False
- **Criteria**:
  - ❌ Identifica la ausencia de mecanismos de supervisión humana efectiva (artículo 14.1 del AI Act) — El artículo 14.1 no aparece en cited_articles; la respuesta menciona la situación pero no cita el artículo requerido.
  - ❌ Cita el artículo 14.2 en hallazgos sobre la falta de protocolo de intervención humana para resultados de baja confiabilidad — El artículo 14.2 no aparece en cited_articles; la respuesta describe el problema pero no emite hallazgos con cita literal del artículo.
  - ❌ Severidad reportada como high coherente con el riesgo de decisiones automatizadas sin supervisión — La respuesta no reporta ninguna severidad ni emite hallazgos formales; solo declara la imposibilidad de analizar por falta de contexto recuperado.

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=3 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
