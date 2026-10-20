/**
 * Compact, model-facing renderings of library data.
 *
 * These are pure functions over API responses. They abbreviate; they never add
 * facts the outline or the events do not carry.
 */

import type { ConversationEvent, ConversationOutline, OutlineEvent, PathOutline } from './benchwarmer/client.ts';

const PREVIEW = 100;

function shorten(text: string | null, max = PREVIEW): string {
	if (!text) return '';
	const flat = text.replace(/\s+/g, ' ').trim();
	return flat.length > max ? `${flat.slice(0, max - 1)}…` : flat;
}

function toolSummary(event: OutlineEvent): string {
	const calls = event.tools.filter((t) => t.kind === 'tool_call');
	const results = event.tools.filter((t) => t.kind === 'tool_result');
	const parts: string[] = [];
	if (calls.length) {
		const names = calls.map((c) => c.tool_name ?? '?').join(',');
		parts.push(`${calls.length} call${calls.length === 1 ? '' : 's'}[${names}]`);
	}
	if (results.length) parts.push(`${results.length} result${results.length === 1 ? '' : 's'}`);
	return parts.join(' ');
}

export function describeEvent(event: OutlineEvent): string {
	const columns = [`#${event.ordinal}`, event.id, `${event.role}/${event.kind}`];
	if (event.boundary) columns.push(`BOUNDARY:${event.boundary}`);
	if (event.text_chars) columns.push(`${event.text_chars}ch`);
	else if (!event.text_captured && event.block_counts.text) columns.push('text-not-captured');
	if (event.reasoning_chars) columns.push(`reasoning:${event.reasoning_chars}ch`);
	const tools = toolSummary(event);
	if (tools) columns.push(tools);
	if (event.headings.length) {
		columns.push(`headings: ${event.headings.map((h) => `${'#'.repeat(h.level)} ${h.label}`).join(' | ')}`);
	}
	if (event.preview) columns.push(`"${shorten(event.preview)}"`);
	return columns.join('  ');
}

export function choosePath(outline: ConversationOutline, pathId?: string): PathOutline | undefined {
	if (pathId) return outline.paths.find((p) => p.id === pathId);
	return outline.paths.find((p) => p.is_original) ?? outline.paths[0];
}

/** One path of an outline as numbered exchanges, with the other paths named. */
export function formatOutline(outline: ConversationOutline, pathId?: string): string {
	const path = choosePath(outline, pathId);
	const byId = new Map(outline.events.map((e) => [e.id, e]));
	const lines: string[] = [
		`conversation ${outline.conversation_id} revision ${outline.revision}: ${outline.event_count} events, ${outline.paths.length} path(s)`,
		`coverage: ${Object.entries(outline.coverage)
			.map(([k, v]) => `${k}=${v}`)
			.join(', ') || 'none recorded'}`
	];
	if (!path) {
		lines.push(pathId ? `no path ${pathId}` : 'no paths');
		return lines.join('\n');
	}
	const others = outline.paths.filter((p) => p.id !== path.id);
	lines.push(
		`path ${path.id}${path.is_original ? ' (original)' : ''}: ${path.event_ids.length} events, ${path.exchanges.length} exchanges, ${path.segments.length} segment(s)` +
			(path.fork_event_id ? `, forks after ${path.fork_event_id}` : '')
	);
	if (others.length) {
		lines.push(
			`other paths: ${others.map((p) => `${p.id} (${p.event_ids.length} events, diverges at ${p.divergent_event_id ?? '?'})`).join('; ')}`
		);
	}
	for (const exchange of path.exchanges) {
		const head = exchange.user_event_id ? `user ${exchange.user_event_id}` : 'before first user turn';
		lines.push(
			`\n${exchange.id}: ${head}; ${exchange.assistant_event_count} assistant event(s), ${exchange.tool_call_count} tool call(s), ${exchange.assistant_text_chars} assistant chars, ${exchange.heading_count} heading(s)`
		);
		for (const eventId of exchange.event_ids) {
			const event = byId.get(eventId);
			if (event) lines.push(`  ${describeEvent(event)}`);
		}
	}
	return lines.join('\n');
}

export interface FormatEventsOptions {
	/** Code points kept per block before truncation. */
	maxBlockChars?: number;
}

/** Captured content of selected events, block by block, with stable ids to cite. */
export function formatEvents(
	events: ConversationEvent[],
	revision: string,
	options: FormatEventsOptions = {}
): string {
	const max = options.maxBlockChars ?? 4000;
	const lines: string[] = [`revision ${revision}; cite event ids and block ids exactly as shown`];
	for (const event of events) {
		lines.push(`\n=== event ${event.id}  #${event.ordinal}  ${event.role}/${event.kind}  parent=${event.parent_id ?? 'none'} ===`);
		if (!event.content.length) lines.push('(no content blocks)');
		for (const block of event.content) {
			const meta = [`block ${block.id}`, block.kind];
			if (block.tool_call_id) meta.push(`tool_call_id=${block.tool_call_id}`);
			if (block.artifact_id) meta.push(`artifact=${block.artifact_id}`);
			if (block.text === null) {
				lines.push(`[${meta.join(' ')}] (text not captured)`);
				continue;
			}
			const chars = Array.from(block.text);
			if (chars.length > max) {
				lines.push(`[${meta.join(' ')} ${chars.length} chars, showing 0..${max}]`);
				lines.push(chars.slice(0, max).join(''));
				lines.push(`…[${chars.length - max} more chars omitted]`);
			} else {
				lines.push(`[${meta.join(' ')} ${chars.length} chars]`);
				lines.push(block.text);
			}
		}
	}
	return lines.join('\n');
}
