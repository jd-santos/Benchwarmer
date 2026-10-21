import { describe, expect, it } from 'vitest';

import type { FixtureConversation, ScrubbedSession } from './benchwarmer/client.ts';
import { checkDisclosure, countPlaceholders, DisclosureError, toFixtureDocument } from './fixture.ts';

describe('checkDisclosure', () => {
	it('refuses to start without --disclose-to and prints the rule', () => {
		expect(() => checkDisclosure('anthropic', undefined)).toThrow(DisclosureError);
		expect(() => checkDisclosure('anthropic', '')).toThrow(/--disclose-to <provider>/);
	});

	it('refuses a provider that differs from the model provider', () => {
		expect(() => checkDisclosure('openrouter', 'anthropic')).toThrow(
			/names "anthropic" but --model would send content to "openrouter"/
		);
	});

	it('accepts the same provider regardless of case and whitespace', () => {
		expect(() => checkDisclosure('anthropic', ' Anthropic ')).not.toThrow();
	});
});

/** The shape `POST /api/v1/fixtures/scrub-pi-session` returns, abbreviated. */
const scrubbed: ScrubbedSession = {
	native_id: 'pi-session',
	source_version: 'session-v3',
	title: null,
	events: [],
	report: {
		schema_version: 1,
		producer: 'benchwarmer.anonymize',
		producer_version: '1',
		native_id: 'pi-session',
		source_version: 'session-v3',
		term_count: 1,
		counts: { email: 1, path: 1, term: 1 },
		placeholders: { '<email-1>': 'email', '/scrubbed/path-1/file-1.log': 'path', '<term-1>': 'term' },
		spans: [],
		notes: []
	},
	fixture: {
		native_id: 'pi-session',
		title: null,
		coverage: { messages: 'available' },
		usage: [{ entry_id: 'a0', provider: 'synthetic', model: 'm' }],
		relationships: [],
		events: [
			{
				native_id: 'u0', ordinal: 10, parent_id: null, kind: 'message', role: 'user', occurred_at: null,
				extensions: { pi_entry_type: 'message' },
				content: [{ kind: 'text', text: 'mail <email-1> about /scrubbed/path-1/file-1.log for <term-1>', tool_call_id: null, artifact_id: null, extensions: {} }]
			},
			{
				native_id: 'a0', ordinal: 20, parent_id: 'u0', kind: 'message', role: 'assistant', occurred_at: null,
				extensions: { pi_entry_type: 'message' },
				content: [{ kind: 'tool_call', text: 'bash', tool_call_id: 'c1', artifact_id: null, extensions: {} }]
			}
		]
	}
};

describe('toFixtureDocument', () => {
	it('wraps a conversation in the schema_version 1 import-batch shape', () => {
		const document = toFixtureDocument(scrubbed.fixture, {
			sourceId: 'fixture-source-pi-anonymized',
			sourceKind: 'pi',
			batchId: 'anonymized-pi-session',
			capturedAt: '2026-10-21T00:00:00.000Z',
			description: 'draft'
		});
		expect(document.schema_version).toBe(1);
		expect(document.imports).toHaveLength(1);
		const batch = document.imports[0]!;
		expect(batch).toMatchObject({ source_id: 'fixture-source-pi-anonymized', source_kind: 'pi', batch_id: 'anonymized-pi-session' });
		expect(batch.conversations[0]).toBe(scrubbed.fixture);
		expect(Object.keys(batch.conversations[0]!.events[0]!)).not.toContain('id');
		expect(batch.conversations[0]!.events[1]!.parent_id).toBe('u0');
	});
});

describe('countPlaceholders', () => {
	it('counts every scrub placeholder still present anywhere in the candidate', () => {
		expect(countPlaceholders(scrubbed.fixture)).toBe(3);
		const rewritten: FixtureConversation = JSON.parse(JSON.stringify(scrubbed.fixture)) as FixtureConversation;
		rewritten.events[0]!.content[0]!.text = 'mail pat@fictional.test about /srv/app/logs/run.log for Pat';
		expect(countPlaceholders(rewritten)).toBe(0);
	});
});
