---
name: redteam-runner
description: Use this skill when running the H9 red team suite, reading `redteam/reports/latest.md`, deciding when to re-run, or extending the attack set. Activates from H9 onwards.
version: 1.0
---

# redteam-runner

Procedimiento canónico para ejecutar la suite de red team de RegulAItor.

## Cuándo invocarme

- Antes de `make redteam` (validar presupuesto; full run cuesta ~$3.31).
- Tras modificar `security/injection.py`, `document/sanitizer.py`, o `citation/validator.py`
  para confirmar que el gate sigue ≥ 0.90.
- Cuando se considera extender la suite (HX1 fuzzing, ampliar a ≥ 80 en avanzado).
- Antes de mergear cualquier PR que toque los módulos de seguridad.

## Procedimiento estándar

### Run estratégico por tipo de cambio

| Cambio | Comando | Coste estimado |
|---|---|---|
| Docs, reports, sin código | No correr | $0 |
| Patterns en `injection.py` / categorías sanitizer / validator | `make redteam-smoke` primero; si pasa, no es necesario full run | $0 |
| Cambio significativo en defensa (nuevo pattern ES, nueva categoría sanitizer) | `make redteam-smoke` luego `make redteam` | ~$3.31 |
| Backend H1-H5 (NO debería tocarse) | n/a — red team no diseñado para regression de backend | n/a |

### Leer el report

`redteam/reports/latest.md` tiene seis secciones: header, gate §16.2 #4, per-escenario,
per-layer, per-attack appendix, reproducibilidad, caveats.

Gate crítico: `block_rate_final ≥ 0.90`. Si falla post-improvements, hay un gap nuevo →
diseñar nuevo pattern o derivar a H15 (calibración Auditor).

Baseline (pre-improvements) y final (post) se reportan ambos. La mejora forma parte del
entregable; no se oculta la métrica pre-fix.

### Ejecutar smoke (CI equivalent)

```bash
make redteam-smoke   # solo ataques deterministas, $0, ~30s
```

Smoke corre únicamente attacks con `requires_e2e: false` (doc-mode sanitizer + injection).
El mismo job corre en CI en cada PR que toca módulos de seguridad.

### Ejecutar full run (human-manual)

```bash
make redteam         # chat E2E + doc determinista + subset requires_e2e=true
```

Costo estimado: ~$3.31 (22 chat × $0.019 + ~15 doc-e2e × $0.193). Requiere `ANTHROPIC_API_KEY`
en `.env` con créditos suficientes. Regenera `redteam/reports/latest.md`.

### Commitear el report

`redteam/reports/latest.md` SIEMPRE va committed cuando hay run relevante. Reports
intermedios y archivos de `redteam/reports/archive/` son gitignored.

```bash
git add redteam/reports/latest.md
git commit -m "feat(redteam): update report post-[reason]"
```

### Añadir un ataque nuevo

1. Diseñar el ataque siguiendo los 10 escenarios §18 — cada ataque debe representar un
   vector realista (no trivial, no artificial).
2. Añadir entrada a `redteam/attacks.jsonl` (campos: `id`, `scenario_id`, `scenario_name`,
   `mode`, `description`, `requires_e2e`, `attack_input`/`attack_file`, `expected_blocked`,
   `layer_expected`).
3. Si es doc-mode: generar/actualizar el PDF en `redteam/documents/` usando
   `redteam/generators/`.
4. Correr `make redteam-smoke` (si determinista) o `make redteam` (si E2E) y verificar que
   el nuevo ataque se bloquea con `expected_blocked: true`.
5. Commitear attacks.jsonl + documento + report actualizado.

## Anti-patterns

- NO mezclar adversarial cases con `evals/gold_set.jsonl` (separados per CLAUDE.md §18).
- NO commitear `redteam/reports/archive/` ni reports intermedios (gitignored).
- NO modificar prompts del Analyst/Auditor para "ganar" red team — eso falsifica el gate.
  Si un ataque pasa, fixea defensas (injection/sanitizer/validator), no prompts.
- NO añadir ataques triviales o artificiales para inflar block_rate. Cada attack representa
  un vector realista §18.
- NO correr full run ($) cuando smoke ($0) basta para verificar un cambio de pattern.
- NO reportar `block_rate_final` sin haber corrido al menos el subset `requires_e2e=false`.

## Referencias

- Spec H9: `docs/superpowers/specs/2026-05-12-h9-redteam-design.md`
- Plan H9: `docs/superpowers/plans/2026-05-12-h9-redteam.md`
- ADR 0011: `docs/adr/0011-redteam-runner.md`
- Security report: `docs/security_report.md`
- Decisions log §H9: `docs/technical_decisions_log.md`
- Attacks: `redteam/attacks.jsonl` (50 ataques — 22 chat-mode + 28 doc-mode).
- Report: `redteam/reports/latest.md`
