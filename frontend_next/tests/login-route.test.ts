import { describe, expect, it } from "vitest";

import { POST } from "@/app/api/login/route";

function loginRequest(body: unknown, url = "http://localhost/api/login"): Request {
  return new Request(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("POST /api/login", () => {
  it("rejects a token shorter than the entropy floor with 400", async () => {
    const res = await POST(loginRequest({ token: "short" }));
    expect(res.status).toBe(400);
  });

  it("rejects a missing token with 400", async () => {
    const res = await POST(loginRequest({}));
    expect(res.status).toBe(400);
  });

  it("accepts a valid token and sets a hardened httpOnly cookie with Secure by default", async () => {
    const res = await POST(loginRequest({ token: `tok_${"a".repeat(20)}` }));
    expect(res.status).toBe(200);
    const setCookie = res.headers.get("set-cookie") ?? "";
    expect(setCookie).toContain("regulaitor_token=");
    expect(setCookie.toLowerCase()).toContain("httponly");
    expect(setCookie.toLowerCase()).toContain("samesite=strict");
    expect(setCookie.toLowerCase()).toContain("path=/");
    // fe-01: fail-secure — Secure is set by default, even on this http test request.
    expect(setCookie.toLowerCase()).toContain("secure");
  });

  it("omits Secure only when REGULAITOR_ALLOW_INSECURE_COOKIE=1 (trusted-LAN http opt-out)", async () => {
    const prev = process.env.REGULAITOR_ALLOW_INSECURE_COOKIE;
    process.env.REGULAITOR_ALLOW_INSECURE_COOKIE = "1";
    try {
      const res = await POST(loginRequest({ token: `tok_${"a".repeat(20)}` }));
      expect(res.status).toBe(200);
      expect((res.headers.get("set-cookie") ?? "").toLowerCase()).not.toContain("secure");
    } finally {
      if (prev === undefined) delete process.env.REGULAITOR_ALLOW_INSECURE_COOKIE;
      else process.env.REGULAITOR_ALLOW_INSECURE_COOKIE = prev;
    }
  });

  it("rejects a cross-origin POST with 403 (fe-02 CSRF guard)", async () => {
    const req = new Request("http://localhost/api/login", {
      method: "POST",
      headers: { "content-type": "application/json", origin: "https://evil.example" },
      body: JSON.stringify({ token: `tok_${"a".repeat(20)}` }),
    });
    const res = await POST(req);
    expect(res.status).toBe(403);
  });
});
