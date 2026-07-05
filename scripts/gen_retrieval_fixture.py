"""One-time generator for the $0 retrieval-regression fixture (roadmap P1.2).

Loads BGE-M3 locally (slow, but $0 — no LLM API), embeds a curated set of gold
(query → expected article) cases, runs the SAME dense LanceDB search production uses,
prints the top-5 per query for inspection, and writes only the cases whose expected
article is within top-k as `evals/fixtures/retrieval_regression.jsonl`. The committed
fixture carries the precomputed query embeddings, so the CI test needs no model load.

Run once: `uv run python scripts/gen_retrieval_fixture.py`
"""

from __future__ import annotations

import json
from pathlib import Path

from regulaitor.rag import embeddings, store
from regulaitor.rag.retrieval import INDEX_PATH

_K = 15  # generous top-k: this is a dense-recall regression guard, not a ranking test

# Curated gold cases: (query, corpus, language, expected_article_id). Chosen from
# well-established provisions; the generator confirms each is actually retrievable.
_CASES = [
    (
        "¿En qué plazo debe notificarse una violación de datos personales a la autoridad de control?",
        "gdpr",
        "es",
        "gdpr.33",
    ),
    (
        "¿Cuándo es obligatorio designar un delegado de protección de datos?",
        "gdpr",
        "es",
        "gdpr.37",
    ),
    (
        "¿Qué derechos de acceso tiene el interesado sobre sus datos personales?",
        "gdpr",
        "es",
        "gdpr.15",
    ),
    (
        "¿Cómo se clasifica un sistema de inteligencia artificial como de alto riesgo?",
        "ai_act",
        "es",
        "ai_act.6",
    ),
    (
        "¿Qué obligaciones de transparencia tienen los sistemas de IA que interactúan con personas físicas?",
        "ai_act",
        "es",
        "ai_act.50",
    ),
    (
        "¿Qué medidas de gestión de riesgos de ciberseguridad deben adoptar las entidades esenciales?",
        "nis2",
        "es",
        "nis2.21",
    ),
    (
        "¿Qué obligaciones de notificación de incidentes graves relacionados con las TIC establece el reglamento?",
        "dora",
        "es",
        "dora.19",
    ),
]


def _article_match(article_id: str, expected: str) -> bool:
    """Article-level (hierarchical) match: the index stores article_id as
    `{norma}.{articulo}[.{apartado}]`, so expected `ai_act.6` matches `ai_act.6.1`.
    Trailing-dot guard avoids `gdpr.3` matching `gdpr.33`."""
    return article_id == expected or article_id.startswith(expected + ".")


def _search(vec: list[float], corpus: str, language: str) -> list[str]:
    table = store.connect(INDEX_PATH, create=False)
    where = f"norma = '{corpus}' AND language = '{language}'"
    rows = table.search(vec).where(where).limit(_K).to_list()
    # Preserve rank order, dedupe article_id (a chunk-level index has many rows/article).
    seen: list[str] = []
    for r in rows:
        aid = r["article_id"]
        if aid not in seen:
            seen.append(aid)
    return seen


def main() -> None:
    queries = [q for q, *_ in _CASES]
    vecs = embeddings.embed(queries)
    out_rows = []
    for (query, corpus, language, expected), vec in zip(_CASES, vecs, strict=True):
        ranked = _search(vec, corpus, language)
        hit = any(_article_match(aid, expected) for aid in ranked)
        rank = next((i + 1 for i, aid in enumerate(ranked) if _article_match(aid, expected)), -1)
        print(f"[{'HIT' if hit else 'MISS'} rank={rank:>2}] {expected:12} top5={ranked[:5]}")
        if hit:
            out_rows.append(
                {
                    "query": query,
                    "corpus": corpus,
                    "language": language,
                    "expected_article_id": expected,
                    "embedding": [round(x, 6) for x in vec],
                }
            )
    out = Path("evals/fixtures/retrieval_regression.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out_rows), encoding="utf-8"
    )
    print(f"\nWrote {len(out_rows)}/{len(_CASES)} cases to {out} (k={_K}).")


if __name__ == "__main__":
    main()
