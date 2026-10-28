import { getTermLists } from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch }) => ({ lists: getTermLists(true, { fetch }) });
