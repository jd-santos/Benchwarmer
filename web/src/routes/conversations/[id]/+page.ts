import { getConversation, getConversationBundles } from '$lib/api/client';
import type { BundleMembership } from '$lib/api/types';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch, params, url }) => {
	const revision = url.searchParams.get('revision');
	return {
		revision,
		query: url.searchParams.get('q'),
		conversation: getConversation(params.id, revision, { fetch }),
		// Marks on cited turns are context; a failure must not hide the conversation.
		bundles: getConversationBundles(params.id, { fetch }).catch((): BundleMembership[] => [])
	};
};
