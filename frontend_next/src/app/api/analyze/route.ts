import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/api-server";
import { MAX_UPLOAD_BYTES, SESSION_COOKIE } from "@/lib/config";
import { crossOriginRejection } from "@/lib/csrf";

export const runtime = "nodejs";
// Document analysis on CPU can take minutes (BGE-M3 reranker per segment).
// maxDuration matters on serverless hosts; on a self-hosted `next start` Node
// server there is no function timeout, but we declare intent here anyway.
export const maxDuration = 600;

// POST /api/analyze — forward the multipart upload (file + corpus + language)
// to the FastAPI /analyze endpoint. We re-emit the FormData so fetch sets a
// fresh multipart boundary; the Bearer token is attached by backendFetch.
export async function POST(request: Request): Promise<NextResponse> {
  const csrf = crossOriginRejection(request);
  if (csrf) return csrf;

  // fe-05: reject an oversized upload on the declared Content-Length BEFORE parsing
  // the body, so it is never buffered or relayed to the backend (which enforces its
  // own authoritative cap). 64KB slack absorbs multipart envelope overhead.
  const declared = request.headers.get("content-length");
  if (declared !== null && /^\d+$/.test(declared) && Number(declared) > MAX_UPLOAD_BYTES + 64 * 1024) {
    return NextResponse.json(
      { error_code: "payload_too_large", message: "El archivo supera el tamaño máximo (10 MB)." },
      { status: 413 },
    );
  }

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
