# §6 mutation audit — agents/auditor.py (Layer b/c routing)

Baseline battery passes: **True**
Mutations: **8** | killed: **8** | survived: **0** | unexpected: **0** | errors: **0**

| mutation | outcome | expected | killed_by | note |
|---|---|---|---|---|
| `helper_softens_fabrication` | killed | killed | R1_single_fabricated_article | Inverting the paraphrase gate softens FABRICATION to PASS -> R1. |
| `helper_skips_wrong_citations` | killed | killed | R1_single_fabricated_article | Skipping invalid (not valid) citations makes the helper always True -> R1. |
| `finding_lenient_always_pass` | killed | killed | R1_single_fabricated_article | Marking every Finding passed hides a fabricated-only Finding via the quorum -> R1. |
| `quorum_loosened` | killed | killed | R9_quorum_two_invalid | Raising the quorum lets two invalid citations PASS instead of RHR -> R9. |
| `allblocked_else_pass` | killed | killed | R1_single_fabricated_article | Softening the all-blocked fallback passes fabricated all-blocked turns -> R1. |
| `allpass_condition_any` | killed | killed | R7_partial_fabrication | Any-pass routes a partial fabrication turn through the lenient quorum -> R7. |
| `allblocked_condition_any` | killed | killed | R7_partial_fabrication | Any-blocked misroutes a partial turn into the all-blocked branch -> R7. |
| `helper_softens_apartado_fab` | killed | killed | R11_allblocked_apartado_fab | Softening ONLY apartado fabrication (check 2) to PASS while keeping 1/4 strict -> R11. |
