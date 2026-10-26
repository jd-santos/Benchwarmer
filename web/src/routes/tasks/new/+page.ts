import { error } from '@sveltejs/kit';
import { getTaskDraft } from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch, url }) => {
	const bundle = url.searchParams.get('bundle')?.trim();
	if (!bundle)
		error(404, 'A task is prepared from a bundle; open one and choose "Prepare as task".');
	const requested = Number.parseInt(url.searchParams.get('revision') ?? '', 10);
	const revision = Number.isInteger(requested) && requested > 0 ? requested : null;
	return { bundle, draft: getTaskDraft(bundle, revision, { fetch }) };
};
