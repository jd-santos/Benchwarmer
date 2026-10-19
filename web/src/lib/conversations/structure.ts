import type { ConversationEvent } from '$lib/api/types';

/**
 * Structure inside captured text, found without rendering Markdown.
 *
 * Segments preserve every character of the source text, so an element built
 * from them has the same textContent as the stored block. Evidence selection
 * relies on that to map DOM offsets back to block offsets.
 */
export type Segment =
	| { kind: 'text'; text: string }
	| { kind: 'heading'; id: string; level: number; marks: string; text: string; tail: string };

const HEADING = /^(#{1,6} +)(.*)$/;

export function segmentText(text: string, blockId: string): Segment[] {
	const segments: Segment[] = [];
	let run = '';
	let count = 0;
	const flush = () => {
		if (run) segments.push({ kind: 'text', text: run });
		run = '';
	};
	for (const line of text.split(/(?<=\n)/)) {
		const body = line.endsWith('\n') ? line.slice(0, -1) : line;
		const match = HEADING.exec(body);
		if (!match) {
			run += line;
			continue;
		}
		flush();
		segments.push({
			kind: 'heading',
			id: `${blockId}::h${count++}`,
			level: match[1].trimEnd().length,
			marks: match[1],
			text: match[2],
			tail: line.length > body.length ? '\n' : ''
		});
	}
	flush();
	return segments;
}

export interface Heading {
	id: string;
	level: number;
	/** Heading text with trailing `#` markers and whitespace removed. */
	label: string;
	eventId: string;
}

export function headingsIn(event: ConversationEvent): Heading[] {
	const headings: Heading[] = [];
	for (const block of event.content) {
		if (block.kind !== 'text' || !block.text) continue;
		for (const segment of segmentText(block.text, block.id)) {
			if (segment.kind !== 'heading') continue;
			const label = segment.text.replace(/\s+#+\s*$/, '').trim();
			if (label) headings.push({ id: segment.id, level: segment.level, label, eventId: event.id });
		}
	}
	return headings;
}

export type OutlineEntry =
	| { kind: 'turn'; event: ConversationEvent; headings: Heading[] }
	| { kind: 'marker'; event: ConversationEvent };

/** User turns with the headings of the replies that follow them, plus captured markers. */
export function outlineEntries(events: ConversationEvent[]): OutlineEntry[] {
	const entries: OutlineEntry[] = [];
	let turn: Extract<OutlineEntry, { kind: 'turn' }> | null = null;
	for (const event of events) {
		if (event.kind !== 'message') {
			entries.push({ kind: 'marker', event });
		} else if (event.role === 'user') {
			turn = { kind: 'turn', event, headings: [] };
			entries.push(turn);
		} else if (event.role === 'assistant' && turn) {
			turn.headings.push(...headingsIn(event));
		}
	}
	return entries;
}

/** Map each event to the user turn it belongs to, for highlighting the outline. */
export function turnOf(events: ConversationEvent[]): Map<string, string> {
	const map = new Map<string, string>();
	let turn: string | null = null;
	for (const event of events) {
		if (event.kind === 'message' && event.role === 'user') turn = event.id;
		if (turn) map.set(event.id, turn);
	}
	return map;
}
