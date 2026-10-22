import { describe, expect, it } from 'vitest';
import {
	EXCLUDED_PROVIDERS,
	createHarnessModels,
	missingKeyHint,
	providerIds,
	providersWithKeys
} from './providers.ts';

describe('providers', () => {
	it('registers the pi-ai catalog minus the excluded providers', () => {
		const ids = providerIds();
		for (const expected of ['anthropic', 'openai', 'openrouter', 'google', 'mistral']) {
			expect(ids).toContain(expected);
		}
		const models = createHarnessModels();
		expect(models.getProvider('openrouter')).toBeDefined();
		expect(models.getModels('openrouter').length).toBeGreaterThan(0);
		for (const excluded of EXCLUDED_PROVIDERS) {
			expect(ids).not.toContain(excluded);
			expect(models.getProvider(excluded)).toBeUndefined();
			expect(models.getModels(excluded)).toEqual([]);
		}
	});

	it('reports which common providers have keys and hints at the missing one', () => {
		const env = { OPENROUTER_API_KEY: 'x', GOOGLE_API_KEY: 'y' };
		expect(providersWithKeys(env)).toEqual(['google', 'openrouter']);
		expect(missingKeyHint('openrouter', env)).toBeNull();
		expect(missingKeyHint('anthropic', env)).toContain('ANTHROPIC_API_KEY');
		expect(missingKeyHint('anthropic', env)).toContain('google, openrouter');
		expect(missingKeyHint('some-unlisted-provider', env)).toBeNull();
	});
});
