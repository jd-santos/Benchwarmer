import { getConversations, getSources } from '$lib/api/client';
import type { PageLoad } from './$types';

export const _PAGE_SIZE = 50;

export interface ConversationFilters {
	q: string;
	sourceId: string;
	offset: number;
}

export function _filtersFrom(searchParams: URLSearchParams): ConversationFilters {
	const offset = Number.parseInt(searchParams.get('offset') ?? '0', 10);
	return {
		q: searchParams.get('q')?.trim() ?? '',
		sourceId: searchParams.get('source') ?? '',
		offset: Number.isFinite(offset) && offset > 0 ? offset : 0
	};
}

export const load: PageLoad = ({ fetch, url }) => {
	const filters = _filtersFrom(url.searchParams);
	return {
		filters,
		conversations: getConversations(
			{
				q: filters.q || undefined,
				sourceId: filters.sourceId || undefined,
				limit: _PAGE_SIZE,
				offset: filters.offset
			},
			{ fetch }
		),
		// The filter is optional; a source-status failure must not hide the library.
		sources: getSources({ fetch }).catch(() => null)
	};
};
