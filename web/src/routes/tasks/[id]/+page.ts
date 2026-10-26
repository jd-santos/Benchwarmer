import { getTask } from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch, params, url }) => {
	const requested = Number.parseInt(url.searchParams.get('version') ?? '', 10);
	const version = Number.isInteger(requested) && requested > 0 ? requested : null;
	return { version, task: getTask(params.id, version, { fetch }) };
};
