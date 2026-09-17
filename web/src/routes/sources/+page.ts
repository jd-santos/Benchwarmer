import { getSources } from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch }) => ({ sources: getSources({ fetch }) });
