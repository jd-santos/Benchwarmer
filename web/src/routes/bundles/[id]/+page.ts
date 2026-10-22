import { getBundle, getRun } from '$lib/api/client';
import type { PageLoad } from './$types';

export const load: PageLoad = ({ fetch, params, url }) => {
	const requested = Number.parseInt(url.searchParams.get('revision') ?? '', 10);
	const revision = Number.isInteger(requested) && requested > 0 ? requested : null;
	const bundle = getBundle(params.id, revision, { fetch });
	return {
		revision,
		bundle,
		// The run's usage is context beside a proposal; a missing record must not hide the bundle.
		run: bundle.then(
			(detail) =>
				detail.provenance ? getRun(detail.provenance.run_id, { fetch }).catch(() => null) : null,
			() => null
		)
	};
};
