import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/api-server";
import { SESSION_COOKIE } from "@/lib/config";

export const runtime = "nodejs";
// Document analysis on CPU can take minutes (BGE-M3 reranker per segment).
// maxDuration matters on serverless hosts; on a self-hosted `next start` Node
// server there is no function timeout, but we declare intent here anyway.
export const maxDuration = 600;

// POST /api/analyze — forward the multipart upload (file + corpus + language)
// to the FastAPI /analyze endpoint. We re-emit the FormData so fetch sets a
// fresh multipart boundary; the Bearer token is attached by backendFetch.
export async function POST(request: Request): Promise<NextResponse> {
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return NextResponse.json(
      { error_code: "bad_request", message: "Se esperaba multipart/form-data." },
      { status: 400 },
    );
  }

  const { status, body } = await backendFetch("/analyze", {
    method: "POST",
    body: form,
  });

  const res = NextResponse.json(body, { status });
  if (status === 401) res.cookies.delete(SESSION_COOKIE); // stale session
  return res;
}
