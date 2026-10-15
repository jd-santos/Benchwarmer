import { describe, expect, it } from 'vitest';
import { summary } from './fixtures';
import { captureGaps, conversationLabel, hasMessageGap, highlightParts, plural } from './format';

describe('conversation formatting', () => {
	it('labels conversations from captured facts only', () => {
		expect(conversationLabel(summary)).toBe('Refund investigation');
		expect(conversationLabel({ ...summary, title: null })).toBe(
			'“I need a refund for the second item.”'
		);
		expect(conversationLabel({ ...summary, title: null, preview: null })).toBe(
			'Untitled conversation'
		);
	});

	it('lists capture gaps without treating unknown as available', () => {
		expect(captureGaps({ usage: 'unknown', messages: 'available', tool_calls: 'partial' })).toEqual(
			[
				{ label: 'tool calls', state: 'partial' },
				{ label: 'usage', state: 'unknown' }
			]
		);
		expect(hasMessageGap({ messages: 'partial' })).toBe(true);
		expect(hasMessageGap({ usage: 'unknown' })).toBe(false);
	});

	it('marks case-insensitive matches', () => {
		expect(highlightParts('Refund the refund', 'REFUND')).toEqual([
			{ text: 'Refund', match: true },
			{ text: ' the ', match: false },
			{ text: 'refund', match: true }
		]);
		expect(highlightParts('plain', null)).toEqual([{ text: 'plain', match: false }]);
	});

	it('pluralizes counts', () => {
		expect(plural(1, 'branch', 'branches')).toBe('1 branch');
		expect(plural(0, 'message')).toBe('0 messages');
	});
});
