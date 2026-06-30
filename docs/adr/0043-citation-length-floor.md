# ADR 0043 — Citation minimum-length floor (§6 Check 3 strict-tightening, HX pre-pilot)

- **Status:** Accepted
- **Date:** 2026-06-30 (decision + implemented).
- **Deciders:** Project owner (founder).
- **Companion ADRs:** 0024 (hierarchical-containment eval metric — the precision
  concept), 0031 (`failed_check` observability field this reuses), 0032 (the
  three-layer §6 architecture this tightens at Layer (a)). Lineage: the v0.1.32-post
  whitespace-only tightening (same "strictly tighten, never loosen" pattern).

## Context

The pre-pilot read-only audit (sec6-01) found that `citation/validator.py` Check 3
is a bare normalized-substring test — `citation_norm in target_norm`. A citation
whose text is a trivial token (e.g. the stopword `"el"`, or `"de"`, `"a"`, `"ia"`)
is a substring of nearly every corpus article, so it validates `True` with **zero
evidentiary content**. Via the Auditor's Finding-Lenient rule one trivially-valid
citation makes a whole Finding PASS. This directly undercuts the product's headline
"auditable, supported citations" differentiator.

Fabrication was **never** at risk: Checks 1/2 still require the article and apartado
to genuinely exist, so the gap is a **precision** gap (weak-but-real citations
pass), not a fabrication hole. v0.1.32-post shipped a pin test documenting the gap;
this ADR closes it.

## Decision

### D1 — A normalized-length floor in Check 3, with a DISTINCT failed_check
`validate()` rejects a citation whose normalized text is shorter than
`_MIN_CITATION_CHARS = 20`, returning `validated=False, failed_check=4` **before**
the substring test, in `validator.py` only — mirroring the existing
`len(citation_norm) == 0` block from v0.1.32-post — NOT as a `Citation.text` schema
field validator. `AuditResult.failed_check` (`citation/schemas.py`) is extended
`Literal[1, 2, 3] | None` → `Literal[1, 2, 3, 4] | None` (additive).

**Why `failed_check=4`, not 3 (the headline of this ADR):** a too-short citation is
a NON-citation, not a paraphrase. The Auditor's paraphrase-routing helper
`_all_blocked_findings_paraphrase_only` (`auditor.py`) softens an all-blocked /
partial-Findings turn to PASS **only when every invalid citation has
`failed_check == 3`** (v0.1.25/v0.1.29). Had the floor reused `failed_check=3`, a
trivial-citation Finding would have been softened straight back to PASS — the floor
would have closed the gap at the validator layer but the turn verdict would not
change (PASS → PASS). Emitting `4` makes the helper's existing `!= 3` guard route a
too-short-only Finding to **BLOCK/RHR**, so the floor closes the gap at the TURN
level. **`auditor.py` is BYTE-UNCHANGED** — the distinct value flows through its
existing logic to the correct strict routing.

**Why validator.py, not the schema:** a schema field validator would reject at
construction, breaking the many tests (and the Analyst emit path) that legitimately
build short-text `Citation` objects expected to be marked *invalid* by the
validator. Putting the floor in `validate()` keeps the rejection at the validation
layer where it belongs, exactly like the whitespace block.

### D2 — The floor value is empirically calibrated (=20), not guessed
Two $0 measurements set the value with a wide safety margin:

- **429 validated citations** mined from the per-citation audit trail of paid runs
  (v0.1.21.1 D2): the **shortest was 53 normalized chars**; p5 = 113; median = 338.
- **4820 corpus text segments** (`corpus/processed/`): the **shortest citable
  segment is 42 normalized chars**; none below 30.

20 sits below **both** the shortest real citation (53) and the shortest citable
corpus segment (42). Reproduce with
`uv run python scripts/sec6_citation_floor_calibration.py` ($0, offline).

**Safety basis (corrected per §6 review — no "by construction" overclaim).** Check 3
is a *substring* test, so a real citation can be a **partial quote** shorter than the
42-char segment it quotes; the "20 < 42" bound therefore does NOT prove no legit
citation is rejected. The actual basis is empirical + directional: the floor rejected
**zero of the 429 observed validated citations** (the shortest was 53, a 2.6× margin),
and even if an unobserved legitimate partial quote < 20 chars existed, rejecting it is
**§6-safe** (see D4). It rejects the entire trivial/short-phrase band (≤19 chars),
closing the documented `"el"`-style gap.

### D3 — §6 invariant interpretation: a strict-tightening of Layer (a)
This is the **first change to `citation/validator.py` decision logic** since H4
(prior changes — ADR-0031's `failed_check`, v0.1.32-post's whitespace block — were
additive observability or empty-input guards). The §6 statement evolves as a
**strict-tightening, never a loosening**:

1. The floor can only make a citation **invalid** that was previously valid; it can
   never make an invalid citation valid. (Monotonic in the safe direction.)
2. Fabrication detection (Checks 1/2 — article/apartado existence) is **untouched**;
   the fabrication chain is unbroken by construction.
3. The §6 enforcement boundary ("no citation, no answer") is **strengthened**: a
   class of zero-evidence citations that previously passed now fails.
4. `auditor.py` is **byte-unchanged**. The rejection originates in the per-citation
   validator (Layer (a)); the distinct `failed_check=4` then flows through the
   Auditor's existing `!= 3` paraphrase guard (Layer (c)) — unmodified — so a
   too-short-only Finding routes to BLOCK/RHR. Layers (b)/(d) are untouched.

### D4 — Measurement honesty (§22.22)
- The calibration cohort (429 citations) is the gold-set-driven paid runs, not the
  universe of real queries. A real-world citation shorter than 20 chars would have to
  be a partial quote of less than ~half the shortest corpus segment; possible in
  principle, but (a) not observed in 429 samples and (b) **§6-safe even if it
  occurred**. The worst case is **the same strict turn-level routing the Auditor
  already applies to any non-paraphrase invalid citation — BLOCK/RHR, never a
  fabrication-pass** (the `failed_check=4` value is what guarantees the strict
  route; this is the corrected D4 framing per the §6 review, replacing an earlier
  draft that mis-stated the routing). The floor sits 2.6× below the observed minimum
  to make even this conservative over-rejection near-impossible.
- The floor (20 chars) closes the trivial-token and short-phrase band but is **not**
  a semantic claim-support (entailment) check — a citation of ≥20 chars that is real
  but does not *support* the Finding still passes Check 3. That boundary is documented
  in `model_card.md §8.1` (sec6-02) and remains covered by the Analyst prompt +
  advisory Council + Ragas faithfulness, not a hard gate. A semantic NLI gate is HX
  carry-forward, out of scope pre-pilot.
- No paid run was needed to ship this: the change is a conservative strict-tightening
  and the calibration is $0. An end-to-end paid confirmation of the verdict-level
  effect on the H10 cohort is available as an optional follow-up but is not required
  for safety.

## Consequences

- **Positive:** the headline §6 differentiator no longer accepts zero-content
  citations; the precision gap documented since v0.1.32-post is closed; the fix is
  $0, calibrated, and reversible (one constant).
- **Negative / residual:** two existing `test_validator.py` regression tests used
  unrealistically-short synthetic citation text and were updated to ≥20-char
  passages (they now exercise their intended substring-scoping logic rather than the
  floor). The floor does not address the claim-support boundary (sec6-02); that
  stays documented, not gated.
- **Reversibility:** revert is a one-constant / one-block change; `failed_check=3`
  keeps the rejection observable in the audit trail.

## Alternatives considered

- **Schema field validator on `Citation.text`** — rejected (D1): too disruptive to
  the construction path and the test suite; the validation layer is the correct home.
- **Higher floor (≥40)** — rejected: closer to the shortest citable segment (42),
  shrinking the safety margin for no additional benefit on the observed cohort.
- **Word-count / stopword-list floor** — rejected: language-specific and brittle; a
  normalized-char floor calibrated against real data is simpler and provably safe.
- **Semantic entailment (NLI) gate for claim-support** — deferred to HX (sec6-02
  do-not-do): disproportionate pre-pilot, and orthogonal to this precision fix.
