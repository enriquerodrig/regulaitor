"""v0.1.8 — per-case JSONL checkpointing for the evaluation harness.

This module preserves per-case results to disk BEFORE the harness advances to
the next case, so that a mid-loop crash (Anthropic credit_balance_too_low,
network timeout, OOM, OS signal) does not lose the work already completed in
RAM.

This was the structural cause of the H15.2 T6 disaster — see
`docs/retriever_h15-2_redesign.md` §4.3 (three converging causes). Before this
module, `evals.harness.main()` accumulated `ChatCaseResult` instances in a
local `list` and rendered the markdown report only at the very end via a single
atomic `_REPORT_PATH.write_text()` call. Any exception in the loop body
(notably `compute_chat_metrics._ragas_metrics_chat` had NO try/except) bubbled
up and killed the loop without persisting anything.

The format is **JSONL** (one JSON object per line) with a `{"kind": ..., "data": ...}`
discriminator so a single checkpoint can mix chat and doc cases. Lines are
written with `flush()` + `os.fsync()` to survive a hard kill.

Reading is forward-compatible-safe: an unknown `kind` raises ValueError loudly
(fail-loud beats silent skip — the harness should not pretend it processed a
case whose schema it does not understand).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from evals.schemas import ChatCaseResult, DocCaseResult

# Production callers pass `root=Path("evals/checkpoints")` (the convention) but
# tests pass a `tmp_path` to keep the filesystem isolated.
DEFAULT_ROOT = Path("evals/checkpoints")

# Discriminator strings — keep stable; load_completed must remain backward
# compatible with any past run's checkpoint files.
_KIND_CHAT = "chat"
_KIND_DOC = "doc"


def checkpoint_path(run_id: str, *, root: Path = DEFAULT_ROOT) -> Path:
    """Deterministic path for `run_id`'s JSONL checkpoint.

    `run_id` is the harness-chosen identifier (today: ISO timestamp + commit SHA
    short; see `evals/harness.py main()`). Two calls with the same `run_id` MUST
    return identical paths so `append_case` and `load_completed` can find the
    same file.
    """
    return root / f"{run_id}.jsonl"


def append_case(
    run_id: str,
    case: ChatCaseResult | DocCaseResult,
    *,
    root: Path = DEFAULT_ROOT,
) -> None:
    """Persist one case result to the run's JSONL checkpoint.

    Creates the parent directory if missing (first case of a run). Writes one
    line, flushes the stream, and fsyncs the file descriptor — survives both a
    Python-level exception (the loop dies but the file is on disk) and a hard
    kill (the OS has committed the page to disk).

    Format:
        {"kind": "chat" | "doc", "data": <model_dump JSON object>}

    `model_dump(mode="json")` is used so Pydantic types that aren't natively
    JSON-serializable (e.g. nested CitationMetrics, CriteriaScore) round-trip
    cleanly through `model_validate` on load.
    """
    path = checkpoint_path(run_id, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)

    kind = _KIND_CHAT if isinstance(case, ChatCaseResult) else _KIND_DOC
    payload = {"kind": kind, "data": case.model_dump(mode="json")}
    line = json.dumps(payload, ensure_ascii=False) + "\n"

    # Open in append mode + manual flush + fsync. We do not use a 'with' block
    # here because we explicitly need the fsync between flush() and close().
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


def load_completed(
    run_id: str,
    *,
    root: Path = DEFAULT_ROOT,
) -> list[ChatCaseResult | DocCaseResult]:
    """Load all per-case results previously persisted for `run_id`.

    Missing checkpoint file → empty list (the first call before any append, or
    a brand-new run_id, returns `[]` rather than raising — callers can use
    `if not load_completed(...)` as a "fresh run" check).

    Unknown `kind` in any line → ValueError (fail loud, do not silently skip).
    Malformed JSON in any line → JSONDecodeError (the file is corrupt and the
    caller must decide whether to abandon or hand-edit it).
    """
    path = checkpoint_path(run_id, root=root)
    if not path.exists():
        return []

    results: list[ChatCaseResult | DocCaseResult] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            entry = json.loads(stripped)
            kind = entry["kind"]
            data = entry["data"]
            if kind == _KIND_CHAT:
                results.append(ChatCaseResult.model_validate(data))
            elif kind == _KIND_DOC:
                results.append(DocCaseResult.model_validate(data))
            else:
                raise ValueError(
                    f"Unknown checkpoint kind {kind!r} in {path} — refusing to silently skip. "
                    "Possible causes: hand-edited file, future harness wrote a newer format, "
                    "corrupted file. Inspect manually."
                )
    return results
