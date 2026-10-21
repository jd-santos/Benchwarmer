/**
 * Usage arithmetic shared by workflows: per-input deltas from session totals
 * and run totals summed back up. Cost figures are pi-ai catalog estimates.
 */

import type { Usage } from '@earendil-works/pi-ai';
import type { UsageState } from '@earendil-works/pi-durable';

export function emptyUsage(): UsageState {
	return { models: {}, tools: {} };
}

const ZERO: Usage = {
	input: 0, output: 0, cacheRead: 0, cacheWrite: 0, totalTokens: 0,
	cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 }
};

function combine(a: Usage, b: Usage, op: (x: number, y: number) => number): Usage {
	return {
		input: op(a.input, b.input),
		output: op(a.output, b.output),
		cacheRead: op(a.cacheRead, b.cacheRead),
		cacheWrite: op(a.cacheWrite, b.cacheWrite),
		totalTokens: op(a.totalTokens, b.totalTokens),
		cost: {
			input: op(a.cost.input, b.cost.input),
			output: op(a.cost.output, b.cost.output),
			cacheRead: op(a.cost.cacheRead, b.cost.cacheRead),
			cacheWrite: op(a.cost.cacheWrite, b.cost.cacheWrite),
			total: op(a.cost.total, b.cost.total)
		}
	};
}

export function addUsage(a: Usage, b: Usage): Usage {
	return combine(a, b, (x, y) => x + y);
}

/** Usage added between two session totals, per model and tool bucket. */
export function usageDelta(after: UsageState, before: UsageState): UsageState {
	const delta = emptyUsage();
	for (const bucket of ['models', 'tools'] as const) {
		for (const [key, usage] of Object.entries(after[bucket])) {
			const diff = combine(usage as Usage, (before[bucket][key] as Usage | undefined) ?? ZERO, (x, y) => x - y);
			if (diff.totalTokens !== 0 || diff.cost.total !== 0) delta[bucket][key] = diff;
		}
	}
	return delta;
}

/** Sum per-input usage into one run total. */
export function sumUsage(parts: Iterable<UsageState>): UsageState {
	const total = emptyUsage();
	for (const part of parts) {
		for (const bucket of ['models', 'tools'] as const) {
			for (const [key, usage] of Object.entries(part[bucket])) {
				const sum = total[bucket][key] as Usage | undefined;
				total[bucket][key] = sum ? addUsage(sum, usage as Usage) : usage;
			}
		}
	}
	return total;
}
