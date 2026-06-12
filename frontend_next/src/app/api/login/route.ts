import { NextResponse } from "next/server";

import { MIN_TOKEN_LEN, SESSION_COOKIE, SESSION_MAX_AGE_S } from "@/lib/config";

// POST /api/login — set the httpOnly session cookie from a presented Bearer
// token. This is OPTIMISTIC: there is no cheap authenticated backend endpoint
// to validate the token against, so the first protected call returns 401 if the
// token is wrong, and the client clears the session and bounces back to /login.
export async function POST(request: Request): Promise<NextResponse> {
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

  // `Secure` keyed to the actual request scheme, not NODE_ENV: a self-hosted
  // deploy over plain http (trusted LAN) must still be able to set the cookie,
  // while an https deploy (behind a TLS-terminating proxy) gets Secure.
  const isHttps =
    request.url.startsWith("https:") ||
    request.headers.get("x-forwarded-proto") === "https";

  const res = NextResponse.json({ ok: true });
  res.cookies.set(SESSION_COOKIE, token.trim(), {
    httpOnly: true,
    secure: isHttps,
    sameSite: "strict",
    path: "/",
    maxAge: SESSION_MAX_AGE_S,
  });
  return res;
}
