import { getHealth, getSources } from '$lib/api/client';
import type { HealthResponse, SourcesResponse } from '$lib/api/types';
import type { PageLoad } from './$types';

export interface FoundationOverview {
	health: HealthResponse;
	sources: SourcesResponse | null;
}

export async function _loadFoundationOverview(
	request: typeof globalThis.fetch = globalThis.fetch
): Promise<FoundationOverview> {
	const health = await getHealth({ fetch: request });
	const sources = health.alembic_revision === null ? null : await getSources({ fetch: request });
	return { health, sources };
}

export const load: PageLoad = ({ fetch }) => ({ overview: _loadFoundationOverview(fetch) });
