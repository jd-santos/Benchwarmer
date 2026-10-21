import { getBundles, getConversations, getHealth, getSources } from '$lib/api/client';
import type { BundleSummary, HealthResponse, SourcesResponse } from '$lib/api/types';
import type { PageLoad } from './$types';

export interface LibraryCounts {
	conversations: number;
	bundles: BundleSummary[];
}

export interface FoundationOverview {
	health: HealthResponse;
	sources: SourcesResponse | null;
	library: LibraryCounts | null;
}

async function loadLibrary(request: typeof globalThis.fetch): Promise<LibraryCounts | null> {
	try {
		const [conversations, bundles] = await Promise.all([
			getConversations({ limit: 1 }, { fetch: request }),
			getBundles({}, { fetch: request })
		]);
		return { conversations: conversations.total, bundles: bundles.items };
	} catch {
		// Counts are orientation only; their absence must not hide system status.
		return null;
	}
}

export async function _loadFoundationOverview(
	request: typeof globalThis.fetch = globalThis.fetch
): Promise<FoundationOverview> {
	const health = await getHealth({ fetch: request });
	if (health.alembic_revision === null) return { health, sources: null, library: null };
	const [sources, library] = await Promise.all([
		getSources({ fetch: request }),
		loadLibrary(request)
	]);
	return { health, sources, library };
}

export const load: PageLoad = ({ fetch }) => ({ overview: _loadFoundationOverview(fetch) });
