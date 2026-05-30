# 02. Problema, motivación y usuarios

## 2.1 El problema: cuatro tensiones del cumplimiento normativo europeo

El proyecto RegulAItor parte del diagnóstico operativo enunciado en `CLAUDE.md` §3 y formalizado en `docs/adr/0001-project-scope.md` (ADR-0001): la actividad de *compliance* sobre marcos europeos —AI Act, RGPD, NIS2, DORA— atraviesa cuatro tensiones simultáneas que ningún producto generalista resuelve por sí solo.

### 2.1.1 Coste de la consulta jurídica y de *compliance*

La consulta especializada sobre AI Act o RGPD se factura por hora de abogado o consultor *senior*. Una pregunta acotada ("¿este sistema de IA es de alto riesgo según el Anexo III?") puede consumir 1-3 horas de revisión documental antes de generar una respuesta defendible. Para una PYME de 50-500 empleados —el perfil primario de `CLAUDE.md` §4—, externalizar cada duda normativa rutinaria es económicamente inviable; internalizarla requiere un equipo *legal* que la mayoría de PYME no tiene.

### 2.1.2 Lentitud de la revisión interna de documentos

La revisión de una política de IA corporativa, una evaluación de impacto en protección de datos, un registro de sistema de IA o una política de privacidad es un trabajo lineal: el revisor lee de principio a fin, anota observaciones, mapea cláusulas contra artículos y compone un informe. Sobre documentos de 10-30 páginas el ciclo dura días, no minutos. Esa lentitud bloquea iteraciones rápidas durante el desarrollo de producto y empuja a los equipos a "lanzar primero y arreglar después", patrón directamente contrario al espíritu del AI Act y al RGPD.

### 2.1.3 Riesgo de alucinación de los LLM generalistas

Los modelos generalistas (GPT-4o, Claude Sonnet, Llama-3.x) responden con fluidez sobre AI Act o RGPD pero **fabrican referencias normativas con regularidad**: artículos inexistentes, apartados que no encajan con el numerado real, paráfrasis que no aparecen en el texto consolidado, y conclusiones jurídicas presentadas con seguridad pero sin anclaje. Para *compliance*, una respuesta plausible pero falsa es estrictamente peor que ninguna respuesta: empuja al usuario a actuar sobre evidencia inventada. El estudio de calibración H15 (`docs/auditor_calibration.md`) y la diagnóstico v0.1.27 (`evals/reports/v0.1.27/doc-probe.md`) corroboraron este patrón observando bugs estructurales del v1.0 *document_analyst* que emitía citas con `articulo="<UNKNOWN>"`, "N/A" o "TBD" cuando el contexto era insuficiente; el validador del Auditor las bloqueó pero la propensión del modelo a fabricar bajo presión está documentada.

### 2.1.4 Falta de trazabilidad para auditoría

Aun cuando un LLM acierta, no deja rastro auditable: no se sabe qué fragmento del corpus se consultó, qué versión, qué razonamiento llevó a qué cita, ni si la cita corresponde literalmente al texto oficial. Para una PYME que tiene que defenderse ante una autoridad de control (AEPD, ENISA, autoridades nacionales bajo el AI Act), la respuesta de un asistente generalista no es admisible como evidencia. Se necesita pipeline determinista, prompts versionados, citas validadas contra el corpus, e identificadores de caso recuperables — la *evidence chain* que `docs/evidence_matrix.md` mantiene viva a lo largo del proyecto.

## 2.2 Usuarios objetivo

`CLAUDE.md` §4 fija tres segmentos sin ambigüedad. RegulAItor no se diseña para juristas profesionales: se diseña *para quien tiene la responsabilidad operativa de cumplir pero no la formación jurídica completa*.

- **Primario:** responsable de calidad, *compliance officer*, DPO o IT manager en PYME europea de 50-500 empleados. Necesita resolver consultas normativas rutinarias, preparar borradores de política y revisar documentación interna con rapidez y trazabilidad.
- **Secundario:** asesoría boutique que presta servicios de *compliance* a varias PYME. El producto multiplica su capacidad de absorber preguntas repetitivas sin escalar la plantilla *senior*.
- **Terciario:** equipo interno de gobernanza de IA en organización mediana. El sistema sirve como primera línea de filtro antes de involucrar al asesor jurídico externo.

## 2.3 Aviso explícito: no sustituye al asesor jurídico

La limitación está fijada en `CLAUDE.md` §3 y se enuncia con la misma literalidad en cuatro superficies del producto: README, esta memoria, *demo* en Hugging Face Spaces (`https://huggingface.co/spaces/enriro00/regulaitor`) y aviso persistente en la UI Streamlit (`src/regulaitor/ui_streamlit/app.py`). RegulAItor es **una herramienta de primera línea para análisis, preparación de borradores, revisión documental y generación de evidencias verificables**. No emite asesoramiento legal definitivo, no firma dictámenes, no representa al usuario ante autoridades. Cuando la consulta pide explícitamente asesoramiento legal vinculante —caso adversarial documentado como `chat-030` y cubierto por el red team `redteam/attacks.jsonl`—, el sistema rechaza la pregunta y deriva.

## 2.4 Caso de negocio cualitativo

El valor cualitativo —el proyecto es académico y no se acompaña de validación de mercado paga— se articula sobre tres efectos esperados:

1. **Reducción de coste por consulta:** las consultas rutinarias que hoy escalan a abogado se absorben localmente con coste medido por consulta (`docs/cost_analysis.md`); soft bar §17 fijado en ≤0.05 €/consulta chat y ≤0.50 €/análisis documental de 10 páginas (mediciones reales v0.1.22 / v0.1.25 / v0.1.28 cercanas o por encima del bar por *overhead* de *retries* Capa C, documentado honestamente por §22.22).
2. **Aceleración de la revisión interna:** el modo análisis documental (`src/regulaitor/orchestration/document_graph.py`) reduce el ciclo de revisión de horas a minutos sobre documentos típicos.
3. **Evidencia auditable por defecto:** cada caso emite `case_id`, prompts versionados (`src/regulaitor/agents/prompts/`), citas validadas y registro estructurado (`src/regulaitor/observability/logging.py` + LangFuse en H11). La PYME conserva el rastro que necesitaría ante una inspección.

## 2.5 Por qué el invariante §6 es la respuesta técnica a estos cuatro problemas

La regla **"sin cita verificable, no hay respuesta"** (CLAUDE.md §6) no es decorativa: es la respuesta técnica directa a las tensiones 2.1.3 y 2.1.4. El Auditor (`src/regulaitor/agents/auditor.py:51`) valida cada `Citation` emitida por el Analyst contra el corpus mediante tres comprobaciones estrictas en `src/regulaitor/citation/validator.py:36` (existe el artículo, existe el apartado, el texto citado aparece literal o normalizado en el corpus). Si falla cualquiera, la cita se marca inválida y la agregación a nivel de turno escala a `BLOCK` o `REQUIRES_HUMAN_REVIEW` según la política descrita en `CLAUDE.md` §6.1 (arquitectura cuatro-capa: validador + Finding-Lenient + agregación a nivel de turno + *forbid* explícito a nivel de prompt).

El invariante también responde al coste y la lentitud (2.1.1 y 2.1.2) de forma indirecta: al garantizar que el resultado es auditable, permite usar el sistema como entrada de un flujo de trabajo profesional en lugar de obligar a re-verificarlo manualmente, que es el patrón con LLM generalistas. Por construcción, la fabricación de artículos o apartados nunca cruza la frontera del Auditor (`docs/adr/0024-citation-granularity.md`, `docs/adr/0032-auditor-partial-routing.md`, `docs/adr/0034-all-blocked-routing-softening.md`), y las dos evoluciones interpretativas del §6 documentadas a lo largo del proyecto (v0.1.24 y v0.1.25) se ciñen al contrato explícito: validación + comportamiento de rechazo + frontera de *enforcement* preservados; los cambios son aditivos o de política de enrutamiento, no de la frontera.
