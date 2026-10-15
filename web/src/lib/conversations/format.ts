import type { CaptureState, ConversationSummary, EventRole } from '$lib/api/types';

const timestampFormat = new Intl.DateTimeFormat('en-US', {
	dateStyle: 'medium',
	timeStyle: 'short',
	timeZone: 'UTC'
});

const timeFormat = new Intl.DateTimeFormat('en-US', {
	timeStyle: 'short',
	timeZone: 'UTC'
});

export function formatTimestamp(value: string): string {
	return `${timestampFormat.format(new Date(value))} UTC`;
}

export function formatTime(value: string): string {
	return `${timeFormat.format(new Date(value))} UTC`;
}

/** Captured title, else quoted captured opening text; never a generated label. */
export function conversationLabel(summary: ConversationSummary): string {
	if (summary.title) return summary.title;
	if (summary.preview) return `“${summary.preview}”`;
	return 'Untitled conversation';
}

export function plural(count: number, singular: string, pluralForm = `${singular}s`): string {
	return `${count} ${count === 1 ? singular : pluralForm}`;
}

const dimensionLabels: Record<string, string> = {
	messages: 'messages',
	tool_calls: 'tool calls',
	usage: 'usage',
	prompts: 'prompts'
};

/** Capture dimensions that are not fully available, in a stable order. */
export function captureGaps(
	coverage: Record<string, CaptureState>
): { label: string; state: CaptureState }[] {
	return Object.entries(coverage)
		.filter(([, state]) => state !== 'available')
		.sort(([first], [second]) => first.localeCompare(second))
		.map(([name, state]) => ({ label: dimensionLabels[name] ?? name.replaceAll('_', ' '), state }));
}

/** Message-level gaps matter while reading; other dimensions stay in details. */
export function hasMessageGap(coverage: Record<string, CaptureState>): boolean {
	const state = coverage.messages;
	return state !== undefined && state !== 'available';
}

const roleLabels: Record<EventRole, string> = {
	system: 'System',
	developer: 'Developer',
	user: 'User',
	assistant: 'Assistant',
	tool: 'Tool',
	unknown: 'Unknown role'
};

export function roleLabel(role: EventRole): string {
	return roleLabels[role] ?? 'Unknown role';
}

export interface TextPart {
	text: string;
	match: boolean;
}

/** Split text into case-insensitive query matches for <mark> rendering. */
export function highlightParts(text: string, query: string | null): TextPart[] {
	const needle = query?.trim().toLocaleLowerCase();
	if (!needle) return [{ text, match: false }];
	const folded = text.toLocaleLowerCase();
	const parts: TextPart[] = [];
	let cursor = 0;
	let position = folded.indexOf(needle);
	while (position !== -1) {
		if (position > cursor) parts.push({ text: text.slice(cursor, position), match: false });
		parts.push({ text: text.slice(position, position + needle.length), match: true });
		cursor = position + needle.length;
		position = folded.indexOf(needle, cursor);
	}
	if (cursor < text.length) parts.push({ text: text.slice(cursor), match: false });
	return parts;
}

export function lineCount(text: string): number {
	return text.split('\n').length;
}
