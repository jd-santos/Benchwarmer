/**
 * The model catalog an operator can pick from, and how a model that the pinned
 * pi-ai catalog does not know is still run.
 *
 * Three sources are merged per provider whose key is present:
 *
 * - the pi-ai catalog pinned with this harness (verified request config,
 *   thinking-level map, prices);
 * - models.dev (`https://models.dev/api.json`), which lists new models before a
 *   pi-ai release does, with release dates, prices, limits, and whether the
 *   model reasons and at which effort levels;
 * - the provider's own model list where it offers one (Anthropic, OpenAI,
 *   OpenRouter, Google), which is the authority on what this key can reach.
 *
 * A model missing from the pi-ai catalog is run by copying the request
 * configuration of its nearest catalog sibling and taking its name, limits,
 * and prices from models.dev when listed there. The run report says which
 * estimate applied. Listing never spends: these are plain GETs.
 */

import type { Api, Model } from '@earendil-works/pi-ai';
import type { MutableModels, Provider } from '@earendil-works/pi-ai/models';

import {
	COMMON_PROVIDER_KEYS,
	EXCLUDED_PROVIDERS,
	createHarnessModels,
	providerBaseUrlOverride,
	providersWithKeys
} from './providers.ts';

export const THINKING_LEVELS = ['off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'] as const;
export type ThinkingLevel = (typeof THINKING_LEVELS)[number];

export const MODELS_DEV_URL = 'https://models.dev/api.json';

/** pi-ai provider ids whose models.dev id differs. */
const MODELS_DEV_PROVIDER_ID: Readonly<Record<string, string>> = {
	together: 'togetherai',
	fireworks: 'fireworks-ai'
};

export type CatalogSource = 'pi-ai' | 'models.dev' | 'provider';

/** USD per million tokens. */
export interface CatalogCost {
	input: number;
	output: number;
	cache_read: number;
	cache_write: number;
}

export interface CatalogModel {
	provider: string;
	id: string;
	name: string;
	/** Whether the model offers reasoning; null when no source says. */
	reasoning: boolean | null;
	/** Thinking levels this harness can request for the model; empty when it offers none. */
	thinking_levels: ThinkingLevel[];
	context_window: number | null;
	max_output: number | null;
	/** ISO date from models.dev or the provider's list; null when neither gives one. */
	release_date: string | null;
	cost: CatalogCost | null;
	sources: CatalogSource[];
	/** Whether the provider's own list currently includes it; null when that list was not available. */
	listed_by_provider: boolean | null;
	/** False when this harness has no catalog entry to configure a request from. */
	runnable: boolean;
}

export interface CatalogProvider {
	id: string;
	name: string;
	/** Environment variables pi-ai reads for the key; values are never reported. */
	key_variables: string[];
	base_url_override: string | null;
	provider_list: 'listed' | 'unavailable' | 'not_offered' | 'skipped';
	models_dev: 'listed' | 'unavailable' | 'skipped';
	model_count: number;
}

export interface ModelCatalog {
	generated_at: string;
	providers: CatalogProvider[];
	/** Newest first within a provider; providers in id order. */
	models: CatalogModel[];
	/** Human-readable notes on what could not be fetched. */
	notes: string[];
}

interface ModelsDevModel {
	id: string;
	name?: string;
	reasoning?: boolean;
	reasoning_options?: ReadonlyArray<{ type: string; values?: string[] }>;
	release_date?: string;
	limit?: { context?: number; output?: number };
	cost?: { input?: number; output?: number; cache_read?: number; cache_write?: number };
}

interface ModelsDevProvider {
	id: string;
	name?: string;
	models: Record<string, ModelsDevModel>;
}

export type ModelsDevCatalog = Record<string, ModelsDevProvider>;

/** One entry of a provider's own model list, normalized. */
export interface ProviderListedModel {
	id: string;
	name?: string;
	release_date?: string;
	reasoning?: boolean;
	context_window?: number;
	max_output?: number;
	cost?: CatalogCost;
}

export interface CatalogFetchOptions {
	env?: NodeJS.ProcessEnv;
	fetch?: typeof fetch;
	/** Per-request timeout; the default suits an interactive listing. */
	timeoutMs?: number;
	/** Skip every network source and describe only the pinned pi-ai catalog. */
	offline?: boolean;
	/** Restrict to one provider id. */
	provider?: string;
	log?: (line: string) => void;
}

function describeError(error: unknown): string {
	return error instanceof Error ? error.message : String(error);
}

async function getJson(
	url: string,
	headers: Record<string, string>,
	fetchImpl: typeof fetch,
	timeoutMs: number
): Promise<unknown> {
	const response = await fetchImpl(url, {
		headers: { accept: 'application/json', ...headers },
		signal: AbortSignal.timeout(timeoutMs)
	});
	if (!response.ok) throw new Error(`HTTP ${response.status} from ${new URL(url).host}`);
	return response.json();
}

export async function fetchModelsDev(
	fetchImpl: typeof fetch = fetch,
	timeoutMs = 8000
): Promise<ModelsDevCatalog> {
	const value = await getJson(MODELS_DEV_URL, {}, fetchImpl, timeoutMs);
	if (!value || typeof value !== 'object') throw new Error('models.dev returned no catalog');
	return value as ModelsDevCatalog;
}

function firstKey(provider: string, env: NodeJS.ProcessEnv): string | undefined {
	for (const name of COMMON_PROVIDER_KEYS[provider] ?? []) {
		const value = env[name]?.trim();
		if (value) return value;
	}
	return undefined;
}

function isoDate(value: unknown): string | undefined {
	if (typeof value === 'number' && Number.isFinite(value)) {
		return new Date(value * 1000).toISOString().slice(0, 10);
	}
	if (typeof value === 'string' && value) return value.slice(0, 10);
	return undefined;
}

function records(value: unknown, key: string): Record<string, unknown>[] {
	if (!value || typeof value !== 'object') return [];
	const list = (value as Record<string, unknown>)[key];
	return Array.isArray(list) ? list.filter((item): item is Record<string, unknown> => !!item && typeof item === 'object') : [];
}

/**
 * The provider's own model list, or null when the provider offers none that
 * this harness reads. Throws when the list exists but could not be fetched.
 * Keys travel only in request headers.
 */
export async function fetchProviderList(
	provider: string,
	baseUrl: string,
	env: NodeJS.ProcessEnv,
	fetchImpl: typeof fetch = fetch,
	timeoutMs = 8000
): Promise<ProviderListedModel[] | null> {
	const key = firstKey(provider, env);
	switch (provider) {
		case 'anthropic': {
			if (!key) throw new Error('no API key variable set (only a key lists models)');
			const listed: ProviderListedModel[] = [];
			let after: string | undefined;
			for (let page = 0; page < 10; page += 1) {
				const url = new URL(`${baseUrl}/v1/models`);
				url.searchParams.set('limit', '1000');
				if (after) url.searchParams.set('after_id', after);
				const body = await getJson(
					url.toString(),
					{ 'x-api-key': key, 'anthropic-version': '2023-06-01' },
					fetchImpl,
					timeoutMs
				);
				for (const item of records(body, 'data')) {
					if (typeof item.id !== 'string') continue;
					const entry: ProviderListedModel = { id: item.id };
					if (typeof item.display_name === 'string') entry.name = item.display_name;
					const date = isoDate(item.created_at);
					if (date) entry.release_date = date;
					listed.push(entry);
				}
				const more = (body as Record<string, unknown>).has_more === true;
				const last = (body as Record<string, unknown>).last_id;
				if (!more || typeof last !== 'string') break;
				after = last;
			}
			return listed;
		}
		case 'openai': {
			if (!key) throw new Error('no API key variable set (only a key lists models)');
			const body = await getJson(`${baseUrl}/models`, { authorization: `Bearer ${key}` }, fetchImpl, timeoutMs);
			return records(body, 'data').flatMap((item) => {
				if (typeof item.id !== 'string') return [];
				const entry: ProviderListedModel = { id: item.id };
				const date = isoDate(item.created);
				if (date) entry.release_date = date;
				return [entry];
			});
		}
		case 'openrouter': {
			const body = await getJson(
				`${baseUrl}/models`,
				key ? { authorization: `Bearer ${key}` } : {},
				fetchImpl,
				timeoutMs
			);
			return records(body, 'data').flatMap((item) => {
				if (typeof item.id !== 'string') return [];
				const entry: ProviderListedModel = { id: item.id };
				if (typeof item.name === 'string') entry.name = item.name;
				const date = isoDate(item.created);
				if (date) entry.release_date = date;
				const parameters = Array.isArray(item.supported_parameters) ? item.supported_parameters : [];
				entry.reasoning = parameters.includes('reasoning') || parameters.includes('include_reasoning');
				if (typeof item.context_length === 'number') entry.context_window = item.context_length;
				const top = item.top_provider;
				const maxCompletion = top && typeof top === 'object' ? (top as Record<string, unknown>).max_completion_tokens : undefined;
				if (typeof maxCompletion === 'number') entry.max_output = maxCompletion;
				const pricing = item.pricing;
				if (pricing && typeof pricing === 'object') {
					const perToken = (field: string): number => {
						const raw = (pricing as Record<string, unknown>)[field];
						const parsed = typeof raw === 'string' ? Number.parseFloat(raw) : typeof raw === 'number' ? raw : 0;
						return Number.isFinite(parsed) ? parsed * 1_000_000 : 0;
					};
					entry.cost = {
						input: perToken('prompt'),
						output: perToken('completion'),
						cache_read: perToken('input_cache_read'),
						cache_write: perToken('input_cache_write')
					};
				}
				return [entry];
			});
		}
		case 'google': {
			if (!key) throw new Error('no API key variable set (only a key lists models)');
			const url = new URL(`${baseUrl}/models`);
			url.searchParams.set('pageSize', '1000');
			const body = await getJson(url.toString(), { 'x-goog-api-key': key }, fetchImpl, timeoutMs);
			return records(body, 'models').flatMap((item) => {
				if (typeof item.name !== 'string') return [];
				const methods = Array.isArray(item.supportedGenerationMethods) ? item.supportedGenerationMethods : [];
				if (methods.length > 0 && !methods.includes('generateContent')) return [];
				const entry: ProviderListedModel = { id: item.name.replace(/^models\//, '') };
				if (typeof item.displayName === 'string') entry.name = item.displayName;
				if (typeof item.inputTokenLimit === 'number') entry.context_window = item.inputTokenLimit;
				if (typeof item.outputTokenLimit === 'number') entry.max_output = item.outputTokenLimit;
				return [entry];
			});
		}
		default:
			return null;
	}
}

/** Model ids a provider's list carries that are not chat models for this harness's purposes. */
const UNUSABLE_ID = /(embedding|tts|whisper|transcribe|moderation|realtime|audio|image|dall-e|sora|search-preview|babbage|davinci|^text-|aqa$|imagen|veo|-vision$|-exp$|^learnlm)/i;

function usableListedModel(provider: string, id: string, known: boolean): boolean {
	if (known) return true;
	if (provider === 'openai') return /^(gpt-|o\d|chatgpt-)/.test(id) && !UNUSABLE_ID.test(id);
	if (provider === 'google') return /^gemini/.test(id) && !UNUSABLE_ID.test(id);
	return !UNUSABLE_ID.test(id);
}

/**
 * Levels the run can request. A model the pi-ai catalog knows (or a model run
 * through a sibling's configuration) follows that entry's level map; otherwise
 * models.dev's effort values decide.
 */
function thinkingLevelsOf(
	configured: Model<Api> | undefined,
	dev: ModelsDevModel | undefined,
	reasoning: boolean | null
): ThinkingLevel[] {
	if (reasoning === false) return [];
	if (configured) {
		const map = configured.thinkingLevelMap as Partial<Record<ThinkingLevel, string | null>> | undefined;
		return THINKING_LEVELS.filter((level) => map?.[level] !== null);
	}
	const effort = dev?.reasoning_options?.find((option) => option.type === 'effort')?.values;
	if (effort && effort.length > 0) {
		const levels = THINKING_LEVELS.filter((level) => effort.includes(level));
		if (levels.length > 0) return ['off', ...levels.filter((level) => level !== 'off')];
	}
	return [...THINKING_LEVELS];
}

function costOf(
	pi: Model<Api> | undefined,
	dev: ModelsDevModel | undefined,
	listed: ProviderListedModel | undefined
): CatalogCost | null {
	if (pi) {
		return {
			input: pi.cost.input,
			output: pi.cost.output,
			cache_read: pi.cost.cacheRead,
			cache_write: pi.cost.cacheWrite
		};
	}
	if (dev?.cost && typeof dev.cost.input === 'number' && typeof dev.cost.output === 'number') {
		return {
			input: dev.cost.input,
			output: dev.cost.output,
			cache_read: dev.cost.cache_read ?? 0,
			cache_write: dev.cost.cache_write ?? 0
		};
	}
	return listed?.cost ?? null;
}

function compareModels(a: CatalogModel, b: CatalogModel): number {
	if (a.release_date && b.release_date && a.release_date !== b.release_date) {
		return a.release_date < b.release_date ? 1 : -1;
	}
	if (Boolean(a.release_date) !== Boolean(b.release_date)) return a.release_date ? -1 : 1;
	return a.id.localeCompare(b.id);
}

/** Build the catalog for every provider with a key present (or the one named). */
export async function buildCatalog(options: CatalogFetchOptions = {}): Promise<ModelCatalog> {
	const env = options.env ?? process.env;
	const fetchImpl = options.fetch ?? fetch;
	const timeoutMs = options.timeoutMs ?? 8000;
	const log = options.log ?? (() => undefined);
	const models = createHarnessModels(env);
	const notes: string[] = [];

	let providerIds = providersWithKeys(env).filter((id) => !EXCLUDED_PROVIDERS.has(id) && models.getProvider(id));
	if (options.provider) providerIds = providerIds.filter((id) => id === options.provider);

	let modelsDev: ModelsDevCatalog | null = null;
	let modelsDevState: CatalogProvider['models_dev'] = 'skipped';
	if (!options.offline && providerIds.length > 0) {
		try {
			modelsDev = await fetchModelsDev(fetchImpl, timeoutMs);
			modelsDevState = 'listed';
		} catch (error) {
			modelsDevState = 'unavailable';
			notes.push(`models.dev could not be read: ${describeError(error)}`);
			log(`models.dev unavailable: ${describeError(error)}`);
		}
	}

	const providers: CatalogProvider[] = [];
	const catalog: CatalogModel[] = [];
	for (const providerId of providerIds.sort()) {
		const provider = models.getProvider(providerId);
		if (!provider) continue;
		const piModels = new Map(models.getModels(providerId).map((model) => [model.id, model]));
		const devProvider = modelsDev?.[MODELS_DEV_PROVIDER_ID[providerId] ?? providerId];
		const devModels = devProvider?.models ?? {};

		let listed: Map<string, ProviderListedModel> | null = null;
		let listState: CatalogProvider['provider_list'] = 'skipped';
		if (!options.offline) {
			try {
				const baseUrl = provider.baseUrl ?? models.getModels(providerId)[0]?.baseUrl;
				if (!baseUrl) throw new Error('the provider has no base URL');
				const result = await fetchProviderList(providerId, baseUrl, env, fetchImpl, timeoutMs);
				if (result === null) {
					listState = 'not_offered';
				} else {
					listed = new Map(result.map((item) => [item.id, item]));
					listState = 'listed';
				}
			} catch (error) {
				listState = 'unavailable';
				notes.push(`${provider.name} did not return its model list: ${describeError(error)}`);
				log(`${providerId} model list unavailable: ${describeError(error)}`);
			}
		}

		const ids = new Set<string>([...piModels.keys(), ...Object.keys(devModels)]);
		for (const [id] of listed ?? []) {
			if (usableListedModel(providerId, id, ids.has(id))) ids.add(id);
		}
		const siblings = [...piModels.values()];
		const entries: CatalogModel[] = [];
		for (const id of ids) {
			const pi = piModels.get(id);
			const dev = devModels[id];
			const fromList = listed?.get(id);
			const template = pi ?? nearestSibling(siblings, id);
			const reasoning = pi ? pi.reasoning : (dev?.reasoning ?? fromList?.reasoning ?? null);
			const sources: CatalogSource[] = [];
			if (pi) sources.push('pi-ai');
			if (dev) sources.push('models.dev');
			if (fromList) sources.push('provider');
			entries.push({
				provider: providerId,
				id,
				name: pi?.name ?? dev?.name ?? fromList?.name ?? id,
				reasoning,
				thinking_levels: thinkingLevelsOf(template, dev, reasoning),
				context_window: pi?.contextWindow ?? dev?.limit?.context ?? fromList?.context_window ?? null,
				max_output: pi?.maxTokens ?? dev?.limit?.output ?? fromList?.max_output ?? null,
				release_date: dev?.release_date ?? fromList?.release_date ?? null,
				cost: costOf(pi, dev, fromList),
				sources,
				listed_by_provider: listed ? listed.has(id) : null,
				runnable: template !== undefined
			});
		}
		entries.sort(compareModels);
		catalog.push(...entries);
		providers.push({
			id: providerId,
			name: provider.name,
			key_variables: [...(COMMON_PROVIDER_KEYS[providerId] ?? [])],
			base_url_override: providerBaseUrlOverride(providerId, env),
			provider_list: listState,
			models_dev: devProvider ? modelsDevState : modelsDevState === 'listed' ? 'unavailable' : modelsDevState,
			model_count: entries.length
		});
	}
	if (providerIds.length === 0) {
		notes.push(
			options.provider
				? `No key for provider "${options.provider}" in the environment.`
				: 'No provider key is set in the environment, so there is nothing to list.'
		);
	}
	return { generated_at: new Date().toISOString(), providers, models: catalog, notes };
}

export interface ResolvedModel {
	model: Model<Api>;
	/** Where the run's cost estimate comes from; recorded on the run. */
	pricingSource: string;
}

/** The catalog sibling whose id shares the longest prefix with `id`; the newest-looking on ties. */
export function nearestSibling(candidates: readonly Model<Api>[], id: string): Model<Api> | undefined {
	let best: Model<Api> | undefined;
	let bestLength = -1;
	for (const candidate of candidates) {
		let length = 0;
		while (length < id.length && length < candidate.id.length && id[length] === candidate.id[length]) length += 1;
		if (length > bestLength || (length === bestLength && best && candidate.id.localeCompare(best.id) > 0)) {
			best = candidate;
			bestLength = length;
		}
	}
	return best;
}

/** Register `model` on its provider so `models.getModel()` and the agent loop find it. */
export function registerModel(models: MutableModels, model: Model<Api>): void {
	const provider = models.getProvider(model.provider);
	if (!provider) throw new Error(`provider ${model.provider} is not registered`);
	const wrapped: Provider = {
		...provider,
		getModels: () => [...provider.getModels().filter((item) => item.id !== model.id), model]
	};
	if (provider.getAllModels) {
		const getAllModels = provider.getAllModels.bind(provider);
		wrapped.getAllModels = () => [...getAllModels().filter((item) => item.id !== model.id), model];
	}
	models.setProvider(wrapped);
}

export interface ResolveModelOptions {
	/** A models.dev catalog already fetched, or null to skip the lookup. Default: fetch it. */
	modelsDev?: ModelsDevCatalog | null;
	fetch?: typeof fetch;
	timeoutMs?: number;
	log?: (line: string) => void;
}

/**
 * The pi-ai catalog entry when there is one; otherwise a model configured
 * from its nearest catalog sibling and models.dev, registered on the provider.
 */
export async function resolveModel(
	models: MutableModels,
	provider: string,
	id: string,
	options: ResolveModelOptions = {}
): Promise<ResolvedModel> {
	const known = models.getModel(provider, id);
	if (known) return { model: known, pricingSource: 'pi-ai model catalog estimate' };
	const log = options.log ?? (() => undefined);
	const siblings = models.getModels(provider);
	const template = nearestSibling(siblings, id);
	if (!template) {
		throw new Error(
			`Unknown model ${provider}/${id}, and no ${provider} catalog entry to configure it from. Run "npm run list-models" to see the catalog.`
		);
	}
	let dev: ModelsDevModel | undefined;
	if (options.modelsDev !== null) {
		try {
			const catalog = options.modelsDev ?? (await fetchModelsDev(options.fetch, options.timeoutMs));
			dev = catalog[MODELS_DEV_PROVIDER_ID[provider] ?? provider]?.models[id];
		} catch (error) {
			log(`models.dev unavailable while configuring ${provider}/${id}: ${describeError(error)}`);
		}
	}
	const cost = costOf(undefined, dev, undefined);
	const model: Model<Api> = {
		...template,
		id,
		name: dev?.name ?? id,
		reasoning: dev?.reasoning ?? template.reasoning,
		contextWindow: dev?.limit?.context ?? template.contextWindow,
		maxTokens: dev?.limit?.output ?? template.maxTokens,
		cost: cost
			? { input: cost.input, output: cost.output, cacheRead: cost.cache_read, cacheWrite: cost.cache_write }
			: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 }
	};
	registerModel(models, model);
	const pricingSource = cost
		? `models.dev catalog estimate (not in the pi-ai catalog; request configured like ${template.id})`
		: `no estimate: ${provider}/${id} is in no catalog, cost recorded as zero (request configured like ${template.id})`;
	log(`model ${provider}/${id} is not in the pinned pi-ai catalog; ${pricingSource}`);
	return { model, pricingSource };
}
