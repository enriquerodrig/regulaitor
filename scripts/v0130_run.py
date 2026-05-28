"""v0.1.30 — title-augmented embeddings paid validation runner.

Mirrors scripts/v0129_run.py (Path-B isolation pattern from v0120_run.py +
h15_run.py + ab_eval.py + v0125_run.py + v0127_run.py + v0129_run.py).

v0.1.30 difference vs v0129_run.py: NONE on env or code path. The validation
measures the EFFECT of v0.1.30 title-augmented corpus embeddings (rebuild
applied at T3 to corpus/indexes/regulaitor.lance/) vs the pre-v0.1.30 snapshot
at corpus/indexes/regulaitor.lance.pre-v0.1.30/. Both share identical Auditor
v0.1.29 + v1.5 chat + v1.6 doc + Tier 2 Capa A+B+C + Council binding ON +
retrieval defaults. Production state env-unset.

For doc cases the v0.1.28 title-prepend query-side (`document_graph.py`) is
also active; v0.1.30 is the symmetric corpus-side counterpart.

USER-GATED. Invoke as:

  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run --env-file .env \\
      python -m scripts.v0130_run \\
      --cases-file evals/v0130_probe_ids.txt --tag probe

  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run --env-file .env \\
      python -m scripts.v0130_run \\
      --cases-file evals/v0130_main_ids.txt --tag v0.1.30-prod-main
"""

from __future__ import annotations

# Carry from v0.1.22 ADR-0029 + v0.1.29 carry: Windows CryptoAPI CRL block fix.
import truststore

truststore.inject_into_ssl()

# ruff: noqa: E402 — the imports below MUST come after truststore.inject_into_ssl().
import argparse  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

from evals.harness import _REPORT_PATH  # noqa: E402
from evals.harness import main as _harness_main  # noqa: E402

_V0130_DIR = Path("evals/reports/v0.1.30")


def _load_case_ids(cases_file: Path) -> set[str]:
    """BOM-safe, comment/blank-skipping id-set loader (v0120_run.py precedent)."""
    return {
        ln.strip()
        for ln in cases_file.read_text(encoding="utf-8-sig").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }


def _isolate_report(tag: str) -> None:
    """Path-B isolation: snapshot this run's report to evals/reports/v0.1.30/<tag>.md,
    then restore the committed canonical evals/reports/latest.md.

    Mirrors scripts/v0129_run.py::_isolate_report exactly.
    """
    _V0130_DIR.mkdir(parents=True, exist_ok=True)
    dest = _V0130_DIR / f"{tag}.md"
    if _REPORT_PATH.exists():
        dest.write_bytes(_REPORT_PATH.read_bytes())
    subprocess.run(["git", "checkout", "HEAD", "--", str(_REPORT_PATH)], check=True, timeout=30)


def run(*, cases_file: Path, tag: str) -> None:
    """Run the harness for v0.1.30 paid validation with PRODUCTION STATE env.

    Production state = env-unset (chat default = v1.5 since v0.1.21 + doc default
    = v1.6 since v0.1.28 + Tier 1 Auditor quorum + Tier 2 Capa A+B+C + retrieval
    defaults + Council binding ON + v0.1.25 D2 partial + v0.1.29 D Mirror
    all-blocked + v0.1.30 title-augmented embeddings via re-indexed corpus).

    cases_file: allowlist (probe doc/chat OR main doc/chat).
    tag: report basename under evals/reports/v0.1.30/.
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
    p = argparse.ArgumentParser(description="v0.1.30 USER-GATED paid validation runner")
    p.add_argument(
        "--cases-file",
        type=Path,
        required=True,
        help="Newline-delimited case-id allowlist (e.g. evals/v0130_probe_ids.txt)",
    )
    p.add_argument(
        "--tag",
        required=True,
        help="Report basename under evals/reports/v0.1.30/ (e.g. probe, v0.1.30-prod-main)",
    )
    return p.parse_args()


if __name__ == "__main__":
    a = parse_args()
    run(cases_file=a.cases_file, tag=a.tag)
