import { getBundle, getBundles } from '$lib/api/client';
import type { BundleSummary } from '$lib/api/types';
import { _filtersFor, _viewFrom, type BundleView } from '../+page';
import type { PageLoad } from './$types';

/** Where a bundle sits in the list it was opened from, for stepping through that list. */
export interface BundleNavigation {
	view: BundleView;
	run: string | null;
	/** One-based, or null when the bundle is no longer in that list. */
	position: number | null;
	total: number;
	previousId: string | null;
	nextId: string | null;
}

export function _navigationFor(
	items: BundleSummary[],
	id: string,
	view: BundleView,
	run: string | null
): BundleNavigation {
	const index = items.findIndex((item) => item.id === id);
	return {
		view,
		run,
		position: index === -1 ? null : index + 1,
		total: items.length,
		previousId: index > 0 ? items[index - 1].id : null,
		nextId: index !== -1 && index < items.length - 1 ? items[index + 1].id : null
	};
}

export const load: PageLoad = ({ fetch, params, url }) => {
	const requested = Number.parseInt(url.searchParams.get('revision') ?? '', 10);
	const revision = Number.isInteger(requested) && requested > 0 ? requested : null;
	const view = _viewFrom(url.searchParams);
	const run = url.searchParams.get('run')?.trim() || null;
	const bundle = getBundle(params.id, revision, { fetch });
	return {
		revision,
		bundle,
		// The list the bundle was opened from, in the list's order, so a reviewer can step through it.
		navigation: getBundles(_filtersFor(view, run), { fetch }).then(
			(response) => _navigationFor(response.items, params.id, view, run),
			() => null
		)
	};
};
