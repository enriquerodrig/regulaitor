// Convenience aliases over the OpenAPI-generated types (`api-types.ts`).
// `api-types.ts` is regenerated from the FastAPI `/openapi.json` via
// `npm run gen:types` — so these aliases track the backend DTOs with zero
// hand-maintained drift (Pydantic DTO is the single source of truth).

import type { components } from "@/lib/api-types";

export type AskRequest = components["schemas"]["AskRequest"];
export type AskResponse = components["schemas"]["AskResponse"];
export type AnalyzeResponse = components["schemas"]["AnalyzeResponse"];
export type HealthResponse = components["schemas"]["HealthResponse"];
export type HealthCheck = components["schemas"]["HealthCheck"];

export type AnswerDTO = components["schemas"]["AnswerDTO"];
export type FindingDTO = components["schemas"]["FindingDTO"];
export type CitationDTO = components["schemas"]["CitationDTO"];
export type AuditResultDTO = components["schemas"]["AuditResultDTO"];
export type CouncilReviewDTO = components["schemas"]["CouncilReviewDTO"];
export type JudgeVoteDTO = components["schemas"]["JudgeVoteDTO"];
export type SanitizerEventDTO = components["schemas"]["SanitizerEventDTO"];
export type SegmentResultDTO = components["schemas"]["SegmentResultDTO"];
export type PIISummaryDTO = components["schemas"]["PIISummaryDTO"];

// Derived unions — taken FROM the DTOs so they cannot desync.
export type Verdict = AskResponse["verdict"];
export type Severity = FindingDTO["severity"];
export type CorpusSelector = AskRequest["corpus"];
export type Language = AskRequest["language"];

/** Backend ErrorResponse shape (error_code / message / case_id). */
export interface ApiErrorBody {
  error_code?: string;
  message?: string;
  case_id?: string | null;
}
