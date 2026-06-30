import { describe, expect, it } from "vitest";

import { crossOriginRejection } from "@/lib/csrf";

function req(headers: Record<string, string>): Request {
  return new Request("http://localhost/api/ask", { method: "POST", headers });
}

describe("crossOriginRejection (fe-02 same-origin guard)", () => {
  it("allows a request with no Origin header (server-to-server / same-origin nav)", () => {
    expect(crossOriginRejection(req({}))).toBeNull();
  });

  it("allows a same-origin request (Origin host matches the request URL host)", () => {
    expect(crossOriginRejection(req({ origin: "http://localhost" }))).toBeNull();
  });

  it("allows a same-origin request when the Host header is authoritative", () => {
    expect(
      crossOriginRejection(req({ host: "app.example", origin: "https://app.example" })),
    ).toBeNull();
  });

  it("rejects a cross-origin request with 403", () => {
    const r = crossOriginRejection(req({ host: "app.example", origin: "https://evil.example" }));
    expect(r).not.toBeNull();
    expect(r?.status).toBe(403);
  });

  it("rejects a sibling-subdomain Origin (exact host match, no suffix matching)", () => {
    const r = crossOriginRejection(req({ host: "app.example", origin: "https://evil.app.example" }));
    expect(r).not.toBeNull();
    expect(r?.status).toBe(403);
  });

  it("rejects a malformed Origin with 403", () => {
    const r = crossOriginRejection(req({ origin: "not-a-url" }));
    expect(r).not.toBeNull();
    expect(r?.status).toBe(403);
  });
});
