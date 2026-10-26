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

/** Whether this application can start harness runs, and what a plan may name. */
export interface ModelWorkConfig {
	can_run: boolean;
	workflows: string[];
	thinking_levels: string[];
	max_inputs: number;
}

/** USD per million tokens, from whichever catalog priced the model. */
export interface CatalogCost {
	input: number;
	output: number;
	cache_read: number;
	cache_write: number;
}

export type CatalogSource = 'pi-ai' | 'models.dev' | 'provider';

/** One model the harness can run with the keys present on the server. */
export interface CatalogModel {
	provider: string;
	id: string;
	name: string;
	reasoning: boolean | null;
	thinking_levels: string[];
	context_window: number | null;
	max_output: number | null;
	release_date: string | null;
	cost: CatalogCost | null;
	sources: CatalogSource[];
	/** Whether the provider's own list includes it; null when that list was not available. */
	listed_by_provider: boolean | null;
	runnable: boolean;
}

export interface CatalogProvider {
	id: string;
	name: string;
	key_variables: string[];
	base_url_override: string | null;
	provider_list: 'listed' | 'unavailable' | 'not_offered' | 'skipped';
	models_dev: 'listed' | 'unavailable' | 'skipped';
	model_count: number;
}

export interface ModelCatalog {
	generated_at: string;
	fetched_at: string;
	providers: CatalogProvider[];
	models: CatalogModel[];
	notes: string[];
}

export type PlanStatus =
	'proposed' | 'approved' | 'running' | 'finished' | 'failed' | 'cancelled' | 'interrupted';

export interface PlanInput {
	conversation_id: string;
	revision: string;
	title: string | null;
}

/** A frozen plan for model work; `estimated_cost` is null until a run reports usage. */
export interface ModelWorkPlan {
	id: string;
	workflow: string;
	status: PlanStatus;
	digest: string;
	inputs: PlanInput[];
	model: { provider: string; model_id: string; thinking_level: string | null };
	max_inputs: number;
	instructions: string | null;
	estimated_cost: null;
	run_id: string | null;
	exit_code: number | null;
	error_summary: string | null;
	created_at: string;
	approved_at: string | null;
	started_at: string | null;
	finished_at: string | null;
}

export interface PlanRequest {
	workflow: string;
	conversation_ids: string[];
	model: { provider: string; model_id: string; thinking_level: string | null };
	instructions: string | null;
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

/* Task versions: a reviewed bundle prepared as a test. Mirrors `benchwarmer.tasks`. */

export type TaskKind = 'chat' | 'agent' | 'coding';
export type TaskStatus = 'draft' | 'approved' | 'retired';
export type CriterionMethod = 'deterministic' | 'llm_judge' | 'human';
export type JudgeEvidence = 'judge.historical' | 'judge.feedback' | 'judge.reviewer_notes';
export type ReconstructionLevel = 'prompt_only' | 'fixture_backed' | 'fixed_multi_turn';
export type Partition = 'development' | 'calibration' | 'holdout';
export type ReviewerLabel = 'pass' | 'fail' | 'unsure';

/** The last event the candidate sees, on the bundle's path in one conversation. */
export interface CutPoint {
	conversation_id: string;
	revision: string;
	event_id: string;
}

export interface Criterion {
	id: string;
	statement: string;
	method: CriterionMethod;
	rubric_version: number;
	judge_evidence: JudgeEvidence[];
	reviewer_label: ReviewerLabel | null;
	note: string | null;
}

export interface Reconstruction {
	level: ReconstructionLevel;
	gaps: string[];
}

export interface ExpectedScope {
	in_scope_paths: string[];
	approval_paths: string[];
	excluded_paths: string[];
}

export interface LeakageReview {
	by: string;
	at: string;
	/** Ids of automatic flags the reviewer looked at and judged not to be leaks. */
	accepted_flags: string[];
	notes: string | null;
}

export interface TaskDocument {
	schema_version?: 1;
	bundle_id: string;
	bundle_revision: number;
	kind: TaskKind;
	summary: string;
	objective: string;
	objective_type: ObjectiveType;
	family: string;
	cut_point: CutPoint;
	reconstruction: Reconstruction;
	criteria: Criterion[];
	expected_scope: ExpectedScope | null;
	leakage_review: LeakageReview | null;
	partition: Partition | null;
	status: TaskStatus;
	reviewer_notes: string;
}

/** One automatic sign that the candidate section may reveal the answer. */
export interface LeakageFlag {
	id: string;
	code: string;
	message: string;
	event_id: string | null;
	criterion_id: string | null;
	item_index: number | null;
}

/** One event on the task's conversation path, placed on one side of the cut. */
export interface SplitEvent {
	event_id: string;
	role: string;
	kind: string;
	occurred_at: string | null;
	preview: string | null;
	/** Bundle item roles citing this event, in item order. */
	cited_as: EvidenceRole[];
}

export interface TaskSplit {
	conversation_id: string;
	revision: string;
	conversation_title: string | null;
	candidate: SplitEvent[];
	judge: SplitEvent[];
	/** Events the bundle cites in other conversations; always judge-only. */
	other_judge: SplitEvent[];
}

export interface TaskVersionRef {
	number: number;
	status: TaskStatus;
	producer: string;
	created_at: string;
}

export interface TaskDetail {
	id: string;
	version: number;
	latest_version: number;
	producer: string;
	created_at: string;
	updated_at: string;
	document: TaskDocument;
	bundle: BundleDocument;
	bundle_latest_revision: number;
	split: TaskSplit;
	flags: LeakageFlag[];
	versions: TaskVersionRef[];
}

/** A proposed starting document for a bundle; nothing is saved. */
export interface TaskDraft {
	document: TaskDocument;
	bundle: BundleDocument;
	split: TaskSplit;
	flags: LeakageFlag[];
}

export interface TaskSummary {
	id: string;
	version: number;
	status: TaskStatus;
	kind: TaskKind;
	summary: string;
	objective: string;
	objective_type: ObjectiveType;
	family: string;
	partition: Partition | null;
	bundle_id: string;
	bundle_revision: number;
	criterion_count: number;
	updated_at: string;
}

export interface TasksResponse {
	items: TaskSummary[];
}

export interface TaskIssue {
	code: string;
	message: string;
	criterion_id: string | null;
}

/** The exported case record; the two sections are stored together and served apart. */
export interface CaseRecord {
	schema_version: 1;
	case: Record<string, unknown> & {
		id: string;
		version: number;
		redaction: { scrub_version: string; term_count: number; manifest: Record<string, number> };
	};
	candidate: Record<string, unknown>;
	judge: Record<string, unknown>;
	digest: string;
}
