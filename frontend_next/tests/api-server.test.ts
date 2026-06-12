import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// server-only is a no-op in Node, but mock it so the import never throws.
vi.mock("server-only", () => ({}));

const cookieGet = vi.fn();
vi.mock("next/headers", () => ({
  cookies: async () => ({ get: cookieGet }),
}));

describe("backendFetch (BFF helper)", () => {
  beforeEach(() => {
    cookieGet.mockReset();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns 401 when auth is required and there is no session token", async () => {
    cookieGet.mockReturnValue(undefined);
    const { backendFetch } = await import("@/lib/api-server");
    const result = await backendFetch("/ask", { method: "POST", body: "{}" });
    expect(result.status).toBe(401);
  });

  it("forwards the session token as Authorization: Bearer", async () => {
    cookieGet.mockReturnValue({ value: "tok_secret_value" });
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { backendFetch } = await import("@/lib/api-server");
    await backendFetch("/health", { requireAuth: false });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("authorization")).toBe("Bearer tok_secret_value");
  });

  it("never sets Authorization when there is no token (health, unauthenticated)", async () => {
    cookieGet.mockReturnValue(undefined);
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { backendFetch } = await import("@/lib/api-server");
    await backendFetch("/health", { requireAuth: false });

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get("authorization")).toBeNull();
  });

  it("maps a backend connection failure to 502", async () => {
    cookieGet.mockReturnValue({ value: "tok_secret_value" });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("ECONNREFUSED")),
    );
    const { backendFetch } = await import("@/lib/api-server");
    const result = await backendFetch("/ask", { method: "POST", body: "{}" });
    expect(result.status).toBe(502);
  });
});
