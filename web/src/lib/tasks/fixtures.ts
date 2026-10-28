import type { PartitionAssignment, TaskDetail, TaskDraft, TaskSummary } from '$lib/api/types';

const ref = {
	conversation_id: 'conversation-a',
	revision: 'rev-2',
	event_id: 'e1',
	block_id: null,
	text_start: null,
	text_end: null
};

const split: TaskDetail['split'] = {
	conversation_id: 'conversation-a',
	revision: 'rev-2',
	conversation_title: 'Refund investigation',
	candidate: [
		{
			event_id: 'e1',
			role: 'user',
			kind: 'message',
			occurred_at: '2026-03-01T10:42:00Z',
			preview: 'I need a refund for the second item.',
			cited_as: ['requirement']
		},
		{
			event_id: 'e2',
			role: 'assistant',
			kind: 'message',
			occurred_at: '2026-03-01T10:43:00Z',
			preview: 'Let me look up the order.',
			cited_as: []
		},
		{
			event_id: 'e3',
			role: 'user',
			kind: 'message',
			occurred_at: '2026-03-01T10:44:00Z',
			preview: 'Order 4411, placed last Tuesday.',
			cited_as: []
		}
	],
	judge: [
		{
			event_id: 'e4',
			role: 'assistant',
			kind: 'message',
			occurred_at: '2026-03-01T10:45:00Z',
			preview: 'I can offer a refund of the second item to the original card.',
			cited_as: ['result']
		},
		{
			event_id: 'e5',
			role: 'user',
			kind: 'message',
			occurred_at: '2026-03-01T10:46:00Z',
			preview: 'Thanks.',
			cited_as: []
		}
	],
	other_judge: []
};

const bundle: TaskDetail['bundle'] = {
	schema_version: 3,
	summary: 'Refund request and the offered resolution',
	objective: 'Resolve a customer refund request',
	objective_type: 'unknown',
	goal: 'Get the second item refunded',
	status: 'reviewed',
	rationale: null,
	missing_evidence: [],
	items: [
		{ ref, role: 'requirement', note: null },
		{ ref: { ...ref, event_id: 'e4' }, role: 'result', note: null }
	]
};

export const taskDraft: TaskDraft = {
	bundle,
	document: {
		schema_version: 1,
		bundle_id: 'bundle-1',
		bundle_revision: 2,
		kind: 'chat',
		summary: 'Refund request and the offered resolution',
		objective: 'Resolve a customer refund request',
		objective_type: 'unknown',
		family: 'conversation-a',
		cut_point: { conversation_id: 'conversation-a', revision: 'rev-2', event_id: 'e3' },
		reconstruction: { level: 'prompt_only', gaps: [] },
		criteria: [],
		expected_scope: null,
		leakage_review: null,
		partition: null,
		status: 'draft',
		reviewer_notes: ''
	},
	split,
	flags: []
};

export const task: TaskDetail = {
	id: 'task-1',
	version: 1,
	latest_version: 1,
	producer: 'web',
	created_at: '2026-10-26T10:00:00Z',
	updated_at: '2026-10-26T10:00:00Z',
	document: {
		...taskDraft.document,
		criteria: [
			{
				id: 'offers-refund-path',
				statement: 'Names a refund path for the item without asking for details already given.',
				method: 'human',
				rubric_version: 1,
				judge_evidence: [],
				needs: [],
				reviewer_label: 'pass',
				note: null
			}
		]
	},
	bundle,
	bundle_latest_revision: 2,
	split,
	flags: [],
	versions: [{ number: 1, status: 'draft', producer: 'web', created_at: '2026-10-26T10:00:00Z' }],
	partition: null,
	partition_assignment_id: null,
	unmet_needs: []
};

export const partitionAssignment: PartitionAssignment = {
	id: 'partition-1',
	seed: 'autumn-1',
	split: { development: 0.6, calibration: 0.2, holdout: 0.2 },
	scope: { statuses: ['draft', 'approved'] },
	task_counts: { development: 5, calibration: 2, holdout: 1 },
	family_counts: { development: 3, calibration: 1, holdout: 1 },
	task_count: 8,
	family_count: 5,
	moved_families: 0,
	producer: 'web',
	created_at: '2026-10-27T09:00:00Z'
};

export const taskSummary: TaskSummary = {
	id: 'task-1',
	version: 1,
	status: 'draft',
	kind: 'chat',
	summary: 'Refund request and the offered resolution',
	objective: 'Resolve a customer refund request',
	objective_type: 'unknown',
	family: 'conversation-a',
	partition: null,
	partition_assignment_id: null,
	bundle_id: 'bundle-1',
	bundle_revision: 2,
	criterion_count: 1,
	analysis_only: false,
	updated_at: '2026-10-26T10:00:00Z'
};
