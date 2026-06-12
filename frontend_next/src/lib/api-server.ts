// Server-only BFF helper. Route handlers call `backendFetch` to forward an
// authenticated request to the FastAPI backend. The Bearer token is read from
// the httpOnly cookie SERVER-SIDE and forwarded as `Authorization: Bearer …`;
// it is never exposed to the browser. No CORS is involved (server-to-server).
//
// `server-only` makes importing this module from a client component a build
// error — a hard guard that the backend origin/token never reach the bundle.

import "server-only";

import { cookies } from "next/headers";

import { SESSION_COOKIE } from "@/lib/config";

/** FastAPI base URL. In docker-compose this is the internal `http://api:8000`;
 *  in local dev it defaults to localhost. Server-only — never sent to clients. */
export const API_BASE_URL = (
  process.env.REGULAITOR_API_URL ?? "http://localhost:8000"
).replace(/\/+$/, "");

export interface BackendResult {
  status: number;
  body: unknown; // parsed JSON (or a synthesized error body on failure)
}

async function readToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value ?? null;
}

/**
 * Forward a request to the FastAPI backend with the session Bearer token.
 *
 * @param path     backend path beginning with "/" (e.g. "/ask")
 * @param init     standard fetch init; pass `requireAuth: false` for /health
 */
export async function backendFetch(
  path: string,
  init: RequestInit & { requireAuth?: boolean } = {},
): Promise<BackendResult> {
  const { requireAuth = true, headers, ...rest } = init;
  const token = await readToken();

  if (requireAuth && !token) {
    return {
      status: 401,
      body: { error_code: "unauthenticated", message: "Sesión no iniciada." },
    };
  }

  const outboundHeaders = new Headers(headers);
  if (token) outboundHeaders.set("authorization", `Bearer ${token}`);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...rest,
      headers: outboundHeaders,
      cache: "no-store",
    });
  } catch {
    return {
      status: 502,
      body: {
        error_code: "backend_unreachable",
        message: "El backend no está disponible.",
      },
    };
  }

  const text = await res.text();
  let body: unknown;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = {
      error_code: "bad_gateway",
      message: "Respuesta no válida del backend.",
    };
  }
  return { status: res.status, body };
}
