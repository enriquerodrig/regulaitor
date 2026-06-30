"""sec6-01 / ADR-0043 — reproduce the citation length-floor calibration ($0, offline).

Two measurements justify ``_MIN_CITATION_CHARS = 20`` in ``citation/validator.py``:

1. The shortest VALIDATED citation across paid runs — mined from the
   ``per_citation_audits`` trail in ``evals/checkpoints/*.jsonl`` (v0.1.21.1 D2).
2. The shortest citable corpus segment — from ``corpus/processed/*.json``.

The floor sits below both, so it cannot reject a full-segment citation and rejected
zero of the observed validated citations, while closing the trivial-token band.

Run: ``uv run python scripts/sec6_citation_floor_calibration.py``
"""

from __future__ import annotations

import glob
import json
import statistics as st

from regulaitor.rag.chunking import _normalize


def _summary(name: str, xs: list[int]) -> None:
    if not xs:
        print(f"{name}: EMPTY")
        return
    xs = sorted(xs)
    p5 = xs[len(xs) // 20]
    print(f"{name}: n={len(xs)} min={xs[0]} p5={p5} median={int(st.median(xs))} max={xs[-1]}")


def validated_citation_lengths() -> list[int]:
    lens: list[int] = []
    for path in sorted(glob.glob("evals/checkpoints/*.jsonl")):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    data = json.loads(line).get("data", {})
                except json.JSONDecodeError:
                    continue
                for entry in data.get("per_citation_audits") or []:
                    cit = entry.get("citation") or {}
                    txt = cit.get("text")
                    if isinstance(txt, str) and entry.get("validated") is True:
                        lens.append(len(_normalize(txt)))
    return lens


def corpus_segment_lengths() -> list[int]:
    lens: list[int] = []

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("text", "texto", "content", "body") and isinstance(v, str) and v.strip():
                    lens.append(len(_normalize(v)))
                else:
                    walk(v)
        elif isinstance(obj, list):
            for x in obj:
                walk(x)

    for path in set(glob.glob("corpus/processed/**/*.json", recursive=True)):
        try:
            with open(path, encoding="utf-8") as fh:
                walk(json.load(fh))
        except (json.JSONDecodeError, OSError):
            continue
    return lens


def main() -> None:
    _summary("VALIDATED citations (normalized chars)", validated_citation_lengths())
    _summary("Corpus citable segments (normalized chars)", corpus_segment_lengths())


if __name__ == "__main__":
    main()
