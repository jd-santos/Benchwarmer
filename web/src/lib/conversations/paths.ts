import type { Branch, ConversationEvent } from '$lib/api/types';
import { formatTime, plural } from './format';

export interface PathDescription {
	branch: Branch;
	/** "Original" or "Alternate N"; alternates are numbered in capture order. */
	name: string;
	/** How this path departs from the others, from captured structure only. */
	divergence: string | null;
	messageCount: number;
	models: string[];
}

function divergenceText(
	branch: Branch,
	events: Map<string, ConversationEvent>,
	isOriginal: boolean
): string | null {
	if (isOriginal || branch.divergent_event_id === null) return null;
	const divergent = events.get(branch.divergent_event_id);
	if (!divergent) return null;
	const what =
		divergent.role === 'user'
			? 'a different user message'
			: divergent.role === 'assistant'
				? 'a different assistant reply'
				: 'a different event';
	return divergent.occurred_at
		? `Branches at ${formatTime(divergent.occurred_at)} with ${what}`
		: `Branches with ${what}`;
}

/** Name and describe every path; models differ only when the source recorded them. */
export function describePaths(
	branches: Branch[],
	events: Map<string, ConversationEvent>
): PathDescription[] {
	let alternate = 0;
	return branches.map((branch) => {
		const isOriginal = branch.is_original;
		const name = isOriginal ? 'Original' : `Alternate ${++alternate}`;
		return {
			branch,
			name,
			divergence: divergenceText(branch, events, isOriginal),
			messageCount: branch.event_ids.filter((id) => events.get(id)?.kind === 'message').length,
			models: branch.models
		};
	});
}

export function pathSummary(path: PathDescription): string {
	const parts = [plural(path.messageCount, 'message')];
	if (path.models.length > 0) parts.push(path.models.join(', '));
	return parts.join(' · ');
}
