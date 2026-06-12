import { NextResponse } from "next/server";

import { SESSION_COOKIE } from "@/lib/config";

// POST /api/logout — clear the session cookie.
export async function POST(): Promise<NextResponse> {
  const res = NextResponse.json({ ok: true });
  res.cookies.delete(SESSION_COOKIE);
  return res;
}
