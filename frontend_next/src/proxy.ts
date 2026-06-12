import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

import { SESSION_COOKIE } from "@/lib/config";

// Next.js 16 "Proxy" (formerly Middleware). One file does two jobs:
//   1. Optimistic auth gate — redirect to /login when there is no session
//      cookie (this is the blessed "optimistic check" use of Proxy; real auth
//      is enforced by the backend on every BFF call).
//   2. Per-request CSP nonce — strict script-src, so Next's inline bootstrap
//      scripts only run with the matching nonce (XSS hardening). Requires
//      dynamic rendering (forced in the root layout).

const PUBLIC_PATHS = ["/login"];

function buildCsp(nonce: string, isDev: boolean): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDev ? " 'unsafe-eval'" : ""}`,
    // Linked Tailwind/shadcn stylesheet is 'self'. Inline style attributes
    // (corpus-chip accent colours) need 'unsafe-inline' for STYLES — a low XSS
    // risk; scripts stay strict (nonce + strict-dynamic).
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' blob: data:",
    "font-src 'self'",
    "connect-src 'self'", // browser only talks to the same-origin BFF
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "upgrade-insecure-requests",
  ].join("; ");
}

export function proxy(request: NextRequest): NextResponse {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);
  const isPublic = PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );

  if (!hasSession && !isPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    return NextResponse.redirect(url);
  }
  if (hasSession && pathname === "/login") {
    const url = request.nextUrl.clone();
    url.pathname = "/ask";
    return NextResponse.redirect(url);
  }

  const nonce = Buffer.from(crypto.randomUUID()).toString("base64");
  const isDev = process.env.NODE_ENV === "development";
  const csp = buildCsp(nonce, isDev);

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("content-security-policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("content-security-policy", csp);
  return response;
}

export const config = {
  // Run on page routes; skip the BFF API, Next internals, the favicon, any
  // static asset by extension, and link prefetches. Prefixes are anchored to a
  // path boundary (api/, _next/...) so a future route merely starting with
  // "api" is NOT accidentally excluded from the auth gate + CSP.
  matcher: [
    {
      source:
        "/((?!api/|_next/static/|_next/image/|favicon\\.ico$|.*\\.(?:svg|png|jpg|jpeg|gif|ico|webp|webmanifest)$).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
