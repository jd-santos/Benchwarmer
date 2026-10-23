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

/** Where this host may import files from, and which source kinds accept a path. */
export interface ImportConfig {
	roots: string[];
	kinds: string[];
}

export interface ImportBatchSummary {
	id: string;
	outcome: string;
	started_at: string;
	completed_at: string;
	error_summary: string | null;
}

/** What one requested import did; `unchanged` means these exact files were imported before. */
export interface ImportRun {
	batch_id: string;
	outcome: 'succeeded' | 'failed' | 'unchanged';
	conversations: number;
	revisions: number;
	snapshots: number;
	error_summary: string | null;
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
	/** First event after the last fork on this path. */
	divergent_event_id: string | null;
	/** Follows the earliest-captured continuation at every fork. */
	is_original: boolean;
	/** Captured history; Benchwarmer trials will add their own origin. */
	origin: 'captured';
	/** Models the source recorded on this path, in path order. */
	models: string[];
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
export type BundleStatus = 'draft' | 'reviewed' | 'analysis_only' | 'rejected';
export type BundleOrigin = 'human' | 'generated';

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

/** The closed vocabulary of work types; mirrors `ObjectiveType` in Python. */
export type ObjectiveType =
	| 'bug'
	| 'feature'
	| 'refactor'
	| 'test'
	| 'performance'
	| 'infrastructure'
	| 'analytics'
	| 'research'
	| 'design'
	| 'writing'
	| 'review'
	| 'unknown';

export interface BundleDocument {
	schema_version?: 3;
	/** What the bundle represents, in a sentence or two for a human reader. */
	summary: string;
	/** The kind of work in general terms; the axis bundles are grouped on. */
	objective: string;
	/** The closed category of that work; the first grouping level above the objective. */
	objective_type: ObjectiveType;
	/** What this particular piece of work tried to achieve. */
	goal: string;
	status: BundleStatus;
	items: BundleItem[];
	rationale: string | null;
	missing_evidence: string[];
}

/** A tool call inside a cited event; arguments are the captured text, if any. */
export interface CitedToolCall {
	tool_call_id: string;
	arguments: string | null;
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
	/** The calls a whole-event citation covers; a block citation lists none. */
	tool_calls: CitedToolCall[];
}

/** Which harness run and model produced a generated revision. */
export interface RunProvenance {
	run_id: string;
	workflow: string;
	harness_version: string;
	provider: string;
	model: string;
	thinking_level: string | null;
	report_path: string | null;
}

export interface BundleRevision {
	number: number;
	origin: BundleOrigin;
	producer: string;
	provenance: RunProvenance | null;
	created_at: string;
}

export interface BundleDetail {
	id: string;
	revision: number;
	latest_revision: number;
	origin: BundleOrigin;
	producer: string;
	provenance: RunProvenance | null;
	request_id: string | null;
	created_at: string;
	updated_at: string;
	document: BundleDocument;
	items: ResolvedBundleItem[];
	revisions: BundleRevision[];
}

/** The latest revision of one bundle; origin and producer describe that revision. */
export interface BundleSummary {
	id: string;
	revision: number;
	summary: string;
	objective: string;
	objective_type: ObjectiveType;
	goal: string;
	status: BundleStatus;
	origin: BundleOrigin;
	producer: string;
	/** The harness run that produced the latest revision, when it was generated. */
	run_id: string | null;
	item_count: number;
	conversation_ids: string[];
	updated_at: string;
}

export interface BundlesResponse {
	items: BundleSummary[];
}

/** Raw token counts for one model or tool and the catalog estimate of their cost in USD. */
export interface RunModelUsage {
	input: number;
	output: number;
	cache_read: number;
	cache_write: number;
	total_tokens: number;
	cost: { input: number; output: number; cache_read: number; cache_write: number; total: number };
}

export interface RunUsageTotal {
	models: Record<string, RunModelUsage>;
	tools: Record<string, RunModelUsage>;
}

/** One conversation or session a harness run worked on. */
export interface RunInput {
	id: string;
	kind: 'conversation' | 'session';
	status: 'done' | 'unanswered' | 'error';
	reason: string | null;
	bundle_ids: string[];
	usage: RunUsageTotal;
}

/** A hand-run harness workflow; cost figures are catalog estimates, not charges. */
export interface HarnessRunRecord {
	run_id: string;
	workflow: string;
	harness_version: string;
	started_at: string;
	finished_at: string;
	api_base_url: string;
	model: {
		provider: string;
		model_id: string;
		thinking_level: string | null;
		base_url_override: string | null;
	};
	producer: string;
	inputs: RunInput[];
	usage_total: RunUsageTotal;
	pricing_source: string;
	report_path: string | null;
}

/** One bundle that cites a conversation, and which of its events, from the latest revision. */
export interface BundleMembership {
	id: string;
	revision: number;
	summary: string;
	status: BundleStatus;
	origin: BundleOrigin;
	run_id: string | null;
	event_ids: string[];
}

/** One run at a glance, as the runs list returns it; ``estimated_cost`` is a catalog estimate in USD. */
export interface RunSummary {
	run_id: string;
	workflow: string;
	provider: string;
	model: string;
	thinking_level: string | null;
	base_url_override: string | null;
	started_at: string;
	finished_at: string;
	input_count: number;
	bundle_count: number;
	total_tokens: number;
	estimated_cost: number;
	pricing_source: string;
}

export interface RunsResponse {
	items: RunSummary[];
}

export interface EvidenceIssue {
	item_index: number | null;
	code: string;
	message: string;
}
