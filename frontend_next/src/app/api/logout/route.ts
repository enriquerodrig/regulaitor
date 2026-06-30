import { NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/config";
import { crossOriginRejection } from "@/lib/csrf";

// POST /api/logout — clear the session cookie.
export async function POST(request: Request): Promise<NextResponse> {
  const csrf = crossOriginRejection(request);
  if (csrf) return csrf;

  const res = NextResponse.json({ ok: true });
  res.cookies.delete(SESSION_COOKIE);
  return res;
}
