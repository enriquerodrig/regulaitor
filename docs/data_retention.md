# Retención de datos y solicitudes de derechos (DSR) — RegulAItor

Política de retención del audit trail y procedimiento operativo para atender
solicitudes de derechos del interesado (GDPR Art. 15 acceso / Art. 17 supresión).
Cubre exclusivamente el **audit store opt-in** (`observability/audit_store.py`,
ADR-0041). El resto del sistema es efímero por defecto (ADR-0039).

## 1. Qué se persiste (y qué no)

El audit store es **opt-in**: con `REGULAITOR_AUDIT_DB` sin definir (el default),
no se persiste nada — el sistema es completamente stateless. Cuando el operador
apunta esa variable a una ruta escribible, se persiste **una fila append-only por
turno** completado de `/ask` y `/analyze`.

| Campo | Contenido | ¿Dato personal? |
|---|---|---|
| `ts` | Timestamp UTC ISO-8601 | No |
| `case_id` | Identificador del turno | No |
| `tenant_id` | Organización/token que originó el turno | Sí (identificador de tenant) |
| `mode`, `corpus`, `language`, `verdict` | Metadatos del turno | No |
| `query_sha256` | **SHA-256** de la consulta — nunca el texto raw | Seudonimizado |
| `n_findings`, `n_citations`, `n_validated`, `n_segments`, `latency_ms`, `cost_eur` | Contadores | No |

**§18.8 — la consulta cruda NUNCA se almacena** (solo su hash SHA-256); el texto
de documentos nunca se persiste. El único identificador con carácter personal es
`tenant_id`; sobre él operan acceso y supresión.

## 2. Retención

- Ventana por defecto: **365 días**, configurable vía
  `REGULAITOR_AUDIT_RETENTION_DAYS` (entero positivo; valores inválidos o no
  positivos → 365 con WARNING).
- Equilibra la trazabilidad-para-auditoría (problema #4 del proyecto) con la
  minimización de datos GDPR (Art. 5.1.e).
- La purga **no es automática**: el operador la ejecuta (típicamente por cron)
  para evitar borrados sorpresa. Ejemplo de cron diario:

  ```cron
  # 03:15 cada día — purga filas del audit trail más antiguas que la ventana
  15 3 * * *  cd /opt/regulaitor && REGULAITOR_AUDIT_DB=/data/audit.db \
              /opt/regulaitor/.venv/bin/python -m scripts.dsr purge
  ```

## 3. Solicitudes de derechos (DSR) — procedimiento del DPO

Los DSR se atienden **mediados por el operador/DPO** mediante la CLI
`scripts/dsr.py`, no self-service: un audit trail debe ser resistente a
manipulación y la supresión GDPR está sujeta a excepciones de retención legal
(Art. 17.3). El tenant puede *consultar* su propio trail en la página `/audit`
del BFF; la exportación/supresión formal es operativa.

Requisito: `REGULAITOR_AUDIT_DB` apuntando a la BD de auditoría (el host de
despliegue). Sin ella, cada comando es un no-op.

### Art. 15 — Acceso

```bash
REGULAITOR_AUDIT_DB=/data/audit.db python -m scripts.dsr export <tenant_id> > dsr-export.json
```

Vuelca en JSON (stdout) todas las filas del tenant, más antiguas primero. El
resumen va a stderr. Entregar el JSON al interesado.

### Art. 17 — Supresión

```bash
REGULAITOR_AUDIT_DB=/data/audit.db python -m scripts.dsr erase <tenant_id> --yes
```

Borra irreversiblemente todas las filas del tenant y reporta el número. El flag
`--yes` es obligatorio (guarda contra borrado accidental). Documentar la fecha,
el `tenant_id` y el número de filas borradas en el registro de tratamientos.

> El tenant del token único legacy (`tenant_id` NULL) se referencia como
> `default` o `-`.

## 4. Garantías de seguridad

- Las operaciones DSR (`export_tenant`/`erase_tenant`/`purge_expired`) son
  **operator-facing**: a diferencia de la ruta de request (`record`, que traga
  errores para no romper un turno), **propagan errores** — una supresión que
  falle en silencio sería un defecto de cumplimiento.
- El alcance por tenant usa `tenant_id IS ?` (parametrizado; sin SQL dinámico).
- Sin nueva superficie API pública: la CLI corre en el host, que ya tiene acceso
  a la BD.

## 5. Referencias

- `observability/audit_store.py` — implementación (ADR-0041, ADR-0039).
- `scripts/dsr.py` — CLI operativa.
- `docs/runbook.md` — operación general.
- `docs/threat_model.md` — límites de confianza y controles.
- `docs/secret_management.md` — rotación de claves.
