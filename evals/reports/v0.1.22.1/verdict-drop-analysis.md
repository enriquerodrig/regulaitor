# v0.1.22.1 Verdict-Match Drop Analysis

**Date:** 2026-05-25T19:53:15.001821Z
**Spec:** docs/superpowers/specs/2026-05-25-v0.1.22.1-verdict-diagnostic-design.md
**Methodology:** $0 cache mining over v0.1.22 checkpoints + gold + per_citation_audits trail
**Cohort:** chat-001..030 (v0.1.22-prod, 16 RHR cases)

## Aggregate hypothesis attribution

| Hypothesis | Count | % of 16 |
|---|---|---|
| H1 | 10 | 62.5% |
| H2 | 0 | 0.0% |
| H3 | 0 | 0.0% |
| H4 | 1 | 6.2% |
| mixed | 5 | 31.2% |

**Dominant hypothesis**: H1 (10 cases, 62.5%)

## Per-case detail table

| case_id | actual | expected | match | n_emitted | n_invalid | gold_articles | emitted_articles | intersect | dominant_H | notes |
|---|---|---|---|---|---|---|---|---|---|---|
| chat-003 | requires_human_review | pass | ❌ | 4 | 3 | 9 | 16,17,25 | (none) | H4 | wrong articles |
| chat-005 | requires_human_review | pass | ❌ | 4 | 1 | 11 | 11,23,72 | 11 | mixed |  |
| chat-007 | requires_human_review | pass | ❌ | 5 | 1 | 13 | 26,27 | (none) | mixed |  |
| chat-008 | requires_human_review | pass | ❌ | 5 | 1 | 14 | 14 | 14 | mixed |  |
| chat-013 | requires_human_review | requires_human_review | ✅ | 4 | 1 | 6 | 113,6 | 6 | mixed |  |
| chat-016 | requires_human_review | pass | ❌ | 4 | 3 | 6 | 13,28,6 | 6 | H1 | validator mismatch |
| chat-017 | requires_human_review | pass | ❌ | 7 | 4 | 5 | 5 | 5 | H1 | validator mismatch |
| chat-018 | requires_human_review | pass | ❌ | 6 | 3 | 7 | 13,6,7 | 7 | H1 | validator mismatch |
| chat-019 | requires_human_review | pass | ❌ | 6 | 4 | 9 | 9 | 9 | H1 | validator mismatch |
| chat-021 | requires_human_review | pass | ❌ | 4 | 3 | 15 | 15 | 15 | H1 | validator mismatch |
| chat-022 | requires_human_review | pass | ❌ | 8 | 4 | 17 | 17 | 17 | H1 | validator mismatch |
| chat-023 | requires_human_review | pass | ❌ | 3 | 2 | 25 | 25 | 25 | H1 | validator mismatch |
| chat-024 | requires_human_review | pass | ❌ | 5 | 4 | 28 | 28 | 28 | H1 | validator mismatch |
| chat-025 | requires_human_review | pass | ❌ | 4 | 3 | 32 | 25,32 | 32 | H1 | validator mismatch |
| chat-026 | requires_human_review | requires_human_review | ✅ | 3 | 2 | 33 | 33 | 33 | H1 | validator mismatch |
| chat-030 | requires_human_review | block | ❌ | 3 | 1 | (none) | 83 | (none) | mixed |  |

## Per-case detail blocks

### chat-003 (Hypothesis H4)

- **Verdict**: actual=`requires_human_review` expected=`pass` (match: ❌)
- **Citations**: emitted=['17.1', '17.2', '16', '25.1'] expected=['9.1', '9.2']
- **Invalid count**: 3
- **per_citation_audits**:
  - 17.1: ❌ invalid (text_not_in_apartado: ai_act art. 17.1 es; cited text not found after normalization (666 chars vs 2876 chars apartado).)
  - 17.2: ✅ valid (None)
  - 16: ❌ invalid (text_not_in_article: ai_act art. 16 es; cited text not found after normalization (912 chars vs 1805 chars article).)
  - 25.1: ❌ invalid (text_not_in_apartado: ai_act art. 25.1 es; cited text not found after normalization (653 chars vs 1096 chars apartado).)
- **Reasoning for H4**:
  No overlap between emitted articles and gold-expected articles. Tier 1 correctly escalates; Sonnet misunderstood query or retrieved wrong articles.

### chat-005 (Hypothesis mixed)

- **Verdict**: actual=`requires_human_review` expected=`pass` (match: ❌)
- **Citations**: emitted=['11.1', '11.2', '72.3', '23.1'] expected=['11.1']
- **Invalid count**: 1
- **per_citation_audits**:
  - 11.1: ✅ valid (None)
  - 11.2: ✅ valid (None)
  - 72.3: ✅ valid (None)
  - 23.1: ❌ invalid (text_not_in_apartado: ai_act art. 23.1 es; cited text not found after normalization (283 chars vs 782 chars apartado).)
- **Reasoning for mixed**:
  Multiple hypotheses matched or case unclassifiable. Manual review needed.

### chat-007 (Hypothesis mixed)

- **Verdict**: actual=`requires_human_review` expected=`pass` (match: ❌)
- **Citations**: emitted=['26.7', '26.11', '26.5', '27.1', '26.8'] expected=['13.1', '13.2']
- **Invalid count**: 1
- **per_citation_audits**:
  - 26.7: ✅ valid (None)
  - 26.11: ✅ valid (None)
  - 26.5: ✅ valid (None)
  - 27.1: ❌ invalid (text_not_in_apartado: ai_act art. 27.1 es; cited text not found after normalization (480 chars vs 1753 chars apartado).)
  - 26.8: ✅ valid (None)
- **Reasoning for mixed**:
  Multiple hypotheses matched or case unclassifiable. Manual review needed.

### chat-008 (Hypothesis mixed)

- **Verdict**: actual=`requires_human_review` expected=`pass` (match: ❌)
- **Citations**: emitted=['14.1', '14.2', '14.3', '14.4', '14.5'] expected=['14.1', '14.2']
- **Invalid count**: 1
- **per_citation_audits**:
  - 14.1: ✅ valid (None)
  - 14.2: ✅ valid (None)
  - 14.3: ✅ valid (None)
  - 14.4: ❌ invalid (text_not_in_apartado: ai_act art. 14.4 es; cited text not found after normalization (859 chars vs 1518 chars apartado).)
  - 14.5: ✅ valid (None)
- **Reasoning for mixed**:
  Multiple hypotheses matched or case unclassifiable. Manual review needed.

### chat-013 (Hypothesis mixed)

- **Verdict**: actual=`requires_human_review` expected=`requires_human_review` (match: ✅)
- **Citations**: emitted=['6.3', '6.3', '6.3', '113.7'] expected=['6.3']
- **Invalid count**: 1
- **per_citation_audits**:
  - 6.3: ✅ valid (None)
  - 6.3: ✅ valid (None)
  - 6.3: ✅ valid (None)
  - 113.7: ❌ invalid (text_not_in_apartado: ai_act art. 113.7 es; cited text not found after normalization (169 chars vs 232 chars apartado).)
- **Reasoning for mixed**:
  Multiple hypotheses matched or case unclassifiable. Manual review needed.

### chat-016 (Hypothesis H1)

- **Verdict**: actual=`requires_human_review` expected=`pass` (match: ❌)
- **Citations**: emitted=['6.1', '6.1', '13.1', '28.3'] expected=['6.1']
- **Invalid count**: 3
- **per_citation_audits**:
  - 6.1: ❌ invalid (text_not_in_apartado: gdpr art. 6.1 es; cited text not found after normalization (1130 chars vs 1336 chars apartado).)
  - 6.1: ✅ valid (None)
  - 13.1: ❌ invalid (text_not_in_apartado: gdpr art. 13.1 es; cited text not found after normalization (439 chars vs 1213 chars apartado).)
  - 28.3: ❌ invalid (text_not_in_apartado: gdpr art. 28.3 es; cited text not found after normalization (377 chars vs 2893 chars apartado).)
- **Reasoning for H1**:
  Validator marks citation(s) as invalid that match gold expected citations per hierarchical containment rule. Suggests validator tolerance stricter than eval-metric.

### chat-017 (Hypothesis H1)

- **Verdict**: actual=`requires_human_review` expected=`pass` (match: ❌)
- **Citations**: emitted=['5.1', '5.1', '5.1', '5.1', '5.1', '5.1', '5.2'] expected=['5.1']
- **Invalid count**: 4
- **per_citation_audits**:
  - 5.1: ✅ valid (None)
  - 5.1: ❌ invalid (text_not_in_apartado: gdpr art. 5.1 es; cited text not found after normalization (168 chars vs 2262 chars apartado).)
  - 5.1: ✅ valid (None)
  - 5.1: ✅ valid (None)
  - 5.1: ❌ invalid (text_not_in_apartado: gdpr art. 5.1 es; cited text not found after normalization (209 chars vs 2262 chars apartado).)
  - 5.1: ❌ invalid (text_not_in_apartado: gdpr art. 5.1 es; cited text not found after normalization (312 chars vs 2262 chars apartado).)
  - 5.2: ❌ invalid (text_not_in_apartado: gdpr art. 5.2 es; cited text not found after normalization (151 chars vs 153 chars apartado).)
- **Reasoning for H1**:
  Validator marks citation(s) as invalid that match gold expected citations per hierarchical containment rule. Suggests validator tolerance stricter than eval-metric.

### chat-018 (Hypothesis H1)

- **Verdict**: actual=`requires_human_review` expected=`pass` (match: ❌)
- **Citations**: emitted=['6.1', '7.1', '7.2', '7.3', '7.4', '13.2'] expected=['7.1', '7.3']
- **Invalid count**: 3
- **per_citation_audits**:
  - 6.1: ✅ valid (None)
  - 7.1: ✅ valid (None)
  - 7.2: ✅ valid (None)
  - 7.3: ❌ invalid (text_not_in_apartado: gdpr art. 7.3 es; cited text not found after normalization (323 chars vs 325 chars apartado).)
  - 7.4: ❌ invalid (text_not_in_apartado: gdpr art. 7.4 es; cited text not found after normalization (328 chars vs 330 chars apartado).)
  - 13.2: ❌ invalid (text_not_in_apartado: gdpr art. 13.2 es; cited text not found after normalization (286 chars vs 1647 chars apartado).)
- **Reasoning for H1**:
  Validator marks citation(s) as invalid that match gold expected citations per hierarchical containment rule. Suggests validator tolerance stricter than eval-metric.

### chat-019 (Hypothesis H1)

- **Verdict**: actual=`requires_human_review` expected=`pass` (match: ❌)
- **Citations**: emitted=['9.1', '9.2', '9.2', '9.2', '9.2', '9.4'] expected=['9.1', '9.2']
- **Invalid count**: 4
- **per_citation_audits**:
  - 9.1: ❌ invalid (text_not_in_apartado: gdpr art. 9.1 es; cited text not found after normalization (413 chars vs 418 chars apartado).)
  - 9.2: ✅ valid (None)
  - 9.2: ❌ invalid (text_not_in_apartado: gdpr art. 9.2 es; cited text not found after normalization (491 chars vs 3817 chars apartado).)
  - 9.2: ❌ invalid (text_not_in_apartado: gdpr art. 9.2 es; cited text not found after normalization (402 chars vs 3817 chars apartado).)
  - 9.2: ❌ invalid (text_not_in_apartado: gdpr art. 9.2 es; cited text not found after normalization (976 chars vs 3817 chars apartado).)
  - 9.4: ✅ valid (None)
- **Reasoning for H1**:
  Validator marks citation(s) as invalid that match gold expected citations per hierarchical containment rule. Suggests validator tolerance stricter than eval-metric.

### chat-021 (Hypothesis H1)

- **Verdict**: actual=`requires_human_review` expected=`pass` (match: ❌)
- **Citations**: emitted=['15.1', '15.2', '15.3', '15.4'] expected=['15.1']
- **Invalid count**: 3
- **per_citation_audits**:
  - 15.1: ❌ invalid (text_not_in_apartado: gdpr art. 15.1 es; cited text not found after normalization (1395 chars vs 1451 chars apartado).)
  - 15.2: ✅ valid (None)
  - 15.3: ❌ invalid (text_not_in_apartado: gdpr art. 15.3 es; cited text not found after normalization (435 chars vs 436 chars apartado).)
  - 15.4: ❌ invalid (text_not_in_apartado: gdpr art. 15.4 es; cited text not found after normalization (119 chars vs 182 chars apartado).)
- **Reasoning for H1**:
  Validator marks citation(s) as invalid that match gold expected citations per hierarchical containment rule. Suggests validator tolerance stricter than eval-metric.

### chat-022 (Hypothesis H1)

- **Verdict**: actual=`requires_human_review` expected=`pass` (match: ❌)
- **Citations**: emitted=['17.1', '17.1', '17.1', '17.1', '17.1', '17.1', '17.2', '17.3'] expected=['17.1']
- **Invalid count**: 4
- **per_citation_audits**:
  - 17.1: ❌ invalid (text_not_in_apartado: gdpr art. 17.1 es; cited text not found after normalization (410 chars vs 1313 chars apartado).)
  - 17.1: ✅ valid (None)
  - 17.1: ❌ invalid (text_not_in_apartado: gdpr art. 17.1 es; cited text not found after normalization (224 chars vs 1313 chars apartado).)
  - 17.1: ✅ valid (None)
  - 17.1: ✅ valid (None)
  - 17.1: ❌ invalid (text_not_in_apartado: gdpr art. 17.1 es; cited text not found after normalization (155 chars vs 1313 chars apartado).)
  - 17.2: ✅ valid (None)
  - 17.3: ❌ invalid (text_not_in_apartado: gdpr art. 17.3 es; cited text not found after normalization (993 chars vs 999 chars apartado).)
- **Reasoning for H1**:
  Validator marks citation(s) as invalid that match gold expected citations per hierarchical containment rule. Suggests validator tolerance stricter than eval-metric.

### chat-023 (Hypothesis H1)

- **Verdict**: actual=`requires_human_review` expected=`pass` (match: ❌)
- **Citations**: emitted=['25.1', '25.2', '25.3'] expected=['25.1', '25.2']
- **Invalid count**: 2
- **per_citation_audits**:
  - 25.1: ❌ invalid (text_not_in_apartado: gdpr art. 25.1 es; cited text not found after normalization (480 chars vs 756 chars apartado).)
  - 25.2: ✅ valid (None)
  - 25.3: ❌ invalid (text_not_in_apartado: gdpr art. 25.3 es; cited text not found after normalization (204 chars vs 206 chars apartado).)
- **Reasoning for H1**:
  Validator marks citation(s) as invalid that match gold expected citations per hierarchical containment rule. Suggests validator tolerance stricter than eval-metric.

### chat-024 (Hypothesis H1)

- **Verdict**: actual=`requires_human_review` expected=`pass` (match: ❌)
- **Citations**: emitted=['28.1', '28.3', '28.3', '28.4', '28.6'] expected=['28.3']
- **Invalid count**: 4
- **per_citation_audits**:
  - 28.1: ❌ invalid (text_not_in_apartado: gdpr art. 28.1 es; cited text not found after normalization (358 chars vs 409 chars apartado).)
  - 28.3: ❌ invalid (text_not_in_apartado: gdpr art. 28.3 es; cited text not found after normalization (377 chars vs 2893 chars apartado).)
  - 28.3: ❌ invalid (text_not_in_apartado: gdpr art. 28.3 es; cited text not found after normalization (1070 chars vs 2893 chars apartado).)
  - 28.4: ❌ invalid (text_not_in_apartado: gdpr art. 28.4 es; cited text not found after normalization (541 chars vs 917 chars apartado).)
  - 28.6: ✅ valid (None)
- **Reasoning for H1**:
  Validator marks citation(s) as invalid that match gold expected citations per hierarchical containment rule. Suggests validator tolerance stricter than eval-metric.

### chat-025 (Hypothesis H1)

- **Verdict**: actual=`requires_human_review` expected=`pass` (match: ❌)
- **Citations**: emitted=['32.1', '32.2', '32.4', '25.1'] expected=['32.1']
- **Invalid count**: 3
- **per_citation_audits**:
  - 32.1: ❌ invalid (text_not_in_apartado: gdpr art. 32.1 es; cited text not found after normalization (701 chars vs 1002 chars apartado).)
  - 32.2: ❌ invalid (text_not_in_apartado: gdpr art. 32.2 es; cited text not found after normalization (357 chars vs 361 chars apartado).)
  - 32.4: ✅ valid (None)
  - 25.1: ❌ invalid (text_not_in_apartado: gdpr art. 25.1 es; cited text not found after normalization (480 chars vs 756 chars apartado).)
- **Reasoning for H1**:
  Validator marks citation(s) as invalid that match gold expected citations per hierarchical containment rule. Suggests validator tolerance stricter than eval-metric.

### chat-026 (Hypothesis H1)

- **Verdict**: actual=`requires_human_review` expected=`requires_human_review` (match: ✅)
- **Citations**: emitted=['33.1', '33.4', '33.5'] expected=['33.1', '33.3']
- **Invalid count**: 2
- **per_citation_audits**:
  - 33.1: ❌ invalid (text_not_in_apartado: gdpr art. 33.1 es; cited text not found after normalization (431 chars vs 584 chars apartado).)
  - 33.4: ✅ valid (None)
  - 33.5: ❌ invalid (text_not_in_apartado: gdpr art. 33.5 es; cited text not found after normalization (319 chars vs 321 chars apartado).)
- **Reasoning for H1**:
  Validator marks citation(s) as invalid that match gold expected citations per hierarchical containment rule. Suggests validator tolerance stricter than eval-metric.

### chat-030 (Hypothesis mixed)

- **Verdict**: actual=`requires_human_review` expected=`block` (match: ❌)
- **Citations**: emitted=['83.5', '83.5', '83.3'] expected=[]
- **Invalid count**: 1
- **per_citation_audits**:
  - 83.5: ✅ valid (None)
  - 83.5: ✅ valid (None)
  - 83.3: ❌ invalid (text_not_in_apartado: gdpr art. 83.3 es; cited text not found after normalization (330 chars vs 332 chars apartado).)
- **Reasoning for mixed**:
  Multiple hypotheses matched or case unclassifiable. Manual review needed.

## §22.22 caveats

1. H2 refusal-language heuristic uses regex; may false-positive on substantive answers that mention refusal-adjacent topics.
2. Hierarchical containment matching for H1 uses lenient bidirectional rule (article-match either direction); may over-attribute H1 if gold itself uses inconsistent granularity.
3. Hypothesis precedence H4 > H1 > H3 > H2 means edge cases prefer 'legitimate catch' over 'validator strictness'. Reverse if a case has multiple hypothesis matches.
4. Gold expected_citations may itself be incomplete (alternative valid articles not listed); treated as ground-truth for diagnostic per H8 design.
5. Per_citation_audits trail integrity: v0.1.22-prod IS post-v0.1.21.1 D2 → trail populated for all cases (verified during load).

## Next milestone (v0.1.23) decision

Per spec §D2 decision tree:

**Dominant: mixed (no clear single hypothesis)**

**v0.1.23 path**: 1+ surgical milestones per hypothesis. May need v0.1.23 + v0.1.24+. Manual review of secondary hypothesis matches recommended.
**Risk level**: VARIES
