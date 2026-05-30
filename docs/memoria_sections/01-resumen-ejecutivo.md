# 1. Resumen ejecutivo y contribución del TFM

## 1.1 Qué es RegulAItor

RegulAItor es un servicio multi-agente de cumplimiento normativo europeo construido como Trabajo Fin de Máster (Máster en IA Generativa). Convierte consultas normativas y revisiones de documentos corporativos (políticas de IA, contratos, evaluaciones de impacto, registros de sistemas de IA) en respuestas e informes auditables sobre cuatro corpus oficiales — Reglamento de IA (AI Act), RGPD, NIS2 y DORA — ingestados desde EUR-Lex y versionados localmente (`corpus/indexes/regulaitor.lance`, 1569 chunks; ver `src/regulaitor/rag/store.py`).

No es un chatbot legal genérico ni sustituye a un asesor jurídico. Es una herramienta de primera línea para análisis, preparación de borradores y generación de evidencias verificables, con dos superficies: modo chat (`/ask`) y modo análisis documental (`/analyze`), expuestas vía FastAPI + Streamlit y desplegadas en Hugging Face Spaces (demo público vivo: <https://huggingface.co/spaces/enriro00/regulaitor>).

## 1.2 Problema que resuelve

Cuatro problemas concretos del compliance europeo en PYME 50-500 empleados (CLAUDE.md §3): alto coste de la consulta jurídica, lentitud de la revisión documental interna, riesgo de alucinación de LLM generalistas y falta de trazabilidad para auditoría. RegulAItor responde con la narrativa ancla del proyecto (CLAUDE.md §2, línea 19):

> "RegulAItor no responde sin cita verificable: convierte la consulta normativa rutinaria y la revisión documental en un acto auditable, en minutos y por céntimos."

## 1.3 Regla central — "no citation, no answer"

El invariante §6 es la columna vertebral del sistema. Toda salida del Analyst-Agent pasa por el Auditor-Agent (`src/regulaitor/agents/auditor.py:54`), que valida cada cita contra el corpus mediante tres comprobaciones estrictas en `src/regulaitor/citation/validator.py:36-144` (article exists, apartado exists, text normalized match) con fail-fast y campo `failed_check: Literal[1,2,3] | None` para observabilidad aditiva (ADR-0031). Si falla cualquier validación crítica, la salida se bloquea o se marca como "requiere revisión humana". No hay atajos.

A lo largo del proyecto, el invariante se ha refinado en una **arquitectura de cuatro capas** (CLAUDE.md §6.1) — todas preservan el enforcement boundary por construcción:

- **Capa (a)** per-citation validator: byte-equivalent desde H4; instrumentación aditiva en v0.1.24 (ADR-0031).
- **Capa (b)** Finding-Lenient aggregation (`auditor.py:65`): byte-unchanged desde v0.1.21.
- **Capa (c)** Turn-level aggregation policy: modificada en v0.1.21 (quorum, ADR-0027), v0.1.25 (partial routing, ADR-0032) y v0.1.29 (all-blocked mirror, ADR-0034) vía el helper compartido `_all_blocked_findings_paraphrase_only` (`auditor.py:20-48`). Cualquier Check 1 ó 2 retorna `False` → fabricación nunca es PASS por construcción.
- **Capa (d)** prompt-level explicit forbid: Analyst v1.5 (chat) y document_analyst v1.6 (doc, ADR-0033).

## 1.4 La contribución del TFM es la metodología

El núcleo de la contribución académica no es un componente aislado sino el **ciclo científico aplicado a un sistema multi-agente con invariante de seguridad**: *diagnose → intervene → measure → refute → revert → document*. Se materializa en trece hitos consecutivos con framing honesto §22.22 (v0.1.19 → v0.1.32), entre ellos dos REVERTs documentados con `§REVERT` retenida como registro científico:

- **v0.1.23** — Auditor lenient quorum (ADR-0030). Predicho verdict_match +0.10; medido -0.03; refutado en T6 paid (€1.76); revertido atómicamente; §6 íntegro. Lección: capa equivocada (Tier 1 quorum NO era el bottleneck per v0.1.24.1 Path B attribution).
- **v0.1.30** — Title-augmented corpus embeddings (ADR-0035). Predicho citation_recall +0.05; medido flat con regresión de precision por sobre-citación; revertido tras probe €0.65; T7 main SKIPPED por disciplina de coste. Lección: la asimetría query-side prepend (ayuda) vs corpus-side prepend (rompe) es el hallazgo científico de v0.1.30.

El resto del linaje (v0.1.25 CONFIRM partial-routing +0.33 verdict_match; v0.1.29 CONFIRM all-blocked +0.08; v0.1.20 prompt flip v1.4) demuestra que la misma disciplina diagnostico-primero produce CONFIRMs y REVERTs sin desestabilizar el invariante §6.

## 1.5 Estado actual y entregables

- **Tag actual:** `v0.1.32-h16-deploy` (H16 cerrado 2026-05-28). Próximo: `v1.0.0` (H17 cierre académico).
- **Demo público vivo:** Hugging Face Spaces (smoke OK: AI Act sistemas alto riesgo → PASS + 2 Findings + 1 cita válida + 1 paraphrase, visibilizando la arquitectura §6.1).
- **Trazabilidad:** 35 ADRs (`docs/adr/0001-*.md`…`0035-*.md`) + `docs/technical_decisions_log.md` (>5300 líneas).
- **Tests:** baseline HEAD post-v0.1.32-post + I-batch + minor-batch: **1000 passed / 0 failed / 1 skipped** en gate `pytest -m "not slow"` (28 deselected slow); mypy strict 71 ficheros Success; cobertura ≥85% (gate); redteam-smoke 0.92 (= gate §16.2 #4 ≥0.90; carry desde v0.1.14).
- **Métricas chat H10 25-case main (cohorte v0.1.29-prod-main vs v0.1.25 baseline cached, `evals/reports/v0.1.29/comparison.md`):** verdict_match 0.76 (+0.08), citation_recall 0.81 (hit aspiracional ≥0.80), faithfulness 0.72, answer_relevancy 0.70. **7/7 bars v0.1.20 PASS preservados** (§17 dual-layer, ADR-0021).
- **Métricas doc v0.1.28 cohorte combinada N=10 (probe 3 + main 7, `evals/reports/v0.1.27/v0.1.28-doc-prod-main.md` y `…-probe.md`):** citation_recall 0 → 0.33 tras v0.1.28 prompt v1.6 + title-prepend query-side (CLAUDE.md §27 v0.1.28); el gap descriptive→obligation queda como trabajo HX (HyDE / hybrid BM25 / custom reranker).

La memoria desarrolla, en las secciones siguientes, cómo cada decisión llega a este estado y por qué la metodología — no el componente — es la contribución defendible.
