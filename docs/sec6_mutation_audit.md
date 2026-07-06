# §6 mutation audit — citation/validator.py

Baseline battery passes: **True**
Mutations: **12** | killed: **11** | survived: **1** (documented equivalents: 1) | unexpected: **0** | errors: **0**

| mutation | outcome | expected | killed_by | note |
|---|---|---|---|---|
| `floor_const_zero` | killed | killed | B4_too_short | Disabling the length floor lets a trivial token validate -> B4 catches it. |
| `floor_boundary_lte` | killed | killed | B7_valid_boundary_20 | Off-by-one at the floor rejects a boundary-length valid citation -> B7. |
| `substring_always_true` | killed | killed | B3_text_not_in_corpus | Forcing the substring test true validates fabricated text -> B3. |
| `textmatch_invert` | killed | killed | B3_text_not_in_corpus | Inverting the match branch flips valid<->invalid -> B3 and B6. |
| `empty_guard_disabled` | survived | equivalent | - | The floor subsumes the empty guard (empty is len 0 < 20 -> also failed_check=4); disabling the guard leaves the reject + code unchanged. Kept for the precise reason string + defense-in-depth clarity (sec6-01b). |
| `check1_code` | killed | killed | B1_fabricated_article | Mislabelling article fabrication as paraphrase (softenable) -> B1. |
| `check2_code` | killed | killed | B2_fabricated_apartado | Mislabelling apartado fabrication as paraphrase (softenable) -> B2. |
| `pass_validated_flip` | killed | killed | B6_valid_long | Flipping the pass return invalidates a real citation -> B6 and B7. |
| `apartado_branch_skip` | killed | killed | B2_fabricated_apartado | Skipping the apartado check validates a fabricated-apartado citation -> B2. |
| `substring_bidirectional` | killed | killed | B8_superset_of_article | Superset match (target in citation) validates 'real text + appended fabrication' -> B8. |
| `floor_raw_length` | killed | killed | B11_raw_padded_short | Keying the floor on RAW length lets a whitespace-padded short token clear it -> B11. |
| `article_self_match` | killed | killed | B10_article_level_fabricated | apartado=None branch self-match validates fabricated whole-article text -> B10. |
