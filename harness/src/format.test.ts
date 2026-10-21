import { describe, expect, it } from 'vitest';

import type { ConversationEvent, ConversationOutline } from './benchwarmer/client.ts';
import { formatEvents, formatOutline } from './format.ts';

const outline: ConversationOutline = {
	schema_version: 1,
	producer: 'benchwarmer.outline',
	producer_version: '1',
	conversation_id: 'conv',
	revision: 'rev',
	event_count: 3,
	coverage: { tool_calls: 'partial' },
	notes: [],
	events: [
		{
			id: 'u1', native_id: 'n1', ordinal: 0, parent_id: null, kind: 'message', role: 'user',
			occurred_at: null, boundary: null, text_chars: 6, reasoning_chars: 0, text_captured: true,
			block_counts: { text: 1 }, tools: [], headings: [], preview: 'Fix it'
		},
		{
			id: 'a2', native_id: 'n2', ordinal: 1, parent_id: 'u1', kind: 'message', role: 'assistant',
			occurred_at: null, boundary: null, text_chars: 20, reasoning_chars: 3, text_captured: true,
			block_counts: { text: 1, tool_call: 2 },
			tools: [
				{ block_id: 'a2:b1', kind: 'tool_call', tool_call_id: 'c1', tool_name: 'bash', chars: 4 },
				{ block_id: 'a2:b2', kind: 'tool_call', tool_call_id: 'c2', tool_name: null, chars: 9 }
			],
			headings: [{ id: 'a2:b0::h0', block_id: 'a2:b0', level: 1, label: 'Plan', text_start: 0, text_end: 6 }],
			preview: '# Plan Run tests'
		},
		{
			id: 'c3', native_id: 'n3', ordinal: 2, parent_id: 'a2', kind: 'compaction', role: 'unknown',
			occurred_at: null, boundary: 'compaction', text_chars: 0, reasoning_chars: 0, text_captured: false,
			block_counts: {}, tools: [], headings: [], preview: null
		}
	],
	paths: [
		{
			id: 'c3', leaf_event_id: 'c3', is_original: true, fork_event_id: null, divergent_event_id: null,
			event_ids: ['u1', 'a2', 'c3'],
			exchanges: [{ id: 'c3:x0', user_event_id: 'u1', event_ids: ['u1', 'a2', 'c3'], assistant_event_count: 1, tool_call_count: 2, assistant_text_chars: 20, heading_count: 1 }],
			segments: [
				{ id: 'c3:s0', event_ids: ['u1', 'a2'], opened_by: 'start', closed_by: 'compaction' },
				{ id: 'c3:s1', event_ids: [], opened_by: 'compaction', closed_by: 'end' }
			]
		}
	]
};

describe('formatOutline', () => {
	it('lists exchanges with measured facts and unknown tool names as ?', () => {
		const text = formatOutline(outline);
		expect(text).toContain('conversation conv revision rev: 3 events, 1 path(s)');
		expect(text).toContain('c3:x0: user u1; 1 assistant event(s), 2 tool call(s)');
		expect(text).toContain('2 calls[bash,?]');
		expect(text).toContain('headings: # Plan');
		expect(text).toContain('BOUNDARY:compaction');
		expect(text).not.toContain('undefined');
	});

	it('reports a missing path instead of guessing', () => {
		expect(formatOutline(outline, 'nope')).toContain('no path nope');
	});
});

describe('formatEvents', () => {
	const events: ConversationEvent[] = [
		{
			id: 'a2', native_id: 'n2', ordinal: 1, parent_id: 'u1', kind: 'message', role: 'assistant',
			occurred_at: null, extensions: {},
			content: [
				{ id: 'a2:b0', kind: 'text', text: 'héllo wörld', tool_call_id: null, artifact_id: null, extensions: {} },
				{ id: 'a2:b1', kind: 'tool_result', text: null, tool_call_id: 'c1', artifact_id: null, extensions: {} }
			]
		}
	];

	it('truncates by code points and marks uncaptured text', () => {
		const text = formatEvents(events, 'rev', { maxBlockChars: 5 });
		expect(text).toContain('[block a2:b0 text 11 chars, showing 0..5]');
		expect(text).toContain('héllo\n…[6 more chars omitted]');
		expect(text).toContain('[block a2:b1 tool_result tool_call_id=c1] (text not captured)');
	});
});
