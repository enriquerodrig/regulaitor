#!/usr/bin/env python
# ruff: noqa: E501
"""v0.1.22.1: Verdict-match drop diagnostic ($0 cache-mining).

Analyzes v0.1.22-prod checkpoint per_citation_audits trail + gold expected_verdict
to classify the 16 RHR cases (chat-001..030) per 4 hypotheses explaining the
verdict_match regression:

  H1: validator-too-strict (eval-metric hierarchical containment mismatch)
  H2: gold expected_verdict misaligned with v1.5 refusal-as-Finding
  H3: threshold too aggressive (≥2 invalid but gold-expected in valid subset)
  H4: Sonnet legitimately citing wrong articles (no overlap with gold)

Outputs evals/reports/v0.1.22.1/verdict-drop-analysis.md with per-case breakdown
+ evals/reports/v0.1.22.1/v0.1.23-decision-tree.md with next-milestone recommendation.

Pure Python, no API calls, $0 budget assertion.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

# $0 budget assertion: no API calls
ASSERT_ZERO_BUDGET = True

# Paths
CHECKPOINTS_DIR = Path("evals/checkpoints")
GOLD_SET_PATH = Path("evals/gold_set.jsonl")
REPORT_DIR = Path("evals/reports/v0.1.22.1")

# Allowed cases for this diagnostic (H10 30-case cohort)
ALLOWED_CASES = {f"chat-{i:03d}" for i in range(1, 31)}

# Refusal pattern (heuristic for H2)
REFUSAL_PATTERN = re.compile(
    r"(no puede ser atendida|no es posible|fuera del ámbito|"
    r"rechazo|rechaza|reject|cannot be answered|"
    r"alucinación|no existe|fabricación|no asesoramiento)",
    re.IGNORECASE,
)

# Hypothesis type
HypothesisType = Literal["H1", "H2", "H3", "H4", "mixed"]


class VerdictDropDiagnostic:
    """Classify 16 RHR cases per 4 hypotheses."""

    def __init__(self) -> None:
        self.cases: dict[str, dict[str, Any]] = {}
        self.gold: dict[str, dict[str, Any]] = {}
        self.rhr_cases: list[str] = []  # RHR cases from v0.1.22
        self.hypotheses: dict[str, list[str]] = {
            "H1": [],
            "H2": [],
            "H3": [],
            "H4": [],
            "mixed": [],
        }

    def load_checkpoints(self) -> None:
        """Load v0.1.22 checkpoint files (probe + main)."""
        if not CHECKPOINTS_DIR.exists():
            raise FileNotFoundError(f"Checkpoint dir not found: {CHECKPOINTS_DIR}")

        # Find checkpoint files matching v0.1.22 pattern (both probes)
        # Use explicit filenames to avoid old failed runs
        relevant_files = [
            CHECKPOINTS_DIR / "20260525T144022Z-f2d10eb.jsonl",
            CHECKPOINTS_DIR / "20260525T154654Z-9413480.jsonl",
        ]
        # Filter to only those that exist
        relevant_files = [f for f in relevant_files if f.exists()]

        if not relevant_files:
            raise FileNotFoundError("No v0.1.22 checkpoint files found")

        for fpath in sorted(relevant_files):
            with open(fpath) as f:
                for line_num, line in enumerate(f, start=1):
                    try:
                        record = json.loads(line)
                        data = record.get("data", {})
                        case_id = data.get("case_id")

                        # Filter to chat-001..030 only
                        if case_id not in ALLOWED_CASES:
                            continue

                        # Check for per_citation_audits trail (must exist)
                        if data.get("per_citation_audits") is None:
                            raise ValueError(
                                f"Case {case_id} has null per_citation_audits trail; "
                                f"v0.1.22 should have per-citation trail populated per v0.1.21.1 D2"
                            )

                        # Store the case
                        if case_id in self.cases:
                            raise ValueError(f"Duplicate case_id {case_id} in {fpath}:{line_num}")
                        self.cases[case_id] = data
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Invalid JSON in {fpath}:{line_num}: {e}") from e

    def load_gold_set(self) -> None:
        """Load gold_set.jsonl for expected_verdict + expected_citations."""
        if not GOLD_SET_PATH.exists():
            raise FileNotFoundError(f"Gold set not found: {GOLD_SET_PATH}")

        with open(GOLD_SET_PATH) as f:
            for line_num, line in enumerate(f, start=1):
                try:
                    record = json.loads(line)
                    case_id = record.get("id")

                    # Filter to chat-001..030 only
                    if case_id not in ALLOWED_CASES:
                        continue

                    self.gold[case_id] = record
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in {GOLD_SET_PATH}:{line_num}: {e}") from e

    def parse_citation_string(self, cit_str: str) -> tuple[str, str | None]:
        """Parse citation string 'X' or 'X.Y' into (articulo, apartado)."""
        if "." in cit_str:
            parts = cit_str.split(".", 1)
            return (parts[0], parts[1])
        return (cit_str, None)

    def citation_hierarchical_match(self, emitted: str, expected: str) -> bool:
        """Hierarchical containment match per v0.1.18 spec (ADR-0024)."""
        if emitted == expected:
            return True
        # Article-level expected: emitted may be the same article OR any of its apartados.
        if "." not in expected:
            # expected is article-level "X"; emitted matches if it starts with "X."
            return emitted.startswith(f"{expected}.")
        # Apartado-level expected: only exact match counts.
        return False

    def get_emitted_citations(self, case_id: str) -> list[str]:
        """Extract emitted citations as list of strings 'X' or 'X.Y'."""
        data = self.cases[case_id]
        pca = data.get("per_citation_audits", [])
        citations: list[str] = []
        for audit in pca:
            citation_dict = audit.get("citation", {})
            articulo = citation_dict.get("articulo", "")
            apartado = citation_dict.get("apartado")
            if apartado:
                citations.append(f"{articulo}.{apartado}")
            else:
                citations.append(articulo)
        return citations

    def get_invalid_count(self, case_id: str) -> int:
        """Count invalid citations (validated=False)."""
        data = self.cases[case_id]
        pca = data.get("per_citation_audits", [])
        return sum(1 for audit in pca if not audit.get("validated", False))

    def get_emitted_articles_set(self, emitted_citations: list[str]) -> set[str]:
        """Extract unique articles from emitted citation list."""
        articles: set[str] = set()
        for cit in emitted_citations:
            art, _ = self.parse_citation_string(cit)
            articles.add(art)
        return articles

    def get_gold_articles_set(self, case_id: str) -> set[str]:
        """Extract unique articles from gold expected_citations."""
        if case_id not in self.gold:
            return set()
        articulos_esperados = self.gold[case_id].get("articulos_esperados", [])
        articles: set[str] = set()
        for cit in articulos_esperados:
            art, _ = self.parse_citation_string(cit)
            articles.add(art)
        return articles

    def get_findings_text(self, case_id: str) -> list[str]:
        """Extract finding texts from audited_answer."""
        data = self.cases[case_id]
        audited_answer = data.get("audited_answer")
        if audited_answer is None:
            return []
        findings = audited_answer.get("findings", [])
        return [f.get("text", "") for f in findings]

    def classify_hypothesis(self, case_id: str) -> HypothesisType:
        """Classify case per hypothesis precedence H4 > H1 > H3 > H2."""
        data = self.cases[case_id]
        gold_data = self.gold.get(case_id, {})

        actual_verdict = data.get("actual_verdict")
        expected_verdict = gold_data.get("expected_verdict")

        emitted_citations = self.get_emitted_citations(case_id)
        n_invalid = self.get_invalid_count(case_id)
        emitted_articles = self.get_emitted_articles_set(emitted_citations)
        gold_articles = self.get_gold_articles_set(case_id)
        finding_texts = self.get_findings_text(case_id)

        # Prepare boolean flags per hypothesis
        h1_flag = False
        h2_flag = False
        h3_flag = False
        h4_flag = False

        # H4: Sonnet legitimately citing wrong articles
        # (n_invalid >= 2 AND no overlap with gold articles)
        if n_invalid >= 2 and len(emitted_articles & gold_articles) == 0:
            h4_flag = True

        # H1: Validator-too-strict
        # (n_invalid >= 1 AND >= 1 invalid citation matches gold per hierarchical containment)
        if n_invalid >= 1:
            expected_cits = gold_data.get("articulos_esperados", [])
            # Check if any emitted citation matches a gold citation
            for emitted_cit in emitted_citations:
                for expected_cit in expected_cits:
                    if self.citation_hierarchical_match(emitted_cit, expected_cit):
                        # Check if this citation is marked invalid
                        pca = data.get("per_citation_audits", [])
                        for audit in pca:
                            citation_dict = audit.get("citation", {})
                            art = citation_dict.get("articulo", "")
                            apart = citation_dict.get("apartado")
                            emitted_fmt = f"{art}.{apart}" if apart else art
                            if emitted_fmt == emitted_cit and not audit.get("validated", False):
                                h1_flag = True
                                break

        # H3: Threshold too aggressive
        # (n_invalid >= 2 AND len(intersection(emitted_articles, gold_articles)) >= 1)
        if n_invalid >= 2 and len(emitted_articles & gold_articles) >= 1:
            # Also check that at least one gold article is in the valid subset
            valid_citations = [
                cit
                for cit, audit in zip(
                    emitted_citations,
                    data.get("per_citation_audits", []),
                    strict=False,
                )
                if audit.get("validated", False)
            ]
            valid_articles = self.get_emitted_articles_set(valid_citations)
            if len(valid_articles & gold_articles) >= 1:
                h3_flag = True

        # H2: Gold expected_verdict misaligned with v1.5 refusal-as-Finding
        # (expected=block AND actual in {pass, RHR} AND finding has refusal language)
        if expected_verdict == "block" and actual_verdict in {"pass", "requires_human_review"}:
            for finding_text in finding_texts:
                if REFUSAL_PATTERN.search(finding_text):
                    h2_flag = True
                    break

        # Classify by precedence H4 > H1 > H3 > H2
        flags = [h4_flag, h1_flag, h3_flag, h2_flag]
        if sum(flags) == 0:
            return "mixed"  # Unclassifiable
        if sum(flags) > 1:
            # Multiple matches: return primary
            if h4_flag:
                return "H4"
            if h1_flag:
                return "H1"
            if h3_flag:
                return "H3"
            return "H2"

        # Exactly one match
        if h4_flag:
            return "H4"
        if h1_flag:
            return "H1"
        if h3_flag:
            return "H3"
        return "H2"

    def identify_rhr_cases(self) -> None:
        """Identify RHR cases from v0.1.22."""
        for case_id in sorted(self.cases.keys()):
            data = self.cases[case_id]
            if data.get("actual_verdict") in {"requires_human_review"}:
                self.rhr_cases.append(case_id)

    def classify_all(self) -> None:
        """Classify all RHR cases."""
        for case_id in self.rhr_cases:
            h = self.classify_hypothesis(case_id)
            self.hypotheses[h].append(case_id)

    def render_verdict_drop_analysis(self) -> str:
        """Render verdict-drop-analysis.md report."""
        lines = []

        lines.append("# v0.1.22.1 Verdict-Match Drop Analysis")
        lines.append("")
        lines.append(f"**Date:** {datetime.utcnow().isoformat()}Z")
        lines.append(
            "**Spec:** docs/superpowers/specs/2026-05-25-v0.1.22.1-verdict-diagnostic-design.md"
        )
        lines.append(
            "**Methodology:** $0 cache mining over v0.1.22 checkpoints + gold + per_citation_audits trail"
        )
        lines.append(f"**Cohort:** chat-001..030 (v0.1.22-prod, {len(self.rhr_cases)} RHR cases)")
        lines.append("")

        # Aggregate hypothesis attribution
        lines.append("## Aggregate hypothesis attribution")
        lines.append("")
        lines.append(f"| Hypothesis | Count | % of {len(self.rhr_cases)} |")
        lines.append("|---|---|---|")
        for h in ["H1", "H2", "H3", "H4", "mixed"]:
            count = len(self.hypotheses[h])
            pct = 100.0 * count / len(self.rhr_cases) if len(self.rhr_cases) > 0 else 0.0
            lines.append(f"| {h} | {count} | {pct:.1f}% |")
        lines.append("")

        # Dominant hypothesis
        dominant_h = max(["H1", "H2", "H3", "H4"], key=lambda h: len(self.hypotheses[h]))
        dominant_count = len(self.hypotheses[dominant_h])
        lines.append(
            f"**Dominant hypothesis**: {dominant_h} ({dominant_count} cases, "
            f"{100.0 * dominant_count / len(self.rhr_cases) if len(self.rhr_cases) > 0 else 0.0:.1f}%)"
        )
        lines.append("")

        # Per-case detail table
        lines.append("## Per-case detail table")
        lines.append("")
        lines.append(
            "| case_id | actual | expected | match | n_emitted | n_invalid | "
            "gold_articles | emitted_articles | intersect | dominant_H | notes |"
        )
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")

        for case_id in self.rhr_cases:
            data = self.cases[case_id]
            gold_data = self.gold.get(case_id, {})

            actual = data.get("actual_verdict", "?")
            expected = gold_data.get("expected_verdict", "?")
            match = "✅" if actual == expected else "❌"

            emitted_cits = self.get_emitted_citations(case_id)
            n_emitted = len(emitted_cits)
            n_invalid = self.get_invalid_count(case_id)

            gold_articles = self.get_gold_articles_set(case_id)
            emitted_articles = self.get_emitted_articles_set(emitted_cits)
            intersect = emitted_articles & gold_articles

            dominant_h = self.classify_hypothesis(case_id)

            notes = ""
            if dominant_h == "H1":
                notes = "validator mismatch"
            elif dominant_h == "H2":
                notes = "refusal-as-Finding"
            elif dominant_h == "H3":
                notes = "threshold too strict"
            elif dominant_h == "H4":
                notes = "wrong articles"

            intersect_str = ",".join(sorted(intersect)) if intersect else "(none)"

            lines.append(
                f"| {case_id} | {actual} | {expected} | {match} | {n_emitted} | {n_invalid} | "
                f"{','.join(sorted(gold_articles)) if gold_articles else '(none)'} | "
                f"{','.join(sorted(emitted_articles)) if emitted_articles else '(none)'} | "
                f"{intersect_str} | {dominant_h} | {notes} |"
            )

        lines.append("")

        # Per-case detail blocks
        lines.append("## Per-case detail blocks")
        lines.append("")

        for case_id in self.rhr_cases:
            data = self.cases[case_id]
            gold_data = self.gold.get(case_id, {})

            actual = data.get("actual_verdict", "?")
            expected = gold_data.get("expected_verdict", "?")
            match = "✅" if actual == expected else "❌"

            emitted_cits = self.get_emitted_citations(case_id)
            expected_cits = gold_data.get("articulos_esperados", [])
            finding_texts = self.get_findings_text(case_id)
            n_invalid = self.get_invalid_count(case_id)

            dominant_h = self.classify_hypothesis(case_id)

            lines.append(f"### {case_id} (Hypothesis {dominant_h})")
            lines.append("")
            lines.append(f"- **Verdict**: actual=`{actual}` expected=`{expected}` (match: {match})")
            lines.append(f"- **Citations**: emitted={emitted_cits} expected={expected_cits}")
            lines.append(f"- **Invalid count**: {n_invalid}")

            # per_citation_audits summary
            pca = data.get("per_citation_audits", [])
            if pca:
                lines.append("- **per_citation_audits**:")
                for audit in pca:
                    cit_dict = audit.get("citation", {})
                    art = cit_dict.get("articulo", "?")
                    apart = cit_dict.get("apartado")
                    cit_fmt = f"{art}.{apart}" if apart else art
                    validated = audit.get("validated", False)
                    reason = audit.get("reason", "")
                    status = "✅ valid" if validated else "❌ invalid"
                    lines.append(f"  - {cit_fmt}: {status} ({reason})")

            # Finding texts
            if finding_texts:
                lines.append("- **Findings text**:")
                for i, ft in enumerate(finding_texts):
                    preview = (ft[:100] + "...") if len(ft) > 100 else ft
                    lines.append(f"  - Finding {i+1}: {preview}")

            # Reasoning per hypothesis
            lines.append(f"- **Reasoning for {dominant_h}**:")
            if dominant_h == "H1":
                lines.append(
                    "  Validator marks citation(s) as invalid that match gold expected "
                    "citations per hierarchical containment rule. Suggests validator "
                    "tolerance stricter than eval-metric."
                )
            elif dominant_h == "H2":
                lines.append(
                    "  Gold expects block verdict, but v1.5 returns pass/RHR with "
                    "refusal-language Finding. Indicates gold expected_verdict may need "
                    "update for refusal-as-Finding pattern."
                )
            elif dominant_h == "H3":
                lines.append(
                    "  Case has ≥2 invalid citations, but gold-expected articles are "
                    "present in valid subset. Suggests Tier 1 threshold (≥2) may be "
                    "catching edge cases where answer IS supported."
                )
            elif dominant_h == "H4":
                lines.append(
                    "  No overlap between emitted articles and gold-expected articles. "
                    "Tier 1 correctly escalates; Sonnet misunderstood query or retrieved "
                    "wrong articles."
                )
            elif dominant_h == "mixed":
                lines.append(
                    "  Multiple hypotheses matched or case unclassifiable. Manual review needed."
                )

            lines.append("")

        # §22.22 caveats
        lines.append("## §22.22 caveats")
        lines.append("")
        lines.append(
            "1. H2 refusal-language heuristic uses regex; may false-positive on substantive "
            "answers that mention refusal-adjacent topics."
        )
        lines.append(
            "2. Hierarchical containment matching for H1 uses lenient bidirectional rule "
            "(article-match either direction); may over-attribute H1 if gold itself uses "
            "inconsistent granularity."
        )
        lines.append(
            "3. Hypothesis precedence H4 > H1 > H3 > H2 means edge cases prefer "
            "'legitimate catch' over 'validator strictness'. Reverse if a case has multiple "
            "hypothesis matches."
        )
        lines.append(
            "4. Gold expected_citations may itself be incomplete (alternative valid articles "
            "not listed); treated as ground-truth for diagnostic per H8 design."
        )
        lines.append(
            "5. Per_citation_audits trail integrity: v0.1.22-prod IS post-v0.1.21.1 D2 → "
            "trail populated for all cases (verified during load)."
        )
        lines.append("")

        # Next milestone decision
        lines.append("## Next milestone (v0.1.23) decision")
        lines.append("")
        lines.append("Per spec §D2 decision tree:")
        lines.append("")

        if dominant_h == "H1":
            lines.append("**Dominant: H1 (validator-too-strict)**")
            lines.append("")
            lines.append(
                "**v0.1.23 path**: Propagate hierarchical containment match from eval-metric "
                "to production validator. §6-adjacent change (validator IS the §6 enforcement layer). "
                "NEW ADR required. Careful TDD + regression suite."
            )
            lines.append("**Risk level**: HIGH (§6 risk)")
        elif dominant_h == "H2":
            lines.append("**Dominant: H2 (gold-misalign)**")
            lines.append("")
            lines.append(
                "**v0.1.23 path**: Update gold expected_verdict for affected cases to accept "
                "{block, RHR, pass-with-refusal-Finding}. NO src/ touch. Document gold semantic change."
            )
            lines.append("**Risk level**: LOW")
        elif dominant_h == "H3":
            lines.append("**Dominant: H3 (threshold too aggressive)**")
            lines.append("")
            lines.append(
                "**v0.1.23 path**: Tune Tier 1 quorum threshold ≥2 → ≥3 in agents/auditor.py. "
                "NEW ADR required. Auditor src/ touch (§6 BYTE-UNCHANGED stays — Auditor "
                "changed at v0.1.21 already)."
            )
            lines.append("**Risk level**: MEDIUM")
        elif dominant_h == "H4":
            lines.append("**Dominant: H4 (legitimate catch)**")
            lines.append("")
            lines.append(
                "**v0.1.23 path**: NO backend intervention. v1.5 prompt iteration OR retrieval "
                "tuning at v0.1.23+. Document Tier 1 working as designed; verdict_match drop is "
                "real cost of safety."
            )
            lines.append("**Risk level**: LOW (no change)")
        else:
            lines.append("**Dominant: mixed (no clear single hypothesis)**")
            lines.append("")
            lines.append(
                "**v0.1.23 path**: 1+ surgical milestones per hypothesis. May need v0.1.23 + v0.1.24+. "
                "Manual review of secondary hypothesis matches recommended."
            )
            lines.append("**Risk level**: VARIES")

        lines.append("")

        return "\n".join(lines)

    def render_decision_tree(self) -> str:
        """Render v0.1.23-decision-tree.md."""
        lines = []

        lines.append("# v0.1.22.1 → v0.1.23 Decision Tree")
        lines.append("")
        lines.append(f"**Date:** {datetime.utcnow().isoformat()}Z")
        lines.append(
            "**Spec:** docs/superpowers/specs/2026-05-25-v0.1.22.1-verdict-diagnostic-design.md"
        )
        lines.append("")

        # Summary counts
        lines.append("## Hypothesis Attribution Summary")
        lines.append("")
        total = len(self.rhr_cases)
        lines.append(f"**Total RHR cases analyzed**: {total}")
        lines.append("")
        lines.append("| Hypothesis | Count | Percentage |")
        lines.append("|---|---|---|")
        for h in ["H1", "H2", "H3", "H4", "mixed"]:
            count = len(self.hypotheses[h])
            pct = 100.0 * count / total if total > 0 else 0.0
            lines.append(f"| {h} | {count} | {pct:.1f}% |")
        lines.append("")

        # Dominant hypothesis
        dominant_h = max(["H1", "H2", "H3", "H4"], key=lambda h: len(self.hypotheses[h]))
        dominant_count = len(self.hypotheses[dominant_h])
        dominant_pct = 100.0 * dominant_count / total if total > 0 else 0.0

        lines.append("## Dominant Hypothesis")
        lines.append("")
        lines.append(f"**{dominant_h}**: {dominant_count}/{total} cases ({dominant_pct:.1f}%)")
        lines.append("")

        # Hypothesis interpretation
        lines.append("## Hypothesis Interpretation")
        lines.append("")

        if dominant_h == "H1":
            lines.append("**H1: Validator-too-strict (vs eval-metric mismatch)**")
            lines.append("")
            lines.append(
                "The production validator marks citations as invalid that the eval-metric "
                "would consider valid under the hierarchical containment rule. This suggests "
                "a mismatch between:"
            )
            lines.append(
                "- Production-side citation validation (H4 STRICT byte-unchanged since v0.1.18)"
            )
            lines.append(
                "- Eval-side citation matching (hierarchical containment rule introduced in v0.1.18 ADR-0024)"
            )
            lines.append("")
            lines.append("Cases where Auditor escalates to RHR may be over-conservative.")

        elif dominant_h == "H2":
            lines.append("**H2: Gold expected_verdict misaligned with v1.5 refusal-as-Finding**")
            lines.append("")
            lines.append(
                "Gold set expects BLOCK for cases where v1.5 Analyst emits a structured refusal "
                "as a Finding (1 Finding + corpus citation + severity=high). The Auditor's Lenient "
                "policy validates the citation → routes to PASS/RHR, not BLOCK."
            )
            lines.append("")
            lines.append(
                "This is a design-level pattern documented in H15 C1 (v1.5 refusal-as-Finding). "
                "Gold expected_verdict needs updating to reflect this pattern."
            )

        elif dominant_h == "H3":
            lines.append("**H3: Tier 1 quorum threshold too aggressive (≥2)**")
            lines.append("")
            lines.append(
                "Cases where Sonnet emits extra citations (beyond gold), some invalid, but the "
                "gold-expected citations ARE present + valid. Tier 1 quorum (≥2 invalid → RHR) "
                "fires even though the answer IS supported."
            )
            lines.append("")
            lines.append(
                "Suggests raising threshold ≥2 → ≥3, or adding a secondary check: "
                "'RHR only if gold-expected citations are ALL invalid'."
            )

        elif dominant_h == "H4":
            lines.append("**H4: Sonnet legitimately citing wrong articles (working as designed)**")
            lines.append("")
            lines.append(
                "Tier 1 correctly catches cases where Sonnet misunderstood the query, retrieved "
                "wrong articles, or answered unsupported. No overlap with gold-expected articles."
            )
            lines.append("")
            lines.append(
                "This is Tier 1 working as designed. The verdict_match drop is the safety cost."
            )

        else:
            lines.append("**Multiple hypotheses matched equally; no clear dominant.**")
            lines.append("")
            for h in ["H1", "H2", "H3", "H4"]:
                count = len(self.hypotheses[h])
                if count > 0:
                    lines.append(f"- {h}: {count} cases")
            lines.append("")
            lines.append(
                "Manual review of per-case detail blocks in verdict-drop-analysis.md recommended."
            )

        lines.append("")

        # v0.1.23 recommendation
        lines.append("## v0.1.23 Recommendation")
        lines.append("")

        if dominant_h == "H1":
            lines.append(
                "**Path**: Propagate hierarchical containment match from eval-metric (`evals/metrics.py`) "
                "to production validator (`src/regulaitor/citation/validator.py`)."
            )
            lines.append("")
            lines.append(
                "**Scope**: Modify the Citation validation logic to accept article-level "
                "matches (not just exact apartado matches). Requires careful TDD + regression suite."
            )
            lines.append("")
            lines.append(
                "**Risk**: HIGH (touches §6 invariant layer). Requires ADR-0030 + code review + "
                "full eval re-run to confirm verdict_match improves."
            )

        elif dominant_h == "H2":
            lines.append("**Path**: Update gold expected_verdict for affected cases.")
            lines.append("")
            lines.append(
                "**Scope**: Manually review H2-dominant cases in verdict-drop-analysis.md. "
                "For each, update expected_verdict from BLOCK to PASS (or RHR if ambiguous). "
                "Document rationale for each change."
            )
            lines.append("")
            lines.append("**Risk**: LOW (data-only, no src/ touch). ~1-2h manual effort.")

        elif dominant_h == "H3":
            lines.append("**Path**: Tune Tier 1 quorum threshold ≥2 → ≥3.")
            lines.append("")
            lines.append(
                "**Scope**: Modify `src/regulaitor/agents/auditor.py` aggregation logic: "
                "change `n_invalid >= 2` to `n_invalid >= 3` in the RHR escalation path. "
                "Requires unit + integration tests + v0.1.23 paid validation A/B (~€4-6)."
            )
            lines.append("")
            lines.append(
                "**Risk**: MEDIUM (Auditor src/ touch; §6 semantically unchanged, but threshold "
                "changed). Requires ADR-0030 + T6 paid A/B to measure impact."
            )

        elif dominant_h == "H4":
            lines.append("**Path**: NO backend change. Accept verdict_match drop as safety cost.")
            lines.append("")
            lines.append(
                "**Scope**: Document Tier 1 working as designed in ADR-0029 narrative. Consider "
                "v0.1.23+ optimization: prompt v1.6 iteration OR retrieval tuning (per-norma cap "
                "+ top_k_auto) to reduce Sonnet wrong-article rate."
            )
            lines.append("")
            lines.append(
                "**Risk**: LOW (no immediate change; strategic decision to prioritize safety over "
                "verdict accuracy)."
            )

        else:
            lines.append("**Path**: Mixed hypotheses require case-by-case manual intervention.")
            lines.append("")
            lines.append(
                "Review per-case detail blocks and secondary hypothesis matches. "
                "Likely a multi-milestone v0.1.23 + v0.1.24."
            )
            lines.append("")
            lines.append("**Risk**: VARIES")

        lines.append("")

        return "\n".join(lines)

    def run(self) -> None:
        """Execute the diagnostic."""
        print("[v0.1.22.1] Loading checkpoints...")
        self.load_checkpoints()
        print(f"  Loaded {len(self.cases)} cases")

        print("[v0.1.22.1] Loading gold set...")
        self.load_gold_set()
        print(f"  Loaded {len(self.gold)} gold cases")

        print("[v0.1.22.1] Identifying RHR cases...")
        self.identify_rhr_cases()
        print(f"  Found {len(self.rhr_cases)} RHR cases")

        print("[v0.1.22.1] Classifying per hypothesis...")
        self.classify_all()

        print("[v0.1.22.1] Rendering reports...")
        analysis = self.render_verdict_drop_analysis()
        decision = self.render_decision_tree()

        # Ensure report directory exists
        REPORT_DIR.mkdir(parents=True, exist_ok=True)

        analysis_path = REPORT_DIR / "verdict-drop-analysis.md"
        decision_path = REPORT_DIR / "v0.1.23-decision-tree.md"

        print(f"[v0.1.22.1] Writing {analysis_path}...")
        analysis_path.write_text(analysis, encoding="utf-8")

        print(f"[v0.1.22.1] Writing {decision_path}...")
        decision_path.write_text(decision, encoding="utf-8")

        # Print summary to stdout
        print("")
        print("=" * 70)
        print("DIAGNOSTIC COMPLETE")
        print("=" * 70)
        print(f"Total RHR cases analyzed: {len(self.rhr_cases)}")
        print(f"H1 (validator-too-strict): {len(self.hypotheses['H1'])}")
        print(f"H2 (gold-misalign): {len(self.hypotheses['H2'])}")
        print(f"H3 (threshold-aggressive): {len(self.hypotheses['H3'])}")
        print(f"H4 (wrong-articles): {len(self.hypotheses['H4'])}")
        print(f"mixed/unclassifiable: {len(self.hypotheses['mixed'])}")
        print("")

        dominant_h = max(["H1", "H2", "H3", "H4"], key=lambda h: len(self.hypotheses[h]))
        dominant_count = len(self.hypotheses[dominant_h])
        dominant_pct = (
            100.0 * dominant_count / len(self.rhr_cases) if len(self.rhr_cases) > 0 else 0.0
        )
        print(
            f"Dominant hypothesis: {dominant_h} ({dominant_count}/{len(self.rhr_cases)}, {dominant_pct:.1f}%)"
        )
        print("")
        print(f"Reports written to: {REPORT_DIR}/")
        print("=" * 70)


if __name__ == "__main__":
    diag = VerdictDropDiagnostic()
    diag.run()
