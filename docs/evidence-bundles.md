# Evidence bundles and pattern discovery

A long conversation can contain several pieces of work. The request for one
piece may be far from the code, tool output, or correction that shows what
happened. Benchwarmer should help us connect those pieces, see the original
context, and decide whether they could become a useful test.

This document describes planned work. Benchwarmer is still focused first on
importing conversations and making their history and cost easy to browse.

## A concrete example

Suppose someone asks an agent to preserve the order of items in a list. Later,
the agent writes code that changes the order. A test exposes the mistake, and
the agent fixes it. The request, first attempt, test result, and correction may
be separated by many other messages.

We need three ways to look at that history:

- A **segment** is a continuous stretch of the original conversation on one
  branch, or execution path. It shows what happened in sequence.
- An **evidence bundle** gathers the specific messages and results needed to
  understand one objective or phase of work. It can link parts that are far
  apart without pretending they happened next to each other. Several bundles
  can overlap, and a bundle can cite multiple sessions when the connection is
  explicit.
- A **task version** is a prepared test based on that work. It contains the
  starting request, files, available tools, and success criteria that another
  agent configuration would receive. It keeps the original answer and later
  corrections out of the candidate's view unless a reviewer deliberately
  creates a new version that includes them.

The bundle in this example should show both the first failure and the recovery.
It may be useful for review even if the starting files are missing and the task
cannot yet be replayed.

## Keeping links to the original history

Every item in a bundle needs a precise link back to the saved conversation. A
link identifies the conversation and its immutable revision, the event (such as
a message or tool result), the content block within that event, and, when
needed, a range of text. Block IDs belong to their event. The shared data
contract must say whether text ranges count bytes or characters and reject
ranges outside the source. These references should move from extension data
into a versioned, shared enrichment contract before broad generated analysis.

Each link also says why the item matters: requirement, action, result,
correction, or supporting context. Benchwarmer must check that the source
exists and that any claimed branch or continuation relationship is valid. A
missing source appears as a coverage gap. Sibling branches can be compared,
but they are not one execution. Conversation compaction and changes to the
agent's configuration also mark boundaries in the context.

## Recording what happened and what it might mean

An **observation** says what the saved evidence supports, such as "the test
failed before the correction." A **judgment** or root-cause hypothesis goes
further, such as "the agent misunderstood the ordering requirement." Keep
these separate and record who or what produced the interpretation and how
uncertain it is. If an event was not captured, we cannot conclude it did not
happen.

Each bundle has a versioned record of its objective, selected evidence, the
role of each item, required context, why those items were chosen, missing
evidence, origin, and review status. Record requested capability, subject
matter, behavior, outcome, recovery, and suitability for evaluation
separately. "Unknown" and "ambiguous" are legitimate values. Keep human
corrections and earlier generated versions; regenerating a bundle never
changes the imported history.

Begin by assembling bundles manually from roughly 20–50 conversations, when
that many are available. Review routine successes, failures, recoveries, and
uncertain cases. What reviewers remove or add will tell us how to improve the
record before asking a model to create bundles at scale. The pilot does not
authorize model analysis of other conversations by itself.

## Finding cases worth a closer look

For long histories, first build a compact outline from information we actually
have: message roles and sizes, tool activity, branches, compactions, and
configuration changes. This helps someone navigate the conversation. It does
not reveal every meaningful detail, and it must not invent latency, tool names,
or hidden execution steps.

If model-assisted review is approved later, use a light screening pass to find
promising cases and read the full evidence only where needed. Record what the
model inspected and skipped. Review a sample of cases it did not flag to
measure what it missed, along with reviewer agreement and analysis cost. Pick
model tiers from those results, not from a model's own confidence. Deeper
reads, retries, and escalations stay within the approved limits on inputs,
disclosure, and cost.

## Seeing patterns across conversations

Once bundles are useful on their own, Benchwarmer can help find recurring
themes. Start with filters and saved queries people can inspect. Add
model-suggested patterns only if they improve discovery on a fixed sample.
Keep "what was this about?" separate from "how did the agent behave?" because
those are different questions. The question we ask and the details we extract
will shape what similarities we can see.

A pattern is a versioned view over bundles. Bundles may belong to more than
one pattern. Show a description, representative examples, evidence for and
against it, the source and producer versions, and how much history was
covered. Human-reviewed merges and splits create new versions. Count both
bundles and distinct source conversations, and disclose overlap so the same
history is not counted as independent evidence. Similar failures do not, by
themselves, establish the same root cause.

Patterns can suggest representative test cases and datasets. Include
successful work and recoveries as well as failures. For a comparison, freeze
the selection rules, exclusions, pattern membership, and versions of the
source, enrichment, and bundles. Later imports or pattern changes must not
silently change an existing run or start new model analysis.

## Turning evidence into a test

Promoting a bundle creates a task draft for review. The draft separates what
the candidate agent is allowed to see from historical evidence reserved for
judging it. Before approval, check for missing starting context, incompatible
branches, and **answer leakage**: accidentally giving the candidate the
original solution or a later correction. Describe what a good result must do
instead of requiring the exact wording of the historical response. Set the
criteria before running candidates.

Test proposed evaluators against failures, successes, and ambiguous or
inapplicable cases. An evaluator that catches only the original failure is not
enough. Keep individual criterion results, calibration evidence, and judge
disagreements. If the judge fails, the candidate remains unjudged; it has not
failed the task. Keep links from each task and dataset entry to its source.
When dividing examples into development, judge calibration, and final holdout
sets, keep the entire source family together. Branches, continuations, derived
bundles and tasks, and nearly identical fixtures must not appear on both sides
of that divide.

## Scope and delivery

History and cost browsing comes first. The following work builds on that base:

- [Evidence references and manual bundles](../todo/work/evidence-bundles/README.md)
  precede broad automated enrichment.
- [Enrichment](../todo/work/conversation-enrichment/README.md) adds measured
  screening and source-linked extraction within approved work plans.
- [Pattern discovery](../todo/work/behavior-patterns/README.md) follows useful
  reviewed bundles; embeddings and a full tracing platform are not prerequisites.
- [Task preparation](../todo/work/task-preparation/README.md) can use manually
  selected bundles without waiting for automated grouping.

Autonomous prompt or code repair, automatic memory rewriting, and an
always-running analysis agent are outside this design. Benchwarmer's goal here
is to compare configurations on representative work, not to reproduce the
full production-repair workflow of another system.

## Ideas behind this design

These sources show different ways to learn from agent histories. They helped
shape the questions and workflow here; the bundle format and delivery order
are Benchwarmer design choices.

- [Vivek Trivedy's talk and transcript](https://www.ai.engineer/talks/CvRngaQZQ3Y-improving-agents-is-data-mining-problem)
  connects saved agent behavior and feedback to better tests and decisions
  about which model and setup a task needs.
- [How LangSmith Engine was built](https://www.langchain.com/blog/how-we-built-langsmith-engine-our-agent-for-improving-agents)
  describes using short outlines to find histories worth reading closely, then
  proposing checks and reusable test examples from what it finds.
- [LangSmith Insights documentation](https://docs.langchain.com/langsmith/insights)
  shows how a focused question and the details extracted from each history
  affect the patterns people can explore.
- [LangSmith's guide to improving judges](https://docs.langchain.com/langsmith/improve-judge-evaluator-feedback)
  shows how to compare a judge's decisions with a varied set of human-labeled
  examples and refine it when they disagree.

Benchwarmer should retain native snapshots and its existing approval boundary
as these ideas are adapted.
