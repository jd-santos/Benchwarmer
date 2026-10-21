/**
 * Model providers for harness workflows.
 *
 * Every provider in the pi-ai catalog is registered, and each resolves its own
 * credentials from the environment (for example `ANTHROPIC_API_KEY`,
 * `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`). The harness never
 * hardcodes one vendor; the operator picks `provider/model-id` on the command
 * line and supplies that provider's key.
 */

import { builtinModels, getBuiltinProviders } from '@earendil-works/pi-ai/providers/all';
import type { MutableModels } from '@earendil-works/pi-ai/models';

/** Environment variables pi-ai reads for the most common providers, for diagnostics only. */
export const COMMON_PROVIDER_KEYS: Readonly<Record<string, readonly string[]>> = {
	anthropic: ['ANTHROPIC_API_KEY'],
	openai: ['OPENAI_API_KEY'],
	openrouter: ['OPENROUTER_API_KEY'],
	google: ['GEMINI_API_KEY', 'GOOGLE_API_KEY'],
	xai: ['XAI_API_KEY'],
	groq: ['GROQ_API_KEY'],
	mistral: ['MISTRAL_API_KEY'],
	deepseek: ['DEEPSEEK_API_KEY'],
	together: ['TOGETHER_API_KEY'],
	fireworks: ['FIREWORKS_API_KEY']
};

/** A models collection with every pi-ai provider registered. */
export function createHarnessModels(): MutableModels {
	return builtinModels();
}

export function providerIds(): string[] {
	return getBuiltinProviders().map(String).sort();
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
