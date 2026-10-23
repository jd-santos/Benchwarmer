import type {
	BundleOrigin,
	BundleStatus,
	EvidenceRole,
	HarnessRunRecord,
	ResolvedBundleItem,
	RunUsageTotal
} from '$lib/api/types';

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

/** The bundle's title is its summary alone; goal and objective are not readable as titles. */
export function bundleLabel(bundle: { summary: string }): string {
	return bundle.summary.trim() || 'Untitled bundle';
}

/** The model id without its provider, for tight table cells; the full name suits a title. */
export function shortModel(model: string): string {
	return model.slice(model.indexOf('/') + 1);
}

/** A dollar figure for a catalog estimate; small amounts keep enough precision to compare. */
export function formatEstimate(usd: number): string {
	if (usd === 0) return '$0';
	if (usd < 0.01) return `$${usd.toFixed(4)}`;
	if (usd < 1) return `$${usd.toFixed(3)}`;
	return `$${usd.toFixed(2)}`;
}

export function usageTotals(usage: RunUsageTotal): { tokens: number; estimate: number } {
	let tokens = 0;
	let estimate = 0;
	for (const bucket of [usage.models, usage.tools]) {
		for (const entry of Object.values(bucket)) {
			tokens += entry.total_tokens;
			estimate += entry.cost.total;
		}
	}
	return { tokens, estimate };
}

/** The run input (one conversation's pass) whose proposals include this bundle, if recorded. */
export function runInputFor(run: HarnessRunRecord, bundleId: string) {
	return run.inputs.find((input) => input.bundle_ids.includes(bundleId)) ?? null;
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
