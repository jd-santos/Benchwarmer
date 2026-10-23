import { describe, expect, it } from 'vitest';
import {
	EXCLUDED_PROVIDERS,
	createHarnessModels,
	missingKeyHint,
	providerBaseUrlOverride,
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

	it('redirects one provider through a base URL override and leaves the others alone', () => {
		const env = { ANTHROPIC_BASE_URL: 'https://anthropic.gateway.example/' };
		expect(providerBaseUrlOverride('anthropic', env)).toBe('https://anthropic.gateway.example');
		expect(providerBaseUrlOverride('openai', env)).toBeNull();
		expect(providerBaseUrlOverride('anthropic', {})).toBeNull();
		expect(() => providerBaseUrlOverride('anthropic', { ANTHROPIC_BASE_URL: 'gateway.example' })).toThrow(/http/);

		const models = createHarnessModels(env);
		expect(models.getProvider('anthropic')?.baseUrl).toBe('https://anthropic.gateway.example');
		const anthropic = models.getModels('anthropic');
		expect(anthropic.length).toBeGreaterThan(0);
		for (const model of anthropic) expect(model.baseUrl).toBe('https://anthropic.gateway.example');
		expect(models.getModel('anthropic', anthropic[0].id)?.baseUrl).toBe('https://anthropic.gateway.example');
		const openai = models.getModels('openai');
		expect(openai.length).toBeGreaterThan(0);
		expect(openai.every((model) => model.baseUrl.includes('gateway.example'))).toBe(false);
	});
});
