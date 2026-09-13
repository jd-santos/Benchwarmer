import { describe, expect, it } from 'vitest';
import { ssr } from './+layout';

describe('root layout configuration', () => {
	it('uses client-side rendering for the static SPA', () => {
		expect(ssr).toBe(false);
	});
});
