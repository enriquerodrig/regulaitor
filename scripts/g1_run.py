"""G1 — sovereign quality A/B runner: Mistral Small + v1.6 vs Sonnet + v1.5.

Answers the sovereign go/no-go: does the open self-hosted model (Mistral Small)
with the citation-format-hardened Analyst prompt v1.6 sustain the §6 chain + quality
close enough to production (Sonnet + v1.5) to make the EU-sovereign deploy (G3) pure
infra? The R1 probe measured Mistral at verdict_match 0.70 (prose-citation failure);
v1.6 (Hard Rule 10) was authored to fix it but never re-measured — this is that
measurement.

2-arm FRESH same-day (no API-drift caveat), Haiku judge constant, per-case checkpoint
(H15.2 lesson). Arm A = default env (Sonnet + v1.5). Arm B = REGULAITOR_ANALYST_
MODEL_CHOICE=self_hosted + REGULAITOR_ANALYST_PROMPT_VERSION=v1.6 (Mistral via the
REGULAITOR_SELFHOST_* env). Judge + Council stay on their default modes for a clean
Analyst-only A/B.

USER-GATED (paid). Invoke with .env loaded (ANTHROPIC_API_KEY for judge/Council +
REGULAITOR_SELFHOST_* for Mistral):

  uv run --env-file .env python -m scripts.g1_run --cases-file evals/g1_probe_ids.txt --tag probe-n5
"""

from __future__ import annotations

# Windows CryptoAPI CRL revocation check fails on this machine (0x80092012),
# blocking all Python httpx HTTPS (api.mistral.ai + api.anthropic.com). Route ssl
# validation through the Windows native trust store BEFORE any HTTP-using import.
import truststore

truststore.inject_into_ssl()

# ruff: noqa: E402 — imports MUST follow truststore.inject_into_ssl().
import argparse  # noqa: E402
import os  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402

# The OpenAI key on this machine is out of quota (429 insufficient_quota). The
# Council's evaluation-mode judge (GPT-4o) would 429 → tenacity retry storm
# (~370-510s/case) before degrading. Unsetting the key makes P4.1 skip that
# judge cleanly (fast) instead. This is ALSO the sovereign-realistic posture:
# the EU-only deploy target (G3) has no US provider, so an OpenAI-free run is
# MORE representative than one against a dead key. Applied to BOTH arms → the
# A/B stays symmetric. Ragas + judge both use Haiku (Anthropic), not OpenAI.
os.environ.pop("OPENAI_API_KEY", None)

from evals.harness import _REPORT_PATH  # noqa: E402
from evals.harness import main as _harness_main  # noqa: E402

_G1_DIR = Path("evals/reports/g1")
_ARM_KEYS = ("REGULAITOR_ANALYST_MODEL_CHOICE", "REGULAITOR_ANALYST_PROMPT_VERSION")


def _load_case_ids(cases_file: Path) -> set[str]:
    """BOM-safe, comment/blank-skipping id-set loader (probe_r1_run.py precedent)."""
    return {
        ln.strip()
        for ln in cases_file.read_text(encoding="utf-8-sig").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }


def _isolate_report(arm_tag: str) -> None:
    """Snapshot latest.md → evals/reports/g1/<arm_tag>.md then restore the committed
    canonical latest.md (Path-B isolation; mirrors probe_r1_run.py). Recover after a
    hard kill with `git checkout HEAD -- evals/reports/latest.md`."""
    _G1_DIR.mkdir(parents=True, exist_ok=True)
    dest = _G1_DIR / f"{arm_tag}.md"
    if _REPORT_PATH.exists():
        dest.write_bytes(_REPORT_PATH.read_bytes())
    subprocess.run(["git", "checkout", "HEAD", "--", str(_REPORT_PATH)], check=True, timeout=30)


def _run_arm(*, arm_tag: str, case_ids: set[str], overrides: dict[str, str]) -> None:
    """Run the harness for one arm with `overrides` applied (and the arm keys cleared
    first so a leaked .env value cannot contaminate arm A), then isolate the report."""
    prev = {k: os.environ.get(k) for k in _ARM_KEYS}
    for k in _ARM_KEYS:
        os.environ.pop(k, None)
    os.environ.update(overrides)
    try:
        try:
            _harness_main(case_ids=case_ids)
        finally:
            _isolate_report(arm_tag)
    finally:
        for k in _ARM_KEYS:
            v = prev[k]
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run(*, cases_file: Path, tag: str) -> None:
    ids = _load_case_ids(cases_file)
    print(f"[g1] cohort = {len(ids)} cases; tag = {tag}")
    print("[g1] Arm A: Sonnet + v1.5 (prod default) ...")
    _run_arm(arm_tag=f"arm-a-sonnet-v15-{tag}", case_ids=ids, overrides={})
    print("[g1] Arm B: Mistral Small + v1.6 (sovereign) ...")
    _run_arm(
        arm_tag=f"arm-b-mistral-v16-{tag}",
        case_ids=ids,
        overrides={
            "REGULAITOR_ANALYST_MODEL_CHOICE": "self_hosted",
            "REGULAITOR_ANALYST_PROMPT_VERSION": "v1.6",
        },
    )
    print(f"[g1] done. reports in {_G1_DIR}/arm-a-sonnet-v15-{tag}.md + arm-b-mistral-v16-{tag}.md")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="G1 sovereign quality A/B runner (USER-GATED, paid)")
    p.add_argument("--cases-file", type=Path, required=True, help="Newline case-id allowlist")
    p.add_argument(
        "--tag", default="probe-n5", help="Report basename suffix under evals/reports/g1/"
    )
    return p.parse_args()


if __name__ == "__main__":
    a = parse_args()
    run(cases_file=a.cases_file, tag=a.tag)
