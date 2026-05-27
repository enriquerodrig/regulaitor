"""v0.1.27 — doc-mode paid validation runner (mirrors scripts/v0125_run.py).

Runs the H5 document pipeline (run_document via harness.run_doc_case) for the
10 doc cases in evals/document_cases/ to measure cost_per_doc_eur + segmenter
v0.1.14 efficacy at scale. Production state = env-unset (doc_analyst default
= v1.0 per analyst.py role-aware ternary; segmenter v0.1.14 fix per ADR-0019).

USER-GATED: real runs cost Anthropic credit; invoke only on explicit OK after
the SKIP/PROCEED gate authorizes. Invoke as:

  uv run --env-file .env python -m scripts.v0127_run \\
      --cases-file evals/v0127_doc_probe_ids.txt --tag doc-probe

  uv run --env-file .env python -m scripts.v0127_run \\
      --cases-file evals/v0127_doc_main_ids.txt --tag v0.1.27-doc-prod-main
"""

from __future__ import annotations

# Carry from v0.1.22 ADR-0029: Windows CryptoAPI CRL block fix.
import truststore

truststore.inject_into_ssl()

# ruff: noqa: E402 — imports below MUST come after truststore.inject_into_ssl().
import argparse  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

from evals.harness import _REPORT_PATH  # noqa: E402
from evals.harness import main as _harness_main  # noqa: E402

_V0127_DIR = Path("evals/reports/v0.1.27")


def _load_case_ids(cases_file: Path) -> set[str]:
    """BOM-safe, comment/blank-skipping id-set loader."""
    return {
        ln.strip()
        for ln in cases_file.read_text(encoding="utf-8-sig").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }


def _isolate_report(tag: str) -> None:
    """Path-B isolation: snapshot this run's report to evals/reports/v0.1.27/<tag>.md,
    then restore the committed canonical evals/reports/latest.md."""
    _V0127_DIR.mkdir(parents=True, exist_ok=True)
    dest = _V0127_DIR / f"{tag}.md"
    if _REPORT_PATH.exists():
        dest.write_bytes(_REPORT_PATH.read_bytes())
    subprocess.run(["git", "checkout", "HEAD", "--", str(_REPORT_PATH)], check=True, timeout=30)


def run(*, cases_file: Path, tag: str) -> None:
    """Run the harness for v0.1.27 doc-mode paid validation under PRODUCTION STATE.

    Production state for doc-mode = env-unset (analyst.py:96 ternary returns
    v1.0 for prompt_role="document_analyst"; segmenter v0.1.14 fix active per
    ADR-0019). Doc cases use the H5 document_graph pipeline via harness.run_doc_case.
    """
    ids = _load_case_ids(cases_file)
    prev = os.environ.get("REGULAITOR_ANALYST_PROMPT_VERSION")
    os.environ.pop("REGULAITOR_ANALYST_PROMPT_VERSION", None)
    try:
        try:
            _harness_main(subset=None, case_ids=ids)
        finally:
            _isolate_report(tag)
    finally:
        if prev is not None:
            os.environ["REGULAITOR_ANALYST_PROMPT_VERSION"] = prev


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="v0.1.27 USER-GATED doc-mode paid validation runner")
    p.add_argument(
        "--cases-file",
        type=Path,
        required=True,
        help="Newline-delimited case-id allowlist (e.g. evals/v0127_doc_probe_ids.txt)",
    )
    p.add_argument(
        "--tag",
        required=True,
        help="Report basename under evals/reports/v0.1.27/ (e.g. doc-probe, v0.1.27-doc-prod-main)",
    )
    return p.parse_args()


if __name__ == "__main__":
    a = parse_args()
    run(cases_file=a.cases_file, tag=a.tag)
