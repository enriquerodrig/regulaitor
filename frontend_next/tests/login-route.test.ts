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

  it("accepts a valid token and sets a hardened httpOnly cookie", async () => {
    const res = await POST(loginRequest({ token: `tok_${"a".repeat(20)}` }));
    expect(res.status).toBe(200);
    const setCookie = res.headers.get("set-cookie") ?? "";
    expect(setCookie).toContain("regulaitor_token=");
    expect(setCookie.toLowerCase()).toContain("httponly");
    expect(setCookie.toLowerCase()).toContain("samesite=strict");
    expect(setCookie.toLowerCase()).toContain("path=/");
    // http request -> no Secure (so a plain-http self-hosted LAN deploy works)
    expect(setCookie.toLowerCase()).not.toContain("secure");
  });

  it("sets Secure on the cookie when the request is https", async () => {
    const res = await POST(
      loginRequest({ token: `tok_${"a".repeat(20)}` }, "https://app.example/api/login"),
    );
    expect(res.status).toBe(200);
    expect((res.headers.get("set-cookie") ?? "").toLowerCase()).toContain("secure");
  });
});
