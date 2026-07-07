# §18 mutation audit — security/injection.py (prompt-injection detection)

Baseline battery passes: **True**
Pattern coverage: **25/25** exercised | uncovered: **none**
Mutations: **9** | killed: **9** | survived: **0** | unexpected: **0** | errors: **0**

| mutation | outcome | expected | killed_by | note |
|---|---|---|---|---|
| `mode_dispatch_disabled` | killed | killed | doc_evaluator | Never applying document patterns lets a document-only attack through -> A7. |
| `ignore_previous_case_sensitive` | killed | killed | ignore_previous | Dropping re.I misses the capitalised 'Ignore all previous instructions' -> A1. |
| `jailbreak_drop_dan` | killed | killed | jailbreak | Removing the DAN alternative misses a bare 'DAN mode' payload -> A5. |
| `reveal_require_system` | killed | killed | reveal | Requiring 'system' misses 'reveal your prompt' -> A4. |
| `role_override_typo` | killed | killed | role_en | A typo in the role-override regex stops it matching -> A3. |
| `final_return_over_detect` | killed | killed | B1_benign_gdpr | Flipping the no-match return flags benign queries as injections -> B1. |
| `role_override_es_typo` | killed | killed | role_es | A typo neuters the ES role-override — 'Ahora eres...' slips through -> role_es. |
| `fake_delimiter_neuter` | killed | killed | fake_delim | Neutering the fake-delimiter regex misses '### END ###' -> fake_delim. |
| `data_exfiltration_neuter` | killed | killed | doc_exfiltration | Neutering the exfiltration regex misses 'Envía... a x@' -> doc_exfiltration. |
