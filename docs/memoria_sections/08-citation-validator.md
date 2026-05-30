# 08. Citation validator y arquitectura §6 de cuatro capas

## 8.1 Propósito y posición en el sistema

El invariante §6 del proyecto (CLAUDE.md §6, "Sin cita verificable, no hay respuesta") es el núcleo diferencial de RegulAItor frente a un chatbot legal generalista. Su implementación no se concentra en un único punto del código, sino en una arquitectura de cuatro capas defensivas, donde cada capa cierra una clase distinta de fallo posible y donde el invariante se preserva por construcción incluso si una de las capas se relaja deliberadamente.

Esta sección documenta:

1. La capa (a) per-citation validator, el guardián canónico del invariante.
2. La capa (b) Finding-Lenient aggregation, regla agregadora por Finding.
3. La capa (c) Turn-level aggregation policy, agregadora por turno con dos sub-rutas modificadas (v0.1.25 y v0.1.29).
4. La capa (d) prompt-level explicit forbid, defensa en profundidad introducida en v0.1.28 (ADR-0033).
5. Las tres evoluciones interpretivas del enunciado §6 que el linaje de hitos ha producido (v0.1.24 ADR-0031, v0.1.25 ADR-0032, v0.1.32-post C1).

El propósito del diseño multi-capa es que la fabricación nunca pueda resultar en un veredicto `PASS`: cualquier intento de fabricar un artículo (Check 1) o un apartado (Check 2) inexistente cae fuera del corpus y se rechaza en la capa (a); cualquier softening posterior en (c) está condicionado a `failed_check==3` (mismatch de paráfrasis cuando artículo y apartado existen), de modo que las rutas de salida BLOCK y REQUIRES_HUMAN_REVIEW se preservan ante fabricación por construcción.

## 8.2 Capa (a) — per-citation validator

### 8.2.1 Contrato y entradas

El validator vive en `src/regulaitor/citation/validator.py:36` y expone una única función pública `validate(citation: Citation, *, loader: LoaderProtocol | None = None) -> AuditResult`. Recibe una `Citation` (Pydantic v2 frozen, `src/regulaitor/citation/schemas.py:17-37`) y devuelve un `AuditResult` (`src/regulaitor/citation/schemas.py:40-52`).

La `Citation` declara `norma`, `articulo`, `apartado` opcional, `language` y `text`. El loader (`regulaitor.corpus.loader`) es la única fuente de verdad sobre la existencia de artículos y apartados en el corpus indexado; el validator nunca compara contra conocimiento del modelo (CLAUDE.md §22.15).

### 8.2.2 Las tres comprobaciones estrictas (fail-fast en orden)

El validator ejecuta tres comprobaciones independientes en orden y devuelve en cuanto la primera falla (`src/regulaitor/citation/validator.py:46-134`):

- **Check 1 — `article_exists`** (líneas 46-61): `loader.get_article(norma, articulo, language)`. Si lanza `KeyError`, el artículo no está en el corpus → `AuditResult(validated=False, article_exists=False, failed_check=1)`. Detecta fabricación de artículo.
- **Check 2 — `apartado_exists`** (líneas 63-88): sólo si `citation.apartado is not None`. `loader.get_paragraph(...)` recupera el texto exacto del apartado; si lanza `KeyError`, el apartado no existe dentro de un artículo que sí existe → `AuditResult(article_exists=True, apartado_exists=False, failed_check=2)`. El `reason` incluye la lista de apartados válidos para facilitar diagnóstico.
- **Check 3 — `text_normalized_match`** (líneas 93-134): la cita y el texto corpus se normalizan mediante `_normalize` (importado de `src/regulaitor/rag/chunking.py`, decisiones log 2026-05-05; lowercase + strip accents + unify dashes + collapse whitespace) y se comprueba `citation_norm in target_norm`. Si no aparece, `failed_check=3`; el `reason` distingue entre `text_not_in_apartado` y `text_not_in_article`.

La decisión de reutilizar `_normalize` del chunker (en lugar de fuzzy matching o thresholds) garantiza simetría matemática entre la forma indexada y la forma comparada: una cita correcta no falla por diferencias triviales (mayúsculas, guiones, espacios múltiples) y una cita incorrecta no pasa por aproximación heurística.

### 8.2.3 El campo aditivo `failed_check` (v0.1.24 ADR-0031)

Hasta v0.1.24 el `AuditResult` exponía únicamente el booleano `validated`. v0.1.24 (ADR-0031) añadió `failed_check: Literal[1, 2, 3] | None = None` a `AuditResult` (`src/regulaitor/citation/schemas.py:49`), poblado por el validator en cada `return` fail-fast. Las cuatro asignaciones son aditivas: la semántica de validación es byte-equivalente a la pre-v0.1.24 (mismo orden de checks, mismo `validated`, mismos `article_exists` / `apartado_exists` / `text_normalized_match` / `reason`).

Este campo no participa en ninguna decisión del validator; es pura observabilidad. Su valor se materializa en las capas superiores (c) v0.1.25 y v0.1.29, que necesitan distinguir entre "la cita apunta a contenido inexistente (Check 1/2 — fabricación)" y "la cita apunta a contenido real pero el texto literal no coincide (Check 3 — paráfrasis)" para tomar decisiones de routing seguras.

### 8.2.4 Defensa en profundidad whitespace (v0.1.32-post)

La revisión profunda de 61 agentes al cierre de H16 (workflow `wf_dc377549-4c0`) identificó el hallazgo crítico C1: `Citation(text=" ")` pasaba `Field(min_length=1)` (longitud uno), luego `_normalize(" ") == ""`, y finalmente `"" in any_string == True` → `validated=True` → §6 PASS. La fabricación con un solo espacio en blanco era empíricamente reproducible contra el corpus en vivo.

El fix v0.1.32-post se aplica en dos capas (`docs/technical_decisions_log.md` §v0.1.32-post):

1. **Capa schema** (`src/regulaitor/citation/schemas.py:28-37`): `@field_validator("text") _reject_whitespace_only` rechaza en construcción cualquier `text` cuyo `strip()` quede vacío, lanzando `ValueError("Citation.text cannot be whitespace-only (§6 invariant)")`.
2. **Defensa en profundidad en el validator** (`src/regulaitor/citation/validator.py:96-116`): tras normalizar, si `len(citation_norm) == 0` se devuelve `AuditResult(validated=False, failed_check=3, reason="empty_citation_text_after_normalization: …")`. Esto cubre el escenario en que un caller futuro construya una `Citation` saltándose el schema (test injection, mutación posterior, deserialización irregular).

Tres regresion tests fijan el contrato: `test_citation_schema_rejects_whitespace_only_text` (parametrizado sobre seis variantes incluido `\xa0` no-break space), `test_validator_rejects_empty_after_normalization_defense_in_depth` (mutación `object.__setattr__` para saltar el schema), y `test_citation_schema_accepts_legitimate_text` (regresión sobre el "ningún input legítimo se ve afectado").

## 8.3 Capa (b) — Finding-Lenient aggregation

La capa (b) vive en `src/regulaitor/agents/auditor.py:59-66`. Para cada Finding del Answer, el AuditorAgent valida cada citation mediante el validator (línea 60) y aplica una agregación Lenient por Finding:

```text
finding_verdicts.append("pass" if any(r.validated for r in this_finding_results) else "blocked")
```

Un Finding pasa si **al menos una** de sus citations valida estrictamente; se bloquea si **todas** sus citations fallan algún check. Esta es la primera capa donde fabricación y paráfrasis se separan operativamente: un Finding con dos citations donde una es Check 1 (fabricación de artículo) y otra es válida pasa Lenient, pero el reason de la inválida persiste en `audit_results` para diagnóstico.

Este bloque es **byte-unchanged desde v0.1.21**: ningún hito posterior (incluidos v0.1.23 REVERT, v0.1.25 D2, v0.1.29 D Mirror) lo ha modificado. La razón es estructural: cualquier softening en la capa (b) tendría el efecto de aceptar fabricación dentro de un Finding individual, lo cual viola el invariante §6 de forma directa. Las decisiones de softening se han trasladado deliberadamente a la capa (c).

## 8.4 Capa (c) — Turn-level aggregation policy

La capa (c) (`src/regulaitor/agents/auditor.py:68-135`) combina los `finding_verdicts` parciales en un veredicto de turno final (`PASS`, `BLOCK`, `REQUIRES_HUMAN_REVIEW`). Tiene tres sub-rutas según la composición de los Finding verdicts:

### 8.4.1 Sub-ruta all-pass-Findings: Tier 1 RHR quorum (v0.1.21 ADR-0027)

`src/regulaitor/agents/auditor.py:87-98`. Cuando todos los Findings pasan Lenient, contamos `n_invalid_citations` agregados sobre el Answer completo. Si `n_invalid_citations >= 2`, escalamos a `REQUIRES_HUMAN_REVIEW` (quorum); si `n_invalid_citations < 2`, `PASS`.

Esta sub-ruta fue introducida en v0.1.21 (ADR-0027 D1) para mitigar el patrón "nonempty-RHR-still-RHR" identificado en v0.1.20 T6.5 (42% de los RHR de v1.0). El umbral binario `>= 2` evita el efecto de una cita aislada inválida forzando RHR cuando el resto del Answer está bien soportado.

v0.1.23 (ADR-0030) intentó relajar este quorum mediante lenient counting (Design B); el experimento se SHIPPED, midió empíricamente, y se REVERTIÓ tras refutación (0/10 H1 cases flipados como se predijo; verdict_match -0.03 frente a +0.10 esperado). La sub-ruta all-pass quedó por tanto STRICT y no se ha vuelto a tocar.

### 8.4.2 Sub-ruta partial-Findings: D2 softening (v0.1.25 ADR-0032)

`src/regulaitor/agents/auditor.py:119-135`. Cuando hay mezcla de Findings que pasan y Findings que bloquean. Pre-v0.1.25 era siempre `RHR`. Post-v0.1.25:

```text
if _all_blocked_findings_paraphrase_only(finding_verdicts, per_finding_results):
    PASS
else:
    RHR
```

El helper compartido (`src/regulaitor/agents/auditor.py:20-48`) devuelve `True` si y sólo si **toda** citation inválida en **todo** Finding bloqueado tiene `failed_check==3`. Cualquier Check 1 o Check 2 → `False` → RHR preservada.

v0.1.25 fue una validación paga (€1.66) con resultado CONFIRM: verdict_match +0.33 (de 0.40 a 0.73 sobre H10 30-case), 9/10 H1 cases flipados RHR→PASS como predicho por v0.1.24.1 Path B 8/10 dominance, 7/7 v0.1.20-bar PASS.

### 8.4.3 Sub-ruta all-blocked-Findings: D Mirror softening (v0.1.29 ADR-0034)

`src/regulaitor/agents/auditor.py:99-118`. Cuando todos los Findings bloquean. Pre-v0.1.29 era siempre `BLOCK`. Post-v0.1.29 reutiliza el **mismo helper** que la sub-ruta partial:

```text
if _all_blocked_findings_paraphrase_only(finding_verdicts, per_finding_results):
    PASS
else:
    BLOCK
```

v0.1.29 (€1.89 paid) midió verdict_match +0.08 (0.68→0.76 sobre H10 25-case main; on-forecast vs predicción ADR-0034 +0.033 a +0.10), con chat-016 flipado BLOCK→PASS como predicho.

### 8.4.4 La garantía estructural §6 en la capa (c)

El helper `_all_blocked_findings_paraphrase_only` es el único punto donde la capa (c) puede aceptar Findings bloqueados como PASS. Su contrato es binario: cualquier `failed_check != 3` en cualquier citation inválida de cualquier Finding bloqueado retorna `False`. Esto significa:

- Check 1 (fabricación de artículo) en cualquier blocked Finding → helper `False` → routing pre-v0.1.25/v0.1.29 preservado (RHR o BLOCK).
- Check 2 (fabricación de apartado) en cualquier blocked Finding → helper `False` → mismo resultado.
- `failed_check=None` (datos cacheados pre-v0.1.24) → helper `False` (conservador) → routing legacy preservado.

Por construcción, ninguna combinación de inputs puede convertir una fabricación en PASS. La cadena de detección capa (a) → capa (b) → capa (c) está unbroken.

## 8.5 Capa (d) — Prompt-level explicit forbid (v0.1.28 ADR-0033)

La capa (d) opera del lado del modelo, no del Auditor. Vive en los system prompts de los agentes Analyst:

- **Chat role**: `src/regulaitor/agents/prompts/analyst/system.v1.5.md` (default desde v0.1.21 final-review C4). Hard rule 4 prohíbe emitir strings placeholder en `articulo` (`UNKNOWN`, `N/A`, `TBD`, etc.); Hard rule 2 implementa Finding-based refusal cuando el contexto recuperado es insuficiente (emite exactamente un Finding con texto = rechazo + citation a un artículo de scope/applicability + `severity="high"`).
- **Doc role**: `src/regulaitor/agents/prompts/document_analyst/system.v1.6.md` (default desde v0.1.28 ADR-0033 D2; flip `default_version = "v1.5" if prompt_role == "analyst" else "v1.6"` en `src/regulaitor/agents/analyst.py:125`). Misma Hard rule 4 + adaptación del patrón de rechazo a análisis de segmentos documentales.

El origen empírico es v0.1.27, donde la primera medición paga de doc-mode con v1.0 + Tier 2 Capa A+B+C reveló 3/3 docs BLOCK con citations placeholder `<UNKNOWN>`: Sonnet, presionado por el retry loop tras `Field(min_length=1)` rechazando empty findings, fabricaba Findings con strings inválidos que el validator (capa a) rechazaba en Check 1, propagando a all-blocked → BLOCK.

La capa (d) es defensa en profundidad: reduce la tasa del bug placeholder mediante disciplina del prompt; la capa (a) sigue siendo el catch final que rechaza cualquier instancia que se cuele. Las dos capas son complementarias, no redundantes: la (d) actúa antes (el modelo no debería ni siquiera generar el placeholder), la (a) actúa después (si se genera, no pasa).

## 8.6 Tres evoluciones interpretativas del enunciado §6

El enunciado §6 ("no citation, no answer") es invariante en su contenido, pero su **formulación operativa** se ha refinado tres veces a medida que el linaje de hitos amplió la superficie tocable sin debilitar la garantía:

### 8.6.1 v0.1.24 ADR-0031 — "byte-equivalent semantics + additive observability"

El predicado pre-v0.1.24 era literal: `src/regulaitor/citation/` byte-unchanged desde H4. v0.1.24 añadió `failed_check` al schema y cuatro asignaciones al validator. La nueva formulación distingue (ADR-0031 §"§6 interpretive evolution"):

1. Validation semantics preserved (mismo orden, mismo `validated`, mismas tres comprobaciones).
2. Rejection behavior preserved (ninguna cita que antes fallaba ahora pasa; ninguna que pasaba ahora falla).
3. §6 enforcement boundary preserved (el binario validate/reject opera en el mismo punto).
4. New field is pure instrumentation (no participa en ninguna decisión del validator).
5. Backward-compat schema-level (Pydantic v2 acepta `failed_check` ausente como `None`).

### 8.6.2 v0.1.25 ADR-0032 — "THREE-layer Auditor architecture"

Pre-v0.1.25 hablábamos de "validator §6" como bloque monolítico. v0.1.25 (ADR-0032 §"§6 interpretive distinction") explicitó la separación entre la capa (a) validator, la capa (b) Finding-Lenient byte-unchanged, y la capa (c) Turn-level aggregation policy modificable. La refinación de la sub-ruta partial (y posteriormente all-blocked en v0.1.29) ocurre exclusivamente en (c) bajo la garantía binaria del helper.

### 8.6.3 v0.1.32-post — "construction-level tightening + dual-layer whitespace defense"

Pre-v0.1.32-post el validator era byte-equivalent semánticamente pero tenía un escape construction-level: `Field(min_length=1)` aceptaba whitespace; `_normalize` lo colapsaba a string vacío; `"" in target` retornaba `True`. La nueva formulación (`docs/technical_decisions_log.md` §v0.1.32-post):

- Antes: byte-equivalent semantics + construction-level escape hatch through Pydantic.
- Después: byte-equivalent on legitimate non-empty inputs (ningún quote legítimo del corpus es whitespace-only); whitespace-only rechazado en DOS capas (schema + validator defense-in-depth).
- El boundary §6 está **estrictamente apretado**, nunca relajado. Ningún caso de uso legítimo se ve afectado.

Esta es una tightening, no una evolución arquitectónica; por eso no genera ADR (ADRs 0024 / 0031 / 0032 ya cubren la arquitectura). El fix se shippea como parte del cierre H16-post, antes de empezar a escribir la memoria, porque el hallazgo de la revisión profunda era time-sensitive: la garantía estructural "por construcción la fabricación nunca es PASS" (CLAUDE.md §6.1) habría sido refutable en directo por un miembro del tribunal escribiendo `Citation(text=" ")` en la demo.

## 8.7 Consecuencias para la defensa del TFM

La arquitectura de cuatro capas es el activo técnico central de RegulAItor. Su valor de defensa académica reside en tres propiedades verificables:

1. **Trazabilidad**: cada citation produce un `AuditResult` con `failed_check`, `reason`, y la cadena de capas que la procesó. El campo `audit_results` del `AuditedAnswer` (`src/regulaitor/citation/schemas.py:139-148`) persiste esta trazabilidad para auditoría posterior.
2. **Modificabilidad sin pérdida de garantía**: las sub-rutas v0.1.25 y v0.1.29 demuestran que se puede mejorar verdict_match (+0.33 y +0.08 respectivamente, medidos en runs pagos) sin tocar el validator ni la agregación Finding-Lenient; el helper binario aísla el riesgo §6.
3. **Reversibilidad probada**: v0.1.23 (Design B sobre la sub-ruta all-pass) y v0.1.30 (title-augmented corpus embeddings, capa retrieval) son las dos reverts documentadas en el linaje §22.22. Ambas se shipearon, midieron, refutaron y revirtieron sin tocar el invariante. Las §REVERT sections de ADR-0030 y ADR-0035 son evidencia metodológica de que la disciplina diagnose-intervene-measure-refute-revert-document funciona.

La regla "no citation, no answer" deja de ser un eslogan en el README y pasa a ser un contrato verificable por capas, con código byte-equivalent donde corresponde, con observabilidad aditiva donde se necesita decidir, y con softening explícito condicionado a un binario que no admite fabricación por construcción.
