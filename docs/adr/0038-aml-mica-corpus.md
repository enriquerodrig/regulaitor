# ADR 0038 — AML / MiCA / TFR Corpus Expansion (Fase 6, HX)

- **Status:** Accepted
- **Date:** 2026-06-11 (decision + implemented).
- **Deciders:** Project owner (founder).
- **Companion ADRs:** 0015 (NIS2+DORA add-a-norma precedent), 0036 (DORA RTS — same
  HTML/Playwright fetch path), 0037 (corpus registry — makes the code-add trivial).

## Context

HX founder constraint #2 ("expand the corpus, ranked by buyer willingness-to-pay").
A `$0` scoping pass (workflow `wf_9d1b0e7a-648`, 10 agents, research→adversarial-verify,
5/5 CELEX verified high-confidence) sized + WTP-ranked the EU financial-crime + crypto
candidate acts for the bullseye (fintech / banking / crypto compliance in EU PYME /
mid-market). Five candidates were assessed:

| Act | CELEX | Arts | WTP | Verdict |
|---|---|---|---|---|
| AMLR — single rulebook Reg (EU) 2024/1624 | 32024R1624 | 90 | **high** | **ingest** |
| MiCA — Reg (EU) 2023/1114 | 32023R1114 | 149 | **high** | **ingest** |
| TFR — crypto travel rule Reg (EU) 2023/1113 | 32023R1113 | 40 | **high** | **ingest** |
| AMLD6 — Dir (EU) 2024/1640 | 32024L1640 | ~80 | medium | defer |
| AMLAR — AMLA Reg (EU) 2024/1620 | 32024R1620 | ~107 | low | defer |

## Decision

Ingest the **three high-WTP acts** as three new normas:
- **`amlr`** (`32024R1624`, OJ 2024-06-19, 90 articles) — the directly-applicable AML
  single rulebook: customer due diligence (Art. 20), beneficial ownership (Art. 51),
  suspicious-transaction reporting (Art. 69), record-keeping (Art. 77). Binds every
  obliged entity (banks, EMIs, payment institutions, CASPs, DNFBPs). Applies 2027 →
  active pre-compliance market window now.
- **`mica`** (`32023R1114`, OJ 2023-06-09, 149 articles) — Markets in Crypto-Assets:
  CASP authorisation/obligations (Art. 59 ff.), ART/EMT (stablecoin) issuers, white
  papers (Title II), market abuse (Title VI). Applies since Dec 2024.
- **`tfr`** (`32023R1113`, OJ 2023-06-09, 40 articles) — the crypto "travel rule":
  originator/beneficiary information accompanying crypto transfers (Art. 14 ff.). Daily
  operational obligation for every CASP; pairs with MiCA.

**Deferred** (documented, not ingested): AMLD6 (a Directive — transposed nationally, so
less directly citable; entity-level obligations live in AMLR) and AMLAR (institutional —
establishes AMLA; hard obligations bind only ~40 large entities under direct supervision,
not the PYME bullseye). Both can be added later in two edits each (the registry).

### Add-a-norma cost (validates ADR-0037)

Adding three normas was **three registry entries + two Literal edits** (`Norma` +
`CorpusSelector` in `schemas.py`) — NOT the ~15-site sweep ADR-0036 paid. Every other
enumeration (CELEX/VERSION/article-counts/chip-style/CLI choices/API guard/UI lists)
derived automatically; the consistency test confirmed no desync. The ADR-0037 refactor
paid for itself on its first real use.

### Source / format

Raw HTML captured via Playwright (EUR-Lex WAF blocks programmatic fetch; ADR-0003/0015/0036
lineage), saved verbatim to `corpus/raw/{amlr,mica,tfr}_{es,en}.html`. **Finding:** EUR-Lex
renders BOTH the 2024 acts and the 2023 acts (MiCA/TFR) with the **same `oj-sti-art` /
`oj-normal` HTML vocabulary** — the OJ *numbering* changed in 2024 (`L_2024/...`) but the
HTML *class* vocabulary did not, so the `html_parser` (Fase 3) handles all three with zero
changes. Article counts validated at ingest: 90/90 + 149/149 + 40/40 coverage_ok, ES+EN.

### Gold + §6

One gold case per norma (`amlr-001` CDD → Art. 20; `mica-001` CASP authorisation → Art. 59;
`tfr-001` travel rule → Art. 14). §6 `citation/validator.py` + `agents/auditor.py`
BYTE-UNCHANGED; the new corpora validate through the same path; the existing 6 normas are
regression-zero (additive index).

## §22.22 disclosures

1. **WTP-ranked partial, not the whole package** (honest scope): AMLD6 + AMLAR deferred as
   medium/low value for the bullseye; the AML obligation surface that drives buyer WTP is
   the directly-applicable AMLR, ingested. A "machinery vs entity-obligation" disambiguation
   (AMLD6) is a documented future add.
2. **Empirical Analyst behaviour NOT measured here ($0 milestone):** that the Analyst emits
   correct, validated citations for the 3 gold cases is a paid-LLM measurement, deferred to
   the next paid eval bundle. Retrieval + validator + schema are verified.
3. **Article-level granularity** (inherited from the HTML parser, ADR-0036 D3): apartado-level
   citations are not available for these corpora.
4. **Application-date nuance — UNMITIGATED open limitation (review F1/F2):** AMLR applies
   from 10 July 2027 (its Art. 90); MiCA/TFR are already in force. The corpus stores the
   base-act text with NO per-corpus in-force metadata, no prompt instruction, and no UI
   signal distinguishing forthcoming from in-force acts — so the system can present AMLR
   obligations in the present tense without flagging the 2027 application date (the gold case
   `amlr-001` rewards present-tense language, matching the 68-case convention). The generic
   "no sustituye asesoría jurídica" disclaimer does NOT cover this specific date-applicability
   risk — do not credit it with mitigating it. A per-corpus applies-from flag surfaced in the
   answer is documented future work. (The date itself IS in the corpus: AMLR Art. 90.)
5. **AMLR Art. 51 ES data blemish (review DATA-1):** the captured EUR-Lex HTML for AMLR
   Art. 51(1) ES reads "participación den la propiedad" — apparently a source typo for "en"
   (the same article's clause (b) reads "en"; the EN parallel reads "ownership interest").
   The corpus stores the **verbatim capture** (faithfulness over silent source-correction; the
   §6 validator uses the corpus as the authority per §22.15, and the Analyst quotes the corpus
   verbatim, so its citations still validate). Consequence: an EXTERNAL citation of the
   grammatically-corrected wording would false-negative on validator Check 3 — a fail-safe
   direction (a legitimate citation over-rejected, never a fabrication accepted). Isolated
   (1 clause of 279 articles; the other corpus "den" tokens are legitimate subjunctives of
   "dar"). Flagged as a known data-quality limitation rather than edited.

## Alternatives considered

- **MiCA + TFR only (crypto pair)** — rejected: narrower (crypto firms only); omits the AML
  core that binds every regulated financial entity.
- **Full AML package + crypto (all 5)** — rejected: AMLAR is institutional (low WTP) and
  AMLD6 is a transposed Directive (medium); ~466 articles for marginal citable value.
- **PDF fetch (like the original 4 corpora)** — unnecessary: the HTML `oj-*` path is proven
  and gives cleaner article structure than PDF.
