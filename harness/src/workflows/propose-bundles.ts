/**
 * Propose evidence bundles for explicitly listed conversations.
 *
 * One Pi Durable conversation per library conversation, run sequentially so a
 * crash resumes from committed state and usage attributes cleanly. Running
 * this command is the approval: the operator names the conversations, the
 * model, and the keys. Nothing in the Benchwarmer app triggers it.
 */

import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

import { BACKGROUND_CONTEXT } from '@earendil-works/chord/context';
import { createRegistry, Harness, type UsageState } from '@earendil-works/pi-durable';
import { openNodeSqliteStorage } from '@earendil-works/pi-durable/storage/sqlite/node';

import { BenchwarmerClient } from '../benchwarmer/client.ts';
import type { RunProvenance } from '../benchwarmer/client.ts';
import { createHarnessModels, missingKeyHint, providerBaseUrlOverride } from '../providers.ts';
import { createLibraryExtension, type ProposedBundleRecord } from '../tools/library.ts';
import { emptyUsage, sumUsage, toRunUsage, usageDelta } from '../usage.ts';

export { usageDelta } from '../usage.ts';

export const WORKFLOW_NAME = 'propose-bundles';

export interface ProposeBundlesOptions {
	apiBaseUrl: string;
	conversationIds: string[];
	provider: string;
	modelId: string;
	thinkingLevel?: 'off' | 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';
	/** SQLite file for durable harness state; one process at a time. */
	storagePath: string;
	/** Directory for the JSON run report. */
	reportDir: string;
	/** Version label of this harness build, recorded in the producer string. */
	harnessVersion: string;
	/** Extra operator instructions appended to the analyst instructions. */
	extraInstructions?: string;
	log?: (line: string) => void;
}

export interface ConversationRunReport {
	conversation_id: string;
	status: 'done' | 'unanswered' | 'error';
	reason?: string;
	bundles_created: ProposedBundleRecord[];
	usage: UsageState;
}

export interface RunReport {
	workflow: typeof WORKFLOW_NAME;
	run_id: string;
	started_at: string;
	finished_at: string;
	api_base_url: string;
	model: {
		provider: string;
		model_id: string;
		thinking_level: string | null;
		/** Where requests went when a base URL override redirected the provider; null for the vendor's own endpoint. */
		base_url_override: string | null;
	};
	producer: string;
	storage_path: string;
	conversations: ConversationRunReport[];
	usage_total: UsageState;
	/** pi-ai's own estimate from its price catalog, not a provider charge. */
	pricing_source: 'pi-ai model catalog estimate';
}

export const ANALYST_INSTRUCTIONS = `You analyze one captured agent conversation from a private library and propose evidence bundles.

An evidence bundle gathers the specific messages and results needed to understand one objective or phase of work: the request (requirement), what the agent did (action), what happened (result), later fixes (correction), and context needed to follow it. Items may be far apart. A bundle never pretends they were adjacent.

Work like this:
1. Call get_outline first. It is deterministic and complete; use it to decide which exchanges matter.
2. Call list_bundles to see what already exists for this conversation and do not duplicate it.
3. Read only the events you need with read_events. Prefer citing a specific block; cite a text range (code points, half-open) when a block is long and only part of it is evidence.
4. Propose one bundle per distinct piece of work with propose_bundle. Include failures, recoveries, and routine successes alike. Give each bundle two statements:
   - goal: what this particular piece of work tried to achieve, with its specifics ("find why the nightly reconciliation posted duplicate credits to 14 accounts").
   - objective: the kind of work in general terms, as one short imperative phrase that could describe the same work in another project ("diagnose duplicate records produced by a scheduled batch job", "verify a fix by replaying historical inputs against a scratch copy"). No project names, dates, identifiers, or figures. Bundles are later grouped by objective, so reuse the same wording when two bundles are the same kind of work.
   Write the rationale as why these items were selected.
5. Record in missing_evidence anything the evidence does not show (uncaptured tool output, compaction gaps, missing starting files). If an event was not captured, do not conclude it did not happen.
6. If propose_bundle reports issues, fix the references and try again. Do not invent event or block ids.
7. Stay on one path per bundle. Sibling branches are different executions.

Report only what the evidence supports. Say "the test failed before the correction", not "the agent misunderstood"; interpretations are not part of the bundle record. If the conversation holds no coherent piece of work, create no bundle and say so.

When finished, answer with a short list of the bundles you created (id, objective, goal) or the reason none were created.`;

export async function proposeBundles(options: ProposeBundlesOptions): Promise<RunReport> {
	const context = BACKGROUND_CONTEXT;
	const log = options.log ?? (() => undefined);
	const startedAt = new Date();
	const runId = `${WORKFLOW_NAME}-${startedAt.toISOString().replace(/[:.]/g, '-')}`;
	const producer = `benchwarmer-harness/${WORKFLOW_NAME}@${options.harnessVersion} ${options.provider}/${options.modelId}`;

	const models = createHarnessModels();
	if (!models.getModel(options.provider, options.modelId)) {
		throw new Error(
			`Unknown model ${options.provider}/${options.modelId}. Run "npm run list-models" to see the catalog.`
		);
	}
	const keyHint = missingKeyHint(options.provider);
	if (keyHint) throw new Error(keyHint);
	const reportPath = path.join(options.reportDir, `${runId}.json`);
	const provenance: RunProvenance = {
		run_id: runId,
		workflow: WORKFLOW_NAME,
		harness_version: options.harnessVersion,
		provider: options.provider,
		model: options.modelId,
		thinking_level: options.thinkingLevel ?? null,
		report_path: reportPath
	};

	const client = new BenchwarmerClient(options.apiBaseUrl);
	const created: ProposedBundleRecord[] = [];
	const library = createLibraryExtension(client, {
		producer,
		provenance,
		onBundleCreated: (record) => {
			created.push(record);
			log(`  created ${record.bundle_id}: ${record.goal}`);
			log(`    objective: ${record.objective}`);
		}
	});
	const registry = createRegistry();
	registry.install(library);

	await mkdir(path.dirname(options.storagePath), { recursive: true });
	const storage = await openNodeSqliteStorage(options.storagePath);
	const harness = await Harness.open(
		storage,
		{
			models,
			registry,
			settings: { extensions: [library], toolExecution: 'sequential' },
			onReport: (error) => log(`  harness report: ${error instanceof Error ? error.message : String(error)}`)
		},
		context
	);
	harness.resume();

	const reports: ConversationRunReport[] = [];
	try {
		const instructions = options.extraInstructions
			? `${ANALYST_INSTRUCTIONS}\n\nOperator notes:\n${options.extraInstructions}`
			: ANALYST_INSTRUCTIONS;
		for (const conversationId of options.conversationIds) {
			log(`conversation ${conversationId}`);
			const before = await harness.usage(context);
			const createdBefore = created.length;
			const report: ConversationRunReport = {
				conversation_id: conversationId,
				status: 'error',
				bundles_created: [],
				usage: emptyUsage()
			};
			try {
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
						content: `Analyze library conversation ${conversationId} and propose evidence bundles for it.`,
						requestId: `${runId}:${conversationId}`
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
			}
			report.bundles_created = created.slice(createdBefore);
			report.usage = usageDelta(await harness.usage(context), before);
			log(`  ${report.status}; ${report.bundles_created.length} bundle(s)`);
			reports.push(report);
		}
	} finally {
		await harness.close(context);
	}

	const finishedAt = new Date();
	const total = sumUsage(reports.map((report) => report.usage));
	const runReport: RunReport = {
		workflow: WORKFLOW_NAME,
		run_id: runId,
		started_at: startedAt.toISOString(),
		finished_at: finishedAt.toISOString(),
		api_base_url: options.apiBaseUrl,
		model: {
			provider: options.provider,
			model_id: options.modelId,
			thinking_level: options.thinkingLevel ?? null,
			base_url_override: providerBaseUrlOverride(options.provider)
		},
		producer,
		storage_path: options.storagePath,
		conversations: reports,
		usage_total: total,
		pricing_source: 'pi-ai model catalog estimate'
	};
	await mkdir(options.reportDir, { recursive: true });
	await writeFile(reportPath, JSON.stringify(runReport, null, 2) + '\n');
	log(`report: ${reportPath}`);
	await recordRun(client, runReport, options.harnessVersion, reportPath, log);
	return runReport;
}

/** Store the run in the application so reviewers see its usage beside the bundles; the file is the fallback. */
async function recordRun(
	client: BenchwarmerClient,
	report: RunReport,
	harnessVersion: string,
	reportPath: string,
	log: (line: string) => void
): Promise<void> {
	try {
		await client.recordRun({
			run_id: report.run_id,
			workflow: report.workflow,
			harness_version: harnessVersion,
			started_at: report.started_at,
			finished_at: report.finished_at,
			api_base_url: report.api_base_url,
			model: report.model,
			producer: report.producer,
			inputs: report.conversations.map((item) => ({
				id: item.conversation_id,
				kind: 'conversation',
				status: item.status,
				reason: item.reason ?? null,
				bundle_ids: item.bundles_created.map((bundle) => bundle.bundle_id),
				usage: toRunUsage(item.usage)
			})),
			usage_total: toRunUsage(report.usage_total),
			pricing_source: report.pricing_source,
			report_path: reportPath
		});
		log(`recorded run ${report.run_id} in the application`);
	} catch (error) {
		log(`could not record the run in the application (the report file stands): ${error instanceof Error ? error.message : String(error)}`);
	}
}
