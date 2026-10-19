import type { ConversationDetail, ConversationSummary } from '$lib/api/types';

export const summary: ConversationSummary = {
	id: 'conversation-a',
	source: { id: 'src-pi', kind: 'pi', display_name: 'Pi · laptop' },
	native_id: 'refund-session',
	revision: 'rev-2',
	captured_at: '2026-03-03T00:00:00Z',
	title: 'Refund investigation',
	preview: 'I need a refund for the second item.',
	started_at: '2026-03-01T10:42:00Z',
	last_activity_at: '2026-03-01T11:18:00Z',
	event_count: 3,
	message_count: 3,
	branch_count: 2,
	relationship_counts: {},
	coverage: { messages: 'available', usage: 'unknown' },
	match_count: 0,
	matches: []
};

export const detail: ConversationDetail = {
	summary,
	is_latest: true,
	revisions: [{ revision: 'rev-2', captured_at: '2026-03-03T00:00:00Z' }],
	events: [
		{
			id: 'e1',
			native_id: 'u1',
			ordinal: 0,
			parent_id: null,
			kind: 'message',
			role: 'user',
			occurred_at: '2026-03-01T10:42:00Z',
			content: [
				{
					id: 'e1:b0',
					kind: 'text',
					text: 'I need a refund for the second item.',
					tool_call_id: null,
					artifact_id: null,
					extensions: {}
				}
			],
			extensions: {}
		},
		{
			id: 'e2',
			native_id: 'a1',
			ordinal: 1,
			parent_id: 'e1',
			kind: 'message',
			role: 'assistant',
			occurred_at: null,
			content: [
				{
					id: 'e2:b0',
					kind: 'text',
					text: null,
					tool_call_id: null,
					artifact_id: null,
					extensions: {}
				}
			],
			extensions: {}
		},
		{
			id: 'e3',
			native_id: 'a2',
			ordinal: 2,
			parent_id: 'e1',
			kind: 'message',
			role: 'assistant',
			occurred_at: '2026-03-01T11:18:00Z',
			content: [
				{
					id: 'e3:b0',
					kind: 'text',
					text: 'I can offer a replacement instead.',
					tool_call_id: null,
					artifact_id: null,
					extensions: {}
				}
			],
			extensions: {}
		}
	],
	artifacts: [],
	metadata: [],
	relationships: [],
	referenced_by: [],
	branches: [
		{
			id: 'e2',
			leaf_event_id: 'e2',
			event_ids: ['e1', 'e2'],
			fork_event_id: 'e1',
			divergent_event_id: 'e2',
			is_original: true,
			origin: 'captured',
			models: ['model-a']
		},
		{
			id: 'e3',
			leaf_event_id: 'e3',
			event_ids: ['e1', 'e3'],
			fork_event_id: 'e1',
			divergent_event_id: 'e3',
			is_original: false,
			origin: 'captured',
			models: ['model-b']
		}
	]
};
