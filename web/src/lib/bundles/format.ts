import type { BundleStatus, EvidenceRole, ResolvedBundleItem } from '$lib/api/types';

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
	}
];

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
