import { getRuns } from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch, url }) => {
	const workflow = url.searchParams.get('workflow')?.trim() || null;
	return {
		workflow,
		runs: getRuns({ workflow }, { fetch })
	};
};
