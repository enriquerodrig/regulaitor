# G1 — Sovereign quality A/B: Mistral Small + v1.6 vs Sonnet + v1.5

**Fecha:** 2026-07-14 · **Tipo:** milestone de pago (medición) · **Presupuesto autorizado:** ~€1.80 esperado / €2.70 high · **Gate:** DP-sovereign go/no-go.

## Pregunta

¿Aguanta el modelo abierto self-hosted (**Mistral Small**) con el prompt Analyst
**v1.6** (Hard Rule 10, disciplina de formato de cita) lo suficiente —calidad + §6—
para que el despliegue EU-soberano (G3) sea **pura infra**, o hay que iterar
(HyDE / otro modelo / prompt) antes de gastar en host?

Contexto: el probe R1 (N=30) midió Mistral Small a `verdict_match 0.70` vs Sonnet
~0.76, con causa raíz en citas prosa-style (`"13.1 y 2"`, `"16.a"`) que el validador
§6 rechaza (Check 2) → RHR espurio. El prompt **v1.6** se autoró para cerrar ese gap
pero **nunca se re-midió**. G1 es esa medición.

## Metodología

- **2-arm FRESCO mismo-día** (sin caveat de API-drift; es la medición fundacional):
  - **Arm A (prod):** Sonnet + analyst v1.5 (default env-unset).
  - **Arm B (soberano):** Mistral Small + analyst v1.6, vía
    `REGULAITOR_ANALYST_MODEL_CHOICE=self_hosted` + `REGULAITOR_ANALYST_PROMPT_VERSION=v1.6`
    (Mistral por `REGULAITOR_SELFHOST_*`). Seam Analyst-only: **juez + Council quedan en
    sus modos default** para un A/B limpio de la elección de modelo Analyst.
- **Juez:** Haiku 4.5 (sin cambios, ADR-0021).
- **Cohorte:** H10 chat. **Probe chat-001..005 (N=5)** → gate SKIP/PROCEED → **main
  chat-006..025 (N=20)**. Incluye 2 casos content-safety (chat-014/015).
- **Checkpoint per-case** (`evals/checkpoint.py`, lección H15.2 T6) → un crash no pierde
  datos. Report isolation Path-B (snapshot a `evals/reports/g1/`, restaura `latest.md`).
- **Runner:** `scripts/g1_run.py` (2-arm wrapper sobre `evals/harness.main`, modelado en
  `probe_r1_run.py`). truststore.inject_into_ssl() (bug CryptoAPI CRL Windows). Pre-flight
  confirmó ambos arms (Sonnet €0.00011 / Mistral €0.0 free-tier) antes del run.

## Criterio de decisión (§22.22 — sin prometer números)

- **Piso de seguridad DURO (innegociable):** 0 fabricaciones, invariante §6 al 100%
  (toda cita emitida validada por el validador byte-unchanged), chat-014/015 content-safe
  (revisión manual), redteam-smoke 0.92 intacto (prompt-blind). Si falla → **no-go
  soberano**, reportado honesto.
- **Calidad (informa el go/no-go, no lo gatea de forma dura):** delta `verdict_match`
  Mistral+v1.6 vs Sonnet+v1.5; cuántos de los 7 `v0.1.20-bar` cruza el arm B; si v1.6
  arregló las citas-prosa del R1 (la causa raíz). **"Aguanta"** = delta aceptable + piso
  PASS → G3 es infra pura. Si no → se sabe antes de gastar en host (carry-forward: HyDE,
  otro modelo abierto, iteración de prompt).

## Invariantes duras

`citation/validator.py` + `auditor.py` + `sanitizer.py`/`injection.py` **byte-unchanged**
(G1 es medición, no toca enforcement). El arm soberano usa sólo los seams env ya shipeados
(v0.1.5-h15 `REGULAITOR_ANALYST_PROMPT_VERSION` + probe-R1 `self_hosted`); cero código de
producción nuevo.

## Coste (rangos)

| | Bajo | Esperado | Alto (×1.5) |
|---|---|---|---|
| G1 2-arm N=25 (5 probe + 20 main) | €1.00 | €1.80 | €2.70 |

Mistral casi gratis ($0.15/$0.60 por M, free-tier €0); coste = Sonnet + juez Haiku +
Council. Free-tier lento (~min/query) → wall-clock de horas, coste € bajo. Si el probe
excede el rango proporcional → SKIP + reportar (disciplina de coste,
[[feedback_cost_estimation_discipline]]).
