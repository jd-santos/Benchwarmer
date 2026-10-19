import { getBundles } from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch }) => ({
	bundles: getBundles(null, { fetch })
});
