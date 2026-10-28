import type {
	CriterionNeed,
	CriterionMethod,
	JudgeEvidence,
	Partition,
	ReconstructionLevel,
	ReviewerLabel,
	TaskKind,
	TaskStatus,
	UnmetNeed
} from '$lib/api/types';

export const kindOptions: { value: TaskKind; label: string; hint: string }[] = [
	{ value: 'chat', label: 'Chat', hint: 'A text reply with no tools' },
	{ value: 'agent', label: 'Agent', hint: 'Tool calls against a service or data' },
	{ value: 'coding', label: 'Coding', hint: 'Changes to files in a workspace' }
];

export const statusOptions: { value: TaskStatus; label: string; hint: string }[] = [
	{ value: 'draft', label: 'Draft', hint: 'Editable. Not exportable.' },
	{
		value: 'approved',
		label: 'Approved',
		hint: 'Exportable and runnable. Content is frozen; an edit starts a new draft version.'
	},
	{ value: 'retired', label: 'Retired', hint: 'Kept for old results, never run again. Final.' }
];

export const methodOptions: { value: CriterionMethod; label: string; hint: string }[] = [
	{
		value: 'human',
		label: 'Human',
		hint: 'A person judges it; your label becomes calibration data'
	},
	{
		value: 'llm_judge',
		label: 'Model judge',
		hint: 'A judge model scores it from the evidence named below'
	},
	{
		value: 'deterministic',
		label: 'Deterministic',
		hint: 'A check in the runner, with no judge evidence'
	}
];

export const judgeEvidenceOptions: { value: JudgeEvidence; label: string }[] = [
	{ value: 'judge.historical', label: 'Historical answer' },
	{ value: 'judge.feedback', label: 'User feedback' },
	{ value: 'judge.reviewer_notes', label: 'Reviewer notes' }
];

export const reviewerLabelOptions: { value: ReviewerLabel; label: string }[] = [
	{ value: 'pass', label: 'Pass' },
	{ value: 'fail', label: 'Fail' },
	{ value: 'unsure', label: 'Unsure' }
];

export const reconstructionOptions: {
	value: ReconstructionLevel;
	label: string;
	hint: string;
}[] = [
	{
		value: 'prompt_only',
		label: 'Prompt and context',
		hint: 'The candidate gets the transcript to the cut point and nothing else'
	},
	{
		value: 'fixture_backed',
		label: 'Fixture-backed',
		hint: 'A known starting workspace and tools are prepared'
	},
	{
		value: 'fixed_multi_turn',
		label: 'Fixed multi-turn',
		hint: 'Later user messages are replayed when they still apply'
	}
];

export const partitionOptions: { value: Partition; label: string; hint: string }[] = [
	{ value: 'development', label: 'Development', hint: 'May guide prompts and judges' },
	{ value: 'calibration', label: 'Calibration', hint: 'May guide rubrics and judge settings' },
	{ value: 'holdout', label: 'Holdout', hint: 'Results must not guide changes' }
];

/** The default split the API applies; mirrors `services.task_partitions.DEFAULT_SPLIT`. */
export const defaultSplit: Record<Partition, number> = {
	development: 0.6,
	calibration: 0.2,
	holdout: 0.2
};

export const needOptions: { value: CriterionNeed; label: string; hint: string }[] = [
	{ value: 'workspace', label: 'Workspace', hint: 'Files the candidate can read or change' },
	{ value: 'tools', label: 'Live tools', hint: 'Tool calls that run, not transcript text' },
	{ value: 'multi_turn', label: 'Later turns', hint: 'Replayed user messages after the cut' }
];

/** What each reconstruction level provides; mirrors `benchwarmer.tasks.SATISFIED_NEEDS`. */
export const satisfiedNeeds: Record<ReconstructionLevel, readonly CriterionNeed[]> = {
	prompt_only: [],
	fixture_backed: ['workspace', 'tools'],
	fixed_multi_turn: ['workspace', 'tools', 'multi_turn']
};

/**
 * Needs the reconstruction level cannot satisfy, as the API computes them. A coding
 * task needs a workspace whatever its criteria say; that entry has no criterion id.
 */
export function unmetNeeds(
	kind: TaskKind,
	level: ReconstructionLevel,
	criteria: { id: string; needs?: CriterionNeed[] }[]
): UnmetNeed[] {
	const satisfied = satisfiedNeeds[level];
	const unmet: UnmetNeed[] = [];
	if (kind === 'coding' && !satisfied.includes('workspace')) {
		unmet.push({ criterion_id: null, needs: ['workspace'] });
	}
	for (const criterion of criteria) {
		const missing = (criterion.needs ?? []).filter((need) => !satisfied.includes(need));
		if (missing.length > 0) unmet.push({ criterion_id: criterion.id, needs: missing });
	}
	return unmet;
}

export function needLabel(need: CriterionNeed): string {
	return needOptions.find((option) => option.value === need)?.label ?? need;
}

export function needsSentence(needs: CriterionNeed[]): string {
	return needs.map((need) => needLabel(need).toLowerCase()).join(', ');
}

export function partitionLabel(partition: Partition): string {
	return partitionOptions.find((option) => option.value === partition)?.label ?? partition;
}

export function reconstructionLabel(level: ReconstructionLevel): string {
	return reconstructionOptions.find((option) => option.value === level)?.label ?? level;
}

export function statusLabel(status: TaskStatus): string {
	return statusOptions.find((option) => option.value === status)?.label ?? status;
}

export function kindLabel(kind: TaskKind): string {
	return kindOptions.find((option) => option.value === kind)?.label ?? kind;
}

export function methodLabel(method: CriterionMethod): string {
	return methodOptions.find((option) => option.value === method)?.label ?? method;
}

export function taskLabel(task: { summary: string; objective: string }): string {
	return task.summary.trim() || task.objective.trim() || 'Untitled task';
}

/** A criterion id from its statement: lowercase words joined by hyphens, at most 63 characters. */
export function slugFor(statement: string, taken: ReadonlySet<string>): string {
	const base =
		statement
			.toLowerCase()
			.replace(/[^a-z0-9]+/g, '-')
			.replace(/^-+|-+$/g, '')
			.split('-')
			.slice(0, 5)
			.join('-')
			.slice(0, 55) || 'criterion';
	let slug = base;
	for (let n = 2; taken.has(slug); n += 1) slug = `${base}-${n}`;
	return slug;
}

/** Download `text` as a file; inert where the page cannot start downloads. */
export function downloadJson(name: string, text: string): void {
	const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
	const anchor = document.createElement('a');
	anchor.href = url;
	anchor.download = name;
	anchor.click();
	URL.revokeObjectURL(url);
}
