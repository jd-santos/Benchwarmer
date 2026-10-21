/**
 * Typed client for Benchwarmer's `/api/v1`.
 *
 * The harness reaches library data only through this API. Python stays
 * authoritative for conversation contracts, evidence resolution, and bundle
 * revisions; nothing here opens the SQLite database.
 */

export type CoverageState = 'available' | 'partial' | 'unavailable' | 'unknown' | 'redacted';
export type EventKind = 'message' | 'compaction' | 'configuration' | 'unknown';
export type EventRole = 'system' | 'developer' | 'user' | 'assistant' | 'tool' | 'unknown';
export type BlockKind = 'text' | 'reasoning' | 'tool_call' | 'tool_result' | 'attachment' | 'unknown';

export interface SourceRef {
	id: string;
	kind: string;
	display_name: string;
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
	coverage: Record<string, CoverageState>;
	match_count: number;
}

export interface ConversationsPage {
	items: ConversationSummary[];
	total: number;
	limit: number;
	offset: number;
}

export interface ContentBlock {
	id: string;
	kind: BlockKind;
	text: string | null;
	tool_call_id: string | null;
	artifact_id: string | null;
	extensions: Record<string, unknown>;
}

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

export interface Branch {
	id: string;
	leaf_event_id: string;
	event_ids: string[];
	fork_event_id: string | null;
	divergent_event_id: string | null;
	is_original: boolean;
	models: string[];
}

export interface ConversationDetail {
	summary: ConversationSummary;
	is_latest: boolean;
	revisions: { revision: string; captured_at: string }[];
	events: ConversationEvent[];
	branches: Branch[];
}

/** Mirrors `benchwarmer.outline.ConversationOutline`. */
export interface Heading {
	id: string;
	block_id: string;
	level: number;
	label: string;
	text_start: number;
	text_end: number;
}

export interface ToolActivity {
	block_id: string;
	kind: 'tool_call' | 'tool_result';
	tool_call_id: string;
	tool_name: string | null;
	chars: number | null;
}

export interface OutlineEvent {
	id: string;
	native_id: string;
	ordinal: number;
	parent_id: string | null;
	kind: EventKind;
	role: EventRole;
	occurred_at: string | null;
	boundary: 'compaction' | 'configuration' | null;
	text_chars: number;
	reasoning_chars: number;
	text_captured: boolean;
	block_counts: Partial<Record<BlockKind, number>>;
	tools: ToolActivity[];
	headings: Heading[];
	preview: string | null;
}

export interface Exchange {
	id: string;
	user_event_id: string | null;
	event_ids: string[];
	assistant_event_count: number;
	tool_call_count: number;
	assistant_text_chars: number;
	heading_count: number;
}

export interface Segment {
	id: string;
	event_ids: string[];
	opened_by: 'start' | 'compaction' | 'configuration';
	closed_by: 'end' | 'compaction' | 'configuration';
}

export interface PathOutline {
	id: string;
	leaf_event_id: string;
	is_original: boolean;
	fork_event_id: string | null;
	divergent_event_id: string | null;
	event_ids: string[];
	exchanges: Exchange[];
	segments: Segment[];
}

export interface ConversationOutline {
	schema_version: 1;
	producer: string;
	producer_version: string;
	conversation_id: string;
	revision: string;
	event_count: number;
	coverage: Record<string, string>;
	events: OutlineEvent[];
	paths: PathOutline[];
	notes: string[];
}

export type EvidenceRole = 'requirement' | 'action' | 'result' | 'correction' | 'context';
export type BundleStatus = 'draft' | 'reviewed' | 'analysis_only';
export type BundleOrigin = 'human' | 'generated';

export interface EvidenceRef {
	conversation_id: string;
	revision: string;
	event_id: string;
	block_id?: string | null;
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
	objective?: string;
	status?: BundleStatus;
	items: BundleItem[];
	rationale?: string | null;
	missing_evidence?: string[];
}

export interface BundleIssue {
	item_index: number | null;
	code: string;
	message: string;
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

export interface BundleDetail {
	id: string;
	revision: number;
	latest_revision: number;
	origin: BundleOrigin;
	producer: string;
	document: Required<Pick<BundleDocument, 'items'>> & BundleDocument;
}

export type CreateBundleResult =
	| { ok: true; bundle: BundleDetail }
	| { ok: false; issues: BundleIssue[] };

export class BenchwarmerApiError extends Error {
	constructor(
		readonly status: number,
		readonly method: string,
		readonly path: string,
		readonly body: string
	) {
		super(`${method} ${path} failed with ${status}: ${body.slice(0, 500)}`);
		this.name = 'BenchwarmerApiError';
	}
}

export interface ListConversationsParams {
	q?: string;
	source_kind?: string;
	limit?: number;
	offset?: number;
}

export class BenchwarmerClient {
	private readonly base: string;

	constructor(
		baseUrl: string,
		private readonly fetchImpl: typeof fetch = fetch
	) {
		this.base = baseUrl.replace(/\/+$/, '') + '/api/v1';
	}

	async listConversations(params: ListConversationsParams = {}): Promise<ConversationsPage> {
		const search = new URLSearchParams();
		for (const [key, value] of Object.entries(params)) {
			if (value !== undefined) search.set(key, String(value));
		}
		const query = search.size ? `?${search}` : '';
		return this.json<ConversationsPage>('GET', `/conversations${query}`);
	}

	async getConversation(id: string, revision?: string): Promise<ConversationDetail> {
		const query = revision ? `?revision=${encodeURIComponent(revision)}` : '';
		return this.json<ConversationDetail>('GET', `/conversations/${encodeURIComponent(id)}${query}`);
	}

	async getOutline(id: string, revision?: string): Promise<ConversationOutline> {
		const query = revision ? `?revision=${encodeURIComponent(revision)}` : '';
		return this.json<ConversationOutline>(
			'GET',
			`/conversations/${encodeURIComponent(id)}/outline${query}`
		);
	}

	async listBundles(conversationId?: string): Promise<BundleSummary[]> {
		const query = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : '';
		const page = await this.json<{ items: BundleSummary[] }>('GET', `/bundles${query}`);
		return page.items;
	}

	/** Create a bundle; evidence that does not resolve comes back as issues, not an exception. */
	async createBundle(
		document: BundleDocument,
		origin: BundleOrigin,
		producer: string
	): Promise<CreateBundleResult> {
		const response = await this.request('POST', '/bundles', { document, origin, producer });
		if (response.status === 422) {
			const body = (await response.json()) as { issues?: BundleIssue[]; detail?: unknown };
			if (Array.isArray(body.issues)) return { ok: false, issues: body.issues };
			return {
				ok: false,
				issues: [{ item_index: null, code: 'invalid_request', message: JSON.stringify(body.detail) }]
			};
		}
		if (!response.ok) {
			throw new BenchwarmerApiError(response.status, 'POST', '/bundles', await response.text());
		}
		return { ok: true, bundle: (await response.json()) as BundleDetail };
	}

	private async request(method: string, path: string, body?: unknown): Promise<Response> {
		const init: RequestInit = { method, headers: { accept: 'application/json' } };
		if (body !== undefined) {
			init.headers = { ...init.headers, 'content-type': 'application/json' };
			init.body = JSON.stringify(body);
		}
		return this.fetchImpl(this.base + path, init);
	}

	private async json<T>(method: string, path: string): Promise<T> {
		const response = await this.request(method, path);
		if (!response.ok) {
			throw new BenchwarmerApiError(response.status, method, path, await response.text());
		}
		return (await response.json()) as T;
	}
}
