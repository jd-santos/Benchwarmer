import { describe, expect, it } from 'vitest';
import { cameFrom, recordNavigation } from './navigation';

describe('back navigation', () => {
	it('goes back only when the previous page is the target list', () => {
		recordNavigation(null);
		expect(cameFrom('/conversations')).toBe(false);

		recordNavigation(new URL('http://localhost/conversations?q=retry'));
		expect(cameFrom('/conversations')).toBe(true);
		expect(cameFrom('/bundles')).toBe(false);
	});
});
