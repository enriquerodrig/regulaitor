---
name: secure-coding-checklist
description: Use this skill before merging any PR that touches src/regulaitor/security/, src/regulaitor/document/sanitizer.py, src/regulaitor/citation/validator.py, or src/regulaitor/agents/auditor.py. Activates from H9 onwards (CLAUDE.md §12.3.10).
version: 1.0
---

# secure-coding-checklist

Checklist canónica para revisión de PRs que tocan módulos de seguridad de RegulAItor.

## Cuándo invocarme

PR que toca cualquiera de estos archivos:

- `src/regulaitor/security/injection.py`
- `src/regulaitor/security/allowlist.py`
- `src/regulaitor/security/pii.py`
- `src/regulaitor/document/sanitizer.py`
- `src/regulaitor/citation/validator.py`
- `src/regulaitor/agents/auditor.py`
- `redteam/` (reglas de evaluación adversarial)

## Checklist

### Pre-merge

- [ ] `make redteam-smoke` verde localmente (block_rate smoke ≥ 0.90).
- [ ] CI job `redteam-smoke` verde en el PR (automático si la rama lo tiene configurado).
- [ ] Los cambios son SOLO additive (`if`/`elif` para nuevas categorías; no `else: do_something_different`; no eliminar checks existentes).
- [ ] Si se añadió un pattern regex: cobertura ES + EN si aplica (la suite tiene ataques bilingües).
- [ ] Si se modificó `sanitizer.py`: caso correspondiente añadido o actualizado en `tests/unit/test_sanitizer.py`.
- [ ] Si se modificó `injection.py`: caso correspondiente añadido en `tests/unit/test_injection.py`.
- [ ] Si se modificó `citation/validator.py`: caso correspondiente añadido en `tests/unit/citation/test_validator.py`.
- [ ] Test unit cubriendo el caso fixed: el test falla ANTES del fix y pasa DESPUÉS (TDD intra-fix).
- [ ] No se modificó arquitectura del Auditor (agregación lenient-strict). Eso es H15+.
- [ ] No se modificó router de LLM ni prompts versionados sin bump de versión.
- [ ] Schemas Pydantic no modificados (frozen + extra=forbid preservado).
- [ ] Entry en `docs/technical_decisions_log.md` (amendment N o decisión nueva).
- [ ] `make lint` verde (ruff + black + mypy).
- [ ] gitleaks clean en pre-commit (no secrets en el diff).

### Post-merge

- [ ] Si la baseline `redteam/reports/latest.md` necesita refresh post-merge: correr
  `make redteam` localmente y commitear el nuevo report.
- [ ] Verificar block_rate_final ≥ 0.90 en el report actualizado.
- [ ] Verificar que ningún ataque que antes pasaba ahora escapa (ningún nuevo escape).

## Anti-patterns

- `--no-verify` en commits a estos archivos. Pre-commit y hooks son críticos para
  detección de secrets y linting.
- Cambiar un threshold o heurística existente sin tests retro-compatibles que demuestren
  que los ataques anteriores siguen siendo bloqueados.
- Comentar un check existente con un TODO pendiente de revisión.
- Mergear PR con CI smoke rojo en módulos de seguridad.
- Modificar prompts del Analyst o Auditor para "ganar" red team (proxy: si el fix es en
  `agents/prompts/`, invocar también `prompt-versioning` skill + bump versión).
- Añadir dependencias nuevas en módulos de seguridad sin revisar CVEs (`pip-audit`).

## Patrones seguros

### Añadir un pattern de injection

```python
# En src/regulaitor/security/injection.py
# Añadir SIEMPRE al final del bloque correspondiente (chat o document)
# Nombre descriptivo en snake_case con prefijo del dominio
_DOCUMENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # ... existing patterns ...
    ("mi_nuevo_pattern", re.compile(r"...", re.IGNORECASE)),  # ES + EN si aplica
]
```

Test acompañante:

```python
# En tests/unit/test_injection.py
def test_mi_nuevo_pattern_detected():
    result, name = detect_injection("texto que activa el pattern", mode="document")
    assert result is True
    assert name == "mi_nuevo_pattern"
```

### Añadir una categoría de sanitizer

```python
# En src/regulaitor/document/sanitizer.py
# Añadir método _check_<categoria>() que retorna list[SanitizationIssue]
# Llamarlo en sanitize_pdf() en el bloque de checks
# Definir SanitizationIssue con severity="critical"|"high"|"info"
```

## Referencias

- CLAUDE.md §18 (10 escenarios atacante).
- CLAUDE.md §22 regla 10 (no warnings, no findings altos).
- ADR 0011 (`docs/adr/0011-redteam-runner.md`).
- Security report (`docs/security_report.md`).
- Skill `redteam-runner` — cómo ejecutar la suite tras un fix.
