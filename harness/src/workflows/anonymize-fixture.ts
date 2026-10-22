/**
 * Turn one raw Pi session into a synthetic fixture draft.
 *
 * The session is read from the path the operator named and scrubbed through
 * the API before any model sees it; the harness never opens the database and
 * the API stores nothing. The model's job is an invented analog with the same
 * structure, written to a gitignored draft for human diff review. Running the
 * command with --disclose-to is the approval for the model work.
 */

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { BACKGROUND_CONTEXT } from '@earendil-works/chord/context';
import { createRegistry, Harness, type UsageState } from '@earendil-works/pi-durable';
import { openNodeSqliteStorage } from '@earendil-works/pi-durable/storage/sqlite/node';

import { BenchwarmerClient } from '../benchwarmer/client.ts';
import { checkDisclosure } from '../fixture.ts';
import { createHarnessModels, missingKeyHint } from '../providers.ts';
import {
	createFixturesExtension,
	type FixtureCheckRecord,
	type FixtureDraftRecord,
	type SessionSlot
} from '../tools/fixtures.ts';
import { emptyUsage, sumUsage, usageDelta } from '../usage.ts';

export const WORKFLOW_NAME = 'anonymize-fixture';

export interface AnonymizeFixtureOptions {
	apiBaseUrl: string;
	/** Absolute paths to complete Pi session files; one Pi Durable conversation each. */
	sessionPaths: string[];
	/** Operator-supplied sensitive terms: names, employers, project names. */
	terms: string[];
	provider: string;
	modelId: string;
	/** Must equal `provider`; the explicit disclosure acknowledgment. */
	discloseTo: string | undefined;
	thinkingLevel?: 'off' | 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';
	storagePath: string;
	reportDir: string;
	harnessVersion: string;
	extraInstructions?: string;
	log?: (line: string) => void;
}

export interface SessionRunReport {
	/** The operator's path is recorded by basename only; the report is for review, not location. */
	session_file: string;
	status: 'done' | 'unanswered' | 'error';
	reason?: string;
	checks: FixtureCheckRecord[];
	drafts_written: FixtureDraftRecord[];
	usage: UsageState;
}

export interface RunReport {
	workflow: typeof WORKFLOW_NAME;
	run_id: string;
	started_at: string;
	finished_at: string;
	api_base_url: string;
	model: { provider: string; model_id: string; thinking_level: string | null };
	disclosed_to: string;
	producer: string;
	storage_path: string;
	draft_dir: string;
	term_count: number;
	sessions: SessionRunReport[];
	usage_total: UsageState;
	pricing_source: 'pi-ai model catalog estimate';
}

export const ANALYST_INSTRUCTIONS = `You turn one scrubbed, private coding-agent session into a synthetic test fixture. The fixture must be useful for testing conversation tooling and must reveal nothing about the real person, their employer, their projects, or their systems.

Work like this:
1. Call read_scrubbed_session once. It returns the session as a fixture-shaped conversation after deterministic scrubbing. Placeholders such as <email-1>, <url-2>, <hostname-1>, <ipv4-1>, <secret-1>, <term-3>, and /scrubbed/path-4/file-4.py stand for removed private values. The same placeholder always stands for the same original.
2. Invent a different but equally plausible engineering scenario of the same shape: the same kind of problem, the same number of steps, the same successes and failures, the same tool usage pattern. Do not reuse the real domain, product names, repository layout, or data. Replace every placeholder with concrete fictional content that fits the new scenario (a fictional person, company, host, address, path, and token-looking string that is obviously fake).
3. Preserve structure exactly: the same events in the same order with the same ordinals, parent links, kinds, roles, block kinds and block order, the same tool_call_id pairing, the same blocks with uncaptured text (keep text null where it was null), the same extension keys, the same relationships, and the same coverage. Keep timestamps shaped like the originals but shift them to a different date. Keep usage entries aligned with the same assistant events. Choose a new native_id.
4. Disguise the user's voice. A person's writing style identifies them, so rewrite every user turn in a clearly different register while keeping the same request and intent: if the original is terse, make it fuller; if casual with typos and lowercase, make it clean and formal, or the reverse; change greeting and sign-off habits, punctuation habits, and sentence length. Never carry over distinctive phrases.
5. Rewrite assistant text, reasoning, and tool-result text to match the new scenario, keeping the same level of detail, the same headings structure, and about the same length.
6. Call check_fixture with your candidate. Fix every fidelity issue and every leak it reports and call it again until it says OK with zero placeholders remaining. Do not weaken structure to make it pass.
7. Only then call write_fixture_draft with a one-sentence summary of the invented scenario. A human reviews the draft against the original before it can enter the test suite.

If the scrubbed session is too fragmentary to invent a faithful analog, say so and write nothing.

When finished, answer with the draft path and the one-sentence summary, or the reason no draft was written.`;

export async function anonymizeFixture(options: AnonymizeFixtureOptions): Promise<RunReport> {
	checkDisclosure(options.provider, options.discloseTo);
	const context = BACKGROUND_CONTEXT;
	const log = options.log ?? (() => undefined);
	const startedAt = new Date();
	const runId = `${WORKFLOW_NAME}-${startedAt.toISOString().replace(/[:.]/g, '-')}`;
	const producer = `benchwarmer-harness/${WORKFLOW_NAME}@${options.harnessVersion} ${options.provider}/${options.modelId}`;
	const draftDir = path.join(options.reportDir, 'fixtures', runId);

	const models = createHarnessModels();
	if (!models.getModel(options.provider, options.modelId)) {
		throw new Error(
			`Unknown model ${options.provider}/${options.modelId}. Run "npm run list-models" to see the catalog and make sure the provider's key is in the environment.`
		);
	}
	const keyHint = missingKeyHint(options.provider);
	if (keyHint) throw new Error(keyHint);

	const client = new BenchwarmerClient(options.apiBaseUrl);
	const session: SessionSlot = { content: '' };
	const checks: FixtureCheckRecord[] = [];
	const drafts: FixtureDraftRecord[] = [];
	const fixtures = createFixturesExtension(client, {
		session,
		terms: options.terms,
		draftDir,
		producer,
		onCheck: (record) => {
			checks.push(record);
			log(`  check: ${record.ok ? 'ok' : `${record.fidelity_issues} fidelity, ${record.leak_issues} leak`}`);
		},
		onDraftWritten: (record) => {
			drafts.push(record);
			log(`  draft: ${record.path}`);
		}
	});
	const registry = createRegistry();
	registry.install(fixtures);

	await mkdir(path.dirname(options.storagePath), { recursive: true });
	const storage = await openNodeSqliteStorage(options.storagePath);
	const harness = await Harness.open(
		storage,
		{
			models,
			registry,
			settings: { extensions: [fixtures], toolExecution: 'sequential' },
			onReport: (error) => log(`  harness report: ${error instanceof Error ? error.message : String(error)}`)
		},
		context
	);
	harness.resume();

	const reports: SessionRunReport[] = [];
	const instructions = options.extraInstructions
		? `${ANALYST_INSTRUCTIONS}\n\nOperator notes:\n${options.extraInstructions}`
		: ANALYST_INSTRUCTIONS;
	try {
		for (const sessionPath of options.sessionPaths) {
			const sessionFile = path.basename(sessionPath);
			log(`session ${sessionFile}`);
			const before = await harness.usage(context);
			const checksBefore = checks.length;
			const draftsBefore = drafts.length;
			const report: SessionRunReport = {
				session_file: sessionFile,
				status: 'error',
				checks: [],
				drafts_written: [],
				usage: emptyUsage()
			};
			try {
				session.content = await readFile(sessionPath, 'utf8');
				const conversation = await harness.createConversation(
					{
						ownership: { kind: 'ownerless' },
						agent: {
							model: { provider: options.provider, modelId: options.modelId },
							...(options.thinkingLevel ? { thinkingLevel: options.thinkingLevel } : {}),
							instructions
						}
					},
					context
				);
				const submission = await conversation.submit(
					{
						type: 'input',
						content: 'Read the scrubbed session and write a synthetic fixture draft for it.',
						requestId: `${runId}:${sessionFile}`
					},
					context
				);
				const settled = await submission.wait(context);
				report.status = settled.status;
				if (settled.status === 'unanswered') report.reason = settled.reason;
			} catch (error) {
				report.status = 'error';
				report.reason = error instanceof Error ? error.message : String(error);
				log(`  error: ${report.reason}`);
			} finally {
				session.content = '';
			}
			report.checks = checks.slice(checksBefore);
			report.drafts_written = drafts.slice(draftsBefore);
			report.usage = usageDelta(await harness.usage(context), before);
			log(`  ${report.status}; ${report.drafts_written.length} draft(s)`);
			reports.push(report);
		}
	} finally {
		await harness.close(context);
	}

	const finishedAt = new Date();
	const runReport: RunReport = {
		workflow: WORKFLOW_NAME,
		run_id: runId,
		started_at: startedAt.toISOString(),
		finished_at: finishedAt.toISOString(),
		api_base_url: options.apiBaseUrl,
		model: {
			provider: options.provider,
			model_id: options.modelId,
			thinking_level: options.thinkingLevel ?? null
		},
		disclosed_to: options.discloseTo ?? '',
		producer,
		storage_path: options.storagePath,
		draft_dir: draftDir,
		term_count: options.terms.length,
		sessions: reports,
		usage_total: sumUsage(reports.map((report) => report.usage)),
		pricing_source: 'pi-ai model catalog estimate'
	};
	await mkdir(options.reportDir, { recursive: true });
	const reportPath = path.join(options.reportDir, `${runId}.json`);
	await writeFile(reportPath, JSON.stringify(runReport, null, 2) + '\n');
	log(`report: ${reportPath}`);
	return runReport;
}
