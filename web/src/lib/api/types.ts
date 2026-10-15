export type CoverageValue = 'available' | 'partial' | 'unavailable' | 'unknown';

export interface HealthResponse {
	status: 'ok';
	alembic_revision: string | null;
	data_root_writable: boolean;
}

export interface SourceCoverage {
	sessions: CoverageValue;
	token_usage: CoverageValue;
	request_ids: CoverageValue;
	actual_charges: CoverageValue;
	list_price_estimates: CoverageValue;
	subscription_expense: CoverageValue;
	quota: CoverageValue;
	credits: CoverageValue;
	prompts: CoverageValue;
	classifications: CoverageValue;
}

export interface SourceStatus {
	id: string;
	kind: string;
	display_name: string;
	last_successful_import_at: string | null;
	coverage: SourceCoverage;
}

export interface SourcesResponse {
	items: SourceStatus[];
}

export type CaptureState = CoverageValue | 'redacted';

export interface SourceRef {
	id: string;
	kind: string;
	display_name: string;
}

export interface SearchHit {
	event_id: string | null;
	block_id: string | null;
	field: string;
	snippet: string;
}

export interface ConversationSummary {
	id: string;
	source: SourceRef;
	native_id: string;
	revision: string;
	captured_at: string;
	title: string | null;
	preview: string | null;
	started_at: string | null;
	last_activity_at: string | null;
	event_count: number;
	message_count: number;
	branch_count: number;
	relationship_counts: Record<string, number>;
	coverage: Record<string, CaptureState>;
	match_count: number;
	matches: SearchHit[];
}

export interface ConversationsResponse {
	items: ConversationSummary[];
	total: number;
	limit: number;
	offset: number;
}

export type BlockKind =
	'text' | 'reasoning' | 'tool_call' | 'tool_result' | 'attachment' | 'unknown';

export interface ContentBlock {
	id: string;
	kind: BlockKind;
	text: string | null;
	tool_call_id: string | null;
	artifact_id: string | null;
	extensions: Record<string, unknown>;
}

export type EventKind = 'message' | 'compaction' | 'configuration' | 'unknown';
export type EventRole = 'system' | 'developer' | 'user' | 'assistant' | 'tool' | 'unknown';

export interface ConversationEvent {
	id: string;
	native_id: string;
	ordinal: number;
	parent_id: string | null;
	kind: EventKind;
	role: EventRole;
	occurred_at: string | null;
	content: ContentBlock[];
	extensions: Record<string, unknown>;
}

export type RelationshipKind = 'branch' | 'continuation' | 'derived_from' | 'unknown';

export interface Relationship {
	kind: RelationshipKind;
	target_source_kind: string;
	target_source_scope_id: string;
	target_native_id: string;
	target_conversation_id: string | null;
	extensions: Record<string, unknown>;
}

export interface IncomingRelationship {
	kind: RelationshipKind;
	conversation_id: string;
}

export interface Branch {
	id: string;
	leaf_event_id: string;
	event_ids: string[];
	fork_event_id: string | null;
}

export interface RevisionRef {
	revision: string;
	captured_at: string;
}

export interface ConversationDetail {
	summary: ConversationSummary;
	is_latest: boolean;
	revisions: RevisionRef[];
	events: ConversationEvent[];
	artifacts: Record<string, unknown>[];
	metadata: Record<string, unknown>[];
	relationships: Relationship[];
	referenced_by: IncomingRelationship[];
	branches: Branch[];
}
