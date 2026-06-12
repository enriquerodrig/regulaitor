import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/api-server";

export const runtime = "nodejs";

// GET /api/health — forward to the FastAPI /health endpoint. Auth is optional:
// /health does not require a token, but we forward it if a session exists.
export async function GET(): Promise<NextResponse> {
  const { status, body } = await backendFetch("/health", { requireAuth: false });
  return NextResponse.json(body, { status });
}
