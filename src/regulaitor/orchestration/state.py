"""ChatState — LangGraph state for the H4 chat E2E flow.

Pydantic v2 BaseModel (decisions log 2026-05-05 entry
"LangGraph state shape: Pydantic v2 BaseModel").
Container is mutable (LangGraph nodes return partial dicts that merge in);
inner objects (Context, Answer, AuditedAnswer) are frozen.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from regulaitor.citation.schemas import Answer, AuditedAnswer, Context, CouncilReview
from regulaitor.corpus.schemas import CorpusSelector, Language


class ChatState(BaseModel):
    """LangGraph state for chat E2E. Mutable across nodes."""

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    corpus: CorpusSelector
    language: Language

    context: Context | None = None
    answer: Answer | None = None
    audited_answer: AuditedAnswer | None = None

    injection_blocked: bool = False
    injection_reason: str | None = None

    council_override: bool | None = None
    council_review: CouncilReview | None = None

    # Fase 6B (ADR-0042): per-tenant Analyst router mode. None => env/default seam.
    model_choice: str | None = None

    errors: list[str] = Field(default_factory=list)
