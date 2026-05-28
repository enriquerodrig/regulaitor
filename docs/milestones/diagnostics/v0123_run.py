"""v0.1.23 — paid validation runner (mirrors scripts/v0120_run.py).

Routes harness report output to evals/reports/v0.1.23/<tag>.md after each run,
then restores the committed canonical evals/reports/latest.md (Path-B isolation
pattern from v0120_run.py + h15_run.py + ab_eval.py).

v0.1.23 difference vs v0120_run.py: NO env override — production state means
chat default = v1.5 (analyst.py:96 flipped at v0.1.21). We explicitly UNSET
REGULAITOR_ANALYST_PROMPT_VERSION so the production default kicks in.

USER-GATED: real runs cost Anthropic credit; invoke only on explicit OK after
the spec's SKIP/PROCEED gate (T2) authorizes. Invoke as:

  uv run --env-file .env python -m scripts.v0123_run \\
      --cases-file evals/v0123_probe_ids.txt --tag probe

  uv run --env-file .env python -m scripts.v0123_run \\
      --cases-file evals/v0123_main_ids.txt --tag v0.1.23-prod-main

  uv run --env-file .env python -m scripts.v0123_run \\
      --cases-file evals/v0123_safety_adhoc_ids.txt --tag v0.1.23-prod-safety-adhoc
"""

from __future__ import annotations

# v0.1.23 infra fix: Windows CryptoAPI CRL revocation check fails on this machine
# (CRYPT_E_NO_REVOCATION_CHECK 0x80092012) blocking ALL Python httpx HTTPS calls
# to api.anthropic.com + huggingface.co. truststore.inject_into_ssl() routes ssl
# validation through Windows native trust store (same as Edge/Chrome browser),
# bypassing the broken CRL check. Must be called BEFORE any HTTP-using import.
# See §22.22 disclosure in ADR-0029.
import truststore

truststore.inject_into_ssl()

# ruff: noqa: E402 — the imports below MUST come after truststore.inject_into_ssl()
# so that any ssl-using module (httpx, anthropic SDK, huggingface_hub) picks up
# the injected default-context. Reordering would re-introduce the SSL block.
import argparse  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

from evals.harness import _REPORT_PATH  # noqa: E402
from evals.harness import main as _harness_main  # noqa: E402

_V0123_DIR = Path("evals/reports/v0.1.23")


def _load_case_ids(cases_file: Path) -> set[str]:
    """BOM-safe, comment/blank-skipping id-set loader (v0120_run.py precedent)."""
    return {
        ln.strip()
        for ln in cases_file.read_text(encoding="utf-8-sig").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }


def _isolate_report(tag: str) -> None:
    """Path-B isolation: snapshot this run's report to evals/reports/v0.1.23/<tag>.md,
    then restore the committed canonical evals/reports/latest.md.

    Mirrors scripts/v0120_run.py::_isolate_report exactly. If the harness
    process is hard-killed between writing latest.md and this call, recover
    the committed baseline with `git checkout HEAD -- evals/reports/latest.md`.
    """
    _V0123_DIR.mkdir(parents=True, exist_ok=True)
    dest = _V0123_DIR / f"{tag}.md"
    if _REPORT_PATH.exists():
        dest.write_bytes(_REPORT_PATH.read_bytes())
    subprocess.run(["git", "checkout", "HEAD", "--", str(_REPORT_PATH)], check=True, timeout=30)


def run(*, cases_file: Path, tag: str) -> None:
    """Run the harness for v0.1.23 paid validation with PRODUCTION STATE env.

    Production state = env-unset (chat default = v1.5 since v0.1.21 + Tier 1
    Auditor quorum + Tier 2 Capa A+B+C + retrieval defaults + Council binding).

    cases_file: allowlist (probe 5 ids OR main 25 ids OR safety 2 ids).
    tag: report basename under evals/reports/v0.1.23/ (e.g. "probe",
         "v0.1.23-prod-main", "v0.1.23-prod-safety-adhoc").
    """
    ids = _load_case_ids(cases_file)
    prev = os.environ.get("REGULAITOR_ANALYST_PROMPT_VERSION")
    # Explicitly UNSET: production state uses analyst.py default (v1.5 chat).
    os.environ.pop("REGULAITOR_ANALYST_PROMPT_VERSION", None)
    try:
        try:
            # subset=None: the case_ids allowlist is the truth source.
            _harness_main(subset=None, case_ids=ids)
        finally:
            # Snapshot + restore canonical latest.md even if the (paid)
            # harness crashed mid/post-run. v0120_run.py precedent.
            _isolate_report(tag)
    finally:
        if prev is not None:
            os.environ["REGULAITOR_ANALYST_PROMPT_VERSION"] = prev


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="v0.1.23 USER-GATED paid validation runner")
    p.add_argument(
        "--cases-file",
        type=Path,
        required=True,
        help="Newline-delimited case-id allowlist (e.g. evals/v0123_probe_ids.txt)",
    )
    p.add_argument(
        "--tag",
        required=True,
        help="Report basename under evals/reports/v0.1.23/ (e.g. probe, v0.1.23-prod-main)",
    )
    return p.parse_args()


if __name__ == "__main__":
    a = parse_args()
    run(cases_file=a.cases_file, tag=a.tag)
