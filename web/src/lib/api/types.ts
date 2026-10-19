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

export type EvidenceRole = 'requirement' | 'action' | 'result' | 'correction' | 'context';
export type BundleStatus = 'draft' | 'reviewed' | 'analysis_only';

export interface EvidenceRef {
	conversation_id: string;
	revision: string;
	event_id: string;
	block_id: string | null;
	text_start?: number | null;
	text_end?: number | null;
}

export interface BundleItem {
	ref: EvidenceRef;
	role: EvidenceRole;
	note?: string | null;
}

export interface BundleDocument {
	schema_version?: 1;
	objective: string;
	status: BundleStatus;
	items: BundleItem[];
	rationale: string | null;
	missing_evidence: string[];
}

export interface ResolvedBundleItem {
	item: BundleItem;
	conversation_title: string | null;
	conversation_is_latest: boolean;
	event_role: string;
	event_kind: string;
	occurred_at: string | null;
	block_kind: string | null;
	excerpt: string | null;
	omitted_before: number | null;
}

export interface BundleRevision {
	number: number;
	origin: 'human' | 'generated';
	producer: string;
	created_at: string;
}

export interface BundleDetail {
	id: string;
	revision: number;
	latest_revision: number;
	origin: 'human' | 'generated';
	producer: string;
	created_at: string;
	updated_at: string;
	document: BundleDocument;
	items: ResolvedBundleItem[];
	revisions: BundleRevision[];
}

export interface BundleSummary {
	id: string;
	revision: number;
	objective: string;
	status: BundleStatus;
	item_count: number;
	conversation_ids: string[];
	updated_at: string;
}

export interface BundlesResponse {
	items: BundleSummary[];
}

export interface EvidenceIssue {
	item_index: number | null;
	code: string;
	message: string;
}
