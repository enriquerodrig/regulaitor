import { NextResponse } from "next/server";

import { MIN_TOKEN_LEN, SESSION_COOKIE, SESSION_MAX_AGE_S } from "@/lib/config";
import { crossOriginRejection } from "@/lib/csrf";

// POST /api/login — set the httpOnly session cookie from a presented Bearer
// token. This is OPTIMISTIC: there is no cheap authenticated backend endpoint
// to validate the token against, so the first protected call returns 401 if the
// token is wrong, and the client clears the session and bounces back to /login.
export async function POST(request: Request): Promise<NextResponse> {
  const csrf = crossOriginRejection(request);
  if (csrf) return csrf;

  let token: unknown;
  try {
    ({ token } = (await request.json()) as { token?: unknown });
  } catch {
    return NextResponse.json(
      { error_code: "bad_request", message: "Cuerpo JSON inválido." },
      { status: 400 },
    );
  }

  if (typeof token !== "string" || token.trim().length < MIN_TOKEN_LEN) {
    return NextResponse.json(
      {
        error_code: "invalid_token",
        message: `El token debe tener al menos ${MIN_TOKEN_LEN} caracteres.`,
      },
      { status: 400 },
    );
  }

  // fe-01: deployment-deterministic Secure flag (fail-secure). Default true; a
  // plain-http trusted-LAN deploy opts out EXPLICITLY via
  // REGULAITOR_ALLOW_INSECURE_COOKIE=1. We do NOT derive this from
  // x-forwarded-proto (an untrusted proxy could spoof it to strip Secure).
  const secure = process.env.REGULAITOR_ALLOW_INSECURE_COOKIE !== "1";

  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, token.trim(), {
    httpOnly: true,
    secure,
    sameSite: "strict",
    path: "/",
    maxAge: SESSION_MAX_AGE_S,
  });
  return res;
}
