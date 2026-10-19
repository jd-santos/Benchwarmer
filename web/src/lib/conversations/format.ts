import type { CaptureState, ConversationSummary, EventRole } from '$lib/api/types';

// Times read in the viewer's own locale and time zone. Full timestamps name the
// zone so a date copied elsewhere stays unambiguous.
const timestampFormat = new Intl.DateTimeFormat(undefined, {
	dateStyle: 'medium',
	timeStyle: 'short'
});

const zoneFormat = new Intl.DateTimeFormat(undefined, { timeZoneName: 'short' });

const timeFormat = new Intl.DateTimeFormat(undefined, { timeStyle: 'short' });

export function formatTimestamp(value: string): string {
	const date = new Date(value);
	const zone = zoneFormat.formatToParts(date).find((part) => part.type === 'timeZoneName');
	return zone ? `${timestampFormat.format(date)} ${zone.value}` : timestampFormat.format(date);
}

export function formatTime(value: string): string {
	return timeFormat.format(new Date(value));
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

const gapNouns: Record<string, string> = {
	messages: 'messages',
	tool_calls: 'tool calls',
	usage: 'usage',
	prompts: 'prompts'
};

/** Short label and explanation for one capture gap, for a hover or hidden hint. */
export function gapLabel(gap: { label: string; state: CaptureState }): {
	text: string;
	explanation: string;
} {
	const noun = gapNouns[gap.label] ?? gap.label;
	const capitalized = noun.charAt(0).toUpperCase() + noun.slice(1);
	switch (gap.state) {
		case 'partial':
			return {
				text: `Some ${noun} missing`,
				explanation: `The source captured only part of the ${noun} for this conversation.`
			};
		case 'redacted':
			return {
				text: `${capitalized} redacted`,
				explanation: `The source removed ${noun} before Benchwarmer imported this conversation.`
			};
		case 'unavailable':
			return {
				text: `${capitalized} not captured`,
				explanation: `The source does not record ${noun}, so they are unknown rather than zero.`
			};
		default:
			return {
				text: `${capitalized} not captured`,
				explanation: `The source did not report ${noun} for this conversation, so they are unknown rather than zero.`
			};
	}
}
