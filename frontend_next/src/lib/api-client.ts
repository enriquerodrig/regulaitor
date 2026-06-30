// Browser-side API client. Calls the Next.js BFF routes (`/api/*`), NOT the
// FastAPI backend directly — the BFF attaches the httpOnly token server-side.
// On a 401 the session is stale: redirect to /login.

import type {
  AnalyzeResponse,
  ApiErrorBody,
  AskRequest,
  AskResponse,
  AuditLogResponse,
  HealthResponse,
} from "@/lib/types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parse<T>(res: Response): Promise<T> {
  const text = await res.text();
  const data = text ? (JSON.parse(text) as unknown) : null;
  if (!res.ok) {
    if (res.status === 401 && typeof window !== "undefined") {
      window.location.href = "/login";
    }
    const err = (data ?? {}) as ApiErrorBody;
    throw new ApiError(res.status, err.error_code ?? "error", err.message ?? `Error ${res.status}`);
  }
  return data as T;
}

export async function login(token: string): Promise<void> {
  const res = await fetch("/api/login", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ token }),
  });
  await parse<{ ok: true }>(res);
}

export async function logout(): Promise<void> {
  await fetch("/api/logout", { method: "POST" });
}

export async function ask(body: AskRequest): Promise<AskResponse> {
  const res = await fetch("/api/ask", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  return parse<AskResponse>(res);
}

export async function analyze(form: FormData): Promise<AnalyzeResponse> {
  // No content-type header: the browser sets multipart/form-data + boundary.
  const res = await fetch("/api/analyze", { method: "POST", body: form });
  return parse<AnalyzeResponse>(res);
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch("/api/health", { method: "GET" });
  return parse<HealthResponse>(res);
}

export async function getAudit(): Promise<AuditLogResponse> {
  const res = await fetch("/api/audit", { method: "GET" });
  return parse<AuditLogResponse>(res);
}
