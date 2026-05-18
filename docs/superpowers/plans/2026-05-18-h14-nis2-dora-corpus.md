# H14 — NIS2 + DORA Corpus Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the NIS2 + DORA consolidated corpora (ES+EN, PDF, mirroring ADR-0003) so all 4 corpora are retrievable end-to-end, add gold-set cases, and verify $0-deterministically — AI Act + RGPD strictly regression-zero (§22.18), honest documented per-corpus partial if a corpus PDF intractably resists.

**Architecture:** Approach 1 — per-corpus `rag-ingest` vertical slices (NIS2, DORA) then one shared integration step (widen the 9 hardcoded 2-value spots → canonical `Norma`, rebuild LanceDB, gold cases, $0 verification, closure). Backend H1–H3/Analyst/Auditor/graphs read-only; only corpus-ingest constants + input-validation literals + gold set + the existing corpus-agnostic LanceDB rebuild are touched.

**Tech Stack:** Python 3.11, `uv`, the H1 corpus pipeline (`corpus/{ingest,pdf_parser,validate,loader}.py`), LanceDB + BGE-M3 (H2 `rag_build`, corpus-agnostic), pytest, Git-LFS.

**Conventions (all tasks):** TDD. `from __future__ import annotations` in new modules. Run tests `python -m pytest`. Commit `SKIP=gitleaks git commit` (gitleaks CI-enforced; **never** `--no-verify`). Conventional messages, **no AI/Co-Authored footer**. Branch `feat/h14-nis2-dora-corpus` (spec `830b753`, on `main` `c25e0d2`). **H14 spends $0** — no paid LLM run; EUR-Lex fetch is network/$0, rebuild is local BGE-M3/$0. The `rag-ingest` SKILL.md is Formex-centric but the corpora are PDF (ADR 0003) — follow the **proven PDF path** below; flag SKILL.md staleness as a doc follow-up in closure (Task 8), never blindly follow stale steps, never silently hack `pdf_parser.py` (rag-ingest step 10 → follow-up ADR).

**Honest-partial rule (spec D2, applies to Tasks 1–3):** if a corpus's PDF cannot be acquired (WAF) or intractably resists `pdf_parser` within the time-box, that corpus is **deferred**: NOT added to `CORPORA_WITH_MANIFESTS`/gold/index; recorded transparently in decisions §H14 + a follow-up ADR. The other corpus + AI Act/RGPD still ship. Never fabricate coverage, never silent-hack the parser (§22.22).

**Exact reference anchors (verified in the codebase — use these literally):**
- `corpus/ingest.py:55` `CELEX: dict[Norma,str] = {"ai_act": "32024R1689", "gdpr": "02016R0679-20160504"}` — note GDPR uses the **consolidated** CELEX form `0XXXX...-YYYYMMDD`. `corpus/ingest.py:60` `VERSION: dict[Norma,str] = {"ai_act":"2024-07-12","gdpr":"2016-05-04"}`.
- `corpus/validate.py:10` `EXPECTED_ARTICLE_COUNTS: dict[Norma,int] = {"ai_act":113,"gdpr":99, # nis2 and dora pinned in H14}`.
- `corpus/ingest.py` `RAW_DIR = corpus/raw`, `MANIFEST_DIR = corpus/manifests`, `PROCESSED_DIR = corpus/processed`; `_resolve_local_source` tries `{corpus}_{lang}.{xml,html,pdf}` in RAW_DIR; `run(..., use_local_only=True)` skips HTTP; parser dispatch maps `"pdf": PdfParser()`. `Makefile`: `ingest:` = `$(UV) run python -m scripts.ingest --corpus all --lang all --use-local-only`; `rag-build:` = `$(UV) run python -m scripts.rag_build --corpus all --lang all`.
- `corpus/pdf_parser.py`: `class PdfParser` with `parse(self, pdf_bytes: bytes) -> list[ParsedArticle]` and internal `_parse_text(text: str)`; raises `PdfParseError`. Tested in `tests/unit/corpus/test_pdf_parser.py` via **synthetic text strings** to `PdfParser()._parse_text(text)` and `parse(b"%PDF-fake")` with `_extract_text` monkeypatched — there are **no real-PDF fixtures** (`tests/fixtures/` has `formex/ html/ rag/`, no `pdf/`).
- The **9 hardcoded 2-value spots** to widen (spec said 6; grounding found 9):
  1. `src/regulaitor/api/schemas.py:43` → `    corpus: Literal["ai_act", "gdpr"]`
  2. `src/regulaitor/api/routes_analyze.py:67` → `    if not all(c in ("ai_act", "gdpr") for c in corpus):`
  3. `src/regulaitor/corpus/loader.py:31` → `CORPORA_WITH_MANIFESTS: tuple[Norma, ...] = ("ai_act", "gdpr")` (honest-partial gate — only **landed** corpora)
  4. `src/regulaitor/ui_streamlit/tab_ask.py:20` → `_CORPUS_CHOICES = ["ai_act", "gdpr"]`
  5. `src/regulaitor/ui_streamlit/tab_analyze.py:25` → `_CORPUS_CHOICES = ["ai_act", "gdpr"]`
  6. `evals/schemas.py:28` → `    corpus_esperado: Literal["ai_act", "gdpr"]` (GoldCaseChat)
  7. `evals/schemas.py:44` → `    corpus_esperado: list[Literal["ai_act", "gdpr"]] = Field(min_length=1)` (GoldCaseDoc)
  8. `scripts/ingest.py:22` → `    p.add_argument("--corpus", choices=["ai_act", "gdpr", "all"], default="all")`
  9. `scripts/rag_build.py:22` → `    p.add_argument("--corpus", choices=["ai_act", "gdpr", "all"], default="all")`
- `Norma = Literal["ai_act","gdpr","nis2","dora"]` (corpus/schemas.py:14) and `ALL_NORMAS = ("ai_act","gdpr","nis2","dora")` (`_targets.py:12`) are **already 4-value** — the widening makes the 9 spots consistent with the already-correct canonical type.
- `GoldCaseChat` (evals/schemas.py): `id: str`, `tipo: Literal["chat"]`, `entrada: str`, `corpus_esperado`, `articulos_esperados: list[str]`, `severidad_esperada`, `criterios_evaluacion: list[str]`, `salida_esperada`, `requiere_revision_humana: bool`, `expected_verdict: Literal["pass","block","requires_human_review"]`. Gold file: `evals/gold_set.jsonl` (one JSON object per line).

---

### Task 1: Acquire the 4 consolidated PDFs (curl-direct, WAF-aware, smoke-verified, Git-LFS)

**Files:**
- Create (Git-LFS, binary): `corpus/raw/nis2_es.pdf`, `corpus/raw/nis2_en.pdf`, `corpus/raw/dora_es.pdf`, `corpus/raw/dora_en.pdf`
- Reference: `.gitattributes` (confirm `corpus/raw/*.pdf` is LFS-tracked — it already is for ai_act/gdpr)

**Context:** EUR-Lex has a CloudFront WAF (the documented reason H1 pivoted to local PDFs — `ingest.py:132` "Task 12 pragmatic pivot for EUR-Lex CloudFront WAF"; `make ingest` uses `--use-local-only`). `curl` is also automated and may hit the WAF. This task acquires + smoke-verifies the PDFs; if the WAF blocks curl, that triggers the honest fallback (do not fake/skip silently).

- [ ] **Step 1: Confirm `corpus/raw/*.pdf` is LFS-tracked**

Run: `git check-attr filter -- corpus/raw/ai_act_es.pdf`
Expected: `corpus/raw/ai_act_es.pdf: filter: lfs` (so new PDFs inherit LFS).

- [ ] **Step 2: Resolve the consolidated CELEX for NIS2 + DORA**

NIS2 = Directive (EU) 2022/2555, DORA = Regulation (EU) 2022/2554. The consolidated CELEX form mirrors GDPR's `02016R0679-20160504` (leading `0`, `-YYYYMMDD` consolidation date). Determine the **latest consolidated** CELEX from the EUR-Lex landing page for each (the consolidated document URL exposes the `0AAAAYNNNN-YYYYMMDD` id):
Run: `curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022L2555" -o /tmp/nis2_landing.html; grep -oE "0?32022L2555[-0-9]*" /tmp/nis2_landing.html | sort -u | head` (and the same for `32022R2554`).
Expected: a consolidated id like `02022L2555-20221227` (NIS2) / `02022R2554-20221227` (DORA). Record the exact ids + consolidation dates (used in Tasks 2–3). **If the landing page is a WAF challenge (HTML contains "Request blocked" / no CELEX id), skip to Step 5 (honest fallback).**

- [ ] **Step 3: Download the 4 consolidated PDFs with a browser User-Agent**

Run (substitute `<NIS2_CCELEX>`/`<DORA_CCELEX>` from Step 2; languages ES, EN):
```bash
for spec in "nis2:<NIS2_CCELEX>" "dora:<DORA_CCELEX>"; do
  c="${spec%%:*}"; celex="${spec##*:}"
  for L in "ES:es" "EN:en"; do
    lp="${L%%:*}"; lf="${L##*:}"
    curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36" \
      "https://eur-lex.europa.eu/legal-content/${lp}/TXT/PDF/?uri=CELEX:${celex}" \
      -o "corpus/raw/${c}_${lf}.pdf"
  done
done
```

- [ ] **Step 4: Smoke-verify each file is a real PDF, not a WAF HTML challenge**

Run: `for f in corpus/raw/nis2_es.pdf corpus/raw/nis2_en.pdf corpus/raw/dora_es.pdf corpus/raw/dora_en.pdf; do printf '%s ' "$f"; head -c4 "$f" | od -c | head -1; stat -c%s "$f"; done`
Expected: each starts with `% P D F` and is > 100 KB. **If any is `< C ! D` / `< h t m` / tiny (a WAF challenge or error page) → that corpus is WAF-blocked: go to Step 5 for that corpus.**

- [ ] **Step 5: Honest fallback (only if WAF-blocked / no usable PDF for a corpus)**

Do NOT fake or silently skip. Report status `DONE_WITH_CONCERNS` to the controller stating exactly which corpus/lang the WAF blocked, the HTTP status/first bytes observed, and the URL tried. The controller decides per spec D2: (a) the user provides that corpus's PDFs into `corpus/raw/`, then resume; or (b) that corpus is deferred-documented (decisions §H14 + follow-up ADR in Task 8) and only the obtainable corpus + AI Act/RGPD proceed. Do not proceed to Step 6 for a blocked corpus.

- [ ] **Step 6: Stage the obtained PDFs via Git-LFS + commit**

```bash
git add corpus/raw/nis2_es.pdf corpus/raw/nis2_en.pdf corpus/raw/dora_es.pdf corpus/raw/dora_en.pdf
git diff --cached --stat   # expect LFS pointer lines, not raw binary
SKIP=gitleaks git commit -m "feat(h14): add NIS2 + DORA consolidated PDFs (EUR-Lex, Git-LFS)"
```
(Commit only the corpora actually obtained; a deferred corpus's PDFs are absent — that is the honest-partial state.)

---

### Task 2: NIS2 slice — CELEX/VERSION/EXPECTED_ARTICLE_COUNTS + parser test + local ingest → manifest

**Files:**
- Modify: `src/regulaitor/corpus/ingest.py:55-63` (`CELEX`, `VERSION`)
- Modify: `src/regulaitor/corpus/validate.py:10-14` (`EXPECTED_ARTICLE_COUNTS`)
- Modify: `tests/unit/corpus/test_pdf_parser.py` (append a NIS2 Directive-structure synthetic test)
- Generated (Git-LFS / committed): `corpus/processed/nis2_{es,en}.json`, `corpus/manifests/nis2.json`

> Skip this whole task (deferred-documented) if Task 1 left NIS2 WAF-blocked and the controller chose defer.

- [ ] **Step 1: Write a failing synthetic NIS2-structure parser test**

Append to `tests/unit/corpus/test_pdf_parser.py` (mirror the existing `test_parses_two_articles_es` shape — feed a synthetic Directive-style text to `_parse_text`; NIS2 articles use "Artículo N" / "Article N" like the others, validate the parser handles its structure):
```python
def test_parses_nis2_directive_structure_es() -> None:
    text = (
        "Artículo 1\n"
        "Objeto\n"
        "1. La presente Directiva establece medidas destinadas a garantizar "
        "un elevado nivel común de ciberseguridad en la Unión.\n"
        "Artículo 2\n"
        "Ámbito de aplicación\n"
        "1. La presente Directiva se aplicará a las entidades esenciales e "
        "importantes a que se refiere el anexo.\n"
    )
    arts = _parse_text(text)
    assert [a.articulo for a in arts] == ["1", "2"]
    assert "elevado nivel común de ciberseguridad" in arts[0].apartados[0].texto
```

- [ ] **Step 2: Run it — expect PASS (parser is structure-generic) or FAIL (NIS2 variation)**

Run: `python -m pytest tests/unit/corpus/test_pdf_parser.py::test_parses_nis2_directive_structure_es -v --override-ini="addopts="`
Expected: PASS if `_parse_text` is structure-generic (likely — same "Artículo N" convention). **If FAIL:** NIS2's structure breaks the parser → this is the spec-D2 / rag-ingest-step-10 trigger: STOP, report the exact failure to the controller (a scoped low-risk parser tweak within the time-box may be allowed via a follow-up ADR, else NIS2 is deferred-documented). Do **not** silently edit `pdf_parser.py`.

- [ ] **Step 3: Add NIS2 to the corpus constants**

`src/regulaitor/corpus/ingest.py` — extend the dicts (use the consolidated CELEX + date resolved in Task 1 Step 2; example values shown, replace with the real resolved ones):
```python
CELEX: dict[Norma, str] = {
    "ai_act": "32024R1689",
    "gdpr": "02016R0679-20160504",
    "nis2": "<NIS2_CCELEX>",   # e.g. "02022L2555-20221227", resolved Task 1
}

VERSION: dict[Norma, str] = {
    "ai_act": "2024-07-12",
    "gdpr": "2016-05-04",
    "nis2": "<NIS2_CONSOLIDATION_DATE>",  # e.g. "2022-12-27"
}
```
`src/regulaitor/corpus/validate.py` — replace the `# nis2 and dora pinned in H14` line with the NIS2 count (pinned from the actual parsed PDF, see Step 5):
```python
EXPECTED_ARTICLE_COUNTS: dict[Norma, int] = {
    "ai_act": 113,
    "gdpr": 99,
    "nis2": <NIS2_ARTICLE_COUNT>,  # pinned from the parsed consolidated PDF (Step 5)
}
```

- [ ] **Step 4: Run the local-only ingest for NIS2**

Run: `uv run --env-file .env python -m scripts.ingest --corpus nis2 --lang all --use-local-only`
Expected: parses `corpus/raw/nis2_{es,en}.pdf`, writes `corpus/processed/nis2_{es,en}.json` + `corpus/manifests/nis2.json`. **Note:** `scripts/ingest.py:22` `--corpus choices` does not yet include `nis2` (widened in Task 4). For this task, invoke the module function directly to avoid the CLI choices gate:
`uv run --env-file .env python -c "from regulaitor.corpus.ingest import run; run(corpus='nis2', languages='all', use_local_only=True)"` (confirm `run`'s exact signature in `ingest.py` and match it; `--lang all` ⇒ `languages='all'`).
Expected: no `PdfParseError`; manifest written. If `PdfParseError` / article count wildly off ⇒ spec-D2 trigger (report, defer or scoped-ADR; never silent-hack).

- [ ] **Step 5: Pin + verify the real NIS2 article count**

Run: `uv run python -c "import json; m=json.load(open('corpus/manifests/nis2.json',encoding='utf-8')); print('articles:', m['stats']['articles_total'], 'celex:', m['celex'], 'version:', m['version'])"`
Set `EXPECTED_ARTICLE_COUNTS["nis2"]` (Step 3) to the printed `articles_total`. Re-run: `uv run --env-file .env python -m pytest tests/unit/corpus/test_validate.py -q --override-ini="addopts="` — expect green (validate passes for nis2 at the pinned count).

- [ ] **Step 6: Run the NIS2 parser test + corpus unit suite**

Run: `python -m pytest tests/unit/corpus/ -q --override-ini="addopts="`
Expected: PASS incl. the new NIS2 test; ai_act/gdpr corpus tests unchanged (regression-zero).

- [ ] **Step 7: Commit the NIS2 slice**

```bash
git add src/regulaitor/corpus/ingest.py src/regulaitor/corpus/validate.py tests/unit/corpus/test_pdf_parser.py corpus/processed/nis2_es.json corpus/processed/nis2_en.json corpus/manifests/nis2.json
SKIP=gitleaks git commit -m "feat(h14): NIS2 slice — CELEX/VERSION/count + parser test + manifest"
```

---

### Task 3: DORA slice — same procedure as Task 2 for DORA

**Files:** same shape as Task 2 with `dora`: `corpus/ingest.py` (`CELEX["dora"]`, `VERSION["dora"]`), `corpus/validate.py` (`EXPECTED_ARTICLE_COUNTS["dora"]`), `tests/unit/corpus/test_pdf_parser.py` (DORA Regulation-structure synthetic test), `corpus/processed/dora_{es,en}.json`, `corpus/manifests/dora.json`.

> Skip (deferred-documented) if Task 1 left DORA WAF-blocked and the controller chose defer.

- [ ] **Step 1: Write a failing synthetic DORA-structure parser test**

Append to `tests/unit/corpus/test_pdf_parser.py`:
```python
def test_parses_dora_regulation_structure_en() -> None:
    text = (
        "Article 1\n"
        "Subject matter\n"
        "1. This Regulation lays down uniform requirements concerning the "
        "security of network and information systems.\n"
        "Article 2\n"
        "Scope\n"
        "1. This Regulation applies to financial entities as defined herein.\n"
    )
    arts = _parse_text(text)
    assert [a.articulo for a in arts] == ["1", "2"]
    assert "uniform requirements" in arts[0].apartados[0].texto
```

- [ ] **Step 2: Run it — PASS (generic) or FAIL (DORA variation → spec-D2 trigger)**

Run: `python -m pytest tests/unit/corpus/test_pdf_parser.py::test_parses_dora_regulation_structure_en -v --override-ini="addopts="`
Expected: PASS, or FAIL ⇒ STOP + report (defer or scoped-ADR; never silent-hack — same rule as Task 2 Step 2).

- [ ] **Step 3: Add DORA to the constants**

`corpus/ingest.py`: add `"dora": "<DORA_CCELEX>"` to `CELEX` and `"dora": "<DORA_CONSOLIDATION_DATE>"` to `VERSION`. `corpus/validate.py`: add `"dora": <DORA_ARTICLE_COUNT>` to `EXPECTED_ARTICLE_COUNTS` (pinned in Step 5).

- [ ] **Step 4: Local-only ingest DORA**

Run: `uv run --env-file .env python -c "from regulaitor.corpus.ingest import run; run(corpus='dora', languages='all', use_local_only=True)"`
Expected: `corpus/processed/dora_{es,en}.json` + `corpus/manifests/dora.json`; no `PdfParseError` (else spec-D2 trigger).

- [ ] **Step 5: Pin + verify DORA article count**

Run: `uv run python -c "import json; m=json.load(open('corpus/manifests/dora.json',encoding='utf-8')); print(m['stats']['articles_total'], m['celex'], m['version'])"`
Set `EXPECTED_ARTICLE_COUNTS["dora"]` to the printed count. Run `python -m pytest tests/unit/corpus/test_validate.py -q --override-ini="addopts="` → green.

- [ ] **Step 6: Corpus unit suite**

Run: `python -m pytest tests/unit/corpus/ -q --override-ini="addopts="` — PASS, ai_act/gdpr/nis2 unchanged.

- [ ] **Step 7: Commit the DORA slice**

```bash
git add src/regulaitor/corpus/ingest.py src/regulaitor/corpus/validate.py tests/unit/corpus/test_pdf_parser.py corpus/processed/dora_es.json corpus/processed/dora_en.json corpus/manifests/dora.json
SKIP=gitleaks git commit -m "feat(h14): DORA slice — CELEX/VERSION/count + parser test + manifest"
```

---

### Task 4: Widen the 9 hardcoded 2-value spots → canonical 4-value `Norma` (only landed corpora for the loader gate)

**Files:** the 9 anchors listed in the header. Define "LANDED" = the set of corpora with a committed manifest from Tasks 2–3 (both, or one if the other was deferred).

- [ ] **Step 1: Write failing tests asserting the 4-value acceptance + ai_act/gdpr unchanged**

Create `tests/unit/test_h14_corpus_widening.py`:
```python
from __future__ import annotations
import pytest
from pydantic import ValidationError


def test_ask_request_accepts_nis2_dora():
    from regulaitor.api.schemas import AskRequest
    for c in ("ai_act", "gdpr", "nis2", "dora"):
        assert AskRequest(query="q", corpus=c, language="es").corpus == c


def test_goldcasechat_accepts_nis2():
    from evals.schemas import GoldCaseChat
    gc = GoldCaseChat(
        id="nis2-001", tipo="chat", entrada="q", corpus_esperado="nis2",
        articulos_esperados=["1"], severidad_esperada=None,
        criterios_evaluacion=["c"], salida_esperada=None,
        requiere_revision_humana=False, expected_verdict="pass",
    )
    assert gc.corpus_esperado == "nis2"


def test_loader_gate_only_landed_corpora():
    # CORPORA_WITH_MANIFESTS must list exactly the corpora with a committed manifest.
    from pathlib import Path
    from regulaitor.corpus.loader import CORPORA_WITH_MANIFESTS
    landed = {p.stem for p in Path("corpus/manifests").glob("*.json")}
    assert set(CORPORA_WITH_MANIFESTS) == landed
```

- [ ] **Step 2: Run — verify it fails**

Run: `python -m pytest tests/unit/test_h14_corpus_widening.py -v --override-ini="addopts="`
Expected: FAIL (`ValidationError` for corpus="nis2"; loader gate mismatch).

- [ ] **Step 3: Widen all 9 spots**

Apply these exact edits:
- `src/regulaitor/api/schemas.py:43`: `    corpus: Literal["ai_act", "gdpr"]` → `    corpus: Literal["ai_act", "gdpr", "nis2", "dora"]`
- `src/regulaitor/api/routes_analyze.py:67`: `    if not all(c in ("ai_act", "gdpr") for c in corpus):` → `    if not all(c in ("ai_act", "gdpr", "nis2", "dora") for c in corpus):`
- `src/regulaitor/corpus/loader.py:31`: `CORPORA_WITH_MANIFESTS: tuple[Norma, ...] = ("ai_act", "gdpr")` → set to the **LANDED** tuple, e.g. `("ai_act", "gdpr", "nis2", "dora")` (drop any deferred corpus — this is the honest-partial gate).
- `src/regulaitor/ui_streamlit/tab_ask.py:20`: `_CORPUS_CHOICES = ["ai_act", "gdpr"]` → `_CORPUS_CHOICES = ["ai_act", "gdpr", "nis2", "dora"]` (landed only).
- `src/regulaitor/ui_streamlit/tab_analyze.py:25`: same as tab_ask.py.
- `evals/schemas.py:28`: `    corpus_esperado: Literal["ai_act", "gdpr"]` → `    corpus_esperado: Literal["ai_act", "gdpr", "nis2", "dora"]`
- `evals/schemas.py:44`: `    corpus_esperado: list[Literal["ai_act", "gdpr"]] = Field(min_length=1)` → `    corpus_esperado: list[Literal["ai_act", "gdpr", "nis2", "dora"]] = Field(min_length=1)`
- `scripts/ingest.py:22`: `choices=["ai_act", "gdpr", "all"]` → `choices=["ai_act", "gdpr", "nis2", "dora", "all"]`
- `scripts/rag_build.py:22`: same as scripts/ingest.py.

(Widen the type literals to the full 4 even for a deferred corpus — the type is already `Norma`-4; only the **runtime gates** `CORPORA_WITH_MANIFESTS` / `_CORPUS_CHOICES` are restricted to LANDED corpora so a deferred corpus is not offered/loaded.)

- [ ] **Step 4: Run — verify pass + regression**

Run: `python -m pytest tests/unit/test_h14_corpus_widening.py tests/unit/api/ tests/unit/corpus/ -q --override-ini="addopts="`
Expected: PASS; existing api/contract + corpus tests green (ai_act/gdpr byte-behaviour unchanged — additive widening only).

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/api/schemas.py src/regulaitor/api/routes_analyze.py src/regulaitor/corpus/loader.py src/regulaitor/ui_streamlit/tab_ask.py src/regulaitor/ui_streamlit/tab_analyze.py evals/schemas.py scripts/ingest.py scripts/rag_build.py tests/unit/test_h14_corpus_widening.py
SKIP=gitleaks git commit -m "feat(h14): widen 9 hardcoded ai_act/gdpr literals to canonical 4-value Norma (landed-only gates)"
```

---

### Task 5: Rebuild the LanceDB index over the landed corpora (corpus-agnostic H2 machinery)

**Files:** regenerates `corpus/indexes/regulaitor.lance/` (LanceDB store; per `.gitignore` the index is local-per-machine — not committed) + the manifests' `chunks`/`embedded_at` fields (committed).

- [ ] **Step 1: Capture the AI Act/RGPD chunk baseline (regression guard)**

Run: `uv run python -c "import json; [print(c, json.load(open(f'corpus/manifests/{c}.json',encoding='utf-8'))['stats']['chunks_total']) for c in ('ai_act','gdpr')]"`
Record the two numbers.

- [ ] **Step 2: Rebuild over all landed corpora**

Run: `uv run --env-file .env python -m scripts.rag_build --corpus all --lang all` (or `make rag-build`). `--corpus all` → `expand_targets` → corpora with a pinned CELEX → the landed set.
Expected: chunks NIS2/DORA embedded (BGE-M3, local, $0); LanceDB upserted; nis2/dora manifests gain `chunks`/`embedded_at`.

- [ ] **Step 3: Verify 4-corpus index + ai_act/gdpr regression-zero**

Run: `uv run python -c "import json; [print(c, json.load(open(f'corpus/manifests/{c}.json',encoding='utf-8'))['stats']['chunks_total']) for c in ('ai_act','gdpr','nis2','dora')]"`
Expected: ai_act/gdpr `chunks_total` **identical to Step 1** (regression-zero, §22.18); nis2/dora > 0.

- [ ] **Step 4: Commit the manifest chunk updates**

```bash
git add corpus/manifests/nis2.json corpus/manifests/dora.json
git diff --cached --quiet corpus/manifests/ai_act.json corpus/manifests/gdpr.json && echo "ai_act/gdpr manifests UNCHANGED (good)" || echo "REGRESSION: ai_act/gdpr manifest changed — investigate before commit"
SKIP=gitleaks git commit -m "feat(h14): rebuild LanceDB over 4 corpora (nis2/dora chunks; ai_act/gdpr unchanged)"
```
(If ai_act/gdpr manifests changed, do NOT commit — that violates §22.18; report and investigate.)

---

### Task 6: Gold set — ≥5 NIS2 + ≥5 DORA chat cases + cross-corpus cases

**Files:** Modify (append): `evals/gold_set.jsonl`

- [ ] **Step 1: Author the cases**

Append to `evals/gold_set.jsonl` (one `GoldCaseChat` JSON per line; `articulos_esperados` must be **real article ids present in the ingested nis2/dora manifests** — verify each against `corpus/manifests/{nis2,dora}.json`). Minimum: 5 NIS2 + 5 DORA + 2 cross-corpus (a query whose `criterios_evaluacion` reference articles from 2 corpora; `corpus_esperado` is the primary corpus). Example one line (NIS2):
```json
{"id": "nis2-001", "tipo": "chat", "entrada": "¿A qué entidades se aplica la Directiva NIS2?", "corpus_esperado": "nis2", "articulos_esperados": ["2"], "severidad_esperada": "info", "criterios_evaluacion": ["cita el art. 2 NIS2 sobre ámbito de aplicación"], "salida_esperada": null, "requiere_revision_humana": false, "expected_verdict": "pass"}
```
Author the remaining 4 NIS2 + 5 DORA + 2 cross-corpus analogously, each with article ids verified against the manifests.

- [ ] **Step 2: Validate the gold file parses**

Run: `uv run python -c "from evals.harness import load_gold_set; ch,doc=load_gold_set(); ns=[c for c in ch if c.corpus_esperado=='nis2']; do=[c for c in ch if c.corpus_esperado=='dora']; print('nis2',len(ns),'dora',len(do),'total chat',len(ch))"`
Expected: nis2 ≥5, dora ≥5; no `ValidationError` (the Task-4 widened `GoldCaseChat` accepts nis2/dora).

- [ ] **Step 3: Commit**

```bash
git add evals/gold_set.jsonl
SKIP=gitleaks git commit -m "feat(h14): gold set — >=5 NIS2 + >=5 DORA + cross-corpus chat cases"
```

---

### Task 7: $0 deterministic verification — cross-corpus retrieval + load + regression-zero

**Files:** Create `tests/integration/test_h14_cross_corpus_retrieval.py`

**Context:** This is the honest §16.3-reframe verification (D3): retrieval finds the correct NIS2/DORA articles (citation-recall-style, the §16.2 #5 safety signal) — **no LLM-judge** ($0). The LLM-judge metric eval + §17 thresholds are explicitly H15.

- [ ] **Step 1: Write the $0 retrieval + regression test**

```python
from __future__ import annotations
import pytest
from regulaitor.corpus import loader as corpus_loader
from regulaitor.rag import retrieval


@pytest.fixture(scope="module", autouse=True)
def _warm():
    corpus_loader.warmup()


def _articulos(corpus: str, query: str) -> set[str]:
    ctx = retrieval.run(query=query, corpus=corpus, language="es")
    return {ch.articulo for ch in ctx.chunks}


def test_nis2_query_retrieves_a_nis2_article():
    got = _articulos("nis2", "¿A qué entidades se aplica la Directiva NIS2?")
    assert got, "no chunks retrieved for nis2"


def test_dora_query_retrieves_a_dora_article():
    got = _articulos("dora", "¿Qué exige DORA sobre gestión del riesgo de las TIC?")
    assert got, "no chunks retrieved for dora"


def test_no_corpus_leakage_aiact_still_works():
    # Regression-zero: AI Act retrieval unaffected by the expansion.
    got = _articulos("ai_act", "sistemas de IA de alto riesgo")
    assert got, "ai_act retrieval regressed"
```
(Confirm `retrieval.run`'s exact signature against `src/regulaitor/rag/retrieval.py` and match it; adjust `ctx.chunks`/`.articulo` to the real `Context`/`RetrievedChunk` field names — they are `Context.chunks: list[RetrievedChunk]`, `RetrievedChunk.articulo`.)

- [ ] **Step 2: Run it**

Run: `uv run --env-file .env python -m pytest tests/integration/test_h14_cross_corpus_retrieval.py -v --override-ini="addopts="`
Expected: PASS — nis2/dora queries return chunks; ai_act regression-zero. ($0 — local BGE-M3 retrieval, no LLM.)

- [ ] **Step 3: `make ingest` loads all landed corpora (smoke)**

Run: `uv run python -c "from regulaitor.corpus import loader; loader.warmup(); [loader.get_manifest(c) for c in loader.CORPORA_WITH_MANIFESTS]; print('loaded:', loader.CORPORA_WITH_MANIFESTS)"`
Expected: no `KeyError`; prints the landed corpora (4, or 3 if one deferred).

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_h14_cross_corpus_retrieval.py
SKIP=gitleaks git commit -m "feat(h14): \$0 deterministic cross-corpus retrieval verification + ai_act regression test"
```

---

### Task 8: Full gate + closure (ADR 0015 + decisions §H14 + evidence_matrix + CLAUDE.md §27 + memory)

**Files:** Create `docs/adr/0015-nis2-dora-corpus.md`; Modify `docs/technical_decisions_log.md`, `docs/evidence_matrix.md`, `CLAUDE.md`; (memory roll-forward is post-merge — Task done by the controller in finishing-a-development-branch, not here).

- [ ] **Step 1: Full test gate**

Run: `python -m pytest -q`
Expected: green; coverage ≥90% (no override — the real gate; H14 added no `# pragma: no cover` paid path). Record the pass count + "Total coverage: NN%".

- [ ] **Step 2: ADR 0015**

Create `docs/adr/0015-nis2-dora-corpus.md` mirroring `docs/adr/0014-council-of-judges.md` structure (Status/Date with `<squash-sha>` placeholder + `tag v0.1.4-h14`; Deciders; Companion ADRs incl. 0003 corpus-pipeline; Context; Decision = D1–D4; Consequences Positive + Negative/accepted-honest [the honest §16.3 reframe: §17 thresholds → H15; any deferred corpus; the 9-not-6 literal refinement; the EUR-Lex CloudFront-WAF/curl reality; the `rag-ingest` SKILL.md Formex-vs-PDF staleness]; Alternatives; References to spec/plan/decisions §H14/ADR 0003).

- [ ] **Step 3: decisions §H14**

Append to `docs/technical_decisions_log.md` (mirror the §H13 section depth/tone): header `## H14 — NIS2 + DORA corpus expansion (cerrado 2026-05-18, squash \`<squash-sha>\`, tag \`v0.1.4-h14\`)`. Capture: D1–D4; the honest §16.3 reframe (eval-thresholds → H15, H14 = ingested+queryable+gold+$0-verified, $0 milestone); the 9-not-6 hardcoded-literal refinement vs the spec's 6; the EUR-Lex CloudFront-WAF root cause + curl-acquisition outcome; any per-corpus deferred-partial (honest, §22.22) + follow-up ADR; the `rag-ingest` SKILL.md Formex-vs-PDF staleness (doc follow-up); article counts pinned for nis2/dora; "no new skills (`rag-ingest` already active since H1; `cost-accounting` stays H17)". End: `H14 cerrado 2026-05-18. Squash \`<squash-sha>\`, tag \`v0.1.4-h14\` (post-merge).`

- [ ] **Step 4: evidence_matrix + CLAUDE.md §27**

`docs/evidence_matrix.md`: Módulo 3 — set the `Corpus NIS2 + DORA` row to ✅ H14 (or deferred-documented for any partial), with the manifest paths + article counts; refresh the State header; add H14 follow-ups (any deferred corpus → future; SKILL.md Formex-vs-PDF doc fix; LLM-judge eval over expanded gold → H15). `CLAUDE.md` §27: move H14 into the closed-milestones list with a dense entry mirroring the H13 entry density (D1–D4 essence, the curl/WAF reality, any partial, $0, honest §16.3 reframe, the 9-literal widening, tag `v0.1.4-h14`, squash `<squash-sha>` post-merge, "Ver decisions §H14"); set "### Hito siguiente" → **H15 — Calibración Auditor + A/B** (carry the H13 reinforcement: 57% Council-vs-Auditor divergence + the over-fires-RHR finding + the `MonotonicEscalatePolicy` promotion seam are the H15 levers).

- [ ] **Step 5: Commit closure docs**

```bash
git add docs/adr/0015-nis2-dora-corpus.md docs/technical_decisions_log.md docs/evidence_matrix.md CLAUDE.md
SKIP=gitleaks git commit -m "docs(h14): close milestone — ADR 0015 + decisions §H14 + evidence_matrix + CLAUDE.md §27"
```

- [ ] **Step 6: Hand off to finishing-a-development-branch**

Final whole-branch review → `superpowers:finishing-a-development-branch` (verify tests on merged result → USER-GATED squash-merge `feat(h14): nis2 + dora corpus expansion` → tag `v0.1.4-h14` → post-merge `docs(h14): populate post-merge SHA` filling the `<squash-sha>` placeholders → delete branch → memory roll-forward `h13_closed_h14_starting.md` → `h14_closed_h15_starting.md`).

---

## Self-Review

**1. Spec coverage:** D1 PDF/CELEX/curl-direct → Task 1 (+ consolidated-CELEX resolution Step 2). D2 best-effort+honest-partial → Task 1 Step 5, Task 2/3 Step 2, Task 4 landed-only gates, Task 8 docs. D3 ≥5+≥5+cross gold + $0 verify + §17→H15 reframe → Tasks 6, 7, 8 Step 3-4. D4 Approach-1 slices+integration + 9-literal widen + LanceDB rebuild + backend read-only → Tasks 2–5. §22.18 regression-zero → Task 4 Step 4, Task 5 Step 1/3/4, Task 7 Step 1. rag-ingest procedure (CELEX/VERSION/EXPECTED counts/parser test/manifest/LFS) → Tasks 1–3. SKILL.md-Formex-vs-PDF + WAF + 9-not-6 refinement honestly recorded → Task 8. Closure (ADR 0015/decisions/evidence_matrix/CLAUDE/tag/memory) → Task 8 + handoff. All spec sections mapped.

**2. Placeholder scan:** The `<NIS2_CCELEX>` / `<…_CONSOLIDATION_DATE>` / `<…_ARTICLE_COUNT>` tokens are **deliberate implementation-time pins resolved by an explicit prior step** (Task 1 Step 2 resolves the CELEX; Task 2/3 Step 5 pins the count from the actual parsed manifest) — this is the rag-ingest/ADR-0003 pattern (counts come from the fetched source, exactly as `validate.py:13` "pinned in H14" intends), not a "fill in later" placeholder. Each is bound by a concrete preceding command with expected output. No `TBD`/"add error handling"/"similar to Task N". The honest-partial branches give explicit STOP+report criteria, not vague handwaving.

**3. Type consistency:** `Norma` 4-value used consistently; `CORPORA_WITH_MANIFESTS`/`_CORPUS_CHOICES` = landed set everywhere (Tasks 4,5,7); `GoldCaseChat` field names match evals/schemas.py (Tasks 4,6); `retrieval.run`/`Context.chunks`/`RetrievedChunk.articulo` flagged for signature-confirmation in Task 7 Step 1; `run(corpus=,languages=,use_local_only=)` flagged for signature-confirmation in Task 2 Step 4. Manifest field `stats.articles_total`/`stats.chunks_total` consistent with corpus/schemas.py `Stats`. No drift.
