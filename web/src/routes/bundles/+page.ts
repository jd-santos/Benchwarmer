import { getBundles, getRun } from '$lib/api/client';
import type { BundleOrigin, BundleStatus } from '$lib/api/types';
import type { PageLoad } from './$types';

/** Which slice of the bundle list is shown; each view is a link, so it survives reloads. */
export type BundleView = 'all' | 'proposed' | 'rejected';

export const _views: { value: BundleView; label: string; hint: string }[] = [
	{ value: 'all', label: 'All bundles', hint: 'Every bundle, latest revision first' },
	{
		value: 'proposed',
		label: 'Proposed drafts',
		hint: 'Drafts a model proposed that no one has reviewed yet'
	},
	{ value: 'rejected', label: 'Rejected', hint: 'Proposals declined with a reason' }
];

export function _viewFrom(searchParams: URLSearchParams): BundleView {
	const view = searchParams.get('view');
	return _views.some((option) => option.value === view) ? (view as BundleView) : 'all';
}

export function _filtersFor(
	view: BundleView,
	run: string | null = null
): { origin?: BundleOrigin; status?: BundleStatus; runId?: string } {
	const byRun = run ? { runId: run } : {};
	switch (view) {
		case 'proposed':
			return { origin: 'generated', status: 'draft', ...byRun };
		case 'rejected':
			return { status: 'rejected', ...byRun };
		default:
			return byRun;
	}
}

export const load: PageLoad = ({ fetch, url }) => {
	const view = _viewFrom(url.searchParams);
	const run = url.searchParams.get('run')?.trim() || null;
	return {
		view,
		run,
		bundles: getBundles(_filtersFor(view, run), { fetch }),
		// Usage for the run being shown; an unrecorded run just shows no figures.
		runRecord: run ? getRun(run, { fetch }).catch(() => null) : null,
		// The count is a hint beside the view link; its failure must not hide the list.
		proposedCount:
			view === 'proposed'
				? null
				: getBundles(_filtersFor('proposed'), { fetch })
						.then((response) => response.items.length)
						.catch(() => null)
	};
};
