"""H11 — Optional LangFuse tracing. Metadata-only; no raw text leaves the
process. No-op (zero overhead, SDK not imported) when LANGFUSE_* env vars
are absent. Any LangFuse failure is swallowed with a WARNING — observability
never breaks or slows the pipeline (spec §2 enfoque A)."""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger("regulaitor.observability")

_REQUIRED_ENV = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")


def is_enabled() -> bool:
    """True only if all three LANGFUSE_* env vars are present and non-empty."""
    return all(os.environ.get(k) for k in _REQUIRED_ENV)


def hash12(value: str) -> str:
    """sha256[:12] — the canonical redaction primitive (matches sanitizer)."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


@dataclass
class TurnTrace:
    """In-memory metadata accumulator. The orchestration layer fills it;
    on context exit it is flushed to LangFuse when enabled, else inert.
    NEVER store raw query/document/citation text here — only metadata
    and hashes (spec §3.3 redaction rule)."""

    kind: Literal["chat", "document"]
    case_id: str
    corpus: str
    language: str
    _root_meta: dict[str, Any] = field(default_factory=dict)
    _spans: dict[str, dict[str, Any]] = field(default_factory=dict)

    def set_root(self, **meta: Any) -> None:
        self._root_meta.update(meta)

    def span(self, name: str, **meta: Any) -> None:
        self._spans[name] = meta


@contextmanager
def trace_turn(
    *,
    kind: Literal["chat", "document"],
    case_id: str,
    corpus: str,
    language: str,
) -> Iterator[TurnTrace]:
    """Yield a TurnTrace. No-op if not is_enabled() (SDK not imported).
    Enabled path is added in the next task."""
    tt = TurnTrace(kind=kind, case_id=case_id, corpus=corpus, language=language)
    if not is_enabled():
        yield tt
        return
    # Enabled path implemented in Task 3.
    yield tt
