import { describe, expect, it } from 'vitest';
import { buildCatalog, nearestSibling, registerModel, resolveModel } from './catalog.ts';
import { createHarnessModels } from './providers.ts';

const MODELS_DEV = {
	anthropic: {
		id: 'anthropic',
		name: 'Anthropic',
		models: {
			'claude-sonnet-5-5': {
				id: 'claude-sonnet-5-5',
				name: 'Claude Sonnet 5.5',
				reasoning: true,
				release_date: '2026-09-01',
				limit: { context: 1000000, output: 128000 },
				cost: { input: 3, output: 15, cache_read: 0.3, cache_write: 3.75 }
			},
			'claude-sonnet-6': {
				id: 'claude-sonnet-6',
				name: 'Claude Sonnet 6',
				reasoning: true,
				reasoning_options: [{ type: 'toggle' }, { type: 'effort', values: ['low', 'medium', 'high'] }],
				release_date: '2027-01-15',
				limit: { context: 2000000, output: 256000 },
				cost: { input: 4, output: 20, cache_read: 0.4, cache_write: 5 }
			}
		}
	}
};

/** A fetch that answers models.dev and Anthropic's model list from fixtures and records the headers it saw. */
function fakeFetch(options: { anthropic?: unknown; anthropicStatus?: number; modelsDev?: unknown } = {}) {
	const calls: { url: string; headers: Record<string, string> }[] = [];
	const fetchImpl = (async (input: string | URL | Request, init?: RequestInit) => {
		const url = String(input);
		calls.push({ url, headers: { ...((init?.headers as Record<string, string>) ?? {}) } });
		if (url.startsWith('https://models.dev/')) {
			return new Response(JSON.stringify(options.modelsDev ?? MODELS_DEV), { status: 200 });
		}
		if (url.startsWith('https://api.anthropic.com/v1/models')) {
			return new Response(JSON.stringify(options.anthropic ?? { data: [], has_more: false }), {
				status: options.anthropicStatus ?? 200
			});
		}
		return new Response('not found', { status: 404 });
	}) as typeof fetch;
	return { fetchImpl, calls };
}

describe('model catalog', () => {
	it('lists only providers with keys and merges the three sources newest first', async () => {
		const { fetchImpl, calls } = fakeFetch({
			anthropic: {
				data: [
					{ type: 'model', id: 'claude-sonnet-5-5', display_name: 'Claude Sonnet 5.5', created_at: '2026-09-01T00:00:00Z' },
					{ type: 'model', id: 'claude-sonnet-6', display_name: 'Claude Sonnet 6', created_at: '2027-01-15T00:00:00Z' },
					{ type: 'model', id: 'claude-brand-new', display_name: 'Claude Brand New', created_at: '2027-03-01T00:00:00Z' }
				],
				has_more: false
			}
		});
		const catalog = await buildCatalog({ env: { ANTHROPIC_API_KEY: 'sk-test' }, fetch: fetchImpl });

		expect(catalog.providers.map((provider) => provider.id)).toEqual(['anthropic']);
		const [anthropic] = catalog.providers;
		expect(anthropic?.provider_list).toBe('listed');
		expect(anthropic?.models_dev).toBe('listed');
		expect(anthropic?.key_variables).toEqual(['ANTHROPIC_API_KEY']);
		expect(JSON.stringify(catalog)).not.toContain('sk-test');
		const listCall = calls.find((call) => call.url.includes('api.anthropic.com'));
		expect(listCall?.headers['x-api-key']).toBe('sk-test');

		const ids = catalog.models.map((model) => model.id);
		expect(ids.slice(0, 2)).toEqual(['claude-brand-new', 'claude-sonnet-6']);
		expect(ids).toContain('claude-sonnet-5-5');

		const fromCatalog = catalog.models.find((model) => model.id === 'claude-sonnet-5-5');
		expect(fromCatalog?.sources).toEqual(['pi-ai', 'models.dev', 'provider']);
		expect(fromCatalog?.thinking_levels).toEqual(['low', 'medium', 'high', 'xhigh', 'max']);
		// The pinned catalog's price wins over models.dev for a model it knows.
		expect(fromCatalog?.cost?.input).toBe(createHarnessModels({}).getModel('anthropic', 'claude-sonnet-5-5')?.cost.input);
		expect(fromCatalog?.listed_by_provider).toBe(true);

		const fromModelsDev = catalog.models.find((model) => model.id === 'claude-sonnet-6');
		expect(fromModelsDev?.sources).toEqual(['models.dev', 'provider']);
		expect(fromModelsDev?.runnable).toBe(true);
		expect(fromModelsDev?.release_date).toBe('2027-01-15');
		expect(fromModelsDev?.cost).toEqual({ input: 4, output: 20, cache_read: 0.4, cache_write: 5 });
		expect(fromModelsDev?.thinking_levels).toEqual(['low', 'medium', 'high', 'xhigh', 'max']);

		const fromProviderOnly = catalog.models.find((model) => model.id === 'claude-brand-new');
		expect(fromProviderOnly?.sources).toEqual(['provider']);
		expect(fromProviderOnly?.reasoning).toBeNull();
		expect(fromProviderOnly?.cost).toBeNull();
		expect(fromProviderOnly?.runnable).toBe(true);

		const unlisted = catalog.models.filter((model) => model.listed_by_provider === false);
		expect(unlisted.length).toBeGreaterThan(0);
	});

	it('keeps the pinned catalog when the network sources fail, and says so', async () => {
		const { fetchImpl } = fakeFetch({ anthropicStatus: 401, modelsDev: null });
		const broken = (async (input: string | URL | Request, init?: RequestInit) => {
			if (String(input).startsWith('https://models.dev/')) throw new Error('offline');
			return fetchImpl(input, init);
		}) as typeof fetch;
		const catalog = await buildCatalog({ env: { ANTHROPIC_API_KEY: 'sk-test' }, fetch: broken });
		expect(catalog.providers[0]?.provider_list).toBe('unavailable');
		expect(catalog.providers[0]?.models_dev).toBe('unavailable');
		expect(catalog.notes.join('\n')).toMatch(/models.dev could not be read: offline/);
		expect(catalog.notes.join('\n')).toMatch(/Anthropic did not return its model list: HTTP 401/);
		expect(catalog.models.length).toBeGreaterThan(0);
		for (const model of catalog.models) {
			expect(model.sources).toEqual(['pi-ai']);
			expect(model.listed_by_provider).toBeNull();
		}
	});

	it('describes only the pinned catalog offline and nothing without keys', async () => {
		const never = (async () => {
			throw new Error('must not fetch');
		}) as typeof fetch;
		const offline = await buildCatalog({ env: { ANTHROPIC_API_KEY: 'sk-test' }, fetch: never, offline: true });
		expect(offline.providers[0]?.provider_list).toBe('skipped');
		expect(offline.providers[0]?.models_dev).toBe('skipped');
		expect(offline.models.every((model) => model.sources.join() === 'pi-ai')).toBe(true);

		const empty = await buildCatalog({ env: {}, fetch: never });
		expect(empty.providers).toEqual([]);
		expect(empty.models).toEqual([]);
		expect(empty.notes[0]).toMatch(/No provider key/);
	});

	it('runs a model outside the pinned catalog through its nearest sibling and records the estimate source', async () => {
		const models = createHarnessModels({});
		const known = await resolveModel(models, 'anthropic', 'claude-sonnet-5-5', { modelsDev: null });
		expect(known.pricingSource).toBe('pi-ai model catalog estimate');

		const sibling = nearestSibling(models.getModels('anthropic'), 'claude-sonnet-6');
		expect(sibling?.id).toMatch(/^claude-sonnet-/);

		const priced = await resolveModel(models, 'anthropic', 'claude-sonnet-6', { modelsDev: MODELS_DEV });
		expect(priced.model.id).toBe('claude-sonnet-6');
		expect(priced.model.name).toBe('Claude Sonnet 6');
		expect(priced.model.api).toBe(sibling?.api);
		expect(priced.model.cost).toEqual({ input: 4, output: 20, cacheRead: 0.4, cacheWrite: 5 });
		expect(priced.model.contextWindow).toBe(2000000);
		expect(priced.pricingSource).toMatch(/^models.dev catalog estimate/);
		expect(models.getModel('anthropic', 'claude-sonnet-6')?.name).toBe('Claude Sonnet 6');
		expect(models.getModels('anthropic').filter((model) => model.id === 'claude-sonnet-6')).toHaveLength(1);

		const unpriced = await resolveModel(models, 'anthropic', 'claude-brand-new', { modelsDev: {} });
		expect(unpriced.model.cost).toEqual({ input: 0, output: 0, cacheRead: 0, cacheWrite: 0 });
		expect(unpriced.pricingSource).toMatch(/^no estimate/);

		await expect(resolveModel(models, 'nobody', 'x', { modelsDev: null })).rejects.toThrow(/Unknown model nobody\/x/);
	});

	it('replaces a registered model instead of duplicating it', () => {
		const models = createHarnessModels({});
		const [first] = models.getModels('anthropic');
		if (!first) throw new Error('catalog is empty');
		registerModel(models, { ...first, name: 'Renamed' });
		expect(models.getModel('anthropic', first.id)?.name).toBe('Renamed');
		expect(models.getModels('anthropic').filter((model) => model.id === first.id)).toHaveLength(1);
	});
});
