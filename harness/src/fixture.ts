/**
 * Pure helpers for the anonymize-fixture workflow: the disclosure gate and the
 * `tests/fixtures` document shape. No I/O, no model, so they are unit-tested
 * without a running API.
 */

import type { FixtureConversation } from './benchwarmer/client.ts';

export const DISCLOSURE_RULE = [
	'This workflow sends scrubbed private conversation content to a model provider.',
	'Decided 2026-10-21: scrubbed sessions may go to any provider the operator names,',
	'but each run must acknowledge the recipient explicitly. Pass --disclose-to <provider>',
	'matching the provider in --model <provider>/<model-id>. Nothing is sent otherwise.',
	'Record: todo/work/fixture-anonymizer/README.md'
].join('\n');

export class DisclosureError extends Error {
	constructor(message: string) {
		super(`${message}\n\n${DISCLOSURE_RULE}`);
		this.name = 'DisclosureError';
	}
}

/** Refuse to start unless the operator named the exact provider that will receive content. */
export function checkDisclosure(modelProvider: string, discloseTo: string | undefined): void {
	if (!discloseTo) {
		throw new DisclosureError('Missing --disclose-to <provider>.');
	}
	if (discloseTo.trim().toLowerCase() !== modelProvider.trim().toLowerCase()) {
		throw new DisclosureError(
			`--disclose-to names "${discloseTo}" but --model would send content to "${modelProvider}".`
		);
	}
}

export interface FixtureDocumentOptions {
	/** Enrolled synthetic source id for the import batch, for example `fixture-source-pi-anonymized`. */
	sourceId: string;
	sourceKind: string;
	batchId: string;
	capturedAt: string;
	description: string;
}

export interface FixtureDocument {
	schema_version: 1;
	description: string;
	imports: {
		source_id: string;
		source_kind: string;
		batch_id: string;
		captured_at: string;
		conversations: FixtureConversation[];
	}[];
}

/** Wrap one fixture conversation in the file shape `demo_conversations.load_demo_conversations` reads. */
export function toFixtureDocument(
	conversation: FixtureConversation,
	options: FixtureDocumentOptions
): FixtureDocument {
	return {
		schema_version: 1,
		description: options.description,
		imports: [
			{
				source_id: options.sourceId,
				source_kind: options.sourceKind,
				batch_id: options.batchId,
				captured_at: options.capturedAt,
				conversations: [conversation]
			}
		]
	};
}

/** Count placeholders still present in a candidate, so a draft is never written half-rewritten. */
export function countPlaceholders(conversation: FixtureConversation): number {
	const pattern = /<(?:term|email|url|ipv4|ipv6|secret|hostname)-\d+>|\/scrubbed\/path-\d+\//g;
	let count = 0;
	const visit = (value: unknown): void => {
		if (typeof value === 'string') count += value.match(pattern)?.length ?? 0;
		else if (Array.isArray(value)) value.forEach(visit);
		else if (value && typeof value === 'object') Object.values(value).forEach(visit);
	};
	visit(conversation);
	return count;
}
