"""G1 arm-B recovery — $0 graph-only capture of the MINIMAL SOVEREIGN STACK.

Anthropic credits were exhausted mid-main (arm A finished clean; arm B would
have degraded to placeholders because the Council + LLM-judge use Haiku). This
recovers arm B (Mistral+v1.6) at $0 WITHOUT any US provider by running only the
sovereign-critical path:

    injection-check (pure Python)
      -> Retriever (BGE-M3, local)
      -> Analyst (Mistral Small, self-hosted EU)
      -> Auditor (pure Python, the §6 enforcement layer)

The Council + LLM-judge (Haiku, Anthropic) are SKIPPED — they are advisory
quality layers, not the sovereign-critical verdict/citation/§6 signal. This is
also an accidental real-world test of the sovereign posture: with Anthropic (US)
fully down, the EU-only stack still produces valid verdicts + citations.

Captures per case: verdict, emitted citations, per-citation §6 validation
(validated + failed_check → fabrication vs paraphrase), and the answer text (for
manual content-safety review of chat-014/015). Writes JSONL; $0.

  HF_HUB_OFFLINE=1 REGULAITOR_RETRIEVAL_CONFIG='{"pre_rerank":12}' \
    uv run --env-file .env python -m scripts.g1_sovereign_capture
"""

from __future__ import annotations

import truststore

truststore.inject_into_ssl()

# ruff: noqa: E402 — imports MUST follow truststore.inject_into_ssl().
import json  # noqa: E402
import os  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

# Sovereign posture: no US provider. OpenAI is out of quota; Anthropic is out of
# credit. The self-hosted (Mistral) Analyst + pure-Python Auditor need neither.
os.environ.pop("OPENAI_API_KEY", None)
# Arm B config: Mistral Analyst + citation-format-hardened prompt v1.6.
os.environ["REGULAITOR_ANALYST_MODEL_CHOICE"] = "self_hosted"
os.environ["REGULAITOR_ANALYST_PROMPT_VERSION"] = "v1.6"

from evals.harness import load_gold_set  # noqa: E402

from regulaitor.agents.analyst import AnalystAgent  # noqa: E402
from regulaitor.agents.auditor import AuditorAgent  # noqa: E402
from regulaitor.agents.retriever import RetrieverAgent  # noqa: E402
from regulaitor.corpus.loader import warmup  # noqa: E402
from regulaitor.security import injection  # noqa: E402

_COHORT = [f"chat-{i:03d}" for i in range(6, 26)]  # chat-006..025 (main N=20)
_OUT = Path("evals/reports/g1/arm-b-mistral-v16-main-n20-sovereign.jsonl")


def _fmt(cit) -> str:
    ap = getattr(cit, "apartado", None)
    return f"{cit.articulo}.{ap}" if ap else cit.articulo


def _capture_case(case, retriever, analyst, auditor) -> dict:
    t0 = time.monotonic()
    blocked, reason = injection.is_injection(case.entrada)
    if blocked:
        return {
            "case_id": case.id,
            "injection_blocked": True,
            "verdict": "blocked_injection",
            "reason": reason,
            "latency_s": round(time.monotonic() - t0, 1),
        }
    ctx = retriever.retrieve(case.entrada, case.corpus_esperado, "es")
    answer = analyst.analyze(case.entrada, ctx, model_choice="self_hosted")
    audited = auditor.audit(answer)

    per_cit = [
        {
            "articulo": _fmt(r.citation),
            "validated": r.validated,
            "failed_check": r.failed_check,  # 1/2=fabrication, 3=paraphrase, 4=too-short
        }
        for r in audited.audit_results
    ]
    emitted = [_fmt(c) for f in audited.answer.findings for c in f.citations]
    fabrications = [p for p in per_cit if p["failed_check"] in (1, 2)]
    return {
        "case_id": case.id,
        "injection_blocked": False,
        "verdict": str(audited.verdict),
        "emitted": emitted,
        "expected_citations": list(case.articulos_esperados),
        "expected_verdict": case.expected_verdict,
        "acceptable_verdicts": getattr(case, "acceptable_verdicts", None),
        "n_findings": len(audited.answer.findings),
        "per_citation": per_cit,
        "n_fabrications": len(fabrications),  # §6 safety floor: MUST be 0
        "n_context_chunks": len(ctx.chunks) if hasattr(ctx, "chunks") else None,
        "answer_text": (audited.answer.text or "")[:600],  # for chat-014/015 safety review
        "latency_s": round(time.monotonic() - t0, 1),
    }


def main() -> None:
    warmup()
    chat_cases, _doc = load_gold_set(case_ids=set(_COHORT))
    by_id = {c.id: c for c in chat_cases}
    retriever, analyst, auditor = RetrieverAgent(), AnalystAgent(), AuditorAgent()
    print(f"[sovereign] cohort={len(_COHORT)} | Analyst=Mistral(self_hosted) prompt=v1.6")
    print("[sovereign] Council + LLM-judge SKIPPED (no Anthropic) — verdict/citation/§6 only")

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    with _OUT.open("w", encoding="utf-8") as fh:
        for cid in _COHORT:
            case = by_id.get(cid)
            if case is None:
                print(f"[sovereign] {cid}: NOT in gold (skip)")
                continue
            try:
                rec = _capture_case(case, retriever, analyst, auditor)
            except Exception as exc:  # noqa: BLE001 — one failure must not kill the run
                rec = {"case_id": cid, "error": f"{type(exc).__name__}: {exc}"[:400]}
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())  # survive a hard kill (v0.1.8 checkpoint discipline)
            if "error" in rec:
                print(f"[sovereign] {cid}: ERROR {rec['error'][:80]}")
            else:
                print(
                    f"[sovereign] {cid}: verdict={rec['verdict']} "
                    f"emitted={rec['emitted']} fab={rec['n_fabrications']} "
                    f"({rec['latency_s']}s)"
                )
    print(f"[sovereign] done -> {_OUT}")


if __name__ == "__main__":
    main()
