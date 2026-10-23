import type { BundleDetail, HarnessRunRecord } from '$lib/api/types';

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
	provenance: null,
	request_id: null,
	created_at: '2026-10-19T10:00:00Z',
	updated_at: '2026-10-19T10:00:00Z',
	document: {
		schema_version: 2,
		summary: '',
		objective: '',
		goal: '',
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
			omitted_before: null,
			tool_calls: []
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
			omitted_before: 2,
			tool_calls: []
		}
	],
	revisions: [
		{
			number: 1,
			origin: 'human',
			producer: 'web',
			provenance: null,
			created_at: '2026-10-19T10:00:00Z'
		}
	]
};

export const proposedProvenance = {
	run_id: 'propose-bundles-2026-10-19T10-00-00-000Z',
	workflow: 'propose-bundles',
	harness_version: '0.0.1',
	provider: 'anthropic',
	model: 'claude-sonnet-5-5',
	thinking_level: 'medium',
	report_path: 'reports/harness/propose-bundles-2026-10-19T10-00-00-000Z.json'
};

export const proposedProducer =
	'benchwarmer-harness/propose-bundles@0.0.1 anthropic/claude-sonnet-5-5';

/** A model's draft awaiting review; the same evidence as `bundle`. */
export const proposedBundle: BundleDetail = {
	...bundle,
	id: 'bundle-2',
	origin: 'generated',
	producer: proposedProducer,
	provenance: proposedProvenance,
	request_id: `${proposedProvenance.run_id}:conversation-a:abc123`,
	document: {
		...bundle.document,
		summary: 'Refund request and the offered resolution',
		objective: 'Resolve a customer refund request',
		goal: 'Get the second item refunded',
		rationale: 'The user asked for a refund and the assistant offered one.'
	},
	revisions: [
		{
			number: 1,
			origin: 'generated',
			producer: proposedProducer,
			provenance: proposedProvenance,
			created_at: '2026-10-19T10:00:00Z'
		}
	]
};

const usage = {
	input: 10,
	output: 3924,
	cache_read: 28395,
	cache_write: 23481,
	total_tokens: 55810,
	cost: {
		input: 0.00002,
		output: 0.03924,
		cache_read: 0.0028395,
		cache_write: 0.093924,
		total: 0.1360235
	}
};

/** The run that produced `proposedBundle`, with one conversation's usage. */
export const proposedRun: HarnessRunRecord = {
	run_id: proposedProvenance.run_id,
	workflow: 'propose-bundles',
	harness_version: '0.0.1',
	started_at: '2026-10-19T10:00:00Z',
	finished_at: '2026-10-19T10:00:29Z',
	api_base_url: 'http://127.0.0.1:8000',
	model: {
		provider: 'anthropic',
		model_id: 'claude-sonnet-5-5',
		thinking_level: null,
		base_url_override: null
	},
	producer: proposedProducer,
	inputs: [
		{
			id: 'conversation-a',
			kind: 'conversation',
			status: 'done',
			reason: null,
			bundle_ids: ['bundle-2', 'bundle-3'],
			usage: { models: { 'anthropic/claude-sonnet-5-5': usage }, tools: {} }
		}
	],
	usage_total: { models: { 'anthropic/claude-sonnet-5-5': usage }, tools: {} },
	pricing_source: 'pi-ai model catalog estimate',
	report_path: 'reports/harness/propose-bundles-2026-10-19T10-00-00-000Z.json'
};
