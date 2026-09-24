-- Synthetic reproduction of the public schema-30 SCHEMA_SQL at
-- NousResearch/hermes-agent commit 693641aa8b4359c602283bdbbc14041e03bc47bc.
PRAGMA foreign_keys = ON;

CREATE TABLE schema_version (version INTEGER NOT NULL);
INSERT INTO schema_version VALUES (30);
CREATE TABLE system_prompts (hash TEXT PRIMARY KEY, prompt TEXT NOT NULL);
CREATE TABLE sessions (
 id TEXT PRIMARY KEY, source TEXT NOT NULL, user_id TEXT, session_key TEXT, chat_id TEXT,
 chat_type TEXT, thread_id TEXT, display_name TEXT, origin_json TEXT, expiry_finalized INTEGER DEFAULT 0,
 model TEXT, model_config TEXT, system_prompt TEXT, system_prompt_hash TEXT, parent_session_id TEXT,
 started_at REAL NOT NULL, ended_at REAL, end_reason TEXT, message_count INTEGER DEFAULT 0,
 tool_call_count INTEGER DEFAULT 0, input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
 cache_read_tokens INTEGER DEFAULT 0, cache_write_tokens INTEGER DEFAULT 0, reasoning_tokens INTEGER DEFAULT 0,
 cwd TEXT, git_branch TEXT, git_repo_root TEXT, git_metadata_generation INTEGER NOT NULL DEFAULT 0,
 billing_provider TEXT, billing_base_url TEXT, billing_mode TEXT, estimated_cost_usd REAL,
 actual_cost_usd REAL, cost_status TEXT, cost_source TEXT, pricing_version TEXT, title TEXT,
 title_source TEXT, last_activity_at REAL, last_activity_description TEXT, last_activity_provenance TEXT,
 api_call_count INTEGER DEFAULT 0, handoff_state TEXT, handoff_platform TEXT, handoff_error TEXT,
 compression_failure_cooldown_until REAL, compression_failure_error TEXT,
 compression_fallback_streak INTEGER NOT NULL DEFAULT 0, compression_ineffective_count INTEGER NOT NULL DEFAULT 0,
 compression_recovery_deadline REAL, profile_name TEXT, rewind_count INTEGER NOT NULL DEFAULT 0,
 archived INTEGER NOT NULL DEFAULT 0, pinned INTEGER NOT NULL DEFAULT 0, hidden INTEGER NOT NULL DEFAULT 0,
 last_read_at REAL, tool_names TEXT,
 FOREIGN KEY (parent_session_id) REFERENCES sessions(id),
 FOREIGN KEY (system_prompt_hash) REFERENCES system_prompts(hash)
);
CREATE TABLE messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES sessions(id), role TEXT NOT NULL,
 content TEXT, tool_call_id TEXT, tool_calls TEXT, tool_name TEXT, effect_disposition TEXT,
 timestamp REAL NOT NULL, token_count INTEGER, finish_reason TEXT, reasoning TEXT, reasoning_content TEXT,
 reasoning_details TEXT, codex_reasoning_items TEXT, codex_message_items TEXT, platform_message_id TEXT,
 observed INTEGER DEFAULT 0, _compressed_summary INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
 compacted INTEGER NOT NULL DEFAULT 0, api_content TEXT, display_kind TEXT, display_metadata TEXT
);
CREATE TABLE session_model_usage (
 session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE, model TEXT NOT NULL,
 billing_provider TEXT NOT NULL DEFAULT '', billing_base_url TEXT NOT NULL DEFAULT '',
 billing_mode TEXT NOT NULL DEFAULT '', task TEXT NOT NULL DEFAULT '', api_call_count INTEGER NOT NULL DEFAULT 0,
 input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0,
 cache_read_tokens INTEGER NOT NULL DEFAULT 0, cache_write_tokens INTEGER NOT NULL DEFAULT 0,
 reasoning_tokens INTEGER NOT NULL DEFAULT 0, estimated_cost_usd REAL NOT NULL DEFAULT 0,
 actual_cost_usd REAL NOT NULL DEFAULT 0, cost_status TEXT, cost_source TEXT, first_seen REAL, last_seen REAL,
 PRIMARY KEY (session_id, model, billing_provider, billing_base_url, billing_mode, task)
);
CREATE TABLE gateway_routing (
 scope TEXT NOT NULL DEFAULT '', session_key TEXT NOT NULL, entry_json TEXT NOT NULL,
 updated_at REAL NOT NULL, PRIMARY KEY (scope, session_key)
);
-- Deliberate additive field used to prove unknown-column preservation.
ALTER TABLE sessions ADD COLUMN fixture_extension TEXT;
INSERT INTO system_prompts VALUES ('fixture-hash', 'fixture prompt');
INSERT INTO sessions (id, source, model, model_config, system_prompt, system_prompt_hash, started_at, ended_at, end_reason, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens, billing_provider, billing_base_url, billing_mode, estimated_cost_usd, actual_cost_usd, cost_status, cost_source, pricing_version, title, archived, pinned, fixture_extension)
VALUES ('session-a', 'fixture', 'model-a', '{}', NULL, 'fixture-hash', 1, 2, 'done', 1, 2, 3, 4, 0, 'provider-a', 'https://example.invalid', 'fixture', .2, 0, 'actual', 'fixture', 'fixture-price', 'first', 0, 1, 'extra');
INSERT INTO sessions (id, source, model, model_config, system_prompt, system_prompt_hash, started_at, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens, billing_provider, billing_base_url, billing_mode, estimated_cost_usd, actual_cost_usd, pricing_version, title, archived, pinned)
VALUES ('session-b', 'fixture', 'model-b', '{}', NULL, 'fixture-hash', 2, 2, 1, 0, 0, 0, 'provider-b', 'https://example.invalid', 'fixture', .1, NULL, 'fixture-price', 'second', 0, 0);
INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (2, 'session-a', 'assistant', 'second message', 2);
INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (1, 'session-a', 'user', 'first message', 1);
INSERT INTO session_model_usage (session_id, model, billing_provider, billing_base_url, billing_mode, task, api_call_count, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, reasoning_tokens, estimated_cost_usd, actual_cost_usd)
VALUES ('session-a', 'model-a', 'provider-a', 'https://example.invalid', 'fixture', '', 1, 1, 2, 3, 4, 0, .1, 0);
INSERT INTO gateway_routing VALUES ('fixture', 'route-a', '{"fixture":true}', 1);
