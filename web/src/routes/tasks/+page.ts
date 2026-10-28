import { getPartitionAssignment, getTasks } from '$lib/api/client';
import type { TaskStatus } from '$lib/api/types';
import type { PageLoad } from './$types';

export type TaskView = 'all' | TaskStatus;

export const _views: { value: TaskView; label: string; hint: string }[] = [
	{ value: 'all', label: 'All tasks', hint: 'Every task, latest version first' },
	{ value: 'draft', label: 'Drafts', hint: 'Being prepared; not exportable' },
	{ value: 'approved', label: 'Approved', hint: 'Exportable and runnable' },
	{ value: 'retired', label: 'Retired', hint: 'Kept for old results' }
];

export function _viewFrom(searchParams: URLSearchParams): TaskView {
	const view = searchParams.get('view');
	return _views.some((option) => option.value === view) ? (view as TaskView) : 'all';
}

export const load: PageLoad = ({ fetch, url }) => {
	const view = _viewFrom(url.searchParams);
	const bundle = url.searchParams.get('bundle')?.trim() || null;
	return {
		view,
		bundle,
		tasks: getTasks(
			{ ...(view === 'all' ? {} : { status: view }), ...(bundle ? { bundleId: bundle } : {}) },
			{ fetch }
		),
		// The latest run is context, not the page's task; its failure must not block the list.
		partitions: getPartitionAssignment({ fetch }).catch(() => null)
	};
};
