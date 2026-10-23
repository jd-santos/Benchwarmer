import type {
	BundleOrigin,
	BundleStatus,
	CitedToolCall,
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

/** The bundle's title is its summary, else its general objective; the goal is never a title. */
export function bundleLabel(bundle: { summary: string; objective: string }): string {
	return bundle.summary.trim() || bundle.objective.trim() || 'Untitled bundle';
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

/** Workflow ids known to the UI, in reader terms; anything else is shown as written. */
const workflowLabels: Record<string, string> = {
	'propose-bundles': 'Propose bundles'
};

export function workflowLabel(workflow: string): string {
	return workflowLabels[workflow] ?? workflow;
}

/** The timestamp part of a run id, which is what distinguishes runs of one workflow. */
export function shortRunId(runId: string): string {
	return runId.replace(/^[a-z-]+-(?=\d{4})/, '');
}

/** A generated id cut to its prefix and the first eight hex digits; the full id suits a title. */
export function shortId(id: string): string {
	return id.replace(/^([a-z]+-)?([0-9a-f]{8})[0-9a-f]{24,}$/, '$1$2');
}

/** Elapsed time between two timestamps, such as "29s" or "4m 12s". */
export function formatDuration(startedAt: string, finishedAt: string): string {
	const seconds = Math.max(0, Math.round((Date.parse(finishedAt) - Date.parse(startedAt)) / 1000));
	if (seconds < 60) return `${seconds}s`;
	const minutes = Math.floor(seconds / 60);
	if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
	return `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
}

/** The run input (one conversation's pass) whose proposals include this bundle, if recorded. */
export function runInputFor(run: HarnessRunRecord, bundleId: string) {
	return run.inputs.find((input) => input.bundle_ids.includes(bundleId)) ?? null;
}

/**
 * What part of the event an item cites, in reader terms. Citing the whole turn is
 * the common case and says nothing beyond the role, so it gets no label.
 */
export function scopeLabel(item: ResolvedBundleItem): string | null {
	if (item.item.ref.text_start != null) return 'Selected text';
	switch (item.block_kind) {
		case null:
			return null;
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

/**
 * A tool call's arguments as indented JSON when they parse; otherwise the captured text.
 * Tool output is left as the tool wrote it.
 */
export function excerptCode(item: ResolvedBundleItem): string {
	const text = item.excerpt ?? '';
	return item.block_kind === 'tool_call' ? formatArguments(text) : text;
}

/** Whether an item's excerpt is tool input or output, which reads as code rather than prose. */
export function isCodeExcerpt(item: ResolvedBundleItem): boolean {
	return item.block_kind === 'tool_call' || item.block_kind === 'tool_result';
}

/** Indented JSON for tool arguments when they parse; otherwise the captured text. */
export function formatArguments(text: string): string {
	try {
		const parsed: unknown = JSON.parse(text);
		return typeof parsed === 'object' && parsed !== null ? JSON.stringify(parsed, null, 2) : text;
	} catch {
		return text;
	}
}

/**
 * One line that says what a tool call did, for a collapsed list: the argument
 * values in order, such as the command or the path, cut to fit.
 */
export function toolCallPreview(call: CitedToolCall, limit = 120): string {
	if (call.arguments === null) return 'arguments not captured';
	let line = call.arguments;
	try {
		const parsed: unknown = JSON.parse(call.arguments);
		if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
			line = Object.entries(parsed)
				.map(
					([key, value]) => `${key}: ${typeof value === 'string' ? value : JSON.stringify(value)}`
				)
				.join(' · ');
		}
	} catch {
		// Not JSON; show the text as captured.
	}
	line = line.replace(/\s+/g, ' ').trim();
	return line.length > limit ? `${line.slice(0, limit - 1)}…` : line;
}
