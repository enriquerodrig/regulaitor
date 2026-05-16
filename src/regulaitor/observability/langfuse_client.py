"""H11 — Optional LangFuse tracing. Metadata-only; no raw text leaves the
process. No-op (zero overhead, SDK not imported) when LANGFUSE_* env vars
are absent. Any LangFuse failure is swallowed with a WARNING — observability
never breaks or slows the pipeline (spec §2 enfoque A)."""

from __future__ import annotations

import atexit
import hashlib
import logging
import os
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

logger = logging.getLogger("regulaitor.observability")

_REQUIRED_ENV = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")

# ---------------------------------------------------------------------------
# Redaction allowlist — every key name the orchestration layer emits via
# TurnTrace.set_root() or .span() must pass this guard.  Raw text is never
# allowed on the 3rd-party egress path (CLAUDE.md §18.8 / spec §3.3).
# ---------------------------------------------------------------------------
_SAFE_META_KEYS = frozenset(
    {
        "case_id",
        "corpus",
        "language",
        "verdict",
        "document_verdict",
        "reason_code",
        "errors",
        "cache_hit",
        "embedding_model",
        "blocked_category",
        "pattern_name",
        "hit",
        "retry_triggered",
    }
)
# Keys whose *suffix* (or whole name) makes them safe (numeric / hash-derived).
_SAFE_KEY_SUFFIXES = (
    "_sha256_12",
    "_hash",
    "_ms",
    "_ms_total",
    "_eur",
    "_eur_total",
    "_count",
    "tokens_in",
    "tokens_out",
)


def _assert_safe_keys(meta: dict[str, Any]) -> None:
    """Raise ValueError if any key is not in the redaction allowlist.

    Allowed: explicit _SAFE_META_KEYS set, n_* counter prefixes, and keys
    matching _SAFE_KEY_SUFFIXES (numeric / hash-derived values).  Everything
    else is rejected — callers must pass hash12(value) not raw text.
    """
    for k in meta:
        if k in _SAFE_META_KEYS:
            continue
        if k.startswith("n_"):
            continue
        if any(k.endswith(s) or k == s for s in _SAFE_KEY_SUFFIXES):
            continue
        raise ValueError(
            f"TurnTrace metadata key {k!r} not in redaction allowlist; "
            "pass hash12(value) not raw text (privacy: 3rd-party egress)."
        )


# ---------------------------------------------------------------------------
# Module-level cached Langfuse client (Issue 1 fix).
# A single client is created lazily on first enabled use and reused across
# all turns.  This prevents unbounded thread/object accretion (the SDK
# starts daemon consumer threads on construction).  flush() per turn drains
# the queue without blocking (threads stay alive for reuse).  shutdown() is
# registered with atexit for clean process exit.
# ---------------------------------------------------------------------------
_client_lock = threading.Lock()
_client: Any = None  # cached Langfuse instance


def _get_client() -> Any:
    """Return the module-level cached Langfuse client, creating it once."""
    global _client  # noqa: PLW0603
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            from langfuse import Langfuse  # lazy import — only on enabled path

            c = Langfuse()
            atexit.register(c.shutdown)
            _client = c
    return _client


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
    and hashes (spec §3.3 redaction rule).

    set_root() and span() enforce a runtime allowlist (_assert_safe_keys)
    to prevent raw text from reaching the 3rd-party egress path."""

    kind: Literal["chat", "document"]
    case_id: str
    corpus: str
    language: str
    _root_meta: dict[str, Any] = field(default_factory=dict)
    _spans: dict[str, dict[str, Any]] = field(default_factory=dict)

    def set_root(self, **meta: Any) -> None:
        _assert_safe_keys(meta)
        self._root_meta.update(meta)

    def span(self, name: str, **meta: Any) -> None:
        _assert_safe_keys(meta)
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
    When enabled: obtain the cached LangFuse client, open a trace,
    accumulate metadata via the yielded TurnTrace, and on exit emit root
    metadata + sub-spans and async-flush (NOT shutdown — threads stay alive
    for reuse, adding ~0 latency to the request path).  Any LangFuse error
    is logged WARNING and swallowed — the pipeline is never broken or blocked."""
    tt = TurnTrace(kind=kind, case_id=case_id, corpus=corpus, language=language)
    if not is_enabled():
        yield tt
        return
    client: Any = None
    trace: Any = None
    try:
        client = _get_client()
        trace = client.trace(
            name=f"{kind}_turn",
            metadata={"case_id": case_id, "corpus": corpus, "language": language},
        )
    except Exception as exc:  # noqa: BLE001 — observability must never break the pipeline
        logger.warning("langfuse init failed; tracing skipped this turn: %s", exc)
        yield tt
        return
    try:
        yield tt
    finally:
        try:
            trace.update(metadata=dict(tt._root_meta))
            for span_name, span_meta in tt._spans.items():
                trace.span(name=span_name, metadata=dict(span_meta))
            client.flush()
        except Exception as exc:  # noqa: BLE001
            logger.warning("langfuse flush failed; trace dropped: %s", exc)
