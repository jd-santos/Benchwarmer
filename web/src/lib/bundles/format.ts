import type { BundleOrigin, BundleStatus, EvidenceRole, ResolvedBundleItem } from '$lib/api/types';

export const roleOptions: { value: EvidenceRole; label: string }[] = [
	{ value: 'requirement', label: 'Requirement' },
	{ value: 'action', label: 'Action' },
	{ value: 'result', label: 'Result' },
	{ value: 'correction', label: 'Correction' },
	{ value: 'context', label: 'Context' }
];

export const statusOptions: { value: BundleStatus; label: string; hint: string }[] = [
	{ value: 'draft', label: 'Draft', hint: 'Still being assembled' },
	{ value: 'reviewed', label: 'Reviewed', hint: 'Evidence and roles checked' },
	{
		value: 'analysis_only',
		label: 'Analysis only',
		hint: 'Useful for review, not for building a task'
	},
	{
		value: 'rejected',
		label: 'Rejected',
		hint: 'Not useful evidence; kept with the reason so proposals can improve'
	}
];

export function originLabel(origin: BundleOrigin): string {
	return origin === 'generated' ? 'Proposed' : 'Human';
}

export interface ProducerDescription {
	/** The workflow or client that produced the revision, such as the web app or a harness workflow. */
	workflow: string;
	version: string | null;
	/** The model as `provider/model-id` when a harness run recorded one. */
	model: string | null;
}

/**
 * Split a producer string into parts the reader can scan.
 *
 * Harness revisions record `workflow@version provider/model`; the web app
 * records `web`. Anything else is shown whole as the workflow.
 */
export function describeProducer(producer: string): ProducerDescription {
	const match = /^(\S+?)(?:@(\S+))?(?: (\S+\/\S+))?$/.exec(producer.trim());
	if (!match) return { workflow: producer, version: null, model: null };
	return { workflow: match[1], version: match[2] ?? null, model: match[3] ?? null };
}

/** Who produced a revision, in one short phrase; the full producer suits a title attribute. */
export function producerLabel(origin: BundleOrigin, producer: string): string {
	const { workflow, model } = describeProducer(producer);
	if (origin === 'generated') return model ? `Proposed by ${model}` : `Proposed by ${workflow}`;
	return workflow === 'web' ? 'Human, in the web app' : `Human, via ${workflow}`;
}

export function statusLabel(status: BundleStatus): string {
	return statusOptions.find((option) => option.value === status)?.label ?? status;
}

export function bundleLabel(objective: string): string {
	return objective.trim() || 'Untitled bundle';
}

/** What part of the event an item cites, in reader terms. */
export function scopeLabel(item: ResolvedBundleItem): string {
	if (item.item.ref.text_start != null) return 'Selected text';
	switch (item.block_kind) {
		case null:
			return item.event_kind === 'message' ? 'Whole message' : 'Whole event';
		case 'tool_result':
			return 'Tool output';
		case 'tool_call':
			return 'Tool call';
		case 'reasoning':
			return 'Reasoning';
		default:
			return 'Text block';
	}
}
