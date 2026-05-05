"""CLI smoke entry: python -m scripts.chat --query "..." --corpus ai_act --lang es."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime

from nanoid import generate

from regulaitor.orchestration.graph import run
from regulaitor.orchestration.state import ChatState


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="regulaitor.chat",
        description="Chat with the RegulAItor Analyst+Auditor pipeline.",
    )
    p.add_argument("--query", required=True)
    p.add_argument("--corpus", choices=["ai_act", "gdpr"], required=True)
    p.add_argument("--lang", choices=["es", "en"], required=True)
    return p


def _serialize_state(state: ChatState) -> dict[str, object]:
    if state.audited_answer is None:
        # Injection-blocked path
        return {
            "case_id": state.case_id,
            "query": state.query,
            "verdict": "blocked_injection" if state.injection_blocked else "no_answer",
            "answer": None,
            "findings": [],
            "audit": {
                "n_citations": 0,
                "n_validated": 0,
                "reason": state.injection_reason,
            },
            "errors": state.errors,
        }
    aa = state.audited_answer
    return {
        "case_id": state.case_id,
        "query": state.query,
        "verdict": aa.verdict.value,
        "answer": aa.answer.text,
        "findings": [
            {
                "text": f.text,
                "severity": f.severity,
                "citations": [c.model_dump() for c in f.citations],
            }
            for f in aa.answer.findings
        ],
        "audit": {
            "n_citations": len(aa.audit_results),
            "n_validated": sum(1 for r in aa.audit_results if r.validated),
            "reason": aa.reason,
        },
        "errors": state.errors,
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    case_id = f"ch-{datetime.now(tz=UTC).strftime('%Y%m%d')}-{generate(size=8)}"
    state = run(query=args.query, corpus=args.corpus, language=args.lang, case_id=case_id)
    output = _serialize_state(state)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if state.audited_answer is None:
        return 1
    if state.audited_answer.verdict.value == "block":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
