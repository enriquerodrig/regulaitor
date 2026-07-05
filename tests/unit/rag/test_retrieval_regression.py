"""$0 dense-retrieval recall regression guard (roadmap P1.2).

Uses PRECOMPUTED BGE-M3 query embeddings (evals/fixtures/retrieval_regression.jsonl,
produced by scripts/gen_retrieval_fixture.py) against the COMMITTED LanceDB index, so
it runs in CI with NO ML-model load — pure lancedb vector search. It is the regression
guard the retrieval layer (directly under the §6 moat, and the layer corpus expansion
churns most) previously lacked: it catches a re-embed, re-chunk, purity/dedup change,
or index compaction that drops a known-good article out of dense top-k. All live-index
recall tests before this were @slow (excluded from CI); this one is $0 and CI-gated.

If you DELIBERATELY change the embedding model or re-index, the precomputed query
vectors go stale vs the new index (mismatched embedding space) and recall drops — that
is the intended signal: regenerate the fixture (scripts/gen_retrieval_fixture.py) and
re-verify recall.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from regulaitor.rag import store
from regulaitor.rag.retrieval import INDEX_PATH

_FIXTURE = Path("evals/fixtures/retrieval_regression.jsonl")
_K = 15  # generous top-k: a dense-recall regression guard, not a ranking test


def _load_cases() -> list[dict[str, Any]]:
    lines = _FIXTURE.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


_CASES = _load_cases()


def _article_match(article_id: str, expected: str) -> bool:
    """Article-level (hierarchical) match: article_id is `{norma}.{articulo}[.{apartado}]`,
    so expected `ai_act.6` matches `ai_act.6.1`. Trailing dot avoids `gdpr.3` vs `gdpr.33`."""
    return article_id == expected or article_id.startswith(expected + ".")


def _ranked_article_ids(vec: list[float], corpus: str, language: str) -> list[str]:
    table = store.connect(INDEX_PATH, create=False)  # read-only; never materialise
    where = f"norma = '{corpus}' AND language = '{language}'"
    rows = table.search(vec).where(where).limit(_K).to_list()
    seen: list[str] = []
    for r in rows:
        aid = r["article_id"]
        if aid not in seen:
            seen.append(aid)
    return seen


def test_fixture_is_present_and_sized() -> None:
    # Guard against a truncated/empty fixture silently passing the recall check.
    assert len(_CASES) >= 5


@pytest.mark.parametrize("case", _CASES, ids=[c["expected_article_id"] for c in _CASES])
def test_expected_article_in_dense_topk(case: dict[str, Any]) -> None:
    ranked = _ranked_article_ids(case["embedding"], case["corpus"], case["language"])
    assert any(
        _article_match(a, case["expected_article_id"]) for a in ranked
    ), f"{case['expected_article_id']} regressed out of dense top-{_K}: {ranked}"
