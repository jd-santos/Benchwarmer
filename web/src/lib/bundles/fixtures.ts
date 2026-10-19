import type { BundleDetail } from '$lib/api/types';

const ref = {
	conversation_id: 'conversation-a',
	revision: 'rev-2',
	event_id: 'e1',
	block_id: null,
	text_start: null,
	text_end: null
};

export const bundle: BundleDetail = {
	id: 'bundle-1',
	revision: 1,
	latest_revision: 1,
	origin: 'human',
	producer: 'web',
	created_at: '2026-10-19T10:00:00Z',
	updated_at: '2026-10-19T10:00:00Z',
	document: {
		schema_version: 1,
		objective: '',
		status: 'draft',
		rationale: null,
		missing_evidence: [],
		items: [
			{ ref, role: 'requirement', note: null },
			{
				ref: { ...ref, event_id: 'e3', block_id: 'e3:b0', text_start: 0, text_end: 11 },
				role: 'action',
				note: null
			}
		]
	},
	items: [
		{
			item: { ref, role: 'requirement', note: null },
			conversation_title: 'Refund investigation',
			conversation_is_latest: true,
			event_role: 'user',
			event_kind: 'message',
			occurred_at: '2026-03-01T10:42:00Z',
			block_kind: null,
			excerpt: 'I need a refund for the second item.',
			omitted_before: null
		},
		{
			item: {
				ref: { ...ref, event_id: 'e3', block_id: 'e3:b0', text_start: 0, text_end: 11 },
				role: 'action',
				note: null
			},
			conversation_title: 'Refund investigation',
			conversation_is_latest: true,
			event_role: 'assistant',
			event_kind: 'message',
			occurred_at: null,
			block_kind: 'text',
			excerpt: 'I can offer',
			omitted_before: 2
		}
	],
	revisions: [{ number: 1, origin: 'human', producer: 'web', created_at: '2026-10-19T10:00:00Z' }]
};
