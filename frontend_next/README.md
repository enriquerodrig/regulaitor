# RegulAItor — Frontend (Next.js)

Fase 5 (HX). Interfaz web multi-tenant para las tres superficies del producto
(Pregunta · Analiza documento · Estado), consumiendo la API FastAPI de RegulAItor.

> El frontend es **pura presentación**. Renderiza lo que la API devuelve verbatim
> (veredicto del Auditor, validez de cada cita, hallazgos) y **nunca** re-deriva un
> veredicto ni re-valida una cita: el invariante §6 "no citation, no answer" vive
> íntegro en el backend.

## Stack

Next.js 16 (App Router, Turbopack) · React 19 · TypeScript estricto · Tailwind v4 ·
shadcn (base-nova / Base UI) · vitest. UI en español, WCAG 2.2 AA.

## Arquitectura (BFF)

- El token Bearer vive **solo** en una cookie `httpOnly + SameSite=Strict` (el
  navegador nunca lo ve en JS). `Secure` se adapta al esquema: https lo activa;
  http (LAN self-host) no, para que la cookie funcione igualmente.
- Los *route handlers* `src/app/api/*` leen la cookie en servidor y reenvían
  `Authorization: Bearer` a la FastAPI (`src/lib/api-server.ts`). **No hay CORS**
  (servidor a servidor). Un 401 limpia la sesión y vuelve a `/login`.
- `src/proxy.ts` (Proxy de Next 16, antes Middleware) hace el *gate* de auth
  optimista **y** fija una CSP por-petición con *nonce* (`script-src` estricto:
  self + nonce + strict-dynamic). El root layout es `force-dynamic` para que el
  nonce aplique.
- Login **optimista**: no hay endpoint barato de validación; el primer 401 de
  cualquier llamada protegida corrige la sesión.

## Tipos sin drift

`src/lib/api-types.ts` se **genera** desde el `/openapi.json` de la FastAPI:

```bash
# con la API levantada (o un openapi.json volcado en la raíz del frontend):
npm run gen:types
```

## Desarrollo

```bash
npm install
npm run dev        # http://localhost:3000 (necesita la API en REGULAITOR_API_URL)
npm run lint
npm run typecheck
npm test           # vitest
npm run build
```

Variable de entorno (servidor): `REGULAITOR_API_URL` (por defecto
`http://localhost:8000`).

## Despliegue (self-hosted)

Pensado para correr junto a la FastAPI vía `docker compose` (ver
`../docker-compose.yml`). El navegador solo necesita `:3000`; el frontend alcanza
la API por la red interna de compose.

```bash
# desde la raíz del repo
docker compose up -d api frontend
# UI en http://localhost:3000 — la API queda interna (api:8000)
```

La imagen usa la salida `standalone` de Next (`node server.js`), runtime no-root.

Decisión de arquitectura: `docs/adr/0040-next-frontend.md`.
