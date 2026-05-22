# scripts/diagnose_no_answer.py
"""v0.1.17 — $0 No-Answer residual diagnostic. Disambiguates the no_answer
residual into 4 sub-cases by mining the judge cache:

- refusal:         Analyst emitted Answer with a structured refusal phrase
                   (legitimate, per v1.1/v1.2/v1.3 Output contract).
- analyst_raise:   Analyst raised before judge was called (no actual_answer
                   ever cached for this case's query).
- transport_error: actual_answer is empty string OR "(backend error)" sentinel
                   from the harness exception wrapper.
- other:           Analyst-emitted prose without standard refusal phrasing.
                   Needs manual review.

Algorithm per spec §2 D3:
1. Parse 3 canonical reports for no_answer cases (emitted=[] + verdict
   mismatch to requires_human_review).
2. Iterate evals/cache/*.json; for each, parse request.user as JSON; if it
   has {query, actual_answer} fields, retain as a CacheEntry.
3. For each no_answer case, find the cache entry by exact match on query.
   If found → classify by actual_answer content. If not found → analyst_raise.
4. Aggregate counts + render markdown report.

CLI: `python -m scripts.diagnose_no_answer` (no args).
Writes docs/no_answer_residual_diagnosis.md. Prints aggregate counts.
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Module constants (spec §2 D3 + §3 Architecture)
# ---------------------------------------------------------------------------

REFUSAL_PHRASES_ES: list[str] = [
    "no encuentro",
    "no encontré",
    "no puedo proporcionar",
    "el corpus no respalda",
    "no respalda",
    "no respaldada",
    "el contexto no apoya",
    "el contexto no respalda",
    "no contiene información",
    "información no disponible",
    "no se encontró",
    "no hay información",
    "no es posible responder",
    "no puedo responder",
    "no dispongo de información",
    "fuera del ámbito del corpus",
]

REFUSAL_PHRASES_EN: list[str] = [
    "i cannot provide",
    "the corpus does not support",
    "no information is available",
    "i don't have information",
    "out of scope of the corpus",
    "i'm unable to answer",
]

REFUSAL_PHRASES: list[str] = REFUSAL_PHRASES_ES + REFUSAL_PHRASES_EN

REPORTS_TO_SCAN: list[Path] = [
    Path("evals/reports/latest.md"),
    Path("evals/reports/h15/candidate-v1.2.md"),
    Path("evals/reports/h15/holdout-v1.2-chat.md"),
]

OUTPUT_PATH: Path = Path("docs/no_answer_residual_diagnosis.md")
CACHE_DIR: Path = Path("evals/cache")

# Case ID regex: matches chat-008, dora-001, nis2-006, xcorpus-002,
# industry-c1, industry-gv5, etc. At least one hyphen; lowercase alphanumeric.
_CASE_RE = re.compile(r"^### ([a-z0-9]+(?:-[a-z0-9]+)+)\s*$", re.M)
_VERDICT_RE = re.compile(r"\*\*Verdict\*\*: actual=`([^`]+)` expected=`([^`]+)`")
_CIT_RE = re.compile(r"\*\*Citations\*\*: emitted=(\[[^\]]*\]) expected=(\[[^\]]*\])")
# Query line in the per-case appendix is NOT directly present; we need to
# look it up via the gold set. But the gold set's `entrada` is what was sent
# to the Analyst, which is what appears in the cache. So we'll look it up
# from `evals/gold_set.jsonl` by case ID.
GOLD_SET_PATH: Path = Path("evals/gold_set.jsonl")


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CacheEntry:
    """One parsed evals/cache/*.json entry; only the fields we need."""

    path: str  # source filename for debugging
    request_user_json: str  # the request.user field (a JSON string)


@dataclass(frozen=True)
class ReportCase:
    """One no_answer case parsed from a report's per-case appendix."""

    report_file: str  # e.g. "latest.md"
    case_id: str  # e.g. "chat-008", "dora-001"
    expected_articles: list[str]
    expected_verdict: str  # "pass" / "block" / "requires_human_review"
    actual_verdict: str  # always "requires_human_review" for our subset
    query: str  # the gold case's entrada (looked up from gold_set.jsonl)


@dataclass(frozen=True)
class NoAnswerDiagnosis:
    """One classified no_answer case."""

    report_file: str
    case_id: str
    expected_articles: list[str]
    expected_verdict: str
    actual_verdict: str
    classification: str  # "refusal" / "analyst_raise" / "transport_error" / "other"
    actual_answer_snippet: str  # first 200 chars OR "(not in cache)" / "(empty)"
    matched_phrase: str | None  # which REFUSAL_PHRASES entry fired
    classifier_confidence: str  # "high" / "medium" / "low"


# ---------------------------------------------------------------------------
# Report parsing
# ---------------------------------------------------------------------------


def _load_gold_queries() -> dict[str, str]:
    """Build a dict {case_id: entrada} from the gold set.

    Used to look up the query string for each no_answer case (the per-case
    appendix in reports doesn't include the query directly).
    """
    queries: dict[str, str] = {}
    if not GOLD_SET_PATH.exists():
        return queries
    with GOLD_SET_PATH.open(encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            case = json.loads(stripped)
            cid = case.get("id")
            entrada = case.get("entrada")
            if cid and entrada:
                queries[cid] = entrada
    return queries


def parse_no_answer_cases_from_report(markdown: str, report_file: str) -> list[ReportCase]:
    """Extract no_answer cases from a report's per-case appendix.

    A case is no_answer when emitted=[] AND actual_verdict != expected_verdict.
    """
    gold_queries = _load_gold_queries()
    cases: list[ReportCase] = []
    blocks = _CASE_RE.split(markdown)
    for i in range(1, len(blocks), 2):
        cid = blocks[i]
        body = blocks[i + 1]
        vm = _VERDICT_RE.search(body)
        cm = _CIT_RE.search(body)
        if vm is None or cm is None:
            continue
        actual = vm.group(1)
        expected = vm.group(2)
        emitted = ast.literal_eval(cm.group(1))
        expected_articles = [str(x) for x in ast.literal_eval(cm.group(2))]
        # no_answer = emitted is empty AND verdict mismatch.
        if emitted or actual == expected:
            continue
        cases.append(
            ReportCase(
                report_file=report_file,
                case_id=cid,
                expected_articles=expected_articles,
                expected_verdict=expected,
                actual_verdict=actual,
                # Query lookup may miss for synthetic-test cases not in gold;
                # in real runs all case IDs will be in gold.
                query=gold_queries.get(cid, ""),
            )
        )
    return cases


# ---------------------------------------------------------------------------
# Cache mining
# ---------------------------------------------------------------------------


def load_cache_entries(cache_dir: Path = CACHE_DIR) -> list[CacheEntry]:
    """Load all parseable cache entries with a request.user JSON string.

    Skips entries that don't fit the judge-prompt shape (request.user not a
    parseable JSON object with `query` and `actual_answer` fields).
    """
    entries: list[CacheEntry] = []
    if not cache_dir.exists():
        return entries
    for path in sorted(cache_dir.glob("*.json")):
        try:
            raw = path.read_text(encoding="utf-8")
            outer = json.loads(raw)
            request = outer.get("request", {})
            user = request.get("user")
            if not isinstance(user, str):
                continue
            # Probe: does it look like a judge prompt with our fields?
            parsed = json.loads(user)
            if "query" not in parsed or "actual_answer" not in parsed:
                continue
            entries.append(CacheEntry(path=path.name, request_user_json=user))
        except (json.JSONDecodeError, OSError):
            continue
    return entries


def find_actual_answer_in_cache(query: str, cache_entries: list[CacheEntry]) -> str | None:
    """Return the actual_answer from the first cache entry whose query matches.

    Exact-match on query; returns None if no match.
    """
    if not query:
        return None
    for entry in cache_entries:
        try:
            parsed = json.loads(entry.request_user_json)
        except json.JSONDecodeError:
            continue
        if parsed.get("query") == query:
            return parsed.get("actual_answer")
    return None


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


def _find_refusal_phrase(text: str) -> str | None:
    """Return the first REFUSAL_PHRASES entry that appears in `text`
    (case-insensitive substring match). None if no match.

    Checks longer phrases first to avoid substring collisions
    (e.g., "no respaldada" before "no respalda").
    """
    lower = text.lower()
    # Sort by length descending to match longest (most specific) first
    sorted_phrases = sorted(REFUSAL_PHRASES, key=len, reverse=True)
    for phrase in sorted_phrases:
        if phrase.lower() in lower:
            return phrase
    return None


def classify_no_answer_case(case: ReportCase, cache_entries: list[CacheEntry]) -> NoAnswerDiagnosis:
    """Classify one no_answer case into one of 4 buckets per spec §2 D3."""
    actual_answer = find_actual_answer_in_cache(case.query, cache_entries)

    if actual_answer is None:
        return NoAnswerDiagnosis(
            report_file=case.report_file,
            case_id=case.case_id,
            expected_articles=case.expected_articles,
            expected_verdict=case.expected_verdict,
            actual_verdict=case.actual_verdict,
            classification="analyst_raise",
            actual_answer_snippet="(not in cache)",
            matched_phrase=None,
            classifier_confidence="medium",  # could also be transport_error;
            # cache absence alone can't fully disambiguate.
        )

    if actual_answer == "" or actual_answer == "(backend error)":
        snippet = "(empty)" if actual_answer == "" else "(backend error)"
        return NoAnswerDiagnosis(
            report_file=case.report_file,
            case_id=case.case_id,
            expected_articles=case.expected_articles,
            expected_verdict=case.expected_verdict,
            actual_verdict=case.actual_verdict,
            classification="transport_error",
            actual_answer_snippet=snippet,
            matched_phrase=None,
            classifier_confidence="high",
        )

    phrase = _find_refusal_phrase(actual_answer)
    snippet = actual_answer[:200]
    if phrase is not None:
        return NoAnswerDiagnosis(
            report_file=case.report_file,
            case_id=case.case_id,
            expected_articles=case.expected_articles,
            expected_verdict=case.expected_verdict,
            actual_verdict=case.actual_verdict,
            classification="refusal",
            actual_answer_snippet=snippet,
            matched_phrase=phrase,
            classifier_confidence="high",
        )

    return NoAnswerDiagnosis(
        report_file=case.report_file,
        case_id=case.case_id,
        expected_articles=case.expected_articles,
        expected_verdict=case.expected_verdict,
        actual_verdict=case.actual_verdict,
        classification="other",
        actual_answer_snippet=snippet,
        matched_phrase=None,
        classifier_confidence="low",  # needs manual review.
    )


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _recommend_intervention(counts: dict[str, int]) -> str:
    """5 conditional branches per spec §3 D4. Returns markdown text."""
    total = sum(counts.values())
    if total == 0:
        return (
            "**No no_answer cases found in the 3 canonical reports.** "
            "Either the reports were regenerated since v0.1.16 OR the "
            "classifier is mis-counting. Investigate."
        )
    pct = {k: (v / total * 100) for k, v in counts.items()}
    if pct.get("refusal", 0) > 50:
        return (
            "**Refusal-dominant.** The Analyst is correctly emitting structured "
            "refusals per the v1.1/v1.2/v1.3 hardened Output contract. The "
            "no_answer outcomes are the contract firing as designed. **No v1.4 "
            "prompt intervention warranted.** The residual is upstream: either "
            "retriever did not surface the right chunks (carry to v0.1.18 "
            "citation granularity / HX retriever re-tuning) OR gold case has "
            "wrong ground truth (carry to HX gold-review). Recommended next "
            "microhito: **v0.1.18** (citation granularity confound)."
        )
    if pct.get("analyst_raise", 0) > 30:
        return (
            "**Analyst-raise-dominant.** The existing Analyst retry-once on "
            "findings-missing (analyst.py:118 H8 addition) isn't catching some "
            "failure mode. **Recommended next microhito: v0.1.17.1** — ship "
            "Analyst prompt v1.4 with tighter Output contract phrasing + "
            "consider harness retry-on-RuntimeError hook (eval-side; ADR-0010 "
            "D8 still firm)."
        )
    if pct.get("transport_error", 0) > 30:
        return (
            "**Transport-error-dominant.** The harness `_error_chat_state` "
            "sentinel is firing on intermittent backend exceptions. "
            "**Recommended next microhito: v0.1.17.1** — ship harness "
            "retry-on-transport-error hook (eval-side; no Analyst prompt "
            "change)."
        )
    if pct.get("other", 0) > 30:
        return (
            "**Other-dominant.** The classifier's REFUSAL_PHRASES seed list is "
            "missing common refusal phrasings the Analyst actually emits. "
            "**Recommended next microhito: v0.1.17.1** — expand "
            "REFUSAL_PHRASES from observed `other` cases + re-run the "
            "diagnostic to confirm the residual collapses."
        )
    return (
        "**Mixed distribution** (no single class > 30-50% threshold). "
        "Recommended next microhito: address the dominant class first "
        "(highest count) and document the others as carry-forward. Review "
        "the per-case table to decide priorities."
    )


def render_diagnosis_markdown(results: list[NoAnswerDiagnosis], counts: dict[str, int]) -> str:
    """Produce the docs/no_answer_residual_diagnosis.md content."""
    total = sum(counts.values())
    parts: list[str] = []
    parts.append("# No-Answer residual diagnostic (v0.1.17)")
    parts.append("")
    parts.append(
        "**Status:** $0 cache-mining diagnostic shipped 2026-05-21 (tag "
        "`v0.1.17-no-answer-diagnosis`). Intervention deferred to v0.1.17.1 "
        "or v0.1.18 based on the recommendation below."
    )
    parts.append("")
    parts.append(
        "**TFM dual-target:** disambiguate the no_answer residual (~23% in "
        "H10 baseline; 2/14 in H15 v1.2 holdout) so the intervention "
        "(if any) targets the actual failure mode."
    )
    parts.append("")
    parts.append("---")
    parts.append("")
    parts.append("## Dataset")
    parts.append("")
    parts.append(
        "Three canonical reports mined for no_answer cases (emitted=[] + "
        "verdict mismatch to requires_human_review):"
    )
    parts.append("")
    parts.append(
        "- `evals/reports/latest.md` (H10 frozen @ `0cc9534`, 30 chat baseline, v1.0 prompt)"
    )
    parts.append("- `evals/reports/h15/candidate-v1.2.md` (H15 v1.2 30-case A/B, same gold set)")
    parts.append(
        "- `evals/reports/h15/holdout-v1.2-chat.md` (H15 v1.2 14-case cross-corpus holdout)"
    )
    parts.append("")
    parts.append(
        f"**Classifier version:** v0.1.17 (4 buckets: refusal / analyst_raise / "
        f"transport_error / other). **Total no_answer cases found:** {total}."
    )
    parts.append("")
    parts.append("## Aggregate counts")
    parts.append("")
    parts.append("| Classification | Count | Share |")
    parts.append("|---|---|---|")
    for label in ("refusal", "analyst_raise", "transport_error", "other"):
        n = counts.get(label, 0)
        share = (n / total * 100) if total else 0.0
        parts.append(f"| {label} | {n} | {share:.0f}% |")
    parts.append(f"| **total** | **{total}** | 100% |")
    parts.append("")
    parts.append("## Per-report breakdown")
    parts.append("")
    by_report: dict[str, dict[str, int]] = {}
    for r in results:
        by_report.setdefault(r.report_file, {})
        by_report[r.report_file].setdefault(r.classification, 0)
        by_report[r.report_file][r.classification] += 1
    for report, sub in sorted(by_report.items()):
        report_total = sum(sub.values())
        parts.append(f"### `{report}` ({report_total} no_answer cases)")
        parts.append("")
        for label in ("refusal", "analyst_raise", "transport_error", "other"):
            n = sub.get(label, 0)
            parts.append(f"- {label}: {n}")
        parts.append("")
    parts.append("## Per-case classification table")
    parts.append("")
    parts.append(
        "| Report | Case | Expected verdict | Classification | Matched phrase | "
        "Confidence | Actual answer (first 200 chars) |"
    )
    parts.append("|---|---|---|---|---|---|---|")
    for r in sorted(results, key=lambda x: (x.report_file, x.case_id)):
        phrase = r.matched_phrase or "—"
        snippet = r.actual_answer_snippet.replace("\n", " ").replace("|", "/")
        parts.append(
            f"| {r.report_file} | {r.case_id} | {r.expected_verdict} | "
            f"{r.classification} | {phrase} | {r.classifier_confidence} | "
            f"{snippet} |"
        )
    parts.append("")
    parts.append("## Trajectory analysis")
    parts.append("")
    h10_counts = by_report.get("latest.md", {})
    h15_counts = by_report.get("candidate-v1.2.md", {})
    parts.append("H10 (v1.0 prompt) → H15 v1.2 (hardened Output contract) class shift:")
    parts.append("")
    for label in ("refusal", "analyst_raise", "transport_error", "other"):
        h10 = h10_counts.get(label, 0)
        h15 = h15_counts.get(label, 0)
        parts.append(f"- {label}: H10={h10} → H15 v1.2={h15} (Δ={h15 - h10:+d})")
    parts.append("")
    parts.append(
        "Reading: if Intervention B (hardened Output contract) worked, we "
        "expect `analyst_raise` and `transport_error` to drop from H10 → H15 "
        "v1.2 while `refusal` rises (the model is now correctly emitting "
        "structured refusals instead of raising)."
    )
    parts.append("")
    parts.append("## Recommended intervention")
    parts.append("")
    parts.append(_recommend_intervention(counts))
    parts.append("")
    parts.append("## §22.22 honest caveats")
    parts.append("")
    parts.append(
        "- **Cache-mining is heuristic**: query-match assumes the gold "
        "`entrada` appears exactly in the judge prompt's `query` field. "
        "If H4 reformulated the query before passing to Analyst, the match "
        "would fail and the case would classify as `analyst_raise`."
    )
    parts.append(
        "- **REFUSAL_PHRASES seed list is human-curated**: 22 phrases (16 "
        "ES + 6 EN). False negatives possible (Analyst phrasing not in seed "
        "→ classified as `other`). Expand if `other` count is high."
    )
    parts.append(
        "- **Cache absence ambiguity**: `analyst_raise` and `transport_error` "
        "are indistinguishable when no cache entry exists for the case "
        "(the cache stores judge prompts; if no judge was called, no "
        "cache entry exists regardless of WHY no judge was called)."
    )
    parts.append(
        "- **The 3 reports are the canonical evidence set**; cases not in "
        "these reports are out of v0.1.17 scope. H15.1/H15.2/v0.1.10-v0.1.15 "
        "reports also exist but are not mined here (avoid scope creep)."
    )
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> int:
    all_cases: list[ReportCase] = []
    for report_path in REPORTS_TO_SCAN:
        if not report_path.exists():
            print(f"WARNING: report not found, skipping: {report_path}")
            continue
        md = report_path.read_text(encoding="utf-8")
        cases = parse_no_answer_cases_from_report(md, report_file=report_path.name)
        all_cases.extend(cases)

    cache_entries = load_cache_entries(CACHE_DIR)
    print(f"Loaded {len(cache_entries)} parseable cache entries from {CACHE_DIR}")
    print(f"Found {len(all_cases)} no_answer cases across {len(REPORTS_TO_SCAN)} reports")

    results: list[NoAnswerDiagnosis] = []
    counts: dict[str, int] = {
        "refusal": 0,
        "analyst_raise": 0,
        "transport_error": 0,
        "other": 0,
    }
    for case in all_cases:
        diag = classify_no_answer_case(case, cache_entries)
        results.append(diag)
        counts[diag.classification] += 1

    print("\n## Aggregate counts")
    total = sum(counts.values())
    for label, n in counts.items():
        pct = (n / total * 100) if total else 0.0
        print(f"  {label}: {n}/{total} ({pct:.0f}%)")

    md = render_diagnosis_markdown(results, counts)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(md, encoding="utf-8")
    print(f"\nWrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
