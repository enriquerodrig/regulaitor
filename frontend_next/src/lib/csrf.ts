import { NextResponse } from "next/server";

function safeHost(u: string): string {
  try {
    return new URL(u).host;
  } catch {
    return "";
  }
}

// fe-02: same-origin guard for state-changing POST routes. Defense-in-depth on top
// of the SameSite=Strict session cookie. Per OWASP, a missing/null Origin is allowed
// (server-to-server calls, some same-origin navigations); a PRESENT cross-origin
// Origin is rejected. The expected host is the Host header (authoritative in a
// Next.js deploy), falling back to the request URL's host. Returns a 403 response to
// short-circuit, or null to proceed.
export function crossOriginRejection(request: Request): NextResponse | null {
  const origin = request.headers.get("origin");
  if (origin === null) return null; // no Origin header — allow (OWASP guidance)

  const expectedHost = request.headers.get("host") ?? safeHost(request.url);
  const originHost = safeHost(origin);
  if (originHost !== "" && originHost === expectedHost) return null; // same-origin

  return NextResponse.json(
    { error_code: "forbidden", message: "Solicitud de origen cruzado rechazada." },
    { status: 403 },
  );
}
