<script lang="ts">
	import { goto, invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import type { ResolvedPathname } from '$app/types';
	import { ApiClientError, createTask, exportTask, updateTask } from '$lib/api/client';
	import type {
		CaseRecord,
		Criterion,
		CriterionMethod,
		CriterionNeed,
		JudgeEvidence,
		LeakageFlag,
		ObjectiveType,
		ReconstructionLevel,
		ReviewerLabel,
		SplitEvent,
		TaskDetail,
		TaskDocument,
		TaskDraft,
		TaskKind,
		TaskStatus
	} from '$lib/api/types';
	import { objectiveTypeLabel, objectiveTypeOptions } from '$lib/bundles/format';
	import {
		eventRole,
		formatTime,
		formatTimestamp,
		plural,
		roleLabel
	} from '$lib/conversations/format';
	import {
		downloadJson,
		judgeEvidenceOptions,
		kindLabel,
		kindOptions,
		methodOptions,
		needOptions,
		needsSentence,
		partitionLabel,
		partitionOptions,
		reconstructionLabel,
		reconstructionOptions,
		reviewerLabelOptions,
		slugFor,
		statusLabel,
		statusOptions,
		taskLabel,
		unmetNeeds
	} from '$lib/tasks/format';
	import RoleGlyph from './RoleGlyph.svelte';

	let {
		detail = null,
		draft: proposed = null
	}: {
		/** An existing task; the editor saves new versions of it. */
		detail?: TaskDetail | null;
		/** A proposed task for a bundle; the editor creates it on first save. */
		draft?: TaskDraft | null;
	} = $props();

	let saved = $state<TaskDetail | null>(null);
	const current = $derived(saved ?? detail);
	const base = $derived<TaskDraft | TaskDetail>(current ?? (proposed as TaskDraft));
	const source = $derived(base.document);
	const readOnly = $derived(current !== null && current.version !== current.latest_version);
	const latestStatus = $derived(current?.document.status ?? 'draft');

	let kind = $derived<TaskKind>(source.kind);
	let summary = $derived(source.summary);
	let objective = $derived(source.objective);
	let objectiveType = $derived<ObjectiveType>(source.objective_type);
	let family = $derived(source.family);
	let cutEventId = $derived(source.cut_point.event_id);
	let level = $derived<ReconstructionLevel>(source.reconstruction.level);
	let gaps = $derived(source.reconstruction.gaps.join('\n'));
	let criteria = $derived<Criterion[]>(
		source.criteria.map((criterion) => ({ ...criterion, needs: criterion.needs ?? [] }))
	);
	let status = $derived<TaskStatus>(source.status);
	let reviewerNotes = $derived(source.reviewer_notes);
	let reviewBy = $derived(source.leakage_review?.by ?? '');
	let reviewNotes = $derived(source.leakage_review?.notes ?? '');
	let accepted = $derived<string[]>([...(source.leakage_review?.accepted_flags ?? [])]);

	let saving = $state(false);
	let messages = $state<string[]>([]);
	let criterionIssues = $state<Record<string, string>>({});
	let conflict = $state<number | null>(null);
	let confirmation = $state('');

	// The conversation path in order; the cut moves along it without a round trip.
	const path = $derived<SplitEvent[]>([...base.split.candidate, ...base.split.judge]);
	const cutIndex = $derived(path.findIndex((event) => event.event_id === cutEventId));
	const candidate = $derived(cutIndex === -1 ? base.split.candidate : path.slice(0, cutIndex + 1));
	const judge = $derived(cutIndex === -1 ? base.split.judge : path.slice(cutIndex + 1));
	const cutMoved = $derived(cutEventId !== source.cut_point.event_id);
	const flags = $derived<LeakageFlag[]>(base.flags);
	const unaccepted = $derived(flags.filter((flag) => !accepted.includes(flag.id)));
	const flagsFor = (criterionId: string) =>
		flags.filter((flag) => flag.criterion_id === criterionId);

	const document_ = $derived<Omit<TaskDocument, 'leakage_review'>>({
		bundle_id: source.bundle_id,
		bundle_revision: source.bundle_revision,
		kind,
		summary: summary.trim(),
		objective: objective.trim(),
		objective_type: objectiveType,
		family: family.trim(),
		cut_point: { ...source.cut_point, event_id: cutEventId },
		reconstruction: {
			level,
			gaps: gaps
				.split('\n')
				.map((line) => line.trim())
				.filter(Boolean)
		},
		criteria: criteria.map((criterion) => ({
			id: criterion.id.trim(),
			statement: criterion.statement.trim(),
			method: criterion.method,
			rubric_version: criterion.rubric_version,
			judge_evidence: criterion.method === 'deterministic' ? [] : criterion.judge_evidence,
			needs: criterion.needs ?? [],
			reviewer_label: criterion.method === 'human' ? criterion.reviewer_label : null,
			note: criterion.note?.trim() || null
		})),
		expected_scope: kind === 'coding' ? source.expected_scope : null,
		// Legacy field, kept as saved. The partition is assigned by family at the task level.
		partition: source.partition ?? null,
		status,
		reviewer_notes: reviewerNotes.trim()
	});
	// Needs the reconstruction level cannot meet; mirrors the API's approval guard.
	const unmet = $derived(unmetNeeds(kind, level, document_.criteria));
	const unmetFor = (criterionId: string) =>
		unmet.find((item) => item.criterion_id === criterionId) ?? null;
	const kindUnmet = $derived(unmet.find((item) => item.criterion_id === null) ?? null);
	const analysisOnly = $derived(unmet.length > 0);
	const assignedPartition = $derived(current?.partition ?? null);
	const reviewTouched = $derived(
		reviewBy.trim() !== (source.leakage_review?.by ?? '') ||
			reviewNotes.trim() !== (source.leakage_review?.notes ?? '') ||
			JSON.stringify([...accepted].sort()) !==
				JSON.stringify([...(source.leakage_review?.accepted_flags ?? [])].sort())
	);
	const dirty = $derived(
		current === null ||
			reviewTouched ||
			JSON.stringify(document_) !== JSON.stringify(withoutReview(source))
	);

	const needsObjective = $derived(status === 'approved' && document_.objective === '');
	const needsCriteria = $derived(status === 'approved' && document_.criteria.length === 0);
	const needsReviewer = $derived(status === 'approved' && reviewBy.trim() === '');
	const needsFlags = $derived(status === 'approved' && (unaccepted.length > 0 || cutMoved));
	const needsBundleReview = $derived(status === 'approved' && base.bundle.status !== 'reviewed');
	const needsReconstruction = $derived(status === 'approved' && analysisOnly);
	const emptyCriterion = $derived(
		document_.criteria.some((criterion) => !criterion.statement || !criterion.id)
	);
	const blocked = $derived(
		needsObjective ||
			needsCriteria ||
			needsReviewer ||
			needsFlags ||
			needsBundleReview ||
			needsReconstruction ||
			emptyCriterion ||
			cutIndex === -1 ||
			(latestStatus === 'retired' && current !== null)
	);
	const bundleHasNewer = $derived(
		current !== null && current.bundle_latest_revision > source.bundle_revision
	);

	function withoutReview(document: TaskDocument): Omit<TaskDocument, 'leakage_review'> {
		return {
			bundle_id: document.bundle_id,
			bundle_revision: document.bundle_revision,
			kind: document.kind,
			summary: document.summary,
			objective: document.objective,
			objective_type: document.objective_type,
			family: document.family,
			cut_point: document.cut_point,
			reconstruction: document.reconstruction,
			criteria: document.criteria.map((criterion) => ({
				...criterion,
				needs: criterion.needs ?? []
			})),
			expected_scope: document.expected_scope ?? null,
			partition: document.partition ?? null,
			status: document.status,
			reviewer_notes: document.reviewer_notes
		};
	}

	function fullDocument(): TaskDocument {
		const by = reviewBy.trim();
		const previous = source.leakage_review;
		const review =
			by === '' && accepted.length === 0 && reviewNotes.trim() === ''
				? null
				: {
						by: by || previous?.by || 'reviewer',
						at: previous && !reviewTouched ? previous.at : new Date().toISOString(),
						accepted_flags: [...accepted],
						notes: reviewNotes.trim() || null
					};
		return { ...document_, leakage_review: review };
	}

	function editCriterion(index: number, change: Partial<Criterion>): void {
		criteria = criteria.map((criterion, position) =>
			position === index ? { ...criterion, ...change } : criterion
		);
	}

	function addCriterion(): void {
		criteria = [
			...criteria,
			{
				id: slugFor('criterion', new Set(criteria.map((criterion) => criterion.id))),
				statement: '',
				method: 'human',
				rubric_version: 1,
				judge_evidence: [],
				needs: [],
				reviewer_label: null,
				note: null
			}
		];
	}

	function toggleNeed(index: number, value: CriterionNeed, on: boolean): void {
		const existing = criteria[index].needs ?? [];
		editCriterion(index, {
			needs: on
				? [...existing.filter((item) => item !== value), value]
				: existing.filter((item) => item !== value)
		});
	}

	/** Derive the id from the statement until the reviewer edits the id by hand. */
	function statementChanged(index: number, statement: string): void {
		const criterion = criteria[index];
		const others = new Set(criteria.filter((_, i) => i !== index).map((c) => c.id));
		const auto = criterion.id === slugFor(criterion.statement, others) || criterion.id === '';
		editCriterion(index, {
			statement,
			...(auto ? { id: slugFor(statement, others) } : {})
		});
	}

	function toggleEvidence(index: number, value: JudgeEvidence, on: boolean): void {
		const existing = criteria[index].judge_evidence;
		editCriterion(index, {
			judge_evidence: on
				? [...existing.filter((item) => item !== value), value]
				: existing.filter((item) => item !== value)
		});
	}

	function toggleFlag(id: string, on: boolean): void {
		accepted = on
			? [...accepted.filter((item) => item !== id), id]
			: accepted.filter((item) => item !== id);
	}

	function sourceHref(eventId: string): ResolvedPathname {
		const base_ = resolve('/conversations/[id]', { id: base.split.conversation_id });
		return `${base_}#${encodeURIComponent(eventId)}` as ResolvedPathname;
	}

	function bundleHref(): ResolvedPathname {
		const base_ = resolve('/bundles/[id]', { id: source.bundle_id });
		return (
			current !== null && current.bundle_latest_revision !== source.bundle_revision
				? `${base_}?revision=${source.bundle_revision}`
				: base_
		) as ResolvedPathname;
	}

	function versionHref(number: number | null): ResolvedPathname {
		const base_ = resolve('/tasks/[id]', { id: (current as TaskDetail).id });
		return (number === null ? base_ : `${base_}?version=${number}`) as ResolvedPathname;
	}

	async function save(): Promise<void> {
		if (saving || !dirty || blocked) return;
		saving = true;
		messages = [];
		criterionIssues = {};
		conflict = null;
		confirmation = '';
		try {
			const document = fullDocument();
			if (current === null) {
				const created = await createTask(document);
				await goto(resolve('/tasks/[id]', { id: created.id }));
				return;
			}
			const before = current.version;
			saved = await updateTask(current.id, document, before);
			accepted = [...(saved.document.leakage_review?.accepted_flags ?? [])];
			confirmation =
				saved.version === before ? 'No changes to save.' : `Saved version ${saved.version}.`;
		} catch (failure) {
			if (failure instanceof ApiClientError && failure.status === 409) {
				const body = failure.body as { latest_version?: unknown } | undefined;
				conflict = typeof body?.latest_version === 'number' ? body.latest_version : 0;
			} else if (failure instanceof ApiClientError && failure.taskIssues.length > 0) {
				for (const issue of failure.taskIssues) {
					if (issue.criterion_id) criterionIssues[issue.criterion_id] = issue.message;
					else messages = [...messages, issue.message];
				}
			} else {
				messages = ['The task could not be saved. Your edits are still here; try again.'];
			}
		} finally {
			saving = false;
		}
	}

	// Export: only an approved version, only the one on screen.
	let terms = $state('');
	let exporting = $state(false);
	let exported = $state<CaseRecord | null>(null);
	let exportError = $state('');
	const exportable = $derived(current !== null && current.document.status === 'approved' && !dirty);
	const exportText = $derived(exported === null ? '' : JSON.stringify(exported, null, 2));

	async function runExport(): Promise<void> {
		if (current === null || exporting) return;
		exporting = true;
		exportError = '';
		exported = null;
		try {
			exported = await exportTask(
				current.id,
				current.version,
				terms
					.split('\n')
					.map((line) => line.trim())
					.filter(Boolean)
			);
		} catch {
			exportError = 'The export failed. Check that the version is approved and try again.';
		} finally {
			exporting = false;
		}
	}
</script>

<div class="task-editor">
	<header class="task-editor__header">
		<h1 class:untitled={!summary.trim() && !objective.trim()}>{taskLabel(document_)}</h1>
		<p class="meta-line">
			<span class="task-status task-status--{status}">{statusLabel(status)}</span>
			{#if analysisOnly}
				<span
					class="task-analysis-only"
					title="Its criteria need more than the reconstruction provides">Analysis only</span
				>
			{/if}
			<span>{kindLabel(kind)}</span>
			{#if assignedPartition}
				<span>{partitionLabel(assignedPartition)} partition</span>
			{/if}
			{#if objectiveType !== 'unknown'}<span>{objectiveTypeLabel(objectiveType)}</span>{/if}
			<span>
				From <a href={bundleHref()}>bundle revision {source.bundle_revision}</a>
			</span>
			{#if current !== null && current.latest_version > 1}
				<span>Version {current.version} of {current.latest_version}</span>
			{/if}
		</p>
		{#if current === null}
			<p class="notice" role="status">
				A proposed task for this bundle. Set the cut point, write criteria, then save to create it.
			</p>
		{:else if readOnly}
			<p class="notice" role="status">
				Viewing an earlier version. <a href={versionHref(null)}>View latest</a>
			</p>
		{:else if latestStatus === 'retired'}
			<p class="notice" role="status">
				This task is retired; it stays for old results and cannot change.
			</p>
		{:else if bundleHasNewer}
			<p class="notice" role="status">
				The bundle has a newer revision ({current.bundle_latest_revision}). This task keeps citing
				revision {source.bundle_revision}; prepare a new task to use the newer one.
			</p>
		{/if}
	</header>

	<form
		class="task-layout"
		onsubmit={(event) => {
			event.preventDefault();
			void save();
		}}
	>
		<section class="task-split" aria-labelledby="task-split-heading">
			<h2 id="task-split-heading">Cut point</h2>
			<p class="field__hint">
				Pick the last turn the candidate sees. Everything after it is evidence for the judge only.
				{#if base.split.conversation_title}
					From <a href={sourceHref(cutEventId)}>{base.split.conversation_title}</a>.
				{/if}
			</p>
			<fieldset class="split-columns" disabled={readOnly}>
				<legend class="visually-hidden">Turns on the conversation path</legend>
				<div class="split-column split-column--candidate">
					<h3>Candidate sees <span class="muted">({plural(candidate.length, 'turn')})</span></h3>
					<ol class="split-list">
						{#each candidate as event, index (event.event_id)}
							{@render turn(event, index === candidate.length - 1)}
						{/each}
					</ol>
				</div>
				<div class="split-column split-column--judge">
					<h3>Judge only <span class="muted">({plural(judge.length, 'turn')})</span></h3>
					{#if judge.length === 0}
						<p class="field__error">
							Nothing follows the cut, so the judge has no historical answer.
						</p>
					{/if}
					<ol class="split-list">
						{#each judge as event (event.event_id)}
							{@render turn(event, false)}
						{/each}
						{#each base.split.other_judge as event (event.event_id)}
							<li class="split-turn split-turn--other">
								<span class="split-turn__who">
									<RoleGlyph role={eventRole(event.role)} />
									{roleLabel(eventRole(event.role))}
								</span>
								<span class="muted">another conversation</span>
								{#if event.preview}<span class="split-turn__preview">{event.preview}</span>{/if}
							</li>
						{/each}
					</ol>
				</div>
			</fieldset>
		</section>

		<fieldset class="task-summary" disabled={readOnly}>
			<legend class="visually-hidden">About the task</legend>
			<div class="field">
				<label for="task-summary">Summary</label>
				<textarea id="task-summary" rows="2" maxlength="4000" bind:value={summary}></textarea>
			</div>
			<div class="field">
				<label for="task-objective">Objective</label>
				<textarea
					id="task-objective"
					rows="2"
					maxlength="4000"
					bind:value={objective}
					aria-invalid={needsObjective}
					aria-describedby={needsObjective ? 'task-objective-error' : undefined}></textarea>
				{#if needsObjective}
					<p id="task-objective-error" class="field__error">An approved task needs an objective.</p>
				{/if}
			</div>
			<div class="field">
				<label for="task-objective-type">Type of work</label>
				<select id="task-objective-type" bind:value={objectiveType}>
					{#each objectiveTypeOptions as option (option.value)}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
			</div>
			<fieldset class="field">
				<legend>Kind</legend>
				<div class="segmented">
					{#each kindOptions as option (option.value)}
						<label>
							<input type="radio" name="kind" value={option.value} bind:group={kind} />
							<span>{option.label}</span>
						</label>
					{/each}
				</div>
				<p class="field__hint">{kindOptions.find((option) => option.value === kind)?.hint}</p>
			</fieldset>
			<div class="field">
				<label for="task-family">Family</label>
				<input id="task-family" type="text" maxlength="255" bind:value={family} />
				<p class="field__hint">
					Shared by every task from the same conversation, its branches, and continuations.
					Partitions are assigned by family.
				</p>
			</div>
			<div class="field">
				<label for="task-reconstruction">Reconstruction</label>
				<select id="task-reconstruction" bind:value={level}>
					{#each reconstructionOptions as option (option.value)}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
				<p class="field__hint">
					{reconstructionOptions.find((option) => option.value === level)?.hint}
				</p>
				{#if kindUnmet}
					<p class="field__error" data-kind-unmet>
						A coding task needs a workspace, which "{reconstructionLabel(level)}" does not provide.
						It stays analysis-only evidence until a fixture backs it.
					</p>
				{:else if analysisOnly}
					<p class="field__hint" data-analysis-only>
						Analysis only at this level: {plural(unmet.length, 'criterion', 'criteria')} below
						{unmet.length === 1 ? 'needs' : 'need'} more than it provides.
					</p>
				{/if}
			</div>
			<div class="field">
				<label for="task-gaps">Reconstruction gaps</label>
				<textarea
					id="task-gaps"
					rows="3"
					placeholder="One per line: truncated tool results, missing files, tools no longer available"
					bind:value={gaps}></textarea>
			</div>
			<div class="field">
				<span class="field__label" id="task-partition-label">Partition</span>
				<p class="field__value" aria-labelledby="task-partition-label" data-partition>
					{#if assignedPartition}
						{partitionLabel(assignedPartition)}
						<span class="muted">
							· {partitionOptions.find((option) => option.value === assignedPartition)?.hint}
						</span>
					{:else}
						<span class="muted">Not assigned</span>
					{/if}
				</p>
				<p class="field__hint">
					Assigned by family from the <a href={resolve('/tasks')}>Tasks list</a>, never per task;
					every task in a family lands on the same side.
				</p>
			</div>
		</fieldset>

		<section class="task-criteria" aria-labelledby="task-criteria-heading">
			<h2 id="task-criteria-heading">Criteria</h2>
			<p class="field__hint">
				Describe acceptable behavior. Quoting the historical answer is flagged; the answer is one
				acceptable result, not the required one.
			</p>
			{#if needsCriteria}
				<p class="field__error">An approved task needs at least one criterion.</p>
			{/if}
			<ol class="criteria-list">
				{#each criteria as criterion, index (index)}
					{@const issue = criterionIssues[criterion.id]}
					{@const flagged = flagsFor(criterion.id)}
					{@const missing = unmetFor(criterion.id)}
					<li
						class="criterion"
						class:criterion--invalid={issue ||
							flagged.length > 0 ||
							(missing && status === 'approved')}
					>
						<div class="field">
							<label for="criterion-{index}-statement">Statement {index + 1}</label>
							<textarea
								id="criterion-{index}-statement"
								rows="2"
								maxlength="2000"
								disabled={readOnly}
								value={criterion.statement}
								oninput={(event) => statementChanged(index, event.currentTarget.value)}></textarea>
						</div>
						<div class="criterion__row">
							<label class="field criterion__method">
								<span>Method</span>
								<select
									disabled={readOnly}
									value={criterion.method}
									onchange={(event) =>
										editCriterion(index, {
											method: event.currentTarget.value as CriterionMethod,
											reviewer_label: null
										})}
								>
									{#each methodOptions as option (option.value)}
										<option value={option.value}>{option.label}</option>
									{/each}
								</select>
							</label>
							<label class="field criterion__id">
								<span>Id</span>
								<input
									type="text"
									pattern="[a-z0-9][a-z0-9-]*"
									maxlength="63"
									disabled={readOnly}
									value={criterion.id}
									oninput={(event) => editCriterion(index, { id: event.currentTarget.value })}
								/>
							</label>
							<label class="field criterion__version">
								<span>Rubric v.</span>
								<input
									type="number"
									min="1"
									step="1"
									disabled={readOnly}
									value={criterion.rubric_version}
									oninput={(event) =>
										editCriterion(index, {
											rubric_version: Math.max(1, Number(event.currentTarget.value) || 1)
										})}
								/>
							</label>
							{#if !readOnly}
								<button
									class="tool-button tool-button--danger criterion__remove"
									type="button"
									aria-label="Remove criterion {index + 1}"
									title="Remove"
									onclick={() => (criteria = criteria.filter((_, i) => i !== index))}>×</button
								>
							{/if}
						</div>
						<p class="field__hint">
							{methodOptions.find((option) => option.value === criterion.method)?.hint}
						</p>
						{#if criterion.method !== 'deterministic'}
							<fieldset class="field criterion__evidence">
								<legend>Judge may read</legend>
								<div class="check-row">
									{#each judgeEvidenceOptions as option (option.value)}
										<label>
											<input
												type="checkbox"
												disabled={readOnly}
												checked={criterion.judge_evidence.includes(option.value)}
												onchange={(event) =>
													toggleEvidence(index, option.value, event.currentTarget.checked)}
											/>
											{option.label}
										</label>
									{/each}
								</div>
							</fieldset>
						{/if}
						<fieldset class="field criterion__needs">
							<legend>Needs from the run</legend>
							<div class="check-row">
								{#each needOptions as option (option.value)}
									<label title={option.hint}>
										<input
											type="checkbox"
											disabled={readOnly}
											checked={(criterion.needs ?? []).includes(option.value)}
											onchange={(event) =>
												toggleNeed(index, option.value, event.currentTarget.checked)}
										/>
										{option.label}
									</label>
								{/each}
							</div>
							{#if missing}
								<p
									class={status === 'approved' ? 'field__error' : 'field__hint'}
									data-criterion-unmet
								>
									Needs {needsSentence(missing.needs)}, which "{reconstructionLabel(level)}" cannot
									provide. {status === 'approved'
										? 'Change the reconstruction or keep the task as analysis-only evidence.'
										: 'Analysis-only at this reconstruction level.'}
								</p>
							{/if}
						</fieldset>
						{#if criterion.method === 'human'}
							<fieldset class="field">
								<legend>Your verdict on the historical answer</legend>
								<div class="segmented segmented--compact">
									{#each reviewerLabelOptions as option (option.value)}
										<label>
											<input
												type="radio"
												name="criterion-{index}-label"
												value={option.value}
												disabled={readOnly}
												checked={criterion.reviewer_label === option.value}
												onchange={() =>
													editCriterion(index, {
														reviewer_label: option.value as ReviewerLabel
													})}
											/>
											<span>{option.label}</span>
										</label>
									{/each}
								</div>
							</fieldset>
						{/if}
						{#each flagged as flag (flag.id)}
							<p class="field__error">{flag.message}</p>
						{/each}
						{#if issue}<p class="field__error">{issue}</p>{/if}
					</li>
				{/each}
			</ol>
			{#if !readOnly}
				<button class="button" type="button" onclick={addCriterion}>Add criterion</button>
			{/if}
		</section>

		<fieldset class="task-review" disabled={readOnly}>
			<legend class="visually-hidden">Review and status</legend>
			<section class="leakage" aria-labelledby="task-leakage-heading">
				<h2 id="task-leakage-heading">Leakage check</h2>
				{#if cutMoved}
					<p class="field__hint">
						The cut point moved. Save to refresh the flags before approving.
					</p>
				{:else if flags.length === 0}
					<p class="field__hint" data-no-flags>
						No automatic flags. Still read the candidate turns for anything written after the cut.
					</p>
				{/if}
				{#if flags.length > 0}
					<ul class="flag-list">
						{#each flags as flag (flag.id)}
							<li class="flag" class:flag--open={!accepted.includes(flag.id)}>
								<label>
									<input
										type="checkbox"
										checked={accepted.includes(flag.id)}
										onchange={(event) => toggleFlag(flag.id, event.currentTarget.checked)}
									/>
									<span class="flag__text">
										{flag.message}
										{#if flag.event_id}
											<a href={sourceHref(flag.event_id)}>View turn</a>
										{/if}
										<span class="flag__accept">Checked, not a leak</span>
									</span>
								</label>
							</li>
						{/each}
					</ul>
				{/if}
				<div class="field">
					<label for="task-review-by">Reviewed by</label>
					<input
						id="task-review-by"
						type="text"
						maxlength="255"
						placeholder="Your name or handle"
						bind:value={reviewBy}
						aria-invalid={needsReviewer}
						aria-describedby={needsReviewer ? 'task-review-by-error' : undefined}
					/>
					{#if needsReviewer}
						<p id="task-review-by-error" class="field__error">
							Approval records who checked the candidate section for leaks.
						</p>
					{/if}
				</div>
				<div class="field">
					<label for="task-review-notes">Leakage notes</label>
					<textarea id="task-review-notes" rows="2" maxlength="4000" bind:value={reviewNotes}
					></textarea>
				</div>
			</section>

			<div class="field">
				<label for="task-reviewer-notes">Notes for the judge</label>
				<textarea
					id="task-reviewer-notes"
					rows="3"
					maxlength="4000"
					placeholder="Context for whoever grades this task; exported in the judge section"
					bind:value={reviewerNotes}></textarea>
			</div>

			<fieldset class="field">
				<legend>Status</legend>
				<div class="segmented">
					{#each statusOptions as option (option.value)}
						<label>
							<input type="radio" name="status" value={option.value} bind:group={status} />
							<span>{option.label}</span>
						</label>
					{/each}
				</div>
				<p class="field__hint">{statusOptions.find((option) => option.value === status)?.hint}</p>
				{#if needsBundleReview}
					<p class="field__error">
						Only a task from a reviewed bundle can be approved; this bundle revision is
						{base.bundle.status}.
					</p>
				{/if}
				{#if needsFlags && !cutMoved}
					<p class="field__error">
						{plural(unaccepted.length, 'leakage flag')} still open. Check each one above or move the cut.
					</p>
				{/if}
				{#if needsReconstruction}
					<p class="field__error" data-approval-unmet>
						Cannot approve as a runnable test: {kindUnmet
							? 'a coding task needs a workspace'
							: `${plural(unmet.length, 'criterion', 'criteria')} ${unmet.length === 1 ? 'needs' : 'need'} ${needsSentence([...new Set(unmet.flatMap((item) => item.needs))])}`},
						which "{reconstructionLabel(level)}" does not provide. Keep it as a draft for
						analysis-only evidence, or prepare a fixture and raise the reconstruction level.
					</p>
				{/if}
			</fieldset>
		</fieldset>

		{#if !readOnly && latestStatus !== 'retired'}
			<div class="save-bar" class:save-bar--dirty={dirty}>
				<p class="save-bar__status" aria-live="polite">
					{#if current === null}New task{:else if dirty}Unsaved changes{:else if confirmation}{confirmation}{:else}No
						changes{/if}
				</p>
				<button class="button button--primary" type="submit" disabled={!dirty || saving || blocked}>
					{saving ? 'Saving…' : current === null ? 'Create task' : 'Save version'}
				</button>
				{#if conflict !== null}
					<div class="notice save-bar__message" role="alert">
						This task was changed elsewhere{conflict ? ` (now version ${conflict})` : ''}. Your
						edits are still here.
						<button class="text-button" type="button" onclick={() => void invalidateAll()}>
							Load the latest and discard my edits
						</button>
					</div>
				{/if}
				{#if messages.length > 0}
					<ul class="field__error save-bar__message" role="alert">
						{#each messages as message, index (index)}<li>{message}</li>{/each}
					</ul>
				{/if}
			</div>
		{/if}
	</form>

	{#if current !== null && current.document.status === 'approved'}
		<section class="task-export" aria-labelledby="task-export-heading">
			<h2 id="task-export-heading">Export case record</h2>
			<p class="field__hint">
				Writes version {current.version} as one JSON document with a candidate section cut at the cut
				point and a judge section with the historical turns. Both are scrubbed with the terms below plus
				the built-in kinds; the record carries counts, never the originals.
			</p>
			<div class="field">
				<label for="task-export-terms">Terms to scrub</label>
				<textarea
					id="task-export-terms"
					rows="3"
					placeholder="One per line: names, customers, hosts, project codenames"
					bind:value={terms}></textarea>
			</div>
			<div class="task-export__actions">
				<button
					class="button"
					type="button"
					disabled={!exportable || exporting}
					onclick={() => void runExport()}
				>
					{exporting ? 'Exporting…' : 'Export case record'}
				</button>
				{#if dirty}<span class="field__hint">Save or discard your edits first.</span>{/if}
				{#if exportError}<span class="field__error" role="alert">{exportError}</span>{/if}
			</div>
			{#if exported}
				<div class="task-export__result" data-export-result>
					<p class="meta-line">
						<span>Digest <code>{exported.digest.slice(0, 12)}</code></span>
						<span>
							{#if Object.keys(exported.case.redaction.manifest).length === 0}
								Nothing scrubbed
							{:else}
								Scrubbed {Object.entries(exported.case.redaction.manifest)
									.map(([kind, count]) => `${count} ${kind}`)
									.join(', ')}
							{/if}
						</span>
					</p>
					<div class="task-export__actions">
						<button
							class="button"
							type="button"
							onclick={() =>
								downloadJson(`${current.id}-v${current.version}.case.json`, exportText)}
						>
							Download JSON
						</button>
						<button
							class="text-button"
							type="button"
							onclick={() => void navigator.clipboard?.writeText(exportText)}
						>
							Copy JSON
						</button>
					</div>
					<details class="task-export__json">
						<summary>Show the record</summary>
						<pre><code>{exportText}</code></pre>
					</details>
				</div>
			{/if}
		</section>
	{/if}

	{#if current !== null && current.versions.length > 1}
		<details class="revisions">
			<summary>{plural(current.versions.length, 'version')}</summary>
			<ol>
				{#each current.versions as version (version.number)}
					<li>
						{#if version.number === current.version}
							<span aria-current="true">Version {version.number} (shown)</span>
						{:else}
							<a
								href={versionHref(
									version.number === current.latest_version ? null : version.number
								)}
							>
								Version {version.number}
							</a>
						{/if}
						· {statusLabel(version.status)} · {formatTimestamp(version.created_at)}
					</li>
				{/each}
			</ol>
		</details>
	{/if}
</div>

{#snippet turn(event: SplitEvent, isCut: boolean)}
	<li class="split-turn split-turn--{eventRole(event.role)}" class:split-turn--cut={isCut}>
		<label class="split-turn__pick">
			<input
				type="radio"
				name="cut"
				value={event.event_id}
				bind:group={cutEventId}
				aria-label="Candidate sees through this {roleLabel(
					eventRole(event.role)
				).toLowerCase()} turn"
			/>
			<span class="split-turn__who">
				<RoleGlyph role={eventRole(event.role)} />
				{roleLabel(eventRole(event.role))}
				{#if event.kind !== 'message'}<span class="muted">{event.kind}</span>{/if}
			</span>
			{#if event.occurred_at}<span class="muted">{formatTime(event.occurred_at)}</span>{/if}
			{#each event.cited_as as role, index (index)}
				<span class="tag tag--neutral">{role}</span>
			{/each}
		</label>
		{#if event.preview}
			<p class="split-turn__preview">{event.preview}</p>
		{:else}
			<p class="split-turn__preview muted">No text captured</p>
		{/if}
		{#if isCut}<p class="split-turn__mark">Cut point: the candidate answers next</p>{/if}
	</li>
{/snippet}
