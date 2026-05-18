# H13 — Council of Judges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an advisory 3-judge multi-provider Council that votes on high-severity/ambiguous chat findings as auditable evidence, without changing the deterministic verdict.

**Architecture:** Approach 1 — a new `council` LangGraph node after `auditor` reached via a conditional edge. Judges run through the existing H12 router (`judge`=Haiku 4.5, `evaluation`=GPT-4o, `cost`=Llama-Groq). A swappable `AggregationPolicy` aggregates votes; `AdvisoryMajorityPolicy` (default) never mutates `state.verdict`; `MonotonicEscalatePolicy` is implemented + unit-tested but wired OFF (the H15 promotion seam). Backend H1–H3 / Analyst / mechanical-Auditor aggregation are read-only; `graph.py`/`state.py`/`api` are in H13 scope per CLAUDE.md §16.3.

**Tech Stack:** Python 3.11, Pydantic v2, LangGraph, pytest, the H12 multi-provider router (Anthropic/OpenAI/Groq via `models/router.py`).

**Conventions (all tasks):** TDD. `from __future__ import annotations` at top of every new module. Run tests with `python -m pytest`. Commit with `SKIP=gitleaks git commit` (gitleaks is CI-enforced; never `--no-verify`). Conventional commit messages, **no AI/Co-Authored-By footer**. Branch: `feat/h13-council-of-judges` (already created, spec committed `70d2fed`). Coverage gate ≥90% on changed subsystems must stay green.

**Reference types (already exist, do not redefine):**
- `regulaitor.citation.schemas.AuditVerdict` — `StrEnum`: `PASS="pass"`, `BLOCK="block"`, `REQUIRES_HUMAN_REVIEW="requires_human_review"`.
- `AuditedAnswer{answer: Answer, verdict: AuditVerdict, audit_results: list[AuditResult], reason: str|None}`.
- `Answer{query: str, language: Language, text: str, findings: list[Finding]}` (frozen).
- `Finding{text: str, citations: list[Citation], severity: Literal["info","low","medium","high"]}` (frozen).
- `Citation{norma, articulo, apartado, language, text}` (frozen, hashable).
- `AuditResult{citation: Citation, validated: bool, article_exists, apartado_exists, text_normalized_match, reason: str|None}`.
- `Context{query, corpus, language, chunks: list[RetrievedChunk], retrieved_at, embedding_model}`; `RetrievedChunk{chunk_id, norma, articulo, apartado, language, text, score, version, source_url}`.
- `regulaitor.models.router.complete(*, messages, system, tools, tool_choice, model_choice, max_tokens) -> CompletionResult`; `CompletionResult` has `.tool_use_input: dict|None`, `.text: str`, `.usage`, `.model_id: str`, `.cost_eur: float`, `.latency_ms: int`.
- `regulaitor.models.router.ModelChoice` Literal + `_MODE_MAP: dict[str, ProviderModel]`; `ProviderModel(NamedTuple): provider: str, model_id: str`; `PROVIDER_ANTHROPIC` constant; `_VALID_MODES = frozenset(get_args(ModelChoice))`.
- `regulaitor.models.config.PRICING: dict[str, tuple[float,float]]` (USD per 1M in/out), `PRICING_SNAPSHOT_DATE`, `cost_eur(model_id, n_in, n_out) -> float`, `ANTHROPIC_SONNET_4_6` constant.

---

### Task 1: Router `judge` mode → Haiku 4.5 + pricing

**Files:**
- Modify: `src/regulaitor/models/config.py`
- Modify: `src/regulaitor/models/router.py`
- Test: `tests/unit/models/test_config.py`, `tests/unit/models/test_router.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/models/test_config.py`:

```python
def test_haiku_45_pricing_present():
    from regulaitor.models import config

    assert config.ANTHROPIC_HAIKU_4_5 == "claude-haiku-4-5-20251001"
    assert config.ANTHROPIC_HAIKU_4_5 in config.PRICING
    in_usd, out_usd = config.PRICING[config.ANTHROPIC_HAIKU_4_5]
    assert in_usd > 0 and out_usd > 0
    # Haiku is cheaper than Sonnet on both legs (sanity, not exact).
    s_in, s_out = config.PRICING[config.ANTHROPIC_SONNET_4_6]
    assert in_usd < s_in and out_usd < s_out
```

Add to `tests/unit/models/test_router.py`:

```python
def test_judge_mode_resolves_to_haiku():
    from regulaitor.models import config, router

    assert "judge" in router._VALID_MODES
    pm = router._MODE_MAP["judge"]
    assert pm.provider == router.PROVIDER_ANTHROPIC
    assert pm.model_id == config.ANTHROPIC_HAIKU_4_5


def test_five_existing_modes_unchanged():
    from regulaitor.models import config, router

    assert router._MODE_MAP["default"].model_id == config.ANTHROPIC_SONNET_4_6
    assert router._MODE_MAP["quality"].model_id == config.ANTHROPIC_SONNET_4_6
    assert router._MODE_MAP["evaluation"].model_id == config.OPENAI_GPT_4O
    assert router._MODE_MAP["cost"].model_id == config.GROQ_LLAMA_70B
    assert router._MODE_MAP["fallback"].model_id == config.OPENAI_GPT_4O_MINI
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/models/test_config.py::test_haiku_45_pricing_present tests/unit/models/test_router.py::test_judge_mode_resolves_to_haiku -v`
Expected: FAIL (`AttributeError: ... ANTHROPIC_HAIKU_4_5` / `KeyError: 'judge'`).

- [ ] **Step 3: Implement config.py**

In `src/regulaitor/models/config.py`, near the other model-id constants add:

```python
ANTHROPIC_HAIKU_4_5 = "claude-haiku-4-5-20251001"
```

In the `PRICING` dict add the entry (published Anthropic list price, USD per 1M tokens; snapshot date already governs reproducibility — keep `PRICING_SNAPSHOT_DATE` as is unless other prices change this milestone):

```python
    ANTHROPIC_HAIKU_4_5: (1.00, 5.00),
```

- [ ] **Step 4: Implement router.py**

In `src/regulaitor/models/router.py`: add `"judge"` to the `ModelChoice` Literal (e.g. `ModelChoice = Literal["default", "quality", "cost", "evaluation", "fallback", "judge"]`) and add the map entry alongside the others:

```python
    "judge": ProviderModel(PROVIDER_ANTHROPIC, config.ANTHROPIC_HAIKU_4_5),
```

(`_VALID_MODES = frozenset(get_args(ModelChoice))` already derives from the Literal — no extra change. `_call_anthropic` is already model-id-parametric since H12, so Haiku dispatches through the existing bespoke Anthropic path.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/models/ -v`
Expected: PASS (all, including the pre-existing H12 router tests — regression-zero on the 5 modes).

- [ ] **Step 6: Commit**

```bash
git add src/regulaitor/models/config.py src/regulaitor/models/router.py tests/unit/models/test_config.py tests/unit/models/test_router.py
SKIP=gitleaks git commit -m "feat(h13): add judge router mode -> Haiku 4.5 + pricing"
```

---

### Task 2: `JudgeVote` + `CouncilReview` schemas

**Files:**
- Modify: `src/regulaitor/citation/schemas.py`
- Test: `tests/unit/citation/test_council_schemas.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/citation/test_council_schemas.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from regulaitor.citation.schemas import AuditVerdict, CouncilReview, JudgeVote


def _vote(vote=AuditVerdict.PASS, ok=True):
    return JudgeVote(
        model_id="claude-haiku-4-5-20251001",
        provider="anthropic",
        vote=vote,
        reason="cita soporta la afirmación",
        ok=ok,
        error_category=None,
    )


def test_judgevote_is_frozen():
    v = _vote()
    with pytest.raises(ValidationError):
        v.vote = AuditVerdict.BLOCK


def test_councilreview_roundtrip():
    cr = CouncilReview(
        triggered=True,
        trigger_reason="auditor_rhr",
        judges=[_vote(), _vote(AuditVerdict.BLOCK)],
        council_verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW,
        agreement="split",
        diverges_from_auditor=True,
        reason="2 judges split",
    )
    assert cr.judges[0].provider == "anthropic"
    assert cr.trigger_reason == "auditor_rhr"


def test_councilreview_rejects_bad_trigger_reason():
    with pytest.raises(ValidationError):
        CouncilReview(
            triggered=False,
            trigger_reason="bogus",
            judges=[],
            council_verdict=AuditVerdict.PASS,
            agreement="degraded",
            diverges_from_auditor=False,
            reason="x",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/citation/test_council_schemas.py -v`
Expected: FAIL (`ImportError: cannot import name 'CouncilReview'`).

- [ ] **Step 3: Implement the schemas**

Append to `src/regulaitor/citation/schemas.py` (after `AuditedAnswer`, before the H5 document section):

```python
class JudgeVote(BaseModel):
    """One Council judge's vote (H13). Frozen; immutable evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    vote: AuditVerdict
    reason: str
    ok: bool
    error_category: str | None


class CouncilReview(BaseModel):
    """Aggregated Council outcome (H13). Advisory: never mutates the verdict."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    triggered: bool
    trigger_reason: Literal["auditor_rhr", "high_severity", "api_override", "not_triggered"]
    judges: list[JudgeVote]
    council_verdict: AuditVerdict
    agreement: Literal["unanimous", "majority", "split", "degraded"]
    diverges_from_auditor: bool
    reason: str
```

(`BaseModel`, `ConfigDict`, `Field`, `Literal`, `AuditVerdict` are already imported in this file.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/citation/test_council_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/citation/schemas.py tests/unit/citation/test_council_schemas.py
SKIP=gitleaks git commit -m "feat(h13): add JudgeVote + CouncilReview schemas"
```

---

### Task 3: `ChatState` Council fields

**Files:**
- Modify: `src/regulaitor/orchestration/state.py`
- Test: `tests/unit/orchestration/test_state.py` (append; create if absent)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/orchestration/test_state.py` (create the file with the import header if it does not exist):

```python
def test_chatstate_council_fields_default_none():
    from regulaitor.orchestration.state import ChatState

    s = ChatState(case_id="c1", query="q", corpus="ai_act", language="es")
    assert s.council_override is None
    assert s.council_review is None


def test_chatstate_accepts_council_override_bool():
    from regulaitor.orchestration.state import ChatState

    s = ChatState(
        case_id="c1", query="q", corpus="ai_act", language="es", council_override=True
    )
    assert s.council_override is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/orchestration/test_state.py -v -k council`
Expected: FAIL (`ValidationError: extra fields not permitted` — `ChatState` is `extra="forbid"`).

- [ ] **Step 3: Implement**

In `src/regulaitor/orchestration/state.py` add the import and the two fields:

```python
from regulaitor.citation.schemas import Answer, AuditedAnswer, Context, CouncilReview
```

Add inside `ChatState` (after `injection_reason`):

```python
    council_override: bool | None = None
    council_review: CouncilReview | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/orchestration/test_state.py -v -k council`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/orchestration/state.py tests/unit/orchestration/test_state.py
SKIP=gitleaks git commit -m "feat(h13): add council_override + council_review to ChatState"
```

---

### Task 4: `AggregationPolicy` + `AdvisoryMajorityPolicy`

**Files:**
- Create: `src/regulaitor/agents/council.py`
- Test: `tests/unit/agents/test_council_policy.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/agents/test_council_policy.py`:

```python
from __future__ import annotations

from regulaitor.agents.council import AdvisoryMajorityPolicy
from regulaitor.citation.schemas import AuditVerdict, JudgeVote

P, B, R = AuditVerdict.PASS, AuditVerdict.BLOCK, AuditVerdict.REQUIRES_HUMAN_REVIEW


def _v(vote, ok=True):
    return JudgeVote(
        model_id="m", provider="p", vote=vote, reason="r", ok=ok, error_category=None
    )


def test_unanimous_three_ok():
    verdict, label = AdvisoryMajorityPolicy().aggregate([_v(P), _v(P), _v(P)])
    assert verdict == P and label == "unanimous"


def test_majority_two_of_three():
    verdict, label = AdvisoryMajorityPolicy().aggregate([_v(B), _v(B), _v(P)])
    assert verdict == B and label == "majority"


def test_split_one_one_one_is_rhr():
    verdict, label = AdvisoryMajorityPolicy().aggregate([_v(P), _v(B), _v(R)])
    assert verdict == R and label == "split"


def test_degraded_two_ok_agree():
    verdict, label = AdvisoryMajorityPolicy().aggregate(
        [_v(B), _v(B), _v(P, ok=False)]
    )
    assert verdict == B and label == "degraded"


def test_degraded_two_ok_disagree_is_rhr():
    verdict, label = AdvisoryMajorityPolicy().aggregate(
        [_v(B), _v(P), _v(P, ok=False)]
    )
    assert verdict == R and label == "degraded"


def test_zero_ok_is_rhr_degraded():
    verdict, label = AdvisoryMajorityPolicy().aggregate(
        [_v(P, ok=False), _v(B, ok=False), _v(R, ok=False)]
    )
    assert verdict == R and label == "degraded"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/agents/test_council_policy.py -v`
Expected: FAIL (`ModuleNotFoundError: regulaitor.agents.council`).

- [ ] **Step 3: Implement the policy**

Create `src/regulaitor/agents/council.py`:

```python
"""CouncilAgent + aggregation policies (H13).

Advisory layer: the Council records evidence and NEVER mutates the
deterministic verdict in H13. MonotonicEscalatePolicy.would_escalate
exists + is unit-tested but is the H15 promotion seam — the graph node
never calls it while _COUNCIL_BINDING is False.
"""

from __future__ import annotations

from collections import Counter
from typing import Literal, Protocol

from regulaitor.citation.schemas import AuditVerdict, JudgeVote

AgreementLabel = Literal["unanimous", "majority", "split", "degraded"]

# H15 promotion seam. Flipping this True + selecting MonotonicEscalatePolicy
# is the entire promotion to a binding gate (see decisions log §H13).
_COUNCIL_BINDING = False


class AggregationPolicy(Protocol):
    def aggregate(
        self, votes: list[JudgeVote]
    ) -> tuple[AuditVerdict, AgreementLabel]: ...


def _modal_verdict(ok_votes: list[JudgeVote]) -> tuple[AuditVerdict, int]:
    """Most common vote among ok votes + its count. Empty -> (RHR, 0)."""
    if not ok_votes:
        return AuditVerdict.REQUIRES_HUMAN_REVIEW, 0
    counts = Counter(v.vote for v in ok_votes)
    verdict, n = counts.most_common(1)[0]
    return verdict, n


class AdvisoryMajorityPolicy:
    """Default H13 policy. Verdict = modal vote iff >=2 ok votes agree,
    else REQUIRES_HUMAN_REVIEW. Label precedence: degraded if <3 ok;
    else unanimous if all 3 agree; else majority if exactly 2 agree;
    else split."""

    def aggregate(
        self, votes: list[JudgeVote]
    ) -> tuple[AuditVerdict, AgreementLabel]:
        ok = [v for v in votes if v.ok]
        modal, n_modal = _modal_verdict(ok)
        verdict = modal if n_modal >= 2 else AuditVerdict.REQUIRES_HUMAN_REVIEW
        if len(ok) < 3:
            return verdict, "degraded"
        if n_modal == 3:
            return modal, "unanimous"
        if n_modal == 2:
            return modal, "majority"
        return AuditVerdict.REQUIRES_HUMAN_REVIEW, "split"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/agents/test_council_policy.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/agents/council.py tests/unit/agents/test_council_policy.py
SKIP=gitleaks git commit -m "feat(h13): AggregationPolicy + AdvisoryMajorityPolicy"
```

---

### Task 5: `MonotonicEscalatePolicy` (implemented, tested, wired OFF)

**Files:**
- Modify: `src/regulaitor/agents/council.py`
- Test: `tests/unit/agents/test_council_policy.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/agents/test_council_policy.py`:

```python
def test_monotonic_aggregate_matches_advisory():
    from regulaitor.agents.council import MonotonicEscalatePolicy

    a = AdvisoryMajorityPolicy().aggregate([_v(B), _v(B), _v(P)])
    m = MonotonicEscalatePolicy().aggregate([_v(B), _v(B), _v(P)])
    assert a == m


def test_monotonic_would_escalate_pass_on_unanimous_block():
    from regulaitor.agents.council import MonotonicEscalatePolicy

    pol = MonotonicEscalatePolicy()
    out = pol.would_escalate(AuditVerdict.PASS, [_v(B), _v(B), _v(B)])
    assert out == AuditVerdict.REQUIRES_HUMAN_REVIEW


def test_monotonic_never_relaxes_block():
    from regulaitor.agents.council import MonotonicEscalatePolicy

    pol = MonotonicEscalatePolicy()
    # 3x PASS but audited was BLOCK -> never relax: stays BLOCK.
    out = pol.would_escalate(AuditVerdict.BLOCK, [_v(P), _v(P), _v(P)])
    assert out == AuditVerdict.BLOCK


def test_monotonic_no_escalate_when_not_unanimous():
    from regulaitor.agents.council import MonotonicEscalatePolicy

    pol = MonotonicEscalatePolicy()
    out = pol.would_escalate(AuditVerdict.PASS, [_v(B), _v(B), _v(P)])
    assert out == AuditVerdict.PASS


def test_council_binding_seam_is_off():
    from regulaitor.agents import council

    assert council._COUNCIL_BINDING is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/agents/test_council_policy.py -v -k monotonic`
Expected: FAIL (`ImportError: cannot import name 'MonotonicEscalatePolicy'`).

- [ ] **Step 3: Implement**

Append to `src/regulaitor/agents/council.py`:

```python
class MonotonicEscalatePolicy:
    """H15 promotion seam (implemented + tested, NOT wired in H13).

    `aggregate` is identical to AdvisoryMajorityPolicy. `would_escalate`
    is the future binding rule: escalate PASS->REQUIRES_HUMAN_REVIEW only
    on a unanimous (all-ok, >=3) BLOCK vote; NEVER relax a BLOCK. The
    graph node never calls would_escalate while _COUNCIL_BINDING is False.
    """

    def aggregate(
        self, votes: list[JudgeVote]
    ) -> tuple[AuditVerdict, AgreementLabel]:
        return AdvisoryMajorityPolicy().aggregate(votes)

    def would_escalate(
        self, audited_verdict: AuditVerdict, votes: list[JudgeVote]
    ) -> AuditVerdict:
        if audited_verdict != AuditVerdict.PASS:
            return audited_verdict  # never relax BLOCK / RHR
        ok = [v for v in votes if v.ok]
        if len(ok) >= 3 and all(v.vote == AuditVerdict.BLOCK for v in ok):
            return AuditVerdict.REQUIRES_HUMAN_REVIEW
        return AuditVerdict.PASS
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/agents/test_council_policy.py -v`
Expected: PASS (11 passed).

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/agents/council.py tests/unit/agents/test_council_policy.py
SKIP=gitleaks git commit -m "feat(h13): MonotonicEscalatePolicy (H15 seam, wired OFF)"
```

---

### Task 6: Council judge prompt (versioned)

**Files:**
- Create: `src/regulaitor/agents/prompts/council/__init__.py` (empty)
- Create: `src/regulaitor/agents/prompts/council/judge.v1.0.md`
- Test: `tests/unit/agents/test_council_prompt.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/agents/test_council_prompt.py`:

```python
from __future__ import annotations

from pathlib import Path

PROMPT = (
    Path(__file__).parents[3]
    / "src/regulaitor/agents/prompts/council/judge.v1.0.md"
)


def test_council_prompt_exists_with_frontmatter():
    text = PROMPT.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "agent: council" in text
    assert "role: council_judge" in text
    assert "version: 1.0" in text
    assert "cast_vote" in text  # references the structured-output tool
    # voting vocabulary present
    for token in ("valid", "invalid", "requires_human_review"):
        assert token in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/agents/test_council_prompt.py -v`
Expected: FAIL (`FileNotFoundError`).

- [ ] **Step 3: Create the prompt files**

Create empty `src/regulaitor/agents/prompts/council/__init__.py`.

Create `src/regulaitor/agents/prompts/council/judge.v1.0.md`:

```markdown
---
agent: council
role: council_judge
version: 1.0
language: es
input_format: json
output_format: tool_call
model_compatibility: [claude-haiku-4-5-20251001, gpt-4o, llama-3.3-70b-versatile]
created: 2026-05-17
changelog:
  - 2026-05-17: initial Council judge prompt for H13 (advisory multi-judge)
---

# Council Judge v1.0

Eres un juez independiente en un tribunal de cumplimiento normativo europeo
(AI Act + RGPD). NO eres un experto jurídico definitivo: eres un revisor
estricto que decide si las CITAS aportadas SOPORTAN la afirmación del hallazgo
(CLAUDE.md §6.4), usando EXCLUSIVAMENTE el texto del corpus que se te entrega.

Recibes un objeto JSON con:
- `answer_text`: resumen del sistema.
- `findings_under_review`: lista de hallazgos; cada uno con `text`,
  `citations` (norma/articulo/apartado/texto citado) y `audit_results`
  (validación mecánica previa).
- `retrieved_context`: fragmentos del corpus recuperados (texto + ubicación).

Decide UN voto global sobre los hallazgos en revisión:
- `valid`: las citas existen Y soportan la afirmación.
- `invalid`: alguna afirmación relevante NO está soportada por sus citas, o
  la cita no dice lo que el hallazgo afirma.
- `requires_human_review`: ambiguo o insuficiente para decidir con confianza.

En caso de duda razonable, vota `requires_human_review`. No inventes
artículos ni texto que no esté en `retrieved_context`.

Emite tu voto EXCLUSIVAMENTE llamando a la tool `cast_vote` con:
`{"vote": "valid|invalid|requires_human_review", "reason": "<1 frase>"}`.
No produzcas texto fuera de la tool call.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/agents/test_council_prompt.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/agents/prompts/council/
SKIP=gitleaks git commit -m "feat(h13): versioned council judge prompt v1.0"
```

---

### Task 7: `CouncilAgent.review`

**Files:**
- Modify: `src/regulaitor/agents/council.py`
- Test: `tests/unit/agents/test_council_agent.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/agents/test_council_agent.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

from regulaitor.agents.council import CouncilAgent
from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditResult,
    AuditVerdict,
    Citation,
    Context,
    Finding,
)


def _citation(text="el artículo dice X"):
    return Citation(
        norma="ai_act", articulo="6", apartado="1", language="es", text=text
    )


def _finding(severity="high", cite_text="el artículo dice X"):
    return Finding(text="afirmación", citations=[_citation(cite_text)], severity=severity)


def _audited(verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW, severity="high"):
    ans = Answer(query="q", language="es", text="resumen", findings=[_finding(severity)])
    ar = AuditResult(
        citation=ans.findings[0].citations[0],
        validated=False,
        article_exists=True,
        apartado_exists=True,
        text_normalized_match=False,
        reason="text_not_in_apartado",
    )
    return AuditedAnswer(answer=ans, verdict=verdict, audit_results=[ar], reason="r")


def _context():
    return Context(
        query="q",
        corpus="ai_act",
        language="es",
        chunks=[],
        retrieved_at=datetime.now(timezone.utc),
        embedding_model="bge-m3",
    )


class _FakeResult:
    def __init__(self, vote):
        self.tool_use_input = {"vote": vote, "reason": "porque sí"}
        self.text = ""
        self.model_id = "fake"
        self.cost_eur = 0.0
        self.latency_ms = 1
        self.usage = None


def test_review_unanimous_invalid_diverges_from_pass():
    with patch("regulaitor.agents.council.router.complete") as m:
        m.return_value = _FakeResult("invalid")
        cr = CouncilAgent().review(
            _audited(verdict=AuditVerdict.PASS),
            _context(),
            trigger_reason="high_severity",
        )
    assert len(cr.judges) == 3
    assert all(j.ok for j in cr.judges)
    assert cr.council_verdict == AuditVerdict.BLOCK
    assert cr.agreement == "unanimous"
    assert cr.diverges_from_auditor is True
    assert cr.trigger_reason == "high_severity"


def test_review_one_judge_fails_is_degraded_turn_survives():
    calls = {"n": 0}

    def _side_effect(*a, **k):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("groq 429 free-tier cap")
        return _FakeResult("valid")

    with patch("regulaitor.agents.council.router.complete", side_effect=_side_effect):
        cr = CouncilAgent().review(
            _audited(), _context(), trigger_reason="auditor_rhr"
        )
    assert len(cr.judges) == 3
    failed = [j for j in cr.judges if not j.ok]
    assert len(failed) == 1
    assert failed[0].error_category == "RuntimeError"
    assert cr.agreement == "degraded"


def test_review_all_judges_fail_council_unavailable():
    with patch(
        "regulaitor.agents.council.router.complete",
        side_effect=RuntimeError("down"),
    ):
        cr = CouncilAgent().review(
            _audited(), _context(), trigger_reason="auditor_rhr"
        )
    assert all(not j.ok for j in cr.judges)
    assert cr.council_verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW
    assert "council_unavailable" in cr.reason


def test_findings_under_review_union_logic():
    # verdict PASS + no high severity + not override => union empty => all findings
    aud = _audited(verdict=AuditVerdict.PASS, severity="low")
    with patch("regulaitor.agents.council.router.complete") as m:
        m.return_value = _FakeResult("valid")
        agent = CouncilAgent()
        reviewed = agent._findings_under_review(aud)
    assert len(reviewed) == 1  # falls back to all findings when union empty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/agents/test_council_agent.py -v`
Expected: FAIL (`ImportError: cannot import name 'CouncilAgent'`).

- [ ] **Step 3: Implement `CouncilAgent`**

Append to `src/regulaitor/agents/council.py` (add imports at top: `import json`, `import logging`, `from pathlib import Path`, and the schema imports):

```python
import json
import logging
from pathlib import Path

from regulaitor.citation.schemas import (
    AuditedAnswer,
    Context,
    CouncilReview,
    Finding,
)
from regulaitor.models import router

logger = logging.getLogger("regulaitor.agents.council")

_PROMPT_PATH = Path(__file__).parent / "prompts" / "council" / "judge.v1.0.md"
_JUDGE_MODES: tuple[str, str, str] = ("judge", "evaluation", "cost")

_VOTE_TOOL = {
    "name": "cast_vote",
    "description": "Cast the judge's single global vote on the findings under review.",
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "vote": {
                "type": "string",
                "enum": ["valid", "invalid", "requires_human_review"],
            },
            "reason": {"type": "string"},
        },
        "required": ["vote", "reason"],
    },
}

# Judge vote vocabulary -> AuditVerdict.
_VOTE_MAP = {
    "valid": AuditVerdict.PASS,
    "invalid": AuditVerdict.BLOCK,
    "requires_human_review": AuditVerdict.REQUIRES_HUMAN_REVIEW,
}


class CouncilAgent:
    """Advisory 3-judge council. Never mutates the verdict in H13."""

    def __init__(self, policy: AggregationPolicy | None = None) -> None:
        self._policy: AggregationPolicy = policy or AdvisoryMajorityPolicy()
        self._system = _PROMPT_PATH.read_text(encoding="utf-8")

    def _findings_under_review(self, audited: AuditedAnswer) -> list[Finding]:
        invalid_citations = {
            r.citation for r in audited.audit_results if not r.validated
        }
        selected = [
            f
            for f in audited.answer.findings
            if f.severity == "high"
            or (
                audited.verdict != AuditVerdict.PASS
                and any(c in invalid_citations for c in f.citations)
            )
        ]
        return selected or list(audited.answer.findings)

    def _user_payload(self, audited: AuditedAnswer, context: Context) -> str:
        findings = self._findings_under_review(audited)
        return json.dumps(
            {
                "answer_text": audited.answer.text,
                "findings_under_review": [
                    {
                        "text": f.text,
                        "citations": [
                            {
                                "norma": str(c.norma),
                                "articulo": c.articulo,
                                "apartado": c.apartado,
                                "text": c.text,
                            }
                            for c in f.citations
                        ],
                        "severity": f.severity,
                    }
                    for f in findings
                ],
                "audit_results": [
                    {"validated": r.validated, "reason": r.reason}
                    for r in audited.audit_results
                ],
                "retrieved_context": [
                    {
                        "articulo": ch.articulo,
                        "apartado": ch.apartado,
                        "text": ch.text,
                    }
                    for ch in context.chunks
                ],
            },
            ensure_ascii=False,
        )

    def _one_judge(self, mode: str, payload: str) -> JudgeVote:
        try:
            result = router.complete(
                messages=[{"role": "user", "content": payload}],
                system=self._system,
                tools=[_VOTE_TOOL],
                tool_choice={"type": "tool", "name": "cast_vote"},
                model_choice=mode,
                max_tokens=600,
            )
            data = result.tool_use_input
            if not isinstance(data, dict) or data.get("vote") not in _VOTE_MAP:
                raise ValueError(f"judge {mode} emitted no valid vote")
            return JudgeVote(
                model_id=result.model_id,
                provider=router._MODE_MAP[mode].provider,
                vote=_VOTE_MAP[data["vote"]],
                reason=str(data.get("reason", ""))[:500],
                ok=True,
                error_category=None,
            )
        except Exception as e:  # advisory: never break the turn
            logger.warning("council judge %s failed: %s", mode, type(e).__name__)
            return JudgeVote(
                model_id=router._MODE_MAP[mode].model_id,
                provider=router._MODE_MAP[mode].provider,
                vote=AuditVerdict.REQUIRES_HUMAN_REVIEW,
                reason="judge_failed",
                ok=False,
                error_category=type(e).__name__,
            )

    def review(
        self,
        audited: AuditedAnswer,
        context: Context,
        *,
        trigger_reason: Literal[
            "auditor_rhr", "high_severity", "api_override", "not_triggered"
        ],
    ) -> CouncilReview:
        payload = self._user_payload(audited, context)
        votes = [self._one_judge(m, payload) for m in _JUDGE_MODES]
        verdict, label = self._policy.aggregate(votes)
        n_ok = sum(1 for v in votes if v.ok)
        reason = (
            "council_unavailable: 0/3 judges responded"
            if n_ok == 0
            else f"{n_ok}/3 judges ok; {label} -> {verdict.value}"
        )
        return CouncilReview(
            triggered=True,
            trigger_reason=trigger_reason,
            judges=votes,
            council_verdict=verdict,
            agreement=label,
            diverges_from_auditor=verdict != audited.verdict,
            reason=reason,
        )
```

(Add `JudgeVote` to the existing `from regulaitor.citation.schemas import ...` line in this file.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/agents/test_council_agent.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Run the full agents suite (regression)**

Run: `python -m pytest tests/unit/agents/ -v`
Expected: PASS (no existing agent test broken).

- [ ] **Step 6: Commit**

```bash
git add src/regulaitor/agents/council.py tests/unit/agents/test_council_agent.py
SKIP=gitleaks git commit -m "feat(h13): CouncilAgent.review (3-judge, advisory, degrade-safe)"
```

---

### Task 8: Graph trigger predicate + routing (pure functions)

**Files:**
- Modify: `src/regulaitor/orchestration/graph.py`
- Test: `tests/unit/orchestration/test_council_routing.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/orchestration/test_council_routing.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

from langgraph.graph import END

from regulaitor.citation.schemas import (
    Answer,
    AuditedAnswer,
    AuditVerdict,
    Citation,
    Finding,
)
from regulaitor.orchestration import graph as g
from regulaitor.orchestration.state import ChatState


def _state(verdict=AuditVerdict.PASS, severity="info", override=None, audited=True):
    s = ChatState(case_id="c", query="q", corpus="ai_act", language="es")
    s.council_override = override
    if audited:
        ans = Answer(
            query="q",
            language="es",
            text="t",
            findings=[
                Finding(
                    text="f",
                    citations=[
                        Citation(
                            norma="ai_act",
                            articulo="6",
                            apartado="1",
                            language="es",
                            text="x",
                        )
                    ],
                    severity=severity,
                )
            ],
        )
        s.audited_answer = AuditedAnswer(
            answer=ans, verdict=verdict, audit_results=[], reason=None
        )
    return s


def test_auto_trigger_on_rhr():
    s = _state(verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW)
    assert g._council_triggered(s) is True
    assert g._council_trigger_reason(s) == "auditor_rhr"


def test_auto_trigger_on_high_severity():
    s = _state(verdict=AuditVerdict.PASS, severity="high")
    assert g._council_triggered(s) is True
    assert g._council_trigger_reason(s) == "high_severity"


def test_no_trigger_on_clean_pass():
    s = _state(verdict=AuditVerdict.PASS, severity="info")
    assert g._council_triggered(s) is False
    assert g._route_after_audit(s) == END


def test_override_true_forces_trigger():
    s = _state(verdict=AuditVerdict.PASS, severity="info", override=True)
    assert g._council_triggered(s) is True
    assert g._council_trigger_reason(s) == "api_override"


def test_override_false_blocks_trigger_even_on_rhr():
    s = _state(verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW, override=False)
    assert g._council_triggered(s) is False


def test_no_trigger_without_audited_answer():
    s = _state(audited=False)
    assert g._council_triggered(s) is False
    assert g._route_after_audit(s) == END


def test_route_returns_council_when_triggered():
    s = _state(verdict=AuditVerdict.REQUIRES_HUMAN_REVIEW)
    assert g._route_after_audit(s) == "council"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/orchestration/test_council_routing.py -v`
Expected: FAIL (`AttributeError: module ... has no attribute '_council_triggered'`).

- [ ] **Step 3: Implement the predicate + router**

In `src/regulaitor/orchestration/graph.py` add these functions (place near `_route_after_injection`):

```python
def _council_trigger_reason(state: ChatState) -> str:
    """Why the Council would run, or 'not_triggered'. Never raises."""
    aud = state.audited_answer
    if aud is None or state.injection_blocked:
        return "not_triggered"
    if state.council_override is False:
        return "not_triggered"
    if state.council_override is True:
        return "api_override"
    if aud.verdict == AuditVerdict.REQUIRES_HUMAN_REVIEW:
        return "auditor_rhr"
    if any(f.severity == "high" for f in aud.answer.findings):
        return "high_severity"
    return "not_triggered"


def _council_triggered(state: ChatState) -> bool:
    return _council_trigger_reason(state) != "not_triggered"


def _route_after_audit(state: ChatState) -> str:
    return "council" if _council_triggered(state) else END
```

Add the import at the top of `graph.py` (the existing schema import block):

```python
from regulaitor.citation.schemas import AuditVerdict
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/orchestration/test_council_routing.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/orchestration/graph.py tests/unit/orchestration/test_council_routing.py
SKIP=gitleaks git commit -m "feat(h13): council trigger predicate + conditional router"
```

---

### Task 9: Graph wiring — `_council_node`, edges, `run(council_override)`

**Files:**
- Modify: `src/regulaitor/orchestration/graph.py`
- Test: `tests/integration/test_council_chat_flow.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_council_chat_flow.py`:

```python
from __future__ import annotations

from unittest.mock import patch

from regulaitor.citation.schemas import AuditVerdict, CouncilReview, JudgeVote
from regulaitor.orchestration import graph as g


def _council_review(verdict=AuditVerdict.BLOCK, diverges=True):
    return CouncilReview(
        triggered=True,
        trigger_reason="auditor_rhr",
        judges=[
            JudgeVote(
                model_id="m",
                provider="p",
                vote=verdict,
                reason="r",
                ok=True,
                error_category=None,
            )
        ],
        council_verdict=verdict,
        agreement="degraded",
        diverges_from_auditor=diverges,
        reason="test",
    )


def test_council_node_attaches_review_without_changing_verdict():
    from regulaitor.citation.schemas import (
        Answer,
        AuditedAnswer,
        Citation,
        Finding,
    )
    from regulaitor.orchestration.state import ChatState

    ans = Answer(
        query="q",
        language="es",
        text="t",
        findings=[
            Finding(
                text="f",
                citations=[
                    Citation(
                        norma="ai_act",
                        articulo="6",
                        apartado="1",
                        language="es",
                        text="x",
                    )
                ],
                severity="high",
            )
        ],
    )
    state = ChatState(case_id="c", query="q", corpus="ai_act", language="es")
    state.audited_answer = AuditedAnswer(
        answer=ans, verdict=AuditVerdict.PASS, audit_results=[], reason=None
    )
    with patch.object(g, "_council") as mk:
        mk.return_value.review.return_value = _council_review()
        out = g._council_node(state)
    assert isinstance(out["council_review"], CouncilReview)
    # Verdict is NOT in the node's return dict -> graph never mutates it.
    assert "verdict" not in out
    assert "audited_answer" not in out


def test_council_node_swallows_exceptions():
    from regulaitor.citation.schemas import (
        Answer,
        AuditedAnswer,
        Citation,
        Finding,
    )
    from regulaitor.orchestration.state import ChatState

    ans = Answer(
        query="q",
        language="es",
        text="t",
        findings=[
            Finding(
                text="f",
                citations=[
                    Citation(
                        norma="ai_act",
                        articulo="6",
                        apartado="1",
                        language="es",
                        text="x",
                    )
                ],
                severity="high",
            )
        ],
    )
    state = ChatState(case_id="c", query="q", corpus="ai_act", language="es")
    state.audited_answer = AuditedAnswer(
        answer=ans, verdict=AuditVerdict.PASS, audit_results=[], reason=None
    )
    with patch.object(g, "_council") as mk:
        mk.return_value.review.side_effect = RuntimeError("boom")
        out = g._council_node(state)
    assert out == {}  # advisory: failure yields no state change


def test_run_threads_council_override(monkeypatch):
    seen = {}

    class _FakeCompiled:
        def invoke(self, initial):
            seen["override"] = initial.council_override
            initial.audited_answer = None
            return initial.model_dump()

    monkeypatch.setattr(g, "_compiled_graph", lambda: _FakeCompiled())
    g.run(query="q", corpus="ai_act", language="es", case_id="c", council_override=True)
    assert seen["override"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/integration/test_council_chat_flow.py -v`
Expected: FAIL (`AttributeError: ... '_council_node'` / `run() got an unexpected keyword argument 'council_override'`).

- [ ] **Step 3: Implement node + lazy agent + edges + run kwarg**

In `src/regulaitor/orchestration/graph.py`:

Add the lazy agent helper (next to `_auditor`):

```python
@functools.lru_cache(maxsize=1)
def _council() -> "CouncilAgent":
    from regulaitor.agents.council import CouncilAgent

    return CouncilAgent()
```

Add the node (after `_auditor_node`):

```python
def _council_node(state: ChatState) -> dict[str, Any]:
    """Advisory: attaches council_review, NEVER returns verdict/audited_answer.
    Any failure is swallowed (returns {}) so the chat turn is unaffected."""
    if state.audited_answer is None:
        return {}
    try:
        review = _council().review(
            state.audited_answer,
            state.context,
            trigger_reason=_council_trigger_reason(state),  # type: ignore[arg-type]
        )
        return {"council_review": review}
    except Exception as e:  # noqa: BLE001 advisory layer must not break the turn
        logger.warning("council_node failed (swallowed): %s", type(e).__name__)
        return {}
```

In `build_graph()` add the node and rewire the auditor edge:

```python
    g.add_node("council", _council_node)
    ...
    # replace `g.add_edge("auditor", END)` with:
    g.add_conditional_edges(
        "auditor",
        _route_after_audit,
        {"council": "council", END: END},
    )
    g.add_edge("council", END)
```

Change `run()` signature + initial state:

```python
def run(
    *, query: str, corpus: str, language: str, case_id: str,
    council_override: bool | None = None,
) -> ChatState:
    ...
        initial = ChatState(
            case_id=case_id,
            query=query,
            corpus=cast(Norma, corpus),
            language=cast(Language, language),
            council_override=council_override,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/integration/test_council_chat_flow.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Regression — existing chat flow untouched**

Run: `python -m pytest tests/unit/orchestration/ tests/integration/ -v`
Expected: PASS (all existing chat/document tests still green; verdict path unchanged).

- [ ] **Step 6: Commit**

```bash
git add src/regulaitor/orchestration/graph.py tests/integration/test_council_chat_flow.py
SKIP=gitleaks git commit -m "feat(h13): wire council node + conditional edge + run() override"
```

---

### Task 10: Observability — council summary in the trace record

**Files:**
- Modify: `src/regulaitor/orchestration/graph.py`
- Modify: `src/regulaitor/observability/langfuse_client.py` (allowlist only)
- Test: `tests/unit/orchestration/test_trace_record_council.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/orchestration/test_trace_record_council.py`:

```python
from __future__ import annotations

from regulaitor.citation.schemas import AuditVerdict, CouncilReview, JudgeVote
from regulaitor.orchestration import graph as g
from regulaitor.orchestration.state import ChatState


def test_trace_record_includes_council_summary():
    s = ChatState(case_id="c", query="secret query text", corpus="ai_act", language="es")
    s.council_review = CouncilReview(
        triggered=True,
        trigger_reason="auditor_rhr",
        judges=[
            JudgeVote(
                model_id="m", provider="p", vote=AuditVerdict.BLOCK,
                reason="r", ok=True, error_category=None,
            )
        ],
        council_verdict=AuditVerdict.BLOCK,
        agreement="degraded",
        diverges_from_auditor=True,
        reason="x",
    )
    rec = g._trace_record(s, 100)
    assert rec["council_triggered"] is True
    assert rec["council_verdict"] == "block"
    assert rec["council_diverges"] is True
    assert rec["n_judges_ok"] == 1
    # SSDLC: no raw query text anywhere in the record
    assert "secret query text" not in str(rec)


def test_trace_record_council_absent_when_no_review():
    s = ChatState(case_id="c", query="q", corpus="ai_act", language="es")
    rec = g._trace_record(s, 10)
    assert rec["council_triggered"] is False
    assert rec["council_verdict"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/orchestration/test_trace_record_council.py -v`
Expected: FAIL (`KeyError: 'council_triggered'`).

- [ ] **Step 3: Implement**

In `src/regulaitor/orchestration/graph.py` `_trace_record`, before the final `return {...}`, compute:

```python
    cr = state.council_review
    council_triggered = cr is not None and cr.triggered
    council_verdict = cr.council_verdict.value if cr is not None else None
    council_diverges = cr.diverges_from_auditor if cr is not None else False
    n_judges_ok = sum(1 for j in cr.judges if j.ok) if cr is not None else 0
```

Add these four keys to the returned dict:

```python
        "council_triggered": council_triggered,
        "council_verdict": council_verdict,
        "council_diverges": council_diverges,
        "n_judges_ok": n_judges_ok,
```

In `src/regulaitor/observability/langfuse_client.py`, add the four new keys to the redaction allowlist set (categorical metadata, no user text — same policy as `verdict`/`n_findings`): `council_triggered`, `council_verdict`, `council_diverges`, `n_judges_ok`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/orchestration/test_trace_record_council.py tests/unit/observability/ -v`
Expected: PASS (incl. existing observability redaction tests still green).

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/orchestration/graph.py src/regulaitor/observability/langfuse_client.py tests/unit/orchestration/test_trace_record_council.py
SKIP=gitleaks git commit -m "feat(h13): council summary in trace record (metadata-only, allowlisted)"
```

---

### Task 11: API surface — request flag, notice, redacted DTO

**Files:**
- Modify: `src/regulaitor/api/schemas.py`
- Modify: `src/regulaitor/api/routes_ask.py`
- Test: `tests/unit/api/test_council_dto.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/api/test_council_dto.py`:

```python
from __future__ import annotations

from regulaitor.api.schemas import AskRequest, council_review_to_dto, council_notice
from regulaitor.citation.schemas import AuditVerdict, CouncilReview, JudgeVote


def _cr(diverges):
    return CouncilReview(
        triggered=True,
        trigger_reason="auditor_rhr",
        judges=[
            JudgeVote(
                model_id="claude-haiku-4-5-20251001",
                provider="anthropic",
                vote=AuditVerdict.BLOCK,
                reason="no soporta",
                ok=True,
                error_category=None,
            )
        ],
        council_verdict=AuditVerdict.BLOCK,
        agreement="degraded",
        diverges_from_auditor=diverges,
        reason="x",
    )


def test_ask_request_accepts_council_flag():
    assert AskRequest(query="q", corpus="ai_act", language="es").council is None
    assert (
        AskRequest(query="q", corpus="ai_act", language="es", council=True).council
        is True
    )


def test_notice_present_only_when_diverges():
    assert council_notice(_cr(True)) is not None
    assert council_notice(_cr(False)) is None
    assert council_notice(None) is None


def test_dto_redacts_to_allowlisted_fields():
    dto = council_review_to_dto(_cr(True))
    assert dto.council_verdict == "block"
    assert dto.diverges_from_auditor is True
    j = dto.judges[0]
    assert j.model_id == "claude-haiku-4-5-20251001"
    assert j.vote == "block"
    # no raw answer/query text leaks through the DTO
    assert not hasattr(j, "answer")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/api/test_council_dto.py -v`
Expected: FAIL (`ImportError: cannot import name 'council_review_to_dto'`).

- [ ] **Step 3: Implement DTO + converter + notice + request flag**

In `src/regulaitor/api/schemas.py`:

Add `council` to `AskRequest` (after `language`):

```python
    council: bool | None = None
```

Add DTOs + helpers (after `AskResponse`, import `CouncilReview` from citation schemas at top):

```python
class JudgeVoteDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    model_id: str
    provider: str
    vote: Literal["pass", "block", "requires_human_review"]
    reason: str
    ok: bool
    error_category: str | None


class CouncilReviewDTO(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    triggered: bool
    trigger_reason: Literal["auditor_rhr", "high_severity", "api_override", "not_triggered"]
    judges: list[JudgeVoteDTO]
    council_verdict: Literal["pass", "block", "requires_human_review"]
    agreement: Literal["unanimous", "majority", "split", "degraded"]
    diverges_from_auditor: bool
    reason: str


def council_review_to_dto(cr: CouncilReview) -> CouncilReviewDTO:
    return CouncilReviewDTO(
        triggered=cr.triggered,
        trigger_reason=cr.trigger_reason,
        judges=[
            JudgeVoteDTO(
                model_id=j.model_id,
                provider=j.provider,
                vote=j.vote.value,
                reason=j.reason,
                ok=j.ok,
                error_category=j.error_category,
            )
            for j in cr.judges
        ],
        council_verdict=cr.council_verdict.value,
        agreement=cr.agreement,
        diverges_from_auditor=cr.diverges_from_auditor,
        reason=cr.reason,
    )


def council_notice(cr: CouncilReview | None) -> str | None:
    if cr is None or not cr.diverges_from_auditor:
        return None
    return (
        "Hallazgo marcado por revisión colegiada (Council): los jueces "
        "independientes discreparon de la validación automática. El veredicto "
        "no cambia; se recomienda revisión humana."
    )
```

Add the two optional fields to `AskResponse`:

```python
    council_notice: str | None = None
    council: CouncilReviewDTO | None = None
```

Update `to_ask_response(state, response_time_ms)` to populate them from `state.council_review`:

```python
        council_notice=council_notice(state.council_review),
        council=(
            council_review_to_dto(state.council_review)
            if state.council_review is not None
            else None
        ),
```

In `src/regulaitor/api/routes_ask.py`, pass the flag into the graph run (find the `graph.run(...)` call):

```python
    state = run(
        query=req.query,
        corpus=req.corpus,
        language=req.language,
        case_id=case_id,
        council_override=req.council,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/api/ -v`
Expected: PASS (incl. existing API contract tests — `AskResponse` new fields are optional, default None, so existing schemathesis/contract tests stay green).

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/api/schemas.py src/regulaitor/api/routes_ask.py tests/unit/api/test_council_dto.py
SKIP=gitleaks git commit -m "feat(h13): API council flag + redacted CouncilReviewDTO + notice"
```

---

### Task 12: Streamlit — prominent notice + optional detail expander

**Files:**
- Modify: `src/regulaitor/ui_streamlit/tab_ask.py`
- Test: `tests/unit/ui_streamlit/test_council_render.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/ui_streamlit/test_council_render.py`:

```python
from __future__ import annotations

from regulaitor.ui_streamlit.tab_ask import council_banner_text


def test_banner_text_present_when_notice():
    out = council_banner_text({"council_notice": "AVISO", "council": {"agreement": "split"}})
    assert "AVISO" in out


def test_banner_text_none_when_absent():
    assert council_banner_text({"council_notice": None}) is None
    assert council_banner_text({}) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/ui_streamlit/test_council_render.py -v`
Expected: FAIL (`ImportError: cannot import name 'council_banner_text'`).

- [ ] **Step 3: Implement the pure helper + wire it**

In `src/regulaitor/ui_streamlit/tab_ask.py` add the pure helper (testable without Streamlit):

```python
def council_banner_text(response: dict) -> str | None:
    """Return the Council notice string to display, or None. Pure (testable)."""
    return response.get("council_notice")
```

Where the response is rendered (after the verdict block), add the Streamlit calls (not unit-tested — Streamlit runtime):

```python
    _notice = council_banner_text(response)
    if _notice:
        st.warning(_notice)
        with st.expander("Council (evidencia) — votos de los jueces"):
            st.json(response.get("council"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/ui_streamlit/test_council_render.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/regulaitor/ui_streamlit/tab_ask.py tests/unit/ui_streamlit/test_council_render.py
SKIP=gitleaks git commit -m "feat(h13): Streamlit council notice banner + detail expander"
```

---

### Task 13: `scripts/council_eval.py` — divergence-study harness ($0, mocked test)

**Files:**
- Create: `src/../scripts/council_eval.py` → exact path `scripts/council_eval.py`
- Modify: `.gitignore`
- Test: `tests/unit/scripts/test_council_eval.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/scripts/test_council_eval.py`:

```python
from __future__ import annotations

from regulaitor.citation.schemas import AuditVerdict, CouncilReview, JudgeVote
from scripts.council_eval import summarize_divergence


def _row(auditor, council, diverges, triggered_auto):
    cr = CouncilReview(
        triggered=True,
        trigger_reason="auditor_rhr" if triggered_auto else "api_override",
        judges=[
            JudgeVote(
                model_id="m", provider="p", vote=council,
                reason="r", ok=True, error_category=None,
            )
        ],
        council_verdict=council,
        agreement="degraded",
        diverges_from_auditor=diverges,
        reason="x",
    )
    return {"auditor_verdict": auditor, "council": cr}


def test_summarize_counts_subset_and_divergence():
    rows = [
        _row(AuditVerdict.PASS, AuditVerdict.BLOCK, True, True),
        _row(AuditVerdict.PASS, AuditVerdict.PASS, False, False),
        _row(AuditVerdict.REQUIRES_HUMAN_REVIEW, AuditVerdict.BLOCK, True, True),
    ]
    s = summarize_divergence(rows)
    assert s["n_total"] == 3
    assert s["n_auto_triggered"] == 2
    assert s["n_diverged"] == 2
    assert s["n_auditor_pass_council_flagged"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/scripts/test_council_eval.py -v`
Expected: FAIL (`ModuleNotFoundError: scripts.council_eval`).

- [ ] **Step 3: Implement the harness**

Create `scripts/council_eval.py`:

```python
"""H13 — Council divergence-study harness.

USER-GATED: forcing the Council over the gold set spends real
Anthropic/OpenAI/Groq credit. Run only on explicit OK (the H12 T10
pattern). $0 unit tests mock the graph; this module's pure summarizer
is what they exercise.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from regulaitor.citation.schemas import AuditVerdict

_REPORT_PATH = Path(__file__).resolve().parents[1] / "evals/reports/latest.council.md"


def summarize_divergence(rows: list[dict]) -> dict:
    """Pure: aggregate per-case auditor-vs-council rows."""
    n_total = len(rows)
    n_auto = sum(1 for r in rows if r["council"].trigger_reason != "api_override")
    n_div = sum(1 for r in rows if r["council"].diverges_from_auditor)
    n_flagged = sum(
        1
        for r in rows
        if r["auditor_verdict"] == AuditVerdict.PASS
        and r["council"].council_verdict != AuditVerdict.PASS
    )
    return {
        "n_total": n_total,
        "n_auto_triggered": n_auto,
        "n_diverged": n_div,
        "n_auditor_pass_council_flagged": n_flagged,
    }


def render_report(summary: dict, rows: list[dict]) -> str:
    lines = [
        "# H13 — Council Divergence Study",
        "",
        "> Advisory Council (verdict unchanged). Honest reframe of the §16.3",
        "> 'Done when': this study IS the deliverable (decisions §H13).",
        "",
        f"- Cases: {summary['n_total']}",
        f"- Auto-triggered subset (RHR or high-severity): {summary['n_auto_triggered']}",
        f"- Council diverged from mechanical Auditor: {summary['n_diverged']}",
        f"- Auditor=PASS but Council flagged: "
        f"{summary['n_auditor_pass_council_flagged']}",
        "",
        "| case | auditor | council | agreement | diverges |",
        "|---|---|---|---|---|",
    ]
    for i, r in enumerate(rows, 1):
        cr = r["council"]
        lines.append(
            f"| {i} | {r['auditor_verdict'].value} | "
            f"{cr.council_verdict.value} | {cr.agreement} | "
            f"{cr.diverges_from_auditor} |"
        )
    return "\n".join(lines) + "\n"


def _run_gold(limit: int | None) -> list[dict]:  # pragma: no cover - paid path
    from evals.harness import load_gold_set  # read-only reuse
    from regulaitor.orchestration import graph

    rows: list[dict] = []
    for case in load_gold_set(kind="chat")[: limit or None]:
        state = graph.run(
            query=case.entrada,
            corpus=case.corpus_esperado,
            language="es",
            case_id=case.id,
            council_override=True,
        )
        if state.audited_answer is None or state.council_review is None:
            continue
        rows.append(
            {
                "auditor_verdict": state.audited_answer.verdict,
                "council": state.council_review,
            }
        )
    return rows


def main() -> None:  # pragma: no cover - paid path
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    rows = _run_gold(args.limit)
    summary = summarize_divergence(rows)
    _REPORT_PATH.write_text(render_report(summary, rows), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":  # pragma: no cover
    main()
```

(If `evals.harness.load_gold_set` has a different name/signature, adapt the import in `_run_gold` to the actual gold-set loader — it is read-only; do not modify the harness. Confirm the symbol with `grep -n "def load_gold" evals/harness.py` before running Task 14.)

In `.gitignore`, add the tracked-evidence exception next to the H12 ones:

```gitignore
!evals/reports/latest.council.md
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/scripts/test_council_eval.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite + coverage gate**

Run: `python -m pytest -q`
Expected: PASS; coverage ≥90% (the `# pragma: no cover` paid paths are excluded by design).

- [ ] **Step 6: Commit**

```bash
git add scripts/council_eval.py tests/unit/scripts/test_council_eval.py .gitignore
SKIP=gitleaks git commit -m "feat(h13): council_eval divergence-study harness ($0 summarizer tested)"
```

---

### Task 14: USER-GATED divergence-study run → `docs/council_analysis.md`

**Files:**
- Create: `docs/council_analysis.md`
- Create (generated, tracked): `evals/reports/latest.council.md`

> **GATE:** This task spends real credit (Haiku + GPT-4o + Llama-Groq over the
> chat gold set, `council_override=True` so every case calls 3 judges). Do
> NOT run without explicit user OK. Before the run: confirm the gold-set
> loader symbol (Task 13 note), estimate spend (≈ 30 chat cases × 3 judges;
> Haiku ~cheap, GPT-4o moderate, Groq free-tier may 429 → degrade), present
> the estimate, and wait for the user's go (the H12 T10 pattern).

- [ ] **Step 1: Pre-flight (no spend)**

Run: `grep -n "def load_gold" evals/harness.py` and adjust `scripts/council_eval.py::_run_gold` if the loader differs. Run `python -m pytest tests/unit/scripts/test_council_eval.py -q` to confirm the summarizer still passes.

- [ ] **Step 2: Present spend estimate + get explicit OK**

State the estimated cost and the known Groq free-tier contamination risk (H12 I-2). **Wait for the user's explicit "run it".** If declined, H13 closes with the harness + a documented "run deferred" note in decisions §H13 (honest, no fabricated numbers — §22.22).

- [ ] **Step 3: Run the gated study**

Run: `python -m scripts.council_eval`
Expected: writes `evals/reports/latest.council.md`; prints the summary JSON.

- [ ] **Step 4: Write `docs/council_analysis.md`**

Author `docs/council_analysis.md` mirroring the honest/caveated tone of `docs/cost_analysis.md`: method (advisory Council, forced override, no Ragas re-score), the divergence table + summary numbers from the run, per-judge abstain rate (Groq cap if hit — documented honestly, **no re-run**), the explicit reading ("advisory ⇒ verdict unchanged by construction; this characterizes the calibration gap for H15"), and caveats. Cite `evals/reports/latest.council.md`.

- [ ] **Step 5: Commit**

```bash
git add docs/council_analysis.md evals/reports/latest.council.md
SKIP=gitleaks git commit -m "docs(h13): council divergence study (gated run, honest/caveated)"
```

---

### Task 15: Closure — ADR 0014 + decisions §H13 + evidence_matrix + CLAUDE.md + memory + tag

**Files:**
- Create: `docs/adr/0014-council-of-judges.md`
- Modify: `docs/technical_decisions_log.md`, `docs/evidence_matrix.md`, `CLAUDE.md`
- Modify: memory `C:\Users\enriq\.claude\projects\c--Users-enriq-Documents-regulaitor-regulaitor\memory\`

- [ ] **Step 1: ADR 0014**

Create `docs/adr/0014-council-of-judges.md` mirroring ADR 0013's structure (Status/Date/Deciders/Companion ADRs; Context; the 7 decisions D1–D7 from the spec incl. advisory-authority + the H15 promotion seam; Consequences positive/negative-honest incl. the divergence-study reframe + any Groq contamination; Alternatives rejected; References). Use the squash placeholder `<squash-sha>` (post-merge populated, the H10–H12 pattern).

- [ ] **Step 2: decisions log §H13**

Append `## H13 — Council of Judges (cerrado 2026-05-17, squash \`<squash-sha>\`, tag \`v0.1.3-h13\`)` to `docs/technical_decisions_log.md`: the 7 decisions + the honest "Done when" reframe (advisory ⇒ no output-improvement claim; success = divergence study) + the explicit H15 promotion path (flip `_COUNCIL_BINDING` + select `MonotonicEscalatePolicy`) + the gated-run outcome (numbers or "deferred") + skills (none new; `cost-accounting` stays H17).

- [ ] **Step 3: evidence_matrix + CLAUDE.md**

In `docs/evidence_matrix.md`: add the Council row under Módulo 2 (`agents/council.py` ✅ H13, advisory, caveated) + any new follow-up (document-mode Council → future; binding promotion → H15). In `CLAUDE.md` §27: add the `**H13** — … cerrado (2026-05-17). Tag v0.1.3-h13. …` entry (mirror the H12 entry density) and change **Hito siguiente** to **H14** (NIS2 + DORA corpus).

- [ ] **Step 4: Commit closure docs**

```bash
git add docs/adr/0014-council-of-judges.md docs/technical_decisions_log.md docs/evidence_matrix.md CLAUDE.md
SKIP=gitleaks git commit -m "docs(h13): close milestone — ADR 0014 + decisions §H13 + evidence_matrix + CLAUDE.md"
```

- [ ] **Step 5: Final whole-branch review + finish branch**

Hand off to `superpowers:finishing-a-development-branch` (verify tests → user picks finish option → squash-merge `feat(h13): council of judges` → tag `v0.1.3-h13` → post-merge `docs(h13): populate post-merge SHA` populating `<squash-sha>` in ADR 0014 / decisions §H13 / CLAUDE.md → delete branch).

- [ ] **Step 6: Memory roll-forward (after merge)**

Create `memory/h13_closed_h14_starting.md` (snapshot: H13 closed, advisory Council live, divergence-study outcome, H15 promotion seam, H14 next = NIS2+DORA), delete `memory/h12_closed_h13_starting.md`, update `memory/MEMORY.md` index line.

---

## Self-Review

**1. Spec coverage:** D1 advisory+notice+seam → Tasks 4,5,9,11,12 (verdict never in node return; `council_notice`; `_COUNCIL_BINDING=False` + monotonic tested). D2 trigger union+override → Task 8. D3 three judges + degrade → Tasks 1,7. D4 chat-only → no document_graph task (explicitly out). D5 divergence study + gated → Tasks 13,14. D6 Approach 1 node → Task 9. D7 router judge mode → Task 1. Observability §5 → Task 10. Schemas §3 → Task 2,3. API §4 → Task 11. Closure §7 → Task 15. All spec sections mapped.

**2. Placeholder scan:** No "TBD"/"add error handling"/"similar to Task N". The two paid paths in Tasks 13/14 are marked `# pragma: no cover` and explicitly user-gated (not a placeholder — a deliberate gated boundary, the H12 pattern). The one soft spot (gold-set loader symbol) has an explicit pre-flight grep step (Task 13 note + Task 14 Step 1) rather than an unverified assumption.

**3. Type consistency:** `CouncilReview`/`JudgeVote` fields identical across Tasks 2,7,8,9,10,11,13. `AggregationPolicy.aggregate -> (AuditVerdict, AgreementLabel)` consistent Tasks 4,5,7. `_council_trigger_reason`/`_council_triggered`/`_route_after_audit` consistent Tasks 8,9. `CouncilAgent(policy=None).review(audited, context, *, trigger_reason)` consistent Tasks 7,9. `run(..., council_override=None)` consistent Tasks 9,11,13. `council_review_to_dto`/`council_notice` consistent Tasks 11,12. No drift.
