# §18.8 mutation audit — document/sanitizer.py (document security)

Baseline battery passes: **True**
Unicode-trick coverage: **6/6** members exercised
Mutations: **11** | killed: **11** | survived: **0** | unexpected: **0** | errors: **0**

| mutation | outcome | expected | killed_by | note |
|---|---|---|---|---|
| `javascript_block_disabled` | killed | killed | javascript | Disabling the JS block lets a JavaScript-declaring PDF through -> javascript. |
| `attachment_block_disabled` | killed | killed | attachment | Disabling the attachment block lets an embedded file through -> attachment. |
| `form_action_block_disabled` | killed | killed | form_action | Disabling the form-action block lets SubmitForm/ImportData through -> form_action. |
| `uri_allowlist_inverted` | killed | killed | uri_action | Inverting the URI allowlist check passes a non-allowlisted URI action -> uri_action. |
| `metadata_injection_disabled` | killed | killed | metadata_injection | Disabling the metadata-injection block lets a poisoned metadata field through. |
| `metadata_url_allowlist_inverted` | killed | killed | metadata_url | Inverting the metadata-URL allowlist passes an exfiltration URL -> metadata_url. |
| `length_floor_disabled` | killed | killed | below_content_floor | Disabling the content floor passes an empty-after-sanitization document. |
| `unicode_strip_disabled` | killed | killed | log_unicode_severity | Inverting the trick check leaves zero-width / bidi codepoints in clean_text. |
| `drop_rlo_from_trick_set` | killed | killed | unicode_202e | Dropping the RLO bidi-override from _UNICODE_TRICKS leaks a Trojan-Source char. |
| `annotation_log_removed` | killed | killed | log_annotation | Dropping the annotation-strip log hides it from the audit trail -> log_annotation. |
| `hidden_text_log_removed` | killed | killed | log_hidden_text | Dropping the hidden-text-strip log hides it from the audit trail -> log_hidden_text. |
