// @vitest-environment jsdom

import { afterEach, describe, expect, it } from 'vitest';
import type { BundleItem } from '$lib/api/types';
import { blockRangeFromSelection, codePointIndex, defaultRole, mergeItems } from './selection';

afterEach(() => {
	document.body.innerHTML = '';
	window.getSelection()?.removeAllRanges();
});

function select(start: [Node, number], end: [Node, number]): Selection {
	const range = document.createRange();
	range.setStart(...start);
	range.setEnd(...end);
	const selection = window.getSelection()!;
	selection.removeAllRanges();
	selection.addRange(range);
	return selection;
}

describe('evidence selection', () => {
	it('counts code points rather than UTF-16 units', () => {
		expect(codePointIndex('a😀b', 3)).toBe(2);
		expect(codePointIndex('plain', 3)).toBe(3);
	});

	it('maps a selection across highlight marks to block offsets', () => {
		document.body.innerHTML =
			'<section id="e1" data-event><div data-block-id="b1">Hi 😀 the<mark>re</mark> friend</div></section>';
		const block = document.querySelector('[data-block-id]')!;
		const [head, mark, tail] = Array.from(block.childNodes);

		const range = blockRangeFromSelection(select([head, 6], [tail, 4]));

		expect(range).toEqual({
			eventId: 'e1',
			blockId: 'b1',
			start: 5,
			end: 14,
			text: 'the' + mark.textContent + ' fri'
		});
	});

	it('ignores collapsed selections and selections across blocks', () => {
		document.body.innerHTML =
			'<section id="e1" data-event><div data-block-id="b1">One</div><div data-block-id="b2">Two</div></section>';
		const [first, second] = Array.from(document.querySelectorAll('[data-block-id]'));

		expect(blockRangeFromSelection(select([first.firstChild!, 1], [first.firstChild!, 1]))).toBe(
			null
		);
		expect(blockRangeFromSelection(select([first.firstChild!, 1], [second.firstChild!, 2]))).toBe(
			null
		);
	});

	it('starts roles from the event producer', () => {
		expect(defaultRole('user')).toBe('requirement');
		expect(defaultRole('assistant')).toBe('action');
		expect(defaultRole('assistant', 'tool_result')).toBe('result');
		expect(defaultRole('system')).toBe('context');
	});

	it('appends only evidence that is not already cited', () => {
		const ref = { conversation_id: 'c', revision: 'r', event_id: 'e1', block_id: null };
		const existing: BundleItem[] = [{ ref, role: 'correction', note: 'kept' }];
		const added: BundleItem[] = [
			{ ref: { ...ref }, role: 'context' },
			{ ref: { ...ref, event_id: 'e2' }, role: 'action' }
		];

		expect(mergeItems(existing, added)).toEqual([existing[0], added[1]]);
	});
});
