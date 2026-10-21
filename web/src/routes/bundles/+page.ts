import { getBundles } from '$lib/api/client';
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

export function _filtersFor(view: BundleView): { origin?: BundleOrigin; status?: BundleStatus } {
	switch (view) {
		case 'proposed':
			return { origin: 'generated', status: 'draft' };
		case 'rejected':
			return { status: 'rejected' };
		default:
			return {};
	}
}

export const load: PageLoad = ({ fetch, url }) => {
	const view = _viewFrom(url.searchParams);
	return {
		view,
		bundles: getBundles(_filtersFor(view), { fetch }),
		// The count is a hint beside the view link; its failure must not hide the list.
		proposedCount:
			view === 'proposed'
				? null
				: getBundles(_filtersFor('proposed'), { fetch })
						.then((response) => response.items.length)
						.catch(() => null)
	};
};
