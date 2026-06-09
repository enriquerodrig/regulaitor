"""Probe R1 — open-model (self_hosted) Analyst measurement runner.

Runs the chat eval harness with the Analyst routed to the open-source
self-hosted model (REGULAITOR_ANALYST_MODEL_CHOICE=self_hosted -> Mistral Small
via REGULAITOR_SELFHOST_* env), leaving the judge/Council constant, to measure
whether the open model sustains the §6 citation chain.

Gate DP2 (product_strategy.md §10): citation_recall >= 0.40 + 0 fabrications +
redteam-smoke >= 0.92 (separate) + valid tool_use. $0 on the Mistral free tier
(the Analyst); only the Haiku judge layer costs a few cents.

USER-GATED. Invoke (loads .env -> ANTHROPIC_API_KEY for judge + REGULAITOR_SELFHOST_*):

  uv run --env-file .env python -m scripts.probe_r1_run --subset 5 --tag probe-n5
"""

from __future__ import annotations

# Windows CryptoAPI CRL revocation check fails on this machine
# (CRYPT_E_NO_REVOCATION_CHECK 0x80092012), blocking ALL Python httpx HTTPS
# calls (api.mistral.ai, api.anthropic.com). truststore.inject_into_ssl() routes
# ssl validation through the Windows native trust store. MUST run before any
# HTTP-using import. See ADR-0029 §22.22 #2 + the probe smoke confirmation.
import truststore

truststore.inject_into_ssl()

# ruff: noqa: E402 — imports below MUST follow truststore.inject_into_ssl() so
# httpx / the openai + anthropic SDKs pick up the injected default ssl context.
import argparse  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

from evals.harness import _REPORT_PATH  # noqa: E402
from evals.harness import main as _harness_main  # noqa: E402

_PROBE_DIR = Path("evals/reports/probe-r1")


def _load_case_ids(cases_file: Path) -> set[str]:
    """BOM-safe, comment/blank-skipping id-set loader (v0129_run.py precedent)."""
    return {
        ln.strip()
        for ln in cases_file.read_text(encoding="utf-8-sig").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }


def _isolate_report(tag: str) -> None:
    """Snapshot this run's report to evals/reports/probe-r1/<tag>.md then restore
    the committed canonical evals/reports/latest.md (Path-B isolation; mirrors
    scripts/v0129_run.py). If hard-killed mid-write, recover the baseline with
    `git checkout HEAD -- evals/reports/latest.md`.
    """
    _PROBE_DIR.mkdir(parents=True, exist_ok=True)
    dest = _PROBE_DIR / f"{tag}.md"
    if _REPORT_PATH.exists():
        dest.write_bytes(_REPORT_PATH.read_bytes())
    subprocess.run(["git", "checkout", "HEAD", "--", str(_REPORT_PATH)], check=True, timeout=30)


def run(
    *,
    subset: int | None,
    tag: str,
    case_ids: set[str] | None = None,
    prompt_version: str | None = None,
) -> None:
    """Run the harness with the Analyst on the self_hosted (open) model.

    Sets REGULAITOR_ANALYST_MODEL_CHOICE=self_hosted (Analyst-only seam; judge
    and Council stay on their default modes for a clean A/B), and optionally
    REGULAITOR_ANALYST_PROMPT_VERSION (e.g. v1.6 citation-format-hardened),
    for the duration of the run; restores prior values afterwards. A case_ids
    allowlist runs exactly those ids (e.g. a chat-only H10 cohort, skipping the
    slow doc cases); subset further truncates AFTER the allowlist filter.
    """
    overrides: dict[str, str] = {"REGULAITOR_ANALYST_MODEL_CHOICE": "self_hosted"}
    if prompt_version is not None:
        overrides["REGULAITOR_ANALYST_PROMPT_VERSION"] = prompt_version
    prev = {k: os.environ.get(k) for k in overrides}
    os.environ.update(overrides)
    try:
        try:
            _harness_main(subset=subset, case_ids=case_ids)
        finally:
            _isolate_report(tag)
    finally:
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Probe R1 self_hosted Analyst runner (USER-GATED)")
    p.add_argument(
        "--subset",
        type=int,
        default=None,
        help="First N chat cases (proportional docs). Omit when using --cases-file.",
    )
    p.add_argument(
        "--cases-file",
        type=Path,
        default=None,
        help="Newline-delimited case-id allowlist (e.g. chat-only H10 cohort). None = subset/all.",
    )
    p.add_argument(
        "--prompt-version",
        default=None,
        help="Analyst prompt version (e.g. v1.6). None = role-aware default (v1.5 chat).",
    )
    p.add_argument(
        "--tag", default="probe-n5", help="Report basename under evals/reports/probe-r1/"
    )
    return p.parse_args()


if __name__ == "__main__":
    a = parse_args()
    ids = _load_case_ids(a.cases_file) if a.cases_file is not None else None
    run(subset=a.subset, tag=a.tag, case_ids=ids, prompt_version=a.prompt_version)
