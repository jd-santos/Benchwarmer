/**
 * Operator entry point. Every run is explicit: conversations, model, API.
 *
 *   npm run propose-bundles -- --conversation <id> [--conversation <id>] --model anthropic/<model-id>
 *   npm run list-models -- [provider]
 */

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { parseArgs } from 'node:util';

import { createModels } from '@earendil-works/pi-ai/models';
import { anthropicProvider } from '@earendil-works/pi-ai/providers/anthropic';
import { openaiProvider } from '@earendil-works/pi-ai/providers/openai';

import { proposeBundles, type ProposeBundlesOptions } from './workflows/propose-bundles.ts';

const HARNESS_ROOT = path.resolve(import.meta.dirname, '..');
const REPO_ROOT = path.resolve(HARNESS_ROOT, '..');
const THINKING = ['off', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'] as const;

function harnessVersion(): string {
	const pkg = JSON.parse(readFileSync(path.join(HARNESS_ROOT, 'package.json'), 'utf8')) as { version: string };
	return pkg.version;
}

function usage(): never {
	process.stderr.write(
		[
			'usage:',
			'  propose-bundles --conversation <id> [--conversation <id>...] --model <provider>/<model-id>',
			'      [--api http://127.0.0.1:8000] [--thinking off|minimal|low|medium|high|xhigh|max]',
			'      [--storage .benchwarmer/harness/propose-bundles.sqlite] [--reports reports/harness]',
			'      [--instructions "extra operator notes"]',
			'  list-models [provider]',
			''
		].join('\n')
	);
	process.exit(2);
}

async function listModels(provider?: string): Promise<void> {
	const models = createModels();
	models.setProvider(anthropicProvider());
	models.setProvider(openaiProvider());
	for (const model of models.getModels(provider)) {
		process.stdout.write(`${model.provider}/${model.id}\n`);
	}
}

async function main(argv: string[]): Promise<void> {
	const [command, ...rest] = argv;
	if (command === 'list-models') {
		await listModels(rest[0]);
		return;
	}
	if (command !== 'propose-bundles') usage();

	const { values } = parseArgs({
		args: rest,
		options: {
			conversation: { type: 'string', multiple: true },
			model: { type: 'string' },
			api: { type: 'string', default: 'http://127.0.0.1:8000' },
			thinking: { type: 'string' },
			storage: { type: 'string', default: path.join(REPO_ROOT, '.benchwarmer', 'harness', 'propose-bundles.sqlite') },
			reports: { type: 'string', default: path.join(REPO_ROOT, 'reports', 'harness') },
			instructions: { type: 'string' }
		},
		strict: true
	});
	const conversationIds = values.conversation ?? [];
	const [provider, ...modelParts] = (values.model ?? '').split('/');
	const modelId = modelParts.join('/');
	if (!conversationIds.length || !provider || !modelId) usage();
	if (values.thinking !== undefined && !(THINKING as readonly string[]).includes(values.thinking)) usage();

	const options: ProposeBundlesOptions = {
		apiBaseUrl: values.api,
		conversationIds,
		provider,
		modelId,
		storagePath: path.resolve(values.storage),
		reportDir: path.resolve(values.reports),
		harnessVersion: harnessVersion(),
		log: (line) => process.stderr.write(`${line}\n`)
	};
	if (values.thinking !== undefined) options.thinkingLevel = values.thinking as (typeof THINKING)[number];
	if (values.instructions !== undefined) options.extraInstructions = values.instructions;

	const report = await proposeBundles(options);
	const bundles = report.conversations.reduce((n, c) => n + c.bundles_created.length, 0);
	process.stderr.write(`${report.conversations.length} conversation(s), ${bundles} bundle(s) proposed\n`);
}

main(process.argv.slice(2)).catch((error: unknown) => {
	process.stderr.write(`${error instanceof Error ? (error.stack ?? error.message) : String(error)}\n`);
	process.exit(1);
});
