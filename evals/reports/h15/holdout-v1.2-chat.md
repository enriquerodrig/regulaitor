# RegulAItor — Evaluation Report

**Run:** 2026-05-19T10:05:36.936855+00:00 | **Commit:** `d104211` | **Models:** claude-sonnet-4-6 (prod), claude-haiku-4-5-20251001 (judge)
**Settings:** temperature=0.0, subset=full, cache hits/misses: 0/14 | **Total cost:** 0.78 €

## Aggregate metrics

| Métrica | Valor | Threshold | Pass |
|---|---|---|---|
| faithfulness_mean | 0.66 | ≥0.85 | ❌ (-0.19) |
| answer_relevancy_mean | 0.66 | ≥0.85 | ❌ (-0.19) |
| context_precision_mean | 0.62 | ≥0.80 | ❌ (-0.18) |
| context_recall_mean | 0.42 | (info) | ➖ |
| citation_precision_mean | 0.00 | ≥0.90 | ❌ (-0.90) |
| citation_recall_mean | 0.00 | ≥0.80 | ❌ (-0.80) |
| verdict_match_rate | 0.43 | ≥0.85 | ❌ (-0.42) |
| severity_match_rate | 0.67 | ≥0.80 | ❌ (-0.13) |
| latency_p95_ms | 430522 | ≤12000 | ❌ (+418522) |
| chat_latency_p95_ms | 430522 | (info) | ➖ |
| doc_latency_p95_ms | 0 | (info) | ➖ |
| cost_per_chat_eur | 0.055 | ≤0.05 | ❌ (+0.005) |
| cost_per_doc_eur | 0.000 | ≤0.50 | ✅ |
| cost_total_eur | 0.78 | (info) | ➖ |
| cache_hit_rate | 0.00 | (info) | ➖ |

## Per-case appendix — chat (14 cases)

### nis2-001

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['2.2', '3.1', '3.2', '3.3'] expected=['2', '3'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.82 context_precision=1.00 context_recall=0.33
- **Latency**: 372140 ms | **Cost**: 0.0548 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 2 NIS2 sobre el ámbito de aplicación (sectores y umbrales de tamaño) — El sistema cita el artículo 2.2, que es una subsección del artículo 2 sobre ámbito de aplicación.
  - ✅ Cita el artículo 3 NIS2 sobre la distinción entre entidades esenciales e importantes — El sistema cita los artículos 3.1, 3.2 y 3.3, que desarrollan la distinción entre entidades esenciales e importantes.
  - ✅ No afirma obligaciones de registro o sanciones sin respaldarlas en los artículos citados — La respuesta no menciona obligaciones de registro ni sanciones; se limita a describir el ámbito de aplicación y criterios de clasificación.

### nis2-002

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['20.1', '20.2', '21.1', '33.4'] expected=['21'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.88 context_precision=1.00 context_recall=0.67
- **Latency**: 357297 ms | **Cost**: 0.0464 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 21 NIS2 sobre medidas para la gestión de riesgos de ciberseguridad — El artículo 21.1 está incluido en la lista de artículos citados por el sistema.
  - ❌ Menciona al menos cuatro de las medidas específicas enumeradas en el artículo 21 (políticas de análisis de riesgos, gestión de incidentes, continuidad de negocio, seguridad de la cadena de suministro, seguridad en la adquisición de sistemas, gestión de vulnerabilidades, ciberhigiene, cifrado, autenticación multifactor) — La respuesta menciona solo dos medidas específicas (gestión de incidentes y formación en ciberseguridad) de forma explícita; no enumera las otras medidas concretas requeridas como análisis de riesgos, continuidad de negocio, cadena de suministro, ciberhigiene, cifrado o autenticación multifactor.
  - ✅ Identifica el principio de proporcionalidad al riesgo como criterio para la adopción de medidas — La respuesta menciona explícitamente que las medidas deben calibrarse teniendo en cuenta el tamaño, exposición a riesgos, probabilidad y gravedad de incidentes, reflejando el principio de proporcionalidad.

### nis2-003

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['23.4'] expected=['23'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.90 context_precision=0.50 context_recall=1.00
- **Latency**: 358202 ms | **Cost**: 0.0539 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 23 NIS2 sobre las obligaciones de notificación de incidentes — El sistema cita 23.4 pero no menciona explícitamente el artículo 23 en la respuesta; la referencia es incompleta respecto a lo esperado.
  - ✅ Menciona los plazos escalonados de notificación: alerta temprana (24 horas), notificación de incidente (72 horas) e informe final (un mes) — La respuesta detalla correctamente los tres plazos escalonados: 24 horas para alerta temprana, 72 horas para notificación de incidente e informe final en un mes.
  - ✅ Identifica al CSIRT o la autoridad competente como destinatarios de la notificación — La respuesta menciona explícitamente que las entidades deben dirigirse al CSIRT o a la autoridad competente.

### nis2-004

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['20.1', '20.2'] expected=['20'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.50 answer_relevancy=0.82 context_precision=1.00 context_recall=1.00
- **Latency**: 350375 ms | **Cost**: 0.0415 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 20 NIS2 sobre gobernanza y responsabilidad de los órganos de dirección — La respuesta cita explícitamente el artículo 20 de la Directiva NIS2 como fundamento de las responsabilidades de los órganos de dirección.
  - ✅ Menciona que los órganos de dirección deben aprobar y supervisar las medidas de gestión de riesgos de ciberseguridad — La respuesta establece claramente que los órganos de dirección deben aprobar las medidas de gestión de riesgos y supervisar su implementación.
  - ✅ Identifica la obligación de formación periódica para los miembros del órgano de dirección — La respuesta menciona explícitamente que los miembros están obligados a asistir a formaciones específicas sobre ciberseguridad.

### nis2-005

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['32.4', '32.5', '34.1', '34.4', '34.6'] expected=['32', '33', '34'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=1.00 answer_relevancy=0.85 context_precision=0.75 context_recall=0.75
- **Latency**: 362297 ms | **Cost**: 0.0586 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 34 NIS2 sobre las condiciones generales para la imposición de multas administrativas a entidades esenciales e importantes — El sistema cita explícitamente el artículo 34.4 al referirse a las multas administrativas para entidades esenciales.
  - ✅ Menciona el límite máximo de multa para entidades esenciales (al menos 10 000 000 EUR o el 2 % del volumen de negocios anual total mundial, optándose por la mayor cuantía) — La respuesta especifica correctamente que las multas pueden ser de hasta 10.000.000 EUR o el 2 % del volumen de negocios anual mundial, aplicándose la cifra mayor.
  - ✅ Menciona que las multas del artículo 34 son adicionales a las medidas de supervisión y ejecución de los artículos 32 y 33, que incluyen, entre otras, la posibilidad de suspender temporalmente certificaciones o autorizaciones y de prohibir temporalmente el ejercicio de funciones directivas (art. 32, apdo. 5); no atribuye al artículo 36 estas medidas concretas — La respuesta describe correctamente las medidas de ejecución del artículo 32 (suspensión de certificaciones, prohibición de funciones directivas) como distintas de las multas, sin atribuir estas medidas al artículo 36.
  - ❌ Cita el artículo 36 únicamente como el precepto que exige a los Estados miembros establecer el régimen general de sanciones (efectivas, proporcionadas, disuasorias) y notificarlo a la Comisión a más tardar el 17 de enero de 2025; no le atribuye la enumeración de medidas específicas (publicación, suspensión, inhabilitación) que son competencia de los artículos 32 y 33 — El artículo 36 no es citado en la respuesta del sistema, por lo que no se menciona su función de exigir a los Estados miembros establecer el régimen general de sanciones ni la fecha de notificación a la Comisión.

### dora-001

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`None` expected=`high` ❌
- **Citations**: emitted=[] expected=['6'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.00 answer_relevancy=0.00 context_precision=0.00 context_recall=0.00
- **Latency**: 373030 ms | **Cost**: 0.0846 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 6 DORA sobre el marco de gestión del riesgo relacionado con las TIC — La respuesta está vacía; no cita ningún artículo.
  - ❌ Menciona que el marco debe ser integral, documentado, revisado anualmente y aprobado por el órgano de dirección — La respuesta está vacía; no contiene información sobre características del marco.
  - ❌ Identifica los componentes mínimos del marco: estrategia, políticas, procedimientos, protocolos y herramientas de TIC — La respuesta está vacía; no enumera componentes del marco.

### dora-002

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['17.3', '18.1', '18.2', '18.3', '19.1'] expected=['18'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.86 answer_relevancy=0.87 context_precision=1.00 context_recall=0.75
- **Latency**: 369686 ms | **Cost**: 0.0636 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 18 DORA sobre clasificación de incidentes relacionados con las TIC — La respuesta cita explícitamente el artículo 18 en el primer párrafo como base del sistema de clasificación.
  - ✅ Menciona al menos tres de los criterios para determinar la gravedad del incidente (clientes afectados, duración, datos afectados, criticidad de los servicios, impacto económico) — La respuesta menciona cinco criterios: número de clientes afectados, duración/inactividad, consecuencias económicas, criticidad de servicios (implícita en 'obligaciones adicionales'), y repercusión en reputación.
  - ✅ Distingue entre incidentes TIC graves (sujetos a notificación obligatoria) y el resto — La respuesta establece claramente que solo los incidentes graves activan obligaciones de notificación a autoridades competentes (art. 19), diferenciándolos del resto.

### dora-003

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['19.1', '19.3', '19.4'] expected=['19', '20'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.86 answer_relevancy=0.86 context_precision=1.00 context_recall=0.60
- **Latency**: 377109 ms | **Cost**: 0.0436 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 19 DORA sobre la obligación de notificación de incidentes graves relacionados con las TIC a la autoridad competente pertinente — La respuesta cita explícitamente el artículo 19 y describe correctamente la obligación de notificación a la autoridad competente.
  - ✅ Menciona los tres informes escalonados previstos en el artículo 19, apartado 4: (a) notificación inicial, (b) informe intermedio y (c) informe final — La respuesta identifica correctamente las tres etapas: notificación inicial, informe intermedio e informe final.
  - ✅ Indica que los plazos concretos para cada uno de esos informes no están fijados directamente en el texto del Reglamento DORA, sino que el artículo 20 encomienda a las Autoridades Europeas de Supervisión (AES) la elaboración de normas técnicas de regulación (RTS) que determinarán dichos plazos — La respuesta explica correctamente que DORA remite al artículo 20 para el desarrollo normativo mediante RTS, sin fijar plazos directos en el texto.
  - ✅ No afirma plazos específicos en horas (como 4 h, 24 h o 72 h) como si estuviesen establecidos directamente en el texto del Reglamento DORA — La respuesta evita afirmar plazos específicos en horas y aclara explícitamente que DORA no establece fechas exactas en el artículo 19.

### dora-004

- **Verdict**: actual=`requires_human_review` expected=`pass` ❌
- **Severity**: actual=`None` expected=`high` ❌
- **Citations**: emitted=[] expected=['30'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.00 answer_relevancy=0.00 context_precision=0.00 context_recall=0.00
- **Latency**: 422202 ms | **Cost**: 0.0903 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 30 DORA sobre las cláusulas contractuales fundamentales con proveedores TIC terceros — El campo `cited_articles` está vacío y no contiene el artículo 30; la respuesta actual está vacía.
  - ❌ Menciona al menos cuatro de los elementos que deben incluir los contratos: descripción de los servicios, indicadores de nivel de servicio, derechos de acceso y auditoría, continuidad del servicio, disposiciones de salida, gestión de incidentes — La respuesta actual está vacía y no contiene ninguno de los elementos requeridos.
  - ❌ No afirma que los contratos con cualquier proveedor TIC requieren estas cláusulas sin distinguir el carácter crítico o importante de la función — La respuesta actual está vacía; no es posible evaluar si hace o no esta distinción.

### dora-005

- **Verdict**: actual=`pass` expected=`pass` ✅
- **Severity**: actual=`info` expected=`medium` ❌
- **Citations**: emitted=['24.1', '24.4', '24.6', '25.1', '26.1'] expected=['24', '25', '26'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.88 answer_relevancy=0.86 context_precision=0.50 context_recall=0.75
- **Latency**: 388921 ms | **Cost**: 0.0832 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 24 DORA sobre los requisitos generales para las pruebas de resiliencia operativa digital — La respuesta cita explícitamente el artículo 24 (24.1, 24.4, 24.6) y describe los requisitos generales del programa de pruebas de resiliencia operativa digital.
  - ✅ Distingue entre pruebas básicas (art. 25, al menos anualmente) y pruebas avanzadas de penetración basadas en amenazas TLPT (art. 26, al menos cada tres años para entidades significativas) — La respuesta diferencia claramente entre pruebas anuales de todos los sistemas (art. 25) y pruebas TLPT cada tres años para entidades no microempresas (art. 26), citando ambos artículos.
  - ✅ Menciona que las pruebas deben cubrir todos los sistemas y aplicaciones TIC que apoyen funciones críticas o importantes — La respuesta indica explícitamente que el programa debe cubrir 'una amplia variedad de pruebas' de 'sistemas y aplicaciones de TIC que sustenten funciones esenciales o importantes'.

### xcorpus-001

- **Verdict**: actual=`pass` expected=`requires_human_review` ❌
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['19.1', '19.2'] expected=['1', '47'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.67 answer_relevancy=0.75 context_precision=0.00 context_recall=0.00
- **Latency**: 379266 ms | **Cost**: 0.0468 € | **Cache hit**: False
- **Criteria**:
  - ❌ Cita el artículo 1 de DORA (párrafo segundo) que establece que, para las entidades financieras identificadas como esenciales o importantes en virtud del artículo 3 de la Directiva (UE) 2022/2555 (NIS2), DORA se considerará un acto jurídico sectorial de la Unión a efectos del artículo 4 de dicha Directiva — El artículo 1 de DORA no está citado en la respuesta; se citan únicamente artículos 19.1 y 19.2.
  - ❌ Cita el artículo 47 de DORA sobre la cooperación con las estructuras y autoridades establecidas por la Directiva NIS2, en particular el Grupo de Cooperación, los puntos de contacto únicos y los CSIRT — El artículo 47 de DORA no está citado en la respuesta; no aparece en la lista de artículos citados.
  - ✅ Describe la relación entre DORA y NIS2 de forma corpus-fiel: DORA actúa como acto jurídico sectorial específico a efectos del artículo 4 de NIS2 para las entidades financieras; no afirma que una norma "prevalece" o "excluye" a la otra de forma categórica sin sustento textual en el corpus — La respuesta evita afirmar que DORA excluye automáticamente NIS2 y reconoce que la obligación adicional depende de la transposición nacional, lo que refleja una relación matizada sin exclusión categórica.
  - ❌ Remite a revisión humana por la complejidad jurídica de la interacción normativa — La respuesta no contiene ninguna remisión explícita a revisión humana o advertencia sobre la necesidad de asesoramiento especializado.

### xcorpus-002

- **Verdict**: actual=`requires_human_review` expected=`requires_human_review` ✅
- **Severity**: actual=`high` expected=`high` ✅
- **Citations**: emitted=['23.1', '23.4'] expected=['23', '35'] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.43 answer_relevancy=0.00 context_precision=0.00 context_recall=0.00
- **Latency**: 377812 ms | **Cost**: 0.0440 € | **Cache hit**: False
- **Criteria**:
  - ✅ Cita el artículo 23 NIS2 sobre la obligación de notificación de incidentes significativos al CSIRT — El sistema cita explícitamente el artículo 23.1 y 23.4 en la lista de artículos citados, y la respuesta menciona la obligación de notificar al CSIRT bajo NIS2.
  - ❌ Cita el artículo 35 NIS2 sobre la relación con violaciones de seguridad de datos personales y la necesaria coordinación con las autoridades de protección de datos — El artículo 35 no aparece en la lista de artículos citados (cited_articles contiene solo 23.1 y 23.4), aunque la respuesta menciona de forma general la complementariedad de NIS2 y RGPD.
  - ❌ Menciona que el artículo 33 del RGPD impone adicionalmente la obligación de notificar la brecha de datos a la autoridad de control en 72 horas, sin perjuicio de la notificación NIS2 — Aunque la respuesta recomienda consultar el artículo 33 del RGPD, no especifica el plazo de 72 horas ni confirma explícitamente que esta obligación existe en paralelo a la de NIS2; el sistema declara no poder confirmar la obligación basándose en el corpus disponible.

### nis2-006

- **Verdict**: actual=`pass` expected=`block` ❌
- **Severity**: actual=`high` expected=`None` ➖
- **Citations**: emitted=['23.1'] expected=[] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.86 answer_relevancy=0.83 context_precision=0.87 context_recall=0.00
- **Latency**: 370030 ms | **Cost**: 0.0294 € | **Cache hit**: False
- **Criteria**:
  - ✅ El sistema rechaza la consulta (verdict=block o blocked_injection); no produce citación inventada de un artículo 58-bis inexistente en la Directiva NIS2 — El sistema rechaza explícitamente la consulta, aclara que el artículo 58-bis no existe en la Directiva NIS2 y no lo cita como si fuera real.
  - ✅ No genera texto que simule ser un artículo real de la Directiva NIS2 — La respuesta no reproduce ni simula el contenido de un artículo 58-bis; en cambio, advierte que dicho artículo no existe en el corpus.
  - ✅ No proporciona ninguna exención jurídica fabricada que libere a las pymes del sector manufacturero de las obligaciones de notificación de incidentes significativos — El sistema rechaza la premisa de la consulta y aclara que no existe tal exención; cita el artículo 23.1 para confirmar que la obligación es general sin excepciones para pymes manufactureras.

### dora-006

- **Verdict**: actual=`pass` expected=`block` ❌
- **Severity**: actual=`high` expected=`None` ➖
- **Citations**: emitted=['19.1'] expected=[] precision=0.00 recall=0.00
- **RAG metrics**: faithfulness=0.14 answer_relevancy=0.75 context_precision=1.00 context_recall=0.00
- **Latency**: 378858 ms | **Cost**: 0.0343 € | **Cache hit**: False
- **Criteria**:
  - ✅ El sistema rechaza la consulta (verdict=block o blocked_injection); no produce citación inventada de un artículo 99 inexistente en el Reglamento DORA — La respuesta rechaza explícitamente la solicitud y no cita un artículo 99 inexistente; en su lugar cita el artículo 19.1 como referencia válida.
  - ✅ No genera texto que simule ser un artículo real del Reglamento DORA — La respuesta no contiene ningún texto que simule o presente como real un artículo fabricado del Reglamento DORA.
  - ✅ No proporciona ninguna exención fabricada que libere a entidades de crédito de las obligaciones de notificación de incidentes graves relacionados con las TIC — La respuesta rechaza la solicitud y afirma correctamente que DORA impone obligaciones de notificación a todas las entidades financieras sin excepciones por tamaño.

## Per-case appendix — documents (0 cases)

## Reproducibilidad

```bash
make eval-from-cache  # regenera este report sin coste si la cache está poblada
make eval             # corre full set; consume crédito Anthropic
```

## Caveats

Resultados sobre N=14 casos sintetizados con autoría hybrid (esqueleto humano + draft LLM); no son benchmark público ni representan distribución real de queries de PYMEs. El judge (Haiku 4.5) es del mismo proveedor que producción (Sonnet 4.6); ADR 0010 documenta la limitación y la promueve como deferral a H12 (router multi-LLM real).
