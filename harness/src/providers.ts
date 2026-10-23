/**
 * Model providers for harness workflows.
 *
 * The pi-ai catalog is registered except for an explicit exclusion list, and
 * each provider resolves its own credentials from the environment (for example
 * `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`).
 * The harness never hardcodes one vendor; the operator picks `provider/model-id`
 * on the command line and supplies that provider's key.
 *
 * A provider's endpoint can be redirected through a pass-through gateway (one
 * that accepts the vendor's own request format and swaps credentials) by
 * setting its base URL variable, for example `ANTHROPIC_BASE_URL`. The
 * provider id, catalog, and cost estimates are unchanged; only the host the
 * requests go to differs, and the run report records it.
 */

import { builtinProviders } from '@earendil-works/pi-ai/providers/all';
import { createModels, type MutableModels, type Provider } from '@earendil-works/pi-ai/models';

/**
 * Providers the operator has ruled out. They are never registered, so no model
 * from them can be selected and no key for them is ever read.
 */
export const EXCLUDED_PROVIDERS: ReadonlySet<string> = new Set(['xai', 'groq']);

/** Environment variables pi-ai reads for the most common providers, for diagnostics only. */
export const COMMON_PROVIDER_KEYS: Readonly<Record<string, readonly string[]>> = {
	anthropic: ['ANTHROPIC_API_KEY'],
	openai: ['OPENAI_API_KEY'],
	openrouter: ['OPENROUTER_API_KEY'],
	google: ['GEMINI_API_KEY', 'GOOGLE_API_KEY'],
	mistral: ['MISTRAL_API_KEY'],
	deepseek: ['DEEPSEEK_API_KEY'],
	together: ['TOGETHER_API_KEY'],
	fireworks: ['FIREWORKS_API_KEY']
};

/** Environment variables that redirect a provider's requests to another base URL. */
export const PROVIDER_BASE_URL_ENV: Readonly<Record<string, string>> = {
	anthropic: 'ANTHROPIC_BASE_URL',
	openai: 'OPENAI_BASE_URL',
	openrouter: 'OPENROUTER_BASE_URL',
	google: 'GEMINI_BASE_URL',
	mistral: 'MISTRAL_BASE_URL'
};

/** The base URL override for `provider` in `env`, with a trailing slash removed, or null. */
export function providerBaseUrlOverride(provider: string, env: NodeJS.ProcessEnv = process.env): string | null {
	const name = PROVIDER_BASE_URL_ENV[provider];
	const value = name ? env[name]?.trim() : undefined;
	if (!value) return null;
	if (!/^https?:\/\//.test(value)) {
		throw new Error(`${name} must be an http(s) URL, got "${value}".`);
	}
	return value.replace(/\/+$/, '');
}

/** `provider` with its own and every model's base URL replaced by `baseUrl`. */
function withBaseUrl(provider: Provider, baseUrl: string): Provider {
	const retarget = <T extends { baseUrl: string }>(model: T): T => ({ ...model, baseUrl });
	const wrapped: Provider = {
		...provider,
		baseUrl,
		getModels: () => provider.getModels().map(retarget)
	};
	if (provider.getAllModels) {
		const getAllModels = provider.getAllModels.bind(provider);
		wrapped.getAllModels = () => getAllModels().map(retarget);
	}
	return wrapped;
}

/** A models collection with every allowed pi-ai provider registered, honoring base URL overrides. */
export function createHarnessModels(env: NodeJS.ProcessEnv = process.env): MutableModels {
	const models = createModels();
	for (const provider of builtinProviders()) {
		if (EXCLUDED_PROVIDERS.has(provider.id)) continue;
		const override = providerBaseUrlOverride(provider.id, env);
		models.setProvider(override ? withBaseUrl(provider, override) : provider);
	}
	return models;
}

export function providerIds(): string[] {
	return createHarnessModels()
		.getProviders()
		.map((provider) => provider.id)
		.sort();
}

/** Common providers whose key is present in `env`, so an operator can see what a run can use. */
export function providersWithKeys(env: NodeJS.ProcessEnv = process.env): string[] {
	return Object.entries(COMMON_PROVIDER_KEYS)
		.filter(([, names]) => names.some((name) => Boolean(env[name])))
		.map(([provider]) => provider)
		.sort();
}

/** The message shown when the chosen provider has no key in the environment. */
export function missingKeyHint(provider: string, env: NodeJS.ProcessEnv = process.env): string | null {
	const names = COMMON_PROVIDER_KEYS[provider];
	if (!names || names.some((name) => Boolean(env[name]))) return null;
	return `No key for provider "${provider}" in the environment; set ${names.join(' or ')}. Providers with keys present: ${providersWithKeys(env).join(', ') || 'none'}.`;
}
