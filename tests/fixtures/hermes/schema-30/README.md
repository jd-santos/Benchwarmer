# Synthetic Hermes schema-30 fixture

`schema.sql` is a synthetic reproduction of the schema-30 definitions for
`schema_version`, `system_prompts`, `sessions`, `messages`,
`session_model_usage`, and `gateway_routing` from public
[NousResearch/hermes-agent commit 693641aa8b4359c602283bdbbc14041e03bc47bc](https://github.com/NousResearch/hermes-agent/blob/693641aa8b4359c602283bdbbc14041e03bc47bc/hermes_state_common.py).

All rows are invented. No Hermes database, profile, path, credential, account
identifier, or conversation content was copied. The one additive
`fixture_extension` column is deliberate test-only evidence that the reader
preserves unknown source fields without assigning them semantics.
