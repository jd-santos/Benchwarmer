/**
 * Pi Durable tools over Benchwarmer's conversation library.
 *
 * Read tools are replay-safe: rerunning them after a crash changes nothing.
 * `propose_bundle` writes a generated draft bundle through the API, so it is
 * not replay-safe; an interrupted call reports `interrupted` to the model
 * instead of silently creating a second bundle.
 */

import { createHash } from 'node:crypto';

import { Type } from '@earendil-works/pi-ai';
import { defineExtension, defineTool, type Extension } from '@earendil-works/pi-durable';

import type {
	BenchwarmerClient,
	BundleDocument,
	BundleItem,
	RunProvenance
} from '../benchwarmer/client.ts';
import { formatEvents, formatOutline } from '../format.ts';

/** A type alias, not an interface, so it satisfies Pi Durable's JSON `details` channel. */
export type ProposedBundleRecord = {
	bundle_id: string;
	conversation_id: string;
	revision: string;
	objective: string;
	item_count: number;
};

/**
 * A creation request id derived from the run and the proposal's content, so a
 * retry after an interrupted call returns the bundle already created instead
 * of a near-duplicate. Without a run id the call is not idempotent.
 */
export function proposalRequestId(runId: string, conversationId: string, document: BundleDocument): string {
	const digest = createHash('sha256').update(JSON.stringify(document)).digest('hex').slice(0, 24);
	return `${runId}:${conversationId}:${digest}`;
}

export interface LibraryExtensionOptions {
	/** Recorded on every generated bundle revision, for example `benchwarmer-harness/propose-bundles@0.0.1 anthropic/model`. */
	producer: string;
	/** Run identity stored with each generated revision so bundles can be grouped and costed per run. */
	provenance?: RunProvenance;
	/** Receives each bundle the model creates, for the run report. */
	onBundleCreated?: (record: ProposedBundleRecord) => void;
}

function text(value: string) {
	return { output: [{ type: 'text' as const, text: value }] };
}

function error(value: string) {
	return { ...text(value), isError: true };
}

export function createLibraryExtension(
	client: BenchwarmerClient,
	options: LibraryExtensionOptions
): Extension {
	const listConversations = defineTool({
		name: 'list_conversations',
		description:
			'List conversations in the library, newest activity first. Optional keyword query. Returns ids, titles, sizes, and sources.',
		parameters: Type.Object({
			q: Type.Optional(Type.String({ description: 'Keyword filter over captured text and metadata' })),
			limit: Type.Optional(Type.Integer({ minimum: 1, maximum: 200 }))
		}),
		replay: 'safe',
		execute: async (args) => {
			const params: { q?: string; limit?: number } = {};
			if (args.q !== undefined) params.q = args.q;
			if (args.limit !== undefined) params.limit = args.limit;
			const page = await client.listConversations(params);
			const lines = page.items.map(
				(c) =>
					`${c.id}  rev=${c.revision}  ${c.source.kind}  events=${c.event_count}  branches=${c.branch_count}  ${c.title ?? '(untitled)'}  "${(c.preview ?? '').slice(0, 80)}"`
			);
			return text(`${page.total} conversation(s); showing ${page.items.length}\n${lines.join('\n')}`);
		}
	});

	const getOutline = defineTool({
		name: 'get_outline',
		description:
			'Deterministic outline of one conversation revision: paths, exchanges, per-event roles, sizes, tool activity, headings, and compaction/configuration boundaries. Read this before reading events. Nothing in it is inferred.',
		parameters: Type.Object({
			conversation_id: Type.String(),
			revision: Type.Optional(Type.String({ description: 'Pin a revision; default latest' })),
			path_id: Type.Optional(Type.String({ description: 'Outline this path instead of the original one' }))
		}),
		replay: 'safe',
		execute: async (args) => {
			const outline = await client.getOutline(args.conversation_id, args.revision);
			return text(formatOutline(outline, args.path_id));
		}
	});

	const readEvents = defineTool({
		name: 'read_events',
		description:
			'Captured content of selected events in one conversation revision, block by block with the exact ids to cite. Select by event ids or an ordinal range; long blocks are truncated unless max_block_chars is raised.',
		parameters: Type.Object({
			conversation_id: Type.String(),
			revision: Type.String({ description: 'The revision the outline reported' }),
			event_ids: Type.Optional(Type.Array(Type.String(), { maxItems: 60 })),
			from_ordinal: Type.Optional(Type.Integer({ minimum: 0 })),
			to_ordinal: Type.Optional(Type.Integer({ minimum: 0, description: 'Inclusive' })),
			max_block_chars: Type.Optional(Type.Integer({ minimum: 200, maximum: 40000 }))
		}),
		replay: 'safe',
		execute: async (args) => {
			if (!args.event_ids && args.from_ordinal === undefined && args.to_ordinal === undefined) {
				return error('Select events with event_ids or from_ordinal/to_ordinal.');
			}
			const detail = await client.getConversation(args.conversation_id, args.revision);
			const wanted = new Set(args.event_ids ?? []);
			const from = args.from_ordinal ?? 0;
			const to = args.to_ordinal ?? Number.MAX_SAFE_INTEGER;
			const selected = detail.events.filter((e) =>
				args.event_ids ? wanted.has(e.id) : e.ordinal >= from && e.ordinal <= to
			);
			if (!selected.length) return error('No events matched the selection in that revision.');
			const opts = args.max_block_chars === undefined ? {} : { maxBlockChars: args.max_block_chars };
			return text(formatEvents(selected, detail.summary.revision, opts));
		}
	});

	const listBundles = defineTool({
		name: 'list_bundles',
		description: 'Existing bundles that cite a conversation, so proposals do not duplicate them.',
		parameters: Type.Object({ conversation_id: Type.String() }),
		replay: 'safe',
		execute: async (args) => {
			const bundles = await client.listBundles(args.conversation_id);
			if (!bundles.length) return text('No bundles cite this conversation yet.');
			return text(
				bundles
					.map((b) => `${b.id}  rev=${b.revision}  ${b.status}  items=${b.item_count}  ${b.objective || '(no objective)'}`)
					.join('\n')
			);
		}
	});

	const itemSchema = Type.Object({
		event_id: Type.String(),
		block_id: Type.Optional(Type.String({ description: 'Cite one block; required for a text range' })),
		text_start: Type.Optional(Type.Integer({ minimum: 0, description: 'Code-point offset, inclusive' })),
		text_end: Type.Optional(Type.Integer({ minimum: 1, description: 'Code-point offset, exclusive' })),
		role: Type.Union([
			Type.Literal('requirement'),
			Type.Literal('action'),
			Type.Literal('result'),
			Type.Literal('correction'),
			Type.Literal('context')
		]),
		note: Type.Optional(Type.String({ maxLength: 4000, description: 'Why this item matters' })),
		conversation_id: Type.Optional(Type.String({ description: 'Only for a related conversation (continuation/branch)' })),
		revision: Type.Optional(Type.String({ description: 'Required with conversation_id' }))
	});

	const proposeBundle = defineTool({
		name: 'propose_bundle',
		description:
			'Create one generated draft evidence bundle from exact event/block references. Benchwarmer validates every reference against the pinned revision and rejects sibling-branch mixes; fix the reported issues and call again. Repeating an identical proposal returns the bundle it already created.',
		parameters: Type.Object({
			conversation_id: Type.String(),
			revision: Type.String(),
			objective: Type.String({ minLength: 1, maxLength: 4000, description: 'What this piece of work tried to achieve' }),
			rationale: Type.String({ minLength: 1, maxLength: 4000, description: 'Why these items were selected' }),
			missing_evidence: Type.Optional(Type.Array(Type.String({ maxLength: 4000 }), { maxItems: 50 })),
			items: Type.Array(itemSchema, { minItems: 1, maxItems: 200 })
		}),
		replay: 'unsafe',
		execute: async (args) => {
			const items: BundleItem[] = [];
			for (const [index, item] of args.items.entries()) {
				if ((item.conversation_id === undefined) !== (item.revision === undefined)) {
					return error(`items[${index}]: conversation_id and revision must be given together.`);
				}
				if ((item.text_start === undefined) !== (item.text_end === undefined)) {
					return error(`items[${index}]: text_start and text_end must be given together.`);
				}
				const ref: BundleItem['ref'] = {
					conversation_id: item.conversation_id ?? args.conversation_id,
					revision: item.revision ?? args.revision,
					event_id: item.event_id,
					block_id: item.block_id ?? null,
					text_start: item.text_start ?? null,
					text_end: item.text_end ?? null
				};
				items.push({ ref, role: item.role, note: item.note ?? null });
			}
			const document: BundleDocument = {
				objective: args.objective,
				status: 'draft',
				items,
				rationale: args.rationale,
				missing_evidence: args.missing_evidence ?? []
			};
			const runId = options.provenance?.run_id;
			const result = await client.createBundle(document, 'generated', options.producer, {
				...(options.provenance ? { provenance: options.provenance } : {}),
				...(runId ? { requestId: proposalRequestId(runId, args.conversation_id, document) } : {})
			});
			if (!result.ok) {
				const issues = result.issues
					.map((i) => `${i.item_index === null ? 'bundle' : `items[${i.item_index}]`}: ${i.code}: ${i.message}`)
					.join('\n');
				return error(`Bundle rejected:\n${issues}`);
			}
			const record: ProposedBundleRecord = {
				bundle_id: result.bundle.id,
				conversation_id: args.conversation_id,
				revision: args.revision,
				objective: args.objective,
				item_count: items.length
			};
			if (!result.existing) options.onBundleCreated?.(record);
			return {
				...text(
					result.existing
						? `This proposal already exists as bundle ${result.bundle.id}; nothing new was created.`
						: `Created generated draft bundle ${result.bundle.id} with ${items.length} item(s).`
				),
				details: record
			};
		}
	});

	return defineExtension({
		name: 'benchwarmer-library',
		tools: [listConversations, getOutline, readEvents, listBundles, proposeBundle]
	});
}
