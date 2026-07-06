# Sovereign deploy (EU, zero US processor) — spike de diseño P4

Spike **$0** (sin infra de pago) que consolida en el repo la arquitectura de
despliegue soberano — hasta ahora sólo en notas privadas. Cubre los constraints
del founder **C1 (inferencia open-source / self-hostable)** y **C3 (deploy
EU-soberano)**. Es un artefacto de ingeniería: el GTM/pricing-strategy vive
aparte. Cifras de coste = list-price con `[verificar]` (derivan trimestralmente).

## 1. Estado real: el plano soberano YA está construido y testeado

No se parte de cero. El código soporta hoy un turno de chat sin ningún procesador
US en la cadena:

| Pieza | Dónde | Estado |
|---|---|---|
| Router mode `self_hosted` → Mistral vía endpoint OpenAI-compatible | `models/router.py:110` (`_MODE_MAP`) | ✅ built |
| Provider `selfhost` (no US) | `models/router.py:76` (`PROVIDER_SELFHOST`) | ✅ built |
| **Garantía no-fallback-US** (`self_hosted` nunca cae a un modelo US) | `router.py:118` (`_NO_FALLBACK_MODES`) | ✅ **CI-invariant** (`test_self_hosted_does_not_fall_back_to_us_model`) |
| Contrato env self-host (`REGULAITOR_SELFHOST_BASE_URL` / `_API_KEY` / `_MODEL`) + fail-fast si faltan | `models/router.py` | ✅ built + tested (`test_router_selfhost.py`) |
| Selección Analyst → self_hosted (`REGULAITOR_ANALYST_MODEL_CHOICE`) | `agents/analyst.py:84` | ✅ built |
| Retrieval acotado para latencia (`REGULAITOR_RETRIEVAL_CONFIG`) | `rag/retrieval.py` | ✅ built |
| Prompt Analyst v1.6 (disciplina de formato de cita para el modelo abierto) | `agents/prompts/analyst/system.v1.6.md` | ✅ built (opt-in) |
| Council degrade-safe si el juez falla | `agents/council.py:209` (`_one_judge` swallow) | ✅ built + tested |
| Multi-tenancy, audit-trail opt-in, BFF Next.js, Docker compose | Fases HX 4/5, ADR-0041 | ✅ built |

**Los 8 knobs de env del runbook Régimen A existen en el código** (verificado
`grep` sobre `src/`) — el contrato de despliegue es ejecutable, no aspiracional.

## 2. El "perfil soberano" (bundle de env)

Un único conjunto de variables convierte el producto en cero-procesador-US. En el
`.env` (a mano; **nunca** `.env.example` — regla del proyecto):

```bash
# --- inferencia soberana (Mistral La Plateforme, residencia EU por defecto) ---
REGULAITOR_ANALYST_MODEL_CHOICE=self_hosted
REGULAITOR_SELFHOST_BASE_URL=https://api.mistral.ai/v1   # o endpoint vLLM propio (Rég. B)
REGULAITOR_SELFHOST_API_KEY=<clave Mistral La Plateforme>
REGULAITOR_SELFHOST_MODEL=mistral-small-latest
REGULAITOR_ANALYST_PROMPT_VERSION=v1.6                   # obligatorio con el modelo abierto (§4 G1)

# --- prueba de soberanía: OMITIR toda clave US ---
# ANTHROPIC_API_KEY / OPENAI_API_KEY / GROQ_API_KEY  ← ausentes por construcción

# --- resto ---
REGULAITOR_AUDIT_DB=/data/audit.db                       # trazabilidad (hash, no texto)
REGULAITOR_RETRIEVAL_CONFIG={"pre_rerank":12}            # latencia razonable
LANCEDB_PATH=/data/indexes/regulaitor.lance
```

Con las claves US ausentes, ningún modelo US se invoca con éxito (§4 detalla el
matiz del Council). El §6 (`citation/validator.py`) es **byte-unchanged** bajo
cualquier modelo Analyst — la validación de citas es determinista, no depende del
LLM. La migración soberana **no toca el invariante §6**.

## 3. Regímenes de coste (list-price `[verificar]`)

| Escenario | Host app | Inferencia | Coste/mo `[verificar]` | Para |
|---|---|---|---|---|
| Audiencia | local / HF Space | Mistral free/API | ~€0 | demos |
| **Piloto (Régimen A)** | Hetzner/Scaleway VM (4 vCPU) | Mistral La Plateforme (FR) | **~€30–120** | design partners |
| Self-host barato (Rég. B) | Hetzner GEX44 20 GB | Mistral 24B cuantizado | **~€265** | demo self-host |
| Self-host creíble (Rég. B) | OVH/Scaleway L4/L40S | Mistral 24B | **~€500–1.150** | cliente regulado (cobrado) |
| Self-host FP16 + HA | 2× L40S + box | Mistral 24B FP16 | **~€1.000–1.500+** | air-gapped |

- **Régimen A** (recomendado para pilotos): la capa app es barata (LanceDB
  embebido, sin DB gestionada); el coste variable son tokens Mistral
  (Small ≈ $0,15/M in · $0,60/M out `[verificar]`, −50% en batch). El box domina.
- **Régimen B** (self-host GPU): el moat máximo (air-gapped), pero la GPU
  always-on muerde (~730 h/mo). Reservar como **tier de pago** al cliente que lo
  *exige*, no para la captación.
- Tiers de host EU: Scaleway (SEAL-3, SecNumCloud en proceso) y OVHcloud
  (SecNumCloud en Bare Metal; **GPU Public Cloud sin confirmar** `[verificar]`)
  son los soberanía-cualificada; Hetzner/Exoscale son "residencia EU" barata sin
  ANSSI. Detalle GTM/moat: notas privadas.

## 4. Análisis de huecos (el entregable del spike)

Ordenado por prioridad. Nada aquí bloquea el arranque de un piloto Régimen A;
son las verdades honestas (§22.22) de lo probado vs lo no probado.

**G1 — Calidad del modelo abierto NO re-medida (paid).** El probe R1 (N=30)
midió Mistral Small: `verdict_match` 0.83 → **0.70** por citas prosa-style
("13.1 y 2", "16.a") que el validador rechaza (Check 2) → RHR espurio. El prompt
**v1.6 se autoró para cerrar ese gap** (Hard Rule 10, disciplina de formato) pero
**no se re-midió de pago**. → El delta de calidad Mistral+v1.6 vs Sonnet es
desconocido. Cierre: un A/B de pago Mistral+v1.6 sobre el H10 30-case
(rango estimado bajo/esperado/alto — pedir OK + presupuesto antes; disciplina de
coste de `feedback_cost_estimation_discipline`). Contexto que **de-risca** esto:
H12 halló que el techo de calidad es system-level (retriever+Auditor), **no** la
elección de modelo — cambiar Sonnet→Mistral degrada menos de lo que intuye.

**G2 — El Council hace 3 llamadas US fallidas por turno de alta severidad ($0,
recomendado P4.1).** Con el perfil soberano (a) (`ANALYST_MODEL_CHOICE=self_hosted`
+ claves US ausentes), el Council sigue en sus `_JUDGE_MODES` US (Haiku/GPT-4o/
Llama) → cada juez falla auth → `_one_judge` lo traga → Council degrada. Correcto
para §6 (el veredicto mecánico del Auditor manda), **pero** son 3 llamadas US
doomed + logs ruidosos por turno auto-triggered. Dos configs, ninguna perfecta:
  - **(a) analyst-only** — Council degrada (sin independencia, 3 llamadas US
    fallidas). Lo del runbook.
  - **(b) global** (`REGULAITOR_ROUTER_MODE=self_hosted`) — TODO en Mistral
    (Analyst + Council + fallback); cero US intentado; **pero** los 3 jueces
    colapsan a un solo modelo → el Council pierde su independencia (su valor≈0).
  - **Recomendación P4.1 ($0):** guard que salte un juez cuyo provider-key esté
    ausente (cero llamadas US doomed, en vez de 3), o un `REGULAITOR_COUNCIL_ENABLED=0`
    explícito para el perfil soberano. Independencia real multi-EU-model = HX.

**G3 — Deploy vivo sigue en HF Spaces (US).** El runbook Régimen A es ejecutable
(env verificado) pero **no ejecutado en un host EU**. Cierre: provisionar
Scaleway/OVH VM + Caddy TLS + `docker compose up api frontend` cuando haya 1.er
design partner (infra, no $0 — pero ~€30–120/mo, no una llamada LLM de pago).

**G4 — El diseño soberano estaba sólo en notas privadas.** Este doc lo cierra:
el contrato de env, la garantía no-US y el perfil soberano quedan en el repo
trazable. (Hecho por este spike.)

## 5. Recomendación

1. **Ahora ($0):** este doc + sección "Sovereign profile" en `H16_DEPLOY.md`
   (hecho). Opcional P4.1: el guard Council-skip-sin-key (G2).
2. **Antes de vender (paid, pedir OK):** A/B Mistral+v1.6 (G1) para cuantificar
   el delta de calidad soberana con números, no intuición.
3. **Con 1.er design partner (infra ~€30–120/mo):** ejecutar Régimen A en host EU
   (G3). Régimen B como upsell cobrado al cliente regulado que lo exige.

El §6 se mantiene byte-unchanged en todo el camino: la soberanía cambia el modelo
Analyst, no el enforcement de citas.

## 6. Referencias

- `models/router.py` — `self_hosted` mode, `PROVIDER_SELFHOST`, `_NO_FALLBACK_MODES`.
- `tests/unit/models/test_router_selfhost.py` — invariante no-US-fallback + contrato env.
- `agents/analyst.py:84` — `_analyst_model_choice()` (self_hosted seam).
- `agents/prompts/analyst/system.v1.6.md` — prompt del modelo abierto (probe R1).
- `agents/council.py:209` — `_one_judge` degrade-safe.
- `docs/H16_DEPLOY.md` §Sovereign profile — bundle de env operativo.
- `docs/data_retention.md` — trazabilidad + DSR (argumento de compliance).
- Notas privadas de deploy/GTM — no en el repo (estrategia comercial).
