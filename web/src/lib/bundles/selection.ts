import type { BundleItem, EvidenceRef, EvidenceRole } from '$lib/api/types';

/** Convert a UTF-16 index (JavaScript strings) to a Unicode code point index. */
export function codePointIndex(text: string, utf16Index: number): number {
	return [...text.slice(0, utf16Index)].length;
}

export interface BlockRange {
	eventId: string;
	blockId: string;
	start: number;
	end: number;
	text: string;
}

/**
 * Describe a text selection that lies inside one rendered content block.
 *
 * Block elements carry `data-block-id` and render exactly the stored text, so
 * offsets into their text content are offsets into the block. Returns null for
 * collapsed selections and selections spanning blocks.
 */
export function blockRangeFromSelection(selection: Selection | null): BlockRange | null {
	if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null;
	const range = selection.getRangeAt(0);
	const element = closestBlock(range.startContainer);
	if (!element || element !== closestBlock(range.endContainer)) return null;
	const eventId = element.closest<HTMLElement>('[data-event]')?.id;
	const blockId = element.dataset.blockId;
	if (!eventId || !blockId) return null;

	const full = element.textContent ?? '';
	const prefix = document.createRange();
	prefix.selectNodeContents(element);
	prefix.setEnd(range.startContainer, range.startOffset);
	const startUnits = prefix.toString().length;
	const endUnits = startUnits + range.toString().length;
	const start = codePointIndex(full, startUnits);
	const end = codePointIndex(full, endUnits);
	if (end <= start) return null;
	return { eventId, blockId, start, end, text: full.slice(startUnits, endUnits) };
}

function closestBlock(node: Node): HTMLElement | null {
	const element = node instanceof HTMLElement ? node : node.parentElement;
	return element?.closest<HTMLElement>('[data-block-id]') ?? null;
}

/** A starting role from who produced the event; reviewers change it freely. */
export function defaultRole(eventRole: string, blockKind: string | null = null): EvidenceRole {
	if (blockKind === 'tool_result' || eventRole === 'tool') return 'result';
	if (eventRole === 'user') return 'requirement';
	if (eventRole === 'assistant') return 'action';
	return 'context';
}

export function refKey(ref: EvidenceRef): string {
	return [ref.event_id, ref.block_id ?? '', ref.text_start ?? '', ref.text_end ?? ''].join('|');
}

/** Append items not already cited; existing items keep their order and edits. */
export function mergeItems(existing: BundleItem[], added: BundleItem[]): BundleItem[] {
	const seen = new Set(existing.map((item) => refKey(item.ref)));
	return [...existing, ...added.filter((item) => !seen.has(refKey(item.ref)))];
}
