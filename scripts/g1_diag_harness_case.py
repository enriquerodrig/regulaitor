"""G1 diagnostic — run the harness's exact per-case path for ONE chat case and
print precisely WHERE it fails (graph guard vs metrics guard) and WHY.

The G1 probe recorded all-zero placeholders (emitted=[], verdict RHR) for every
case, yet a direct graph.run on chat-001 produced 4 real findings + verdict pass.
The harness has two guards that both emit that placeholder:
  - run_chat_case: except Exception -> _error_chat_state (graph raised)
  - main loop:     except Exception -> _error_chat_result (compute_chat_metrics raised)
This isolates which one fires and surfaces the raw traceback.

Runs with OPENAI_API_KEY unset (the dead insufficient_quota key that triggers the
Council/router 429 retry storms). That is also the sovereign-realistic config:
no US provider. USER-GATED (paid: 1 Sonnet Analyst call + Haiku judge ~ €0.05).

  HF_HUB_OFFLINE=1 REGULAITOR_RETRIEVAL_CONFIG='{"pre_rerank":12}' \
    uv run --env-file .env python -m scripts.g1_diag_harness_case
"""

from __future__ import annotations

import truststore

truststore.inject_into_ssl()

# ruff: noqa: E402 — imports MUST follow truststore.inject_into_ssl().
import os  # noqa: E402
import traceback  # noqa: E402
from functools import partial  # noqa: E402

# Sovereign-realistic + removes the dead-key 429 retry storm. P4.1 makes the
# Council skip a judge whose provider key is absent instead of 429-looping.
os.environ.pop("OPENAI_API_KEY", None)

from evals.cache import cache_call  # noqa: E402
from evals.harness import (
    _real_anthropic_invoke,  # noqa: E402
    load_gold_set,  # noqa: E402
    run_chat_case,  # noqa: E402
)
from evals.judge import score_criteria  # noqa: E402
from evals.metrics import compute_chat_metrics  # noqa: E402

from regulaitor.corpus.loader import warmup  # noqa: E402

CASE_ID = "chat-001"


def main() -> None:
    warmup()
    chat_cases, _doc = load_gold_set(case_ids={CASE_ID})
    case = next(c for c in chat_cases if c.id == CASE_ID)

    print(f"[diag] OPENAI_API_KEY present: {'OPENAI_API_KEY' in os.environ}")
    print(f"[diag] running graph for {CASE_ID} ...")
    state, latency_ms, cost_eur, cache_hit = run_chat_case(case, cache_only=False)

    print(f"[diag] graph done. latency_ms={latency_ms} cost_eur={cost_eur:.4f}")
    print(f"[diag] state.errors = {getattr(state, 'errors', None)}")
    aa = getattr(state, "audited_answer", None)
    if aa is None:
        print("[diag] >>> GRAPH GUARD FIRED: audited_answer is None (run_chat raised).")
    else:
        ans = getattr(aa, "answer", None)
        findings = getattr(ans, "findings", None) if ans else None
        print(f"[diag] audited_answer.verdict = {getattr(aa, 'verdict', None)}")
        print(f"[diag] n_findings = {len(findings) if findings else 0}")
        for i, f in enumerate(findings or []):
            cits = [c.articulo for c in getattr(f, "citations", [])]
            print(f"[diag]   finding{i}: sev={getattr(f, 'severity', None)} cits={cits}")

    print("[diag] now running compute_chat_metrics (judge=Haiku) ...")
    judge_call = partial(cache_call, invoke=_real_anthropic_invoke, cache_only=False)
    judge_score_fn = partial(score_criteria, cache_call=judge_call)
    try:
        result = compute_chat_metrics(
            case,
            state,
            judge_call=judge_call,
            judge_score_fn=judge_score_fn,
            latency_ms=latency_ms,
            cost_eur=cost_eur,
            cache_hit=cache_hit,
        )
        print("[diag] >>> compute_chat_metrics SUCCEEDED.")
        print(f"[diag] result.actual_verdict = {result.actual_verdict}")
        print(f"[diag] result.citations.emitted = {result.citations.emitted}")
        print(
            f"[diag] faithfulness={result.faithfulness} answer_relevancy={result.answer_relevancy} "
            f"context_precision={result.context_precision}"
        )
    except Exception:  # noqa: BLE001 — diagnostic: surface the raw traceback
        print("[diag] >>> METRICS GUARD WOULD FIRE: compute_chat_metrics RAISED:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
