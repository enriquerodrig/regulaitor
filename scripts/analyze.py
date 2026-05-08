"""H5 CLI smoke entry: python -m scripts.analyze --file path.pdf --lang es --corpus ai_act,gdpr.

Exit codes (spec §11):
    0  PASS
    1  BLOCK or REQUIRES_HUMAN_REVIEW
    2  extraction error (bad mime, corrupted file, magic mismatch)
    3  configuration error (corpus invalid, API key missing)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from regulaitor.citation.schemas import AuditVerdict
from regulaitor.document.extractor import ExtractionError
from regulaitor.orchestration.document_graph import run_document

_VALID_CORPUS = {"ai_act", "gdpr", "nis2", "dora"}


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="regulaitor.analyze",
        description="Analyze a document with the RegulAItor H5 pipeline.",
    )
    p.add_argument("--file", required=True, type=Path)
    p.add_argument("--lang", choices=["es", "en"], required=True)
    p.add_argument(
        "--corpus",
        required=True,
        help="Comma-separated subset of: ai_act,gdpr,nis2,dora",
    )
    p.add_argument("--max-tokens-per-segment", type=int, default=1500)
    p.add_argument("--output", choices=["json", "md"], default="json")
    p.add_argument("--verbose", action="store_true")
    return p


def _detect_mime_from_bytes_and_path(path: Path, file_bytes: bytes) -> str:
    """Magic-byte aware mime detection (defense over extension-only)."""
    if file_bytes.startswith(b"%PDF-"):
        return "application/pdf"
    if path.suffix.lower() in (".md", ".markdown"):
        return "text/markdown"
    raise ValueError(f"cannot detect mime for {path}; only PDF + Markdown supported")


def _redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Default-safe redaction: drop sanitizer_log + flatten per-segment audit detail."""
    payload.pop("sanitizer_log", None)
    payload["segments"] = [
        {
            "id": sr["segment"]["id"],
            "title": sr["segment"]["title"],
            "skipped": sr["skipped"],
            "skip_reason": sr["skip_reason"],
            "verdict": (sr["audited_answer"]["verdict"] if sr["audited_answer"] else None),
            "n_findings": (
                len(sr["audited_answer"]["answer"]["findings"]) if sr["audited_answer"] else 0
            ),
        }
        for sr in payload["segments"]
    ]
    return payload


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not os.getenv("ANTHROPIC_API_KEY"):
        print("error: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 3

    requested = [c.strip() for c in args.corpus.split(",") if c.strip()]
    if not requested or any(c not in _VALID_CORPUS for c in requested):
        print(
            f"error: invalid corpus list {requested}; valid: {sorted(_VALID_CORPUS)}",
            file=sys.stderr,
        )
        return 3

    try:
        file_bytes = args.file.read_bytes()
    except OSError as e:
        print(f"error: cannot read {args.file}: {e}", file=sys.stderr)
        return 2

    try:
        mime = _detect_mime_from_bytes_and_path(args.file, file_bytes)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        report = run_document(
            file_bytes=file_bytes,
            mime_type=mime,
            language=args.lang,
            corpus=requested,
        )
    except ExtractionError as e:
        print(f"error: extraction failed: {e}", file=sys.stderr)
        return 2

    if args.output == "json":
        payload = report.model_dump(mode="json")
        if not args.verbose:
            payload = _redact_payload(payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"# DocumentReport `{report.case_id}`\n")
        print(f"- verdict: **{report.document_verdict.value}**")
        print(
            f"- segments: {report.n_segments_total} (pass={report.n_segments_pass}, "
            f"block={report.n_segments_block}, review={report.n_segments_review}, "
            f"skipped_injection={report.n_segments_blocked_by_injection})"
        )
        print(f"- latency_ms_total: {report.latency_ms_total}")
        print(f"- cost_eur_total: {report.cost_eur_total:.4f}")
        if report.document_reason:
            print(f"- reason: `{report.document_reason}`")

    if report.document_verdict == AuditVerdict.PASS:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
