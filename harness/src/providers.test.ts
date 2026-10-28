import { describe, expect, it } from 'vitest';
import { builtinProviders } from '@earendil-works/pi-ai/providers/all';

import {
	createHarnessModels,
	missingKeyHint,
	providerAllowed,
	providerBaseUrlOverride,
	providerIds,
	providerLists,
	providersWithKeys
} from './providers.ts';

describe('providers', () => {
	it('registers the whole pi-ai catalog when no provider lists are set', () => {
		const ids = providerIds({});
		expect(ids).toEqual(
			builtinProviders()
				.map((provider) => provider.id)
				.sort()
		);
		for (const expected of ['anthropic', 'openai', 'openrouter', 'google', 'mistral']) {
			expect(ids).toContain(expected);
		}
		const models = createHarnessModels({});
		expect(models.getProvider('openrouter')).toBeDefined();
		expect(models.getModels('openrouter').length).toBeGreaterThan(0);
	});

	it('reads the allow and deny lists from the environment', () => {
		expect(providerLists({})).toEqual({ allow: new Set(), deny: new Set() });
		expect(providerLists({ BENCHWARMER_PROVIDER_ALLOW: '', BENCHWARMER_PROVIDER_DENY: '' })).toEqual({
			allow: new Set(),
			deny: new Set()
		});
		const lists = providerLists({
			BENCHWARMER_PROVIDER_ALLOW: ' anthropic, openai ,',
			BENCHWARMER_PROVIDER_DENY: 'openai'
		});
		expect([...lists.allow]).toEqual(['anthropic', 'openai']);
		expect([...lists.deny]).toEqual(['openai']);
		expect(providerAllowed('anthropic', lists)).toBe(true);
		expect(providerAllowed('openai', lists)).toBe(false);
		expect(providerAllowed('mistral', lists)).toBe(false);
	});

	it('registers only the providers the lists permit', () => {
		const allowed = createHarnessModels({ BENCHWARMER_PROVIDER_ALLOW: 'anthropic,openrouter' });
		expect(allowed.getProviders().map((provider) => provider.id).sort()).toEqual(['anthropic', 'openrouter']);
		expect(allowed.getProvider('openai')).toBeUndefined();
		expect(allowed.getModels('openai')).toEqual([]);

		const denied = createHarnessModels({ BENCHWARMER_PROVIDER_DENY: 'mistral' });
		expect(denied.getProvider('mistral')).toBeUndefined();
		expect(denied.getProvider('anthropic')).toBeDefined();
		expect(providerIds({ BENCHWARMER_PROVIDER_DENY: 'mistral' })).toEqual(providerIds({}).filter((id) => id !== 'mistral'));

		const both = createHarnessModels({ BENCHWARMER_PROVIDER_ALLOW: 'anthropic,openai', BENCHWARMER_PROVIDER_DENY: 'openai' });
		expect(both.getProviders().map((provider) => provider.id)).toEqual(['anthropic']);
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
