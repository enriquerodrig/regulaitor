import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/api-server";
import { SESSION_COOKIE } from "@/lib/config";
import { crossOriginRejection } from "@/lib/csrf";

export const runtime = "nodejs";

// POST /api/ask — forward the chat query (JSON) to the FastAPI /ask endpoint.
export async function POST(request: Request): Promise<NextResponse> {
  const csrf = crossOriginRejection(request);
  if (csrf) return csrf;

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json(
      { error_code: "bad_request", message: "Cuerpo JSON inválido." },
      { status: 400 },
    );
  }

  const { status, body } = await backendFetch("/ask", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });

  const res = NextResponse.json(body, { status });
  if (status === 401) res.cookies.delete(SESSION_COOKIE); // stale session
  return res;
}
