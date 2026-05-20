"""RetrieverAgent — thin LangGraph adapter around rag/retrieval.

Wraps the canonical retrieval helper output in a Context Pydantic object
for downstream H4 LangGraph state. Decisions log 2026-05-05 entry
"Context como Pydantic wrapper".
"""

from __future__ import annotations

from datetime import UTC, datetime

from regulaitor.citation.schemas import Context
from regulaitor.corpus.schemas import CorpusSelector, Language
from regulaitor.rag import embeddings
from regulaitor.rag import retrieval as rag_retrieval


class RetrieverAgent:
    """Stateless adapter exposing retrieve(query, corpus, language) -> Context.

    The agent does not call any LLM and does not orchestrate; it is the
    minimal indirection between LangGraph state (H4) and the canonical helper.
    """

    def retrieve(
        self,
        query: str,
        corpus: CorpusSelector,
        language: Language,
        top_k: int | None = None,
    ) -> Context:
        if corpus == "auto":
            chunks, resolved = rag_retrieval.run_auto(query, language, rag_retrieval.DEFAULT_CONFIG)
        else:
            chunks = rag_retrieval.run(query, corpus, language, top_k=top_k)
            resolved = [corpus]
        return Context(
            query=query,
            corpus=corpus,
            language=language,
            chunks=chunks,
            retrieved_at=datetime.now(tz=UTC),
            embedding_model=embeddings.model_identifier(),
            resolved_normas=resolved,
        )
