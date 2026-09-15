export type CoverageValue = 'available' | 'partial' | 'unavailable' | 'unknown';

export interface HealthResponse {
	status: 'ok';
	alembic_revision: string | null;
	data_root_writable: boolean;
}

export interface SourceCoverage {
	sessions: CoverageValue;
	token_usage: CoverageValue;
	request_ids: CoverageValue;
	actual_charges: CoverageValue;
	list_price_estimates: CoverageValue;
	subscription_expense: CoverageValue;
	quota: CoverageValue;
	credits: CoverageValue;
	prompts: CoverageValue;
	classifications: CoverageValue;
}

export interface SourceStatus {
	id: string;
	kind: string;
	display_name: string;
	last_successful_import_at: string | null;
	coverage: SourceCoverage;
}

export interface SourcesResponse {
	items: SourceStatus[];
}
