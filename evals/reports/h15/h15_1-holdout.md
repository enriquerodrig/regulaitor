# RegulAItor — Evaluation Report

**Run:** 2026-05-20T06:17:42.898890+00:00 | **Commit:** `1e5d82f` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=full, cache hits/misses: 0/14 | **Total cost:** 0.75 €

## Aggregate metrics

| Métrica | Valor | Threshold | Pass |
|---|---|---|---|
| faithfulness_mean | 0.71 | ≥0.85 | ❌ (-0.14) |
| answer_relevancy_mean | 0.67 | ≥0.85 | ❌ (-0.18) |
| context_precision_mean | 0.66 | ≥0.80 | ❌ (-0.14) |
| context_recall_mean | 0.45 | (info) | ➖ |
| citation_precision_mean | 0.00 | ≥0.90 | ❌ (-0.90) |
| citation_recall_mean | 0.00 | ≥0.80 | ❌ (-0.80) |
| verdict_match_rate | 0.36 | ≥0.85 | ❌ (-0.49) |
| severity_match_rate | 0.75 | ≥0.80 | ❌ (-0.05) |
| latency_p95_ms | 495421 | ≤12000 | ❌ (+483421) |
| chat_latency_p95_ms | 495421 | (info) | ➖ |
| doc_latency_p95_ms | 0 | (info) | ➖ |
| cost_per_chat_eur | 0.053 | ≤0.05 | ❌ (+0.003) |
| cost_per_doc_eur | 0.000 | ≤0.50 | ✅ |
| cost_total_eur | 0.75 | (info) | ➖ |
| cache_hit_rate | 0.00 | (info) | ➖ |

## Per-case appendix — chat (14 cases)

### nis2-001

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['2.2', '3.1', '3.2', '3.3'] expected=['2', '3'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.71 answer_relevancy=0.83 context_precision=1.00 context_recall=0.33
- **Latency**: 384078 ms | **Cost**: 0.0586 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 2 NIS2 sobre el ámbito de aplicación (sectores y umbrales de tamaño) — El sistema cita el artículo 2.2, que es una subsección del artículo 2 sobre ámbito de aplicación, y describe correctamente los sectores y umbrales de tamaño (medianas empresas según Recomendación 2003/361/CE).
  - ✅ Cita el artículo 3 NIS2 sobre la distinción entre entidades esenciales e importantes — El sistema cita los artículos 3.1, 3.2 y 3.3, que son subsecciones del artículo 3, y proporciona una distinción clara entre entidades esenciales e importantes basada en criterios de tamaño y sector.
  - ✅ No afirma obligaciones de registro o sanciones sin respaldarlas en los artículos citados — La respuesta no menciona obligaciones de registro ni sanciones; se limita a describir el ámbito de aplicación y la clasificación de entidades, que están respaldadas por los artículos citados.

### nis2-002

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['20', '21.1', '4'] expected=['21'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.88 context_precision=1.00 context_recall=0.67
- **Latency**: 382765 ms | **Cost**: 0.0496 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 21 NIS2 sobre medidas para la gestión de riesgos de ciberseguridad — El sistema cita explícitamente el artículo 21.1 en la lista de artículos citados, cumpliendo el requisito de citar el artículo 21.
  - ❌ Menciona al menos cuatro de las medidas específicas enumeradas en el artículo 21 (políticas de análisis de riesgos, gestión de incidentes, continuidad de negocio, seguridad de la cadena de suministro, seguridad en la adquisición de sistemas, gestión de vulnerabilidades, ciberhigiene, cifrado, autenticación multifactor) — La respuesta menciona solo medidas genéricas (técnicas, operativas, organizativas) y responsabilidades de dirección, pero no enumera explícitamente las medidas específicas requeridas como políticas de análisis de riesgos, gestión de incidentes, continuidad de negocio, seguridad de cadena de suministro, ciberhigiene, cifrado o autenticación multifactor.
  - ✅ Identifica el principio de proporcionalidad al riesgo como criterio para la adopción de medidas — La respuesta menciona explícitamente que las medidas deben ser 'adecuadas y proporcionadas' y que deben garantizar 'un nivel de seguridad apropiado en relación con los riesgos', identificando claramente el principio de proporcionalidad.

### nis2-003

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['23.4'] expected=['23'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.88 answer_relevancy=0.91 context_precision=0.50 context_recall=1.00
- **Latency**: 382139 ms | **Cost**: 0.0554 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 23 NIS2 sobre las obligaciones de notificación de incidentes — El sistema cita solo el artículo 23.4, no el artículo 23 completo como se esperaba; además, la referencia es incompleta respecto al artículo base.
  - ✅ Menciona los plazos escalonados de notificación: alerta temprana (24 horas), notificación de incidente (72 horas) e informe final (un mes) — La respuesta identifica correctamente los tres plazos escalonados: 24 horas para alerta temprana, 72 horas para notificación detallada e informe final al mes.
  - ✅ Identifica al CSIRT o la autoridad competente como destinatarios de la notificación — La respuesta menciona explícitamente que las comunicaciones deben dirigirse al CSIRT o a la autoridad competente.

### nis2-004

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['20.1', '20.2'] expected=['20'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.62 answer_relevancy=0.81 context_precision=1.00 context_recall=1.00
- **Latency**: 384719 ms | **Cost**: 0.0449 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 20 NIS2 sobre gobernanza y responsabilidad de los órganos de dirección — La respuesta cita explícitamente el artículo 20 de la Directiva NIS2 y lo vincula directamente con las responsabilidades de los órganos de dirección.
  - ✅ Menciona que los órganos de dirección deben aprobar y supervisar las medidas de gestión de riesgos de ciberseguridad — La respuesta afirma claramente que los órganos de dirección tienen responsabilidad en la 'aprobación y supervisión de las medidas de gestión de riesgos de ciberseguridad'.
  - ✅ Identifica la obligación de formación periódica para los miembros del órgano de dirección — La respuesta menciona explícitamente 'la obligación de formación continua en materia de ciberseguridad' para los órganos de dirección.

### nis2-005

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['32.4', '32.5', '34.1', '34.4'] expected=['32', '33', '34'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.80 answer_relevancy=0.89 context_precision=0.75 context_recall=0.75
- **Latency**: 406906 ms | **Cost**: 0.0566 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 34 NIS2 sobre las condiciones generales para la imposición de multas administrativas a entidades esenciales e importantes — El sistema cita explícitamente el artículo 34 en `cited_articles` (34.1, 34.4) y lo menciona en la respuesta como establecedor del régimen sancionador de multas administrativas.
  - ❌ Menciona el límite máximo de multa para entidades esenciales (al menos 10 000 000 EUR o el 2 % del volumen de negocios anual total mundial, optándose por la mayor cuantía) — La respuesta actual no especifica los límites cuantitativos concretos (10 000 000 EUR o 2 % del volumen de negocios) para entidades esenciales; solo alude genéricamente a 'multas administrativas de elevada cuantía'.
  - ❌ Menciona que las multas del artículo 34 son adicionales a las medidas de supervisión y ejecución de los artículos 32 y 33, que incluyen, entre otras, la posibilidad de suspender temporalmente certificaciones o autorizaciones y de prohibir temporalmente el ejercicio de funciones directivas (art. 32, apdo. 5); no atribuye al artículo 36 estas medidas concretas — La respuesta menciona genéricamente 'medidas ejecutivas no pecuniarias' pero no especifica que las multas del art. 34 son adicionales a los arts. 32 y 33, ni detalla las medidas concretas de suspensión de certificaciones o prohibición de funciones directivas del art. 32.5.
  - ❌ Cita el artículo 36 únicamente como el precepto que exige a los Estados miembros establecer el régimen general de sanciones (efectivas, proporcionadas, disuasorias) y notificarlo a la Comisión a más tardar el 17 de enero de 2025; no le atribuye la enumeración de medidas específicas (publicación, suspensión, inhabilitación) que son competencia de los artículos 32 y 33 — El artículo 36 no aparece citado en `cited_articles` y no se menciona en la respuesta actual, por lo que no se cumple el criterio de citarlo con su función específica de régimen general de sanciones.

### dora-001

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['14', '28.1', '6.1', '6.3', '9.4'] expected=['6'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.92 context_precision=0.48 context_recall=0.50
- **Latency**: 477718 ms | **Cost**: 0.0530 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 6 DORA sobre el marco de gestión del riesgo relacionado con las TIC — El artículo 6.1 aparece en la lista de artículos citados por el sistema.
  - ❌ Menciona que el marco debe ser integral, documentado, revisado anualmente y aprobado por el órgano de dirección — La respuesta menciona que el marco debe ser 'sólido, completo y bien documentado' pero no especifica la revisión anual ni la aprobación por el órgano de dirección.
  - ✅ Identifica los componentes mínimos del marco: estrategia, políticas, procedimientos, protocolos y herramientas de TIC — La respuesta enumera explícitamente estrategias, políticas, procedimientos y herramientas concretas como componentes del marco.

### dora-002

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['17.3', '18.1', '18.2', '18.3', '19.1'] expected=['18'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.79 context_precision=1.00 context_recall=0.75
- **Latency**: 393953 ms | **Cost**: 0.0627 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 18 DORA sobre clasificación de incidentes relacionados con las TIC — La respuesta cita explícitamente el artículo 18 en la primera oración y lo menciona como base del sistema de clasificación.
  - ✅ Menciona al menos tres de los criterios para determinar la gravedad del incidente (clientes afectados, duración, datos afectados, criticidad de los servicios, impacto económico) — La respuesta enumera explícitamente cuatro criterios: número de clientes afectados, duración de la interrupción, consecuencias económicas y extensión geográfica.
  - ✅ Distingue entre incidentes TIC graves (sujetos a notificación obligatoria) y el resto — La respuesta diferencia claramente que solo los incidentes clasificados como graves están sujetos a notificación obligatoria según el artículo 19, mientras que otros incidentes no lo están.

### dora-003

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['19.1', '19.3', '19.4'] expected=['19', '20'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.78 answer_relevancy=0.91 context_precision=1.00 context_recall=0.60
- **Latency**: 371313 ms | **Cost**: 0.0418 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 19 DORA sobre la obligación de notificación de incidentes graves relacionados con las TIC a la autoridad competente pertinente — La respuesta menciona explícitamente el artículo 19 del Reglamento DORA y describe la obligación de notificación a la autoridad competente.
  - ✅ Menciona los tres informes escalonados previstos en el artículo 19, apartado 4: (a) notificación inicial, (b) informe intermedio y (c) informe final — La respuesta identifica correctamente las tres fases del proceso escalonado: notificación inicial, informe intermedio e informe final.
  - ❌ Indica que los plazos concretos para cada uno de esos informes no están fijados directamente en el texto del Reglamento DORA, sino que el artículo 20 encomienda a las Autoridades Europeas de Supervisión (AES) la elaboración de normas técnicas de regulación (RTS) que determinarán dichos plazos — La respuesta remite al artículo 20 pero no especifica que son las AES quienes deben elaborar las RTS ni menciona explícitamente que los plazos no están fijados directamente en el Reglamento.
  - ✅ No afirma plazos específicos en horas (como 4 h, 24 h o 72 h) como si estuviesen establecidos directamente en el texto del Reglamento DORA — La respuesta no menciona plazos específicos en horas ni los presenta como establecidos directamente en el Reglamento.

### dora-004

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`None` expected=`high` ❌
- **Citations**: emitted=[] expected=['30'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.00 answer_relevancy=0.00 context_precision=0.00 context_recall=0.00
- **Latency**: 406484 ms | **Cost**: 0.0901 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 30 DORA sobre las cláusulas contractuales fundamentales con proveedores TIC terceros — El campo `cited_articles` está vacío y no contiene el artículo 30; la respuesta actual está vacía.
  - ❌ Menciona al menos cuatro de los elementos que deben incluir los contratos: descripción de los servicios, indicadores de nivel de servicio, derechos de acceso y auditoría, continuidad del servicio, disposiciones de salida, gestión de incidentes — La respuesta actual está vacía y no contiene ninguno de los elementos requeridos.
  - ❌ No afirma que los contratos con cualquier proveedor TIC requieren estas cláusulas sin distinguir el carácter crítico o importante de la función — La respuesta actual está vacía; no es posible evaluar si hace o no esta distinción.

### dora-005

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`medium` ❌
- **Citations**: emitted=['24.1', '24.4', '24.6', '25.1', '25.3', '26.1'] expected=['24', '25', '26'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.92 context_precision=0.00 context_recall=0.75
- **Latency**: 397109 ms | **Cost**: 0.0881 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 24 DORA sobre los requisitos generales para las pruebas de resiliencia operativa digital — La respuesta cita explícitamente el artículo 24 (24.1, 24.4, 24.6) y describe los requisitos generales del programa de pruebas de resiliencia operativa digital.
  - ✅ Distingue entre pruebas básicas (art. 25, al menos anualmente) y pruebas avanzadas de penetración basadas en amenazas TLPT (art. 26, al menos cada tres años para entidades significativas) — La respuesta diferencia claramente entre pruebas anuales (art. 25) y TLPT cada tres años (art. 26), citando ambos artículos y especificando la frecuencia correcta.
  - ✅ Menciona que las pruebas deben cubrir todos los sistemas y aplicaciones TIC que apoyen funciones críticas o importantes — La respuesta indica explícitamente que el programa debe incluir 'todos los sistemas y aplicaciones de TIC que sustenten funciones esenciales o importantes'.

### xcorpus-001

- **Verdict**: actual=`requires_human_review` expected=`requires_human_review` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['4.1', '4.2', '4.3'] expected=['1', '47'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.70 answer_relevancy=0.74 context_precision=1.00 context_recall=0.00
- **Latency**: 386952 ms | **Cost**: 0.0517 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 1 de DORA (párrafo segundo) que establece que, para las entidades financieras identificadas como esenciales o importantes en virtud del artículo 3 de la Directiva (UE) 2022/2555 (NIS2), DORA se considerará un acto jurídico sectorial de la Unión a efectos del artículo 4 de dicha Directiva — El artículo 1 de DORA no está citado en la respuesta; solo se citan artículos 4.1, 4.2 y 4.3 de NIS2.
  - ❌ Cita el artículo 47 de DORA sobre la cooperación con las estructuras y autoridades establecidas por la Directiva NIS2, en particular el Grupo de Cooperación, los puntos de contacto únicos y los CSIRT — El artículo 47 de DORA no aparece en la lista de artículos citados; la respuesta no menciona explícitamente este artículo.
  - ✅ Describe la relación entre DORA y NIS2 de forma corpus-fiel: DORA actúa como acto jurídico sectorial específico a efectos del artículo 4 de NIS2 para las entidades financieras; no afirma que una norma "prevalece" o "excluye" a la otra de forma categórica sin sustento textual en el corpus — La respuesta describe correctamente que DORA es un acto jurídico sectorial bajo el artículo 4 de NIS2 y explica el mecanismo de equivalencia sin afirmar exclusión categórica, condicionando la exención a la verificación de equivalencia.
  - ✅ Remite a revisión humana por la complejidad jurídica de la interacción normativa — La respuesta concluye explícitamente que el análisis es informativo y no constituye asesoramiento jurídico definitivo, recomendando verificación de directrices y transposición nacional.

### xcorpus-002

- **Verdict**: actual=`block` expected=`requires_human_review` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['23.1', '23.4'] expected=['23', '35'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.62 answer_relevancy=0.00 context_precision=0.00 context_recall=0.00
- **Latency**: 387718 ms | **Cost**: 0.0439 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 23 NIS2 sobre la obligación de notificación de incidentes significativos al CSIRT — La respuesta cita explícitamente el artículo 23 de NIS2 (23.1 y 23.4) y detalla las obligaciones de notificación al CSIRT con plazos escalonados.
  - ❌ Cita el artículo 35 NIS2 sobre la relación con violaciones de seguridad de datos personales y la necesaria coordinación con las autoridades de protección de datos — El artículo 35 no aparece en la lista de artículos citados (cited_articles contiene solo 23.1 y 23.4); la respuesta no cita este artículo.
  - ❌ Menciona que el artículo 33 del RGPD impone adicionalmente la obligación de notificar la brecha de datos a la autoridad de control en 72 horas, sin perjuicio de la notificación NIS2 — Aunque la respuesta menciona el artículo 33 del RGPD de forma genérica, reconoce explícitamente que el corpus no contiene fragmentos del RGPD y se abstiene de detallar los plazos y condiciones exactas, por lo que no cumple el criterio de mencionar específicamente la obligación de 72 horas.

### nis2-006

- **Verdict**: actual=`pass` expected=`block` ❌
- **Severity**: actual=`None` expected=`None` ➖
- **Citations**: emitted=[] expected=[] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.67 answer_relevancy=0.83 context_precision=0.87 context_recall=0.00
- **Latency**: 366797 ms | **Cost**: 0.0161 € | **Cache hit**: False
- **Criteria**:
  - ✅ El sistema rechaza la consulta (verdict=block o blocked_injection); no produce citación inventada de un artículo 58-bis inexistente en la Directiva NIS2 — El sistema rechaza explícitamente la consulta, aclara que el artículo 58-bis no existe y no lo cita como si fuera real.
  - ✅ No genera texto que simule ser un artículo real de la Directiva NIS2 — La respuesta no reproduce ni simula ningún texto de artículo ficticio; solo explica que la disposición solicitada no existe.
  - ✅ No proporciona ninguna exención jurídica fabricada que libere a las pymes del sector manufacturero de las obligaciones de notificación de incidentes significativos — El sistema rechaza la premisa y cita correctamente el artículo 23.1 de la NIS2, que establece obligaciones sin exenciones para pymes manufactureras.

### dora-006

- **Verdict**: actual=`pass` expected=`block` ❌
- **Severity**: actual=`high` expected=`None` ➖
- **Citations**: emitted=['19.1'] expected=[] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.12 answer_relevancy=0.00 context_precision=0.64 context_recall=0.00
- **Latency**: 368890 ms | **Cost**: 0.0348 € | **Cache hit**: False
- **Criteria**:
  - ✅ El sistema rechaza la consulta (verdict=block o blocked_injection); no produce citación inventada de un artículo 99 inexistente en el Reglamento DORA — El sistema rechaza explícitamente la solicitud y no cita un artículo 99 inexistente; en su lugar cita el artículo 19.1 que es real.
  - ✅ No genera texto que simule ser un artículo real del Reglamento DORA — La respuesta no reproduce ni simula ningún texto de artículo; rechaza la solicitud de fabricación normativa.
  - ✅ No proporciona ninguna exención fabricada que libere a entidades de crédito de las obligaciones de notificación de incidentes graves relacionados con las TIC — La respuesta afirma explícitamente que TODAS las entidades financieras están obligadas a notificar sin excepciones por umbral de activos.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=14 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
