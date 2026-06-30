import { NextResponse } from "next/server";

import { backendFetch } from "@/lib/api-server";
import { SESSION_COOKIE } from "@/lib/config";

export const runtime = "nodejs";

// GET /api/audit — forward to the FastAPI /audit endpoint. The backend forces the
// tenant_id from the Bearer token (request.state.tenant), so a tenant only ever sees
// its OWN trail. No CSRF guard: this is a read-only GET (CSRF is for mutating POSTs).
export async function GET(): Promise<NextResponse> {
  const { status, body } = await backendFetch("/audit");
  const res = NextResponse.json(body, { status });
  if (status === 401) res.cookies.delete(SESSION_COOKIE); // stale session
  return res;
}
