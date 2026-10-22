/**
 * Pi Durable tools for turning one scrubbed Pi session into a synthetic fixture.
 *
 * The session content is held by the harness process, read from the path the
 * operator named; the model never chooses a path. `read_scrubbed_session` and
 * `check_fixture` are replay-safe reads against the API. `write_fixture_draft`
 * writes a file under the gitignored report directory for human diff review,
 * never into `tests/fixtures/`, so it is not replay-safe.
 */

import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { Type, type Static } from '@earendil-works/pi-ai';
import { defineExtension, defineTool, type Extension } from '@earendil-works/pi-durable';

import type { BenchwarmerClient, FixtureConversation } from '../benchwarmer/client.ts';
import { countPlaceholders, toFixtureDocument } from '../fixture.ts';

export type FixtureDraftRecord = {
	native_id: string;
	path: string;
	event_count: number;
	placeholders_remaining: number;
};

export type FixtureCheckRecord = {
	native_id: string;
	ok: boolean;
	fidelity_issues: number;
	leak_issues: number;
};

/** The session currently being anonymized; the workflow fills it before each conversation. */
export interface SessionSlot {
	content: string;
}

export interface FixturesExtensionOptions {
	/** Complete Pi session JSONL for the current session, read by the operator's command. */
	session: SessionSlot;
	/** Operator-supplied sensitive terms scrubbed and leak-checked. */
	terms: string[];
	/** Directory for drafts: `reports/harness/fixtures/<runId>/`. */
	draftDir: string;
	/** Recorded in the draft document description. */
	producer: string;
	onCheck?: (record: FixtureCheckRecord) => void;
	onDraftWritten?: (record: FixtureDraftRecord) => void;
}

const blockSchema = Type.Object({
	kind: Type.Union(
		['text', 'reasoning', 'tool_call', 'tool_result', 'attachment', 'unknown'].map((k) => Type.Literal(k))
	),
	text: Type.Union([Type.String(), Type.Null()]),
	tool_call_id: Type.Union([Type.String(), Type.Null()]),
	artifact_id: Type.Union([Type.String(), Type.Null()]),
	extensions: Type.Record(Type.String(), Type.Unknown())
});

const eventSchema = Type.Object({
	native_id: Type.String(),
	ordinal: Type.Integer({ minimum: 0 }),
	parent_id: Type.Union([Type.String(), Type.Null()]),
	kind: Type.Union(['message', 'compaction', 'configuration', 'unknown'].map((k) => Type.Literal(k))),
	role: Type.Union(
		['system', 'developer', 'user', 'assistant', 'tool', 'unknown'].map((k) => Type.Literal(k))
	),
	occurred_at: Type.Union([Type.String(), Type.Null()]),
	content: Type.Array(blockSchema),
	extensions: Type.Record(Type.String(), Type.Unknown())
});

export const fixtureConversationSchema = Type.Object({
	native_id: Type.String({ description: 'Invented session id; never the original' }),
	title: Type.Union([Type.String(), Type.Null()]),
	coverage: Type.Union([Type.Record(Type.String(), Type.String()), Type.Null()]),
	usage: Type.Array(Type.Record(Type.String(), Type.Unknown())),
	events: Type.Array(eventSchema),
	relationships: Type.Array(Type.Record(Type.String(), Type.Unknown()))
});

type FixtureConversationInput = Static<typeof fixtureConversationSchema>;

function asFixture(input: FixtureConversationInput): FixtureConversation {
	return input as FixtureConversation;
}

function text(value: string) {
	return { output: [{ type: 'text' as const, text: value }] };
}

function error(value: string) {
	return { ...text(value), isError: true };
}

function formatCounts(counts: Partial<Record<string, number>>): string {
	const parts = Object.entries(counts).map(([k, v]) => `${k}=${v}`);
	return parts.length ? parts.join(' ') : 'nothing detected';
}

export function createFixturesExtension(
	client: BenchwarmerClient,
	options: FixturesExtensionOptions
): Extension {
	const readScrubbedSession = defineTool({
		name: 'read_scrubbed_session',
		description:
			'The operator-selected Pi session after deterministic scrubbing, as a fixture-shaped conversation JSON. Placeholders like <email-1>, <url-2>, <term-3>, /scrubbed/path-4/file-4.py stand for removed private values; the same placeholder always means the same original. Read this once, then write your invented analog from it.',
		parameters: Type.Object({}),
		replay: 'safe',
		execute: async () => {
			if (!options.session.content) return error('No session is loaded for this run.');
			const scrubbed = await client.scrubPiSession(options.session.content, options.terms);
			const report = scrubbed.report;
			const header = [
				`session ${scrubbed.native_id} (${scrubbed.source_version ?? 'unknown format'}): ${scrubbed.fixture.events.length} events`,
				`scrubbed: ${formatCounts(report.counts)}; operator terms: ${report.term_count}`,
				`placeholders: ${Object.keys(report.placeholders).join(', ') || 'none'}`,
				'',
				'fixture conversation (scrubbed; rewrite every text while keeping structure):'
			].join('\n');
			return text(`${header}\n${JSON.stringify(scrubbed.fixture, null, 1)}`);
		}
	});

	const checkFixture = defineTool({
		name: 'check_fixture',
		description:
			'Compare a candidate fixture conversation with the original session: structural fidelity (event count, ordinals, parents, kinds, roles, block kinds, captured-text gaps, tool pairing, extension keys, relationships) and leaks (operator terms or any scrubbed original text). Call until it reports ok. Issues name locations and offsets, never the private text.',
		parameters: Type.Object({ candidate: fixtureConversationSchema }),
		replay: 'safe',
		execute: async (args) => {
			const candidate = asFixture(args.candidate);
			const result = await client.checkFixture(options.session.content, candidate, options.terms);
			const remaining = countPlaceholders(candidate);
			options.onCheck?.({
				native_id: result.native_id,
				ok: result.ok && remaining === 0,
				fidelity_issues: result.fidelity.length,
				leak_issues: result.leaks.length
			});
			const lines = [
				`fidelity issues: ${result.fidelity.length}`,
				...result.fidelity.map((i) => `  ${i.code}${i.ordinal === null ? '' : ` @ordinal ${i.ordinal}`}: ${i.message}`),
				`leak issues: ${result.leaks.length}`,
				...result.leaks.map(
					(i) => `  ${i.code}${i.category ? ` (${i.category})` : ''} at ${i.location} [${i.text_start}..${i.text_end}]`
				),
				`placeholders still present: ${remaining}`
			];
			const ok = result.ok && remaining === 0;
			return {
				...text(`${ok ? 'OK' : 'NOT OK'}\n${lines.join('\n')}`),
				details: { ok, fidelity: result.fidelity.length, leaks: result.leaks.length, placeholders: remaining }
			};
		}
	});

	const writeFixtureDraft = defineTool({
		name: 'write_fixture_draft',
		description:
			'Write the finished candidate as a fixture-format JSON draft for human diff review. Only call after check_fixture reports OK. The draft goes to the run report directory, never into tests/fixtures/.',
		parameters: Type.Object({
			candidate: fixtureConversationSchema,
			summary: Type.String({ minLength: 1, maxLength: 400, description: 'One sentence on the invented scenario' })
		}),
		replay: 'unsafe',
		execute: async (args) => {
			const candidate = asFixture(args.candidate);
			const remaining = countPlaceholders(candidate);
			if (remaining > 0) {
				return error(`Draft refused: ${remaining} placeholder(s) remain. Replace every placeholder with invented content first.`);
			}
			if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$/.test(candidate.native_id)) {
				return error('Draft refused: native_id must be a short identifier (letters, digits, . _ -).');
			}
			const document = toFixtureDocument(candidate, {
				sourceId: 'fixture-source-pi-anonymized',
				sourceKind: 'pi',
				batchId: `anonymized-${candidate.native_id}`,
				capturedAt: new Date().toISOString(),
				description: `Synthetic analog written by ${options.producer}; pending human diff review. ${args.summary}`
			});
			await mkdir(options.draftDir, { recursive: true });
			const target = path.join(options.draftDir, `${candidate.native_id}.json`);
			await writeFile(target, JSON.stringify(document, null, 2) + '\n');
			const record: FixtureDraftRecord = {
				native_id: candidate.native_id,
				path: target,
				event_count: candidate.events.length,
				placeholders_remaining: remaining
			};
			options.onDraftWritten?.(record);
			return { ...text(`Draft written to ${target} for review.`), details: record };
		}
	});

	return defineExtension({
		name: 'benchwarmer-fixtures',
		tools: [readScrubbedSession, checkFixture, writeFixtureDraft]
	});
}
