---
name: subagent-check
description: Training wheel that makes the subagent decision visible on every task prompt, so the user learns to split big tasks into parts a subagent can take. Use when the training-wheels hook names it, or when the user asks whether part of a task should go to a subagent.
---

# Subagent check

The user is learning when delegation pays off. Each task prompt gets the decision made in the open: which part, if any, a subagent should take, and why. Spawning waits for the user's word; the line is a proposal, never a launch.

## Which prompts

A **task** asks for work: edit, build, run, research, write. A question about a fact or an opinion, and a short reply ("yes", "go", a correction), are not tasks; answer those without the line.

## One-part or two-part task

Open the reply with one line, before the first tool call, then start the task:

- `Subagent: <piece> → <agent type>: <reason>. Ask: "<one-line prompt the user could type>"`, or
- `Subagent: none: <reason>`, where the reason is one of: sequential steps, a mechanical edit (one find-and-replace pattern), or a judgement only this conversation can make.

The `Ask:` line is the lesson: a prompt in the user's voice that would launch the subagent, written so the user can see what a good delegation prompt names.

## Task with three or more parts

Count parts as units of output: each file that needs its own reading or rewrite, each batch of documents, and each step whose result a later step needs. Replace the line with a short numbered split. Mark each part `subagent (<agent type>)` or `here`, and end each part in its **check**: the observable result that shows it is done.

## Shapes that name a subagent

A subagent starts with no conversation. Consistency across files and this conversation's context are reasons to write a good brief, not reasons for `none`.

- The same judgement pass (rewrite, style pass, review) over 3 or more files: one agent per file, the shared rules in every brief.
- Reading 5 or more papers or notes to grade, sort or extract: one read-only agent per batch.
- A wide read-only sweep whose large output should stay out of this context.
- An adversarial second read of a document or a finding.
- A design question: one agent per direction, side by side, with the results compared in the main session.

## Briefs

Each brief is one job with a done-condition the agent can check. Scaffold, layout and script get separate briefs. Pick the agent type with the smallest fixed context that has the tools the job needs: a small model compacts early, and its instructions and tool definitions never shrink. When an agent dies, check its files on disk before relaunching.
