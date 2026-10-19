import { getBundle } from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch, params, url }) => {
	const requested = Number.parseInt(url.searchParams.get('revision') ?? '', 10);
	const revision = Number.isInteger(requested) && requested > 0 ? requested : null;
	return { revision, bundle: getBundle(params.id, revision, { fetch }) };
};
