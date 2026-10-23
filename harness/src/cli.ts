/**
 * Operator entry point. Every run is explicit: conversations, model, API.
 *
 *   npm run propose-bundles -- --conversation <id> [--conversation <id>] --model <provider>/<model-id>
 *   npm run anonymize-fixture -- --session <path> --model <provider>/<model-id> --disclose-to <provider> --term <t>
 *   npm run list-models -- [provider]
 */

import { readFileSync } from 'node:fs';
import path from 'node:path';
import { parseArgs } from 'node:util';

import { DISCLOSURE_RULE, DisclosureError } from './fixture.ts';
import { createHarnessModels, providerBaseUrlOverride, providersWithKeys } from './providers.ts';
import { anonymizeFixture, type AnonymizeFixtureOptions } from './workflows/anonymize-fixture.ts';
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
			'  anonymize-fixture --session <path> [--session <path>...] --model <provider>/<model-id>',
			'      --disclose-to <provider> [--term <sensitive term>...] [--terms-file <path>]',
			'      [--api http://127.0.0.1:8000] [--thinking <level>] [--storage <sqlite>] [--reports <dir>]',
			'      [--instructions "extra operator notes"]',
			'  list-models [provider]',
			'',
			DISCLOSURE_RULE,
			''
		].join('\n')
	);
	process.exit(2);
}

async function listModels(provider?: string): Promise<void> {
	const models = createHarnessModels();
	for (const model of models.getModels(provider)) {
		process.stdout.write(`${model.provider}/${model.id}\n`);
	}
	const ready = providersWithKeys();
	process.stderr.write(`providers with keys in this environment: ${ready.join(', ') || 'none'}\n`);
	for (const id of ready) {
		const override = providerBaseUrlOverride(id);
		if (override) process.stderr.write(`${id} requests go to ${override}\n`);
	}
}

async function main(argv: string[]): Promise<void> {
	const [command, ...rest] = argv;
	if (command === 'list-models') {
		await listModels(rest[0]);
		return;
	}
	if (command === 'anonymize-fixture') {
		await runAnonymizeFixture(rest);
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

async function runAnonymizeFixture(args: string[]): Promise<void> {
	const { values } = parseArgs({
		args,
		options: {
			session: { type: 'string', multiple: true },
			model: { type: 'string' },
			'disclose-to': { type: 'string' },
			term: { type: 'string', multiple: true },
			'terms-file': { type: 'string' },
			api: { type: 'string', default: 'http://127.0.0.1:8000' },
			thinking: { type: 'string' },
			storage: { type: 'string', default: path.join(REPO_ROOT, '.benchwarmer', 'harness', 'anonymize-fixture.sqlite') },
			reports: { type: 'string', default: path.join(REPO_ROOT, 'reports', 'harness') },
			instructions: { type: 'string' }
		},
		strict: true
	});
	const sessionPaths = (values.session ?? []).map((p) => path.resolve(p));
	const [provider, ...modelParts] = (values.model ?? '').split('/');
	const modelId = modelParts.join('/');
	if (!sessionPaths.length || !provider || !modelId) usage();
	if (values.thinking !== undefined && !(THINKING as readonly string[]).includes(values.thinking)) usage();
	const terms = [...(values.term ?? [])];
	if (values['terms-file'] !== undefined) {
		for (const line of readFileSync(values['terms-file'], 'utf8').split(/\r?\n/)) {
			const term = line.trim();
			if (term && !term.startsWith('#')) terms.push(term);
		}
	}

	const options: AnonymizeFixtureOptions = {
		apiBaseUrl: values.api,
		sessionPaths,
		terms,
		provider,
		modelId,
		discloseTo: values['disclose-to'],
		storagePath: path.resolve(values.storage),
		reportDir: path.resolve(values.reports),
		harnessVersion: harnessVersion(),
		log: (line) => process.stderr.write(`${line}\n`)
	};
	if (values.thinking !== undefined) options.thinkingLevel = values.thinking as (typeof THINKING)[number];
	if (values.instructions !== undefined) options.extraInstructions = values.instructions;

	const report = await anonymizeFixture(options);
	const drafts = report.sessions.reduce((n, s) => n + s.drafts_written.length, 0);
	process.stderr.write(`${report.sessions.length} session(s), ${drafts} draft(s) written to ${report.draft_dir}\n`);
}

main(process.argv.slice(2)).catch((error: unknown) => {
	if (error instanceof DisclosureError) {
		process.stderr.write(`${error.message}\n`);
		process.exit(2);
	}
	process.stderr.write(`${error instanceof Error ? (error.stack ?? error.message) : String(error)}\n`);
	process.exit(1);
});
