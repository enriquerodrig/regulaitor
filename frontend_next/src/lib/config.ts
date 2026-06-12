// Shared (client + server) constants. Nothing secret here.
//
// The API base URL is intentionally NOT here: it is server-only and lives in
// `api-server.ts` (guarded by `server-only`) so the FastAPI origin can never be
// inlined into the browser bundle.

/** httpOnly session cookie that holds the Bearer token. Never readable by JS. */
export const SESSION_COOKIE = "regulaitor_token";

/** Minimum token length, mirrored from the backend entropy guard
 *  (`src/regulaitor/security/tenancy.py::_MIN_TOKEN_LEN`). */
export const MIN_TOKEN_LEN = 16;

/** Session lifetime (seconds). The token cookie expires after this. */
export const SESSION_MAX_AGE_S = 60 * 60 * 8; // 8h
