import { NextRequest } from "next/server";
import { describe, expect, it } from "vitest";

import { proxy } from "@/proxy";
import { SESSION_COOKIE } from "@/lib/config";

function requestFor(path: string, withSession = false): NextRequest {
  const req = new NextRequest(new URL(`http://localhost${path}`));
  if (withSession) req.cookies.set(SESSION_COOKIE, `tok_${"a".repeat(20)}`);
  return req;
}

describe("proxy auth gate", () => {
  it("redirects an unauthenticated page request to /login", () => {
    const res = proxy(requestFor("/ask"));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toContain("/login");
  });

  it("allows /login without a session", () => {
    const res = proxy(requestFor("/login"));
    expect(res.headers.get("location")).toBeNull();
  });

  it("redirects an authenticated visitor away from /login to /ask", () => {
    const res = proxy(requestFor("/login", true));
    expect(res.headers.get("location")).toContain("/ask");
  });
});

describe("proxy CSP", () => {
  it("sets a strict, nonce-based CSP on an authenticated page", () => {
    const res = proxy(requestFor("/ask", true));
    const csp = res.headers.get("content-security-policy") ?? "";
    expect(csp).toMatch(/script-src 'self' 'nonce-[^']+' 'strict-dynamic'/);
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("default-src 'self'");
  });

  it("emits a fresh nonce per request", () => {
    const a = proxy(requestFor("/ask", true)).headers.get("content-security-policy") ?? "";
    const b = proxy(requestFor("/ask", true)).headers.get("content-security-policy") ?? "";
    expect(a).not.toBe(b);
  });
});
