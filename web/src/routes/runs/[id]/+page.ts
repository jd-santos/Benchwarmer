import { getRun } from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch, params }) => ({
	run: getRun(params.id, { fetch })
});
