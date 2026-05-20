"""v0.1.9 — xcorpus-002 retrieval diagnostic (MINIMAL, ~30-60s $0 local CPU).

Question being diagnosed (H15.1 open issue, ADR-0017 §Consequences):

    xcorpus-002 (gold case): "operador NIS2 con fuga de datos personales,
    ¿notificar solo al CSIRT (NIS2) o también APD (RGPD)?"
    Expected articles: NIS2 art 23 + NIS2 art 35 + GDPR art 33.

    In H15.1's auto-path measurement the system surfaced NIS2 art 23.1 / 23.4
    but did NOT surface NIS2 art 35 nor GDPR art 33; verdict regressed
    RHR ✅ → block ❌.

Minimal 3-call diagnostic (NOT a sweep — the original 36-cell sweep
underestimated CPU-bound rerank cost and timed out before producing output).
Each call answers exactly one diagnostic question:

    1. **Current defaults** (purity_threshold=0.6, top_k=5, pre_rerank=50)
       → confirms / refutes the H15.1 finding (NIS2-23 only, not 35 or GDPR-33).
    2. **Lower threshold** (purity_threshold=0.5, otherwise defaults)
       → if this surfaces NIS2-35 / GDPR-33, the purity gate is the root cause
       and lowering the default is a viable v0.1.9 win.
    3. **Dense-only at pre_rerank=200** (no rerank, no purity gate)
       → if NIS2-35 / GDPR-33 are NOT in the dense pool even at pre_rerank=200,
       no tuning lever can recover them → root cause is dense-retrieval depth,
       which is a separate (larger) milestone than v0.1.9.

Invocation: `uv run python -m scripts.diagnose_xcorpus_002`
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from regulaitor.corpus import loader
from regulaitor.rag import embeddings, reranker, retrieval, store
from regulaitor.rag.build import INDEX_PATH

QUERY = (
    "Nuestra organización es operador de infraestructura digital sujeta a "
    "NIS2 y hemos sufrido un incidente que implica fuga de datos personales. "
    "¿Debemos notificarlo solo al CSIRT según NIS2 o también a la autoridad "
    "de protección de datos según el RGPD?"
)
LANGUAGE = "es"
EXPECTED: list[tuple[str, str]] = [("nis2", "23"), ("nis2", "35"), ("gdpr", "33")]
REPORT_PATH = Path("docs/xcorpus_002_investigation.md")


def _present(items: list[dict[str, Any]]) -> set[tuple[str, str]]:
    return {(c["norma"], c["articulo"]) for c in items if (c["norma"], c["articulo"]) in EXPECTED}


def _emitted_keys(chunks: list[Any]) -> list[str]:
    return [f"{c.norma}.{c.articulo}" for c in chunks]


def main() -> None:
    print("[v0.1.9] xcorpus-002 minimal diagnostic starting...")
    loader.warmup()
    reranker.warmup()

    # ---------------------------------------------------------------------
    # Call 1: auto-path with current production defaults
    # ---------------------------------------------------------------------
    print("\n[1/3] auto-path with current defaults (purity=0.6, top_k=5, pre_rerank=50)")
    cfg_default = retrieval.RetrievalConfig()  # all defaults
    chunks1, resolved1 = retrieval.run_auto(QUERY, LANGUAGE, cfg_default)
    emitted1 = _emitted_keys(chunks1)
    present1 = _present([{"norma": c.norma, "articulo": c.articulo} for c in chunks1])
    print(f"      resolved_normas: {resolved1}")
    print(f"      emitted: {emitted1}")
    print(f"      expected present: {sorted(present1)} ({len(present1)}/3)")

    # ---------------------------------------------------------------------
    # Call 2: auto-path with lower purity_threshold
    # ---------------------------------------------------------------------
    print("\n[2/3] auto-path with purity_threshold=0.5 (otherwise defaults)")
    cfg_lower = retrieval.RetrievalConfig(purity_threshold=0.5)
    chunks2, resolved2 = retrieval.run_auto(QUERY, LANGUAGE, cfg_lower)
    emitted2 = _emitted_keys(chunks2)
    present2 = _present([{"norma": c.norma, "articulo": c.articulo} for c in chunks2])
    print(f"      resolved_normas: {resolved2}")
    print(f"      emitted: {emitted2}")
    print(f"      expected present: {sorted(present2)} ({len(present2)}/3)")

    # ---------------------------------------------------------------------
    # Call 3: dense-only at pre_rerank=200 (no rerank, no purity gate)
    # ---------------------------------------------------------------------
    print("\n[3/3] dense-only pool at pre_rerank=200 (no rerank, no purity gate)")
    [qvec] = embeddings.embed([QUERY])
    table = store.connect(INDEX_PATH)
    where_clause = f"language = '{LANGUAGE}'"
    cands = list(table.search(qvec).where(where_clause).limit(200).to_list())
    per_norma = Counter(c["norma"] for c in cands)
    present3 = _present(cands)
    print(f"      candidate pool n={len(cands)}, per-norma: {dict(per_norma)}")
    print(f"      expected present in pool: {sorted(present3)} ({len(present3)}/3)")
    print(f"      expected MISSING from pool: {sorted(set(EXPECTED) - present3)}")

    # ---------------------------------------------------------------------
    # Write findings to markdown
    # ---------------------------------------------------------------------
    markdown = _render_markdown(
        emitted1, resolved1, present1, emitted2, resolved2, present2, per_norma, present3
    )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(markdown, encoding="utf-8")
    # ASCII arrow to survive Windows cp1252 console encoding (the unicode
    # arrow U+2192 crashes default Windows stdout — discovered the hard way).
    print(f"\n[v0.1.9] diagnostic complete -> {REPORT_PATH}")


def _render_markdown(
    emitted1: list[str],
    resolved1: list[Any],
    present1: set[tuple[str, str]],
    emitted2: list[str],
    resolved2: list[Any],
    present2: set[tuple[str, str]],
    per_norma3: Counter,
    present3: set[tuple[str, str]],
) -> str:
    expected_str = ", ".join(f"`{n}.{a}`" for (n, a) in EXPECTED)
    missing3 = sorted(set(EXPECTED) - present3)
    missing3_str = ", ".join(f"`{n}.{a}`" for (n, a) in missing3) or "—"

    lines: list[str] = []
    lines.append("# xcorpus-002 retrieval diagnostic (v0.1.9)\n")
    lines.append(
        "Investigation of why the H15.1 auto-path measurement on the cross-corpus "
        "case xcorpus-002 did NOT surface NIS2 art 35 nor GDPR art 33 (only NIS2 "
        "art 23.1 / 23.4), causing verdict regression RHR ✅ → block ❌.\n"
    )
    lines.append(f"**Query:** {QUERY}\n")
    lines.append(f"**Expected articles (per gold set):** {expected_str}\n")
    lines.append("---\n")

    lines.append("## Diagnostic results (3 calls, $0 local CPU)\n")
    lines.append("| Call | Config | Emitted articles | Resolved normas | Expected present |")
    lines.append("|---|---|---|---|---|")
    lines.append(
        f"| 1 (defaults) | purity=0.6, top_k=5, pre_rerank=50 | "
        f"{', '.join(f'`{k}`' for k in emitted1)} | {'+'.join(str(r) for r in resolved1)} | "
        f"{len(present1)}/3 ({', '.join(f'`{n}.{a}`' for (n, a) in sorted(present1)) or '—'}) |"
    )
    lines.append(
        f"| 2 (lower threshold) | purity=0.5, top_k=5, pre_rerank=50 | "
        f"{', '.join(f'`{k}`' for k in emitted2)} | {'+'.join(str(r) for r in resolved2)} | "
        f"{len(present2)}/3 ({', '.join(f'`{n}.{a}`' for (n, a) in sorted(present2)) or '—'}) |"
    )
    lines.append("")

    lines.append("### Call 3: dense-only pool diagnostic (the root-cause discriminator)\n")
    lines.append(
        "Raw top-200 candidates from LanceDB (no rerank, no purity gate). If an "
        "expected article is MISSING here, no tuning lever can recover it — the "
        "issue is in dense retrieval / embedding, not the post-rerank gate.\n"
    )
    lines.append(f"**Pool size:** {sum(per_norma3.values())} candidates")
    lines.append(
        "**Per-norma counts:** " + ", ".join(f"`{k}`={v}" for k, v in sorted(per_norma3.items()))
    )
    lines.append(
        f"**Expected present in pool:** {len(present3)}/3 "
        f"({', '.join(f'`{n}.{a}`' for (n, a) in sorted(present3)) or '—'})"
    )
    lines.append(f"**Expected MISSING from pool:** {missing3_str}\n")
    lines.append("---\n")

    lines.append("## Interpretation (§22.22-honest, data-driven)\n")
    # Decision tree
    if len(missing3) > 0:
        lines.append(
            "**Root cause: dense-retrieval depth (NOT the purity gate).**\n\n"
            f"At pre_rerank=200 the dense pool already misses {missing3_str}. The "
            "tuning levers exposed in `RetrievalConfig` operate AFTER dense "
            "retrieval (rerank + purity gate), so no `purity_threshold` /  "
            "`top_k` / `pre_rerank` combination within current architecture can "
            "recover the missing article(s).\n\n"
            "**Implication for v0.1.9**: NO production default change. The fix "
            "is OUT of v0.1.9's scope (would require either re-embed with a "
            "different model, query-expansion, or corpus re-chunking — all "
            "larger milestones). This is a **documented deeper ceiling** (H15-style "
            "honest outcome).\n"
        )
    elif present2 > present1:
        lines.append(
            "**Root cause: purity gate too aggressive at default 0.6.**\n\n"
            f"Call 2 (purity=0.5) recovered "
            f"{', '.join(f'`{n}.{a}`' for (n, a) in sorted(present2 - present1))} "
            f"that Call 1 (purity=0.6) discarded. The dense pool DID contain the "
            "expected articles (Call 3 confirms); the gate was filtering them out.\n\n"
            "**Implication for v0.1.9**: candidate for promoting "
            "`purity_threshold=0.5` to production default. Requires ADR-0019 + "
            "downstream test updates + paid validation in v0.1.16 to confirm no "
            "regression on the rest of the gold set.\n"
        )
    else:
        lines.append(
            "**Root cause: reranker scoring on this query (not the purity gate, "
            "not dense-retrieval depth).**\n\n"
            "The dense pool contains all expected articles (Call 3) but neither "
            "Call 1 (defaults) nor Call 2 (lower threshold) surfaces the missing "
            "ones — the reranker is positioning them outside top-5. Lowering "
            "`purity_threshold` alone does not help.\n\n"
            "**Implication for v0.1.9**: the immediate tuning lever is `top_k` "
            "(or `pre_rerank` with `top_k` raised), but raising `top_k` "
            "invalidates downstream chunk-budget assumptions. Documented as "
            "deeper ceiling for v0.1.9; the reranker-layer fix is a separate "
            "milestone.\n"
        )
    lines.append("---\n")
    lines.append(
        "_Generated by `scripts/diagnose_xcorpus_002.py`. Re-run after any change "
        "to `_apply_purity_gate`, BGE-M3, or the reranker. The slow integration "
        "test `tests/integration/test_xcorpus_002_purity_sweep.py` pins these "
        "results for regression detection._\n"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
