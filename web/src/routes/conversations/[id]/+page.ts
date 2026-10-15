import { getConversation } from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch, params, url }) => {
	const revision = url.searchParams.get('revision');
	return {
		revision,
		query: url.searchParams.get('q'),
		conversation: getConversation(params.id, revision, { fetch })
	};
};
