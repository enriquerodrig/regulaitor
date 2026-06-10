# ADR 0037 — Corpus registry: single source of truth for per-norma config (HX)

- **Status:** Accepted
- **Date:** 2026-06-10 (decision + implemented).
- **Deciders:** Project owner (founder).
- **Companion ADRs:** 0015 (NIS2+DORA — first "add-a-norma" pain), 0036 (DORA RTS
  — flagged the closed-Literal cost + caught a missed enumeration site in review).

## Context

Adding a corpus to RegulAItor meant editing ~15 hardcoded enumeration sites (the
closed `Norma = Literal[...]` model). ADR-0036's adversarial review empirically
proved the miss-risk: `scripts/analyze.py`'s `_VALID_CORPUS` and
`GoldCaseDoc.corpus_esperado` were both forgotten when the DORA RTS normas were
added. HX founder constraint #2 ("expand the corpus") guarantees this keeps
recurring, so the duplication was rewired to a single source of truth.

**Why not "derived from manifests" (the original framing):** the manifests are
the *output* of ingest. `celex`, `version`, and `expected_articles` are *inputs*
needed BEFORE the manifest exists (to fetch/pin/validate) — they cannot derive
from manifests (circular). And `label`/`color` are human-curated. So the single
source must be a *declared* registry, not a manifest-derived one.

**Why the `Norma` Literal stays static:** a `Literal` is a compile-time type
consumed by mypy + Pydantic (it constrains `Citation.norma` — §6-adjacent). It
cannot be generated from runtime data without losing that static safety (a typo
in `Citation.norma="ai_cat"` would no longer be caught). Making `Norma = str` was
rejected for exactly this reason.

## Decision

`src/regulaitor/corpus/registry.py` holds one `CorpusSpec` per norma
(`celex`, `version`, `expected_articles`, `label`, `color`) in `CORPUS_REGISTRY:
dict[Norma, CorpusSpec]`, plus the canonical `ALL_NORMAS = tuple(CORPUS_REGISTRY)`.

Every prior enumeration now DERIVES from it:
- `corpus/_targets.py::ALL_NORMAS` — re-exports the registry's tuple.
- `corpus/loader.py::CORPORA_WITH_MANIFESTS` = `ALL_NORMAS`.
- `corpus/validate.py::EXPECTED_ARTICLE_COUNTS` = `{n: s.expected_articles ...}`.
- `corpus/ingest.py::CELEX` / `VERSION` = `{n: s.celex ...}` / `{n: s.version ...}`.
- `ui_streamlit/_render.py::_NORMA_STYLE` = `{n: (s.label, s.color) ...}`.
- `scripts/{ingest,rag_build}.py` `--corpus` choices = `[*ALL_NORMAS, "all"]`.
- `api/routes_analyze.py` corpus guard = `c in ALL_NORMAS`.
- `ui_streamlit/{tab_ask,tab_analyze}.py::_CORPUS_CHOICES` derive from `ALL_NORMAS`.
- `api/schemas.py::AskRequest.corpus` = the canonical `CorpusSelector` (no re-list).

The `Norma` + `CorpusSelector` Literals (`schemas.py`) stay manual (a `Literal`
cannot be composed from another at the type level). A consistency test
(`tests/unit/corpus/test_registry_consistency.py`) asserts
`set(get_args(Norma)) == set(CORPUS_REGISTRY)` and
`set(get_args(CorpusSelector)) == set(get_args(Norma)) | {"auto"}` — so a desync
is impossible. **Adding a corpus is now three edits in two files** (the `Norma`
Literal + the `CorpusSelector` Literal in `schemas.py`, + one `CORPUS_REGISTRY`
entry in `registry.py`); the consistency test makes any forgotten one a hard,
clearly-asserted CI failure rather than a silent escape.

## Consequences

- The ~15-site closed-Literal cost collapses to three edits in two files + a test
  that makes the miss-risk (ADR-0036's empirical defect) structurally impossible.
- §6 untouched: the `Norma` type is byte-identical; `citation/validator.py` +
  `agents/auditor.py` byte-unchanged. The refactor only re-sources runtime data.
- Regression-zero: 6 regression tests pin that every derived value
  (CELEX/VERSION/article-counts/chip-style) equals what it replaced.

## §22.22 disclosures

1. **Not fully manifest-derived** (honest reframe of the request): ingest inputs
   (celex/version/counts) + display fields (label/color) are *declared* in the
   registry, not derived from manifests — by necessity (circularity + human curation).
2. **Two Literals stay manual** — a `Literal` cannot be generated from runtime
   data; the consistency test is the mechanism that makes the three edits safe,
   not full automation. One edit (the registry) drives derivation; the other two
   (`Norma` + `CorpusSelector` in `schemas.py`) are enforced-consistent by the test
   (forget either and the gate fails loudly — not a silent escape).
3. **Layering note:** UI chip `label`/`color` live in a corpus-domain registry.
   This couples display data to the domain config for the sake of single-source;
   judged worth it (per-norma display is human-curated and would otherwise be the
   one remaining duplicate site).
4. **Supersedes ADR-0015 D2's `CORPORA_WITH_MANIFESTS` seam (honest reversal):**
   `loader.py::CORPORA_WITH_MANIFESTS` is now `= ALL_NORMAS`. ADR-0015 listed this
   exact alias under "Alternatives considered" and *rejected* it, to keep an
   "honest-partial" seam (declare a norma in `ALL_NORMAS` before its manifest
   exists). That seam was never exercised — every norma has always been registered
   together with its manifest. This refactor deliberately collapses it for the
   single-source-of-truth gain; the new (mild) constraint is **register a corpus
   together with its manifest** (warmup now requires every `ALL_NORMAS` member to
   have a manifest; `test_h14_corpus_widening` still grounds the set against disk).
   ADR-0015's blessed "even better" fix — deriving the set from the on-disk
   manifests — remains deferred (it would need lazy/CWD-robust evaluation rather
   than an import-time scan). The v1.0.0 memoria + `evidence_matrix` describe the
   pre-HX separated state and are historically accurate for that tag.

## Alternatives considered

- **`Norma = str` + pure runtime validation** — rejected: loses mypy/Pydantic
  static checking of corpus values (the §6-adjacent `Citation.norma` guard).
- **Keep the 15 sites, add only the missing guard tests** — rejected: treats the
  symptom (missed sites) not the cause (duplication); cost recurs every corpus.
- **Manifest-derived registry** — rejected: celex/version/counts are ingest
  inputs that predate the manifest (circular); label/color aren't in manifests.
