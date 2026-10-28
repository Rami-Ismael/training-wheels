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

- `Subagent: <piece> → <agent type>: <the condition it meets, with its evidence>. Ask: "<one-line prompt the user could type>"`, or
- `Subagent: none: <reason>`, where the reason is the first step of the keep-or-fold test that the piece fails.

The `Ask:` line is the lesson: a prompt in the user's voice that would launch the subagent, written so the user can see what a good delegation prompt names.

## Task with three or more parts

Count parts as units of output: each file that needs its own reading or rewrite, each batch of documents, and each step whose result a later step needs. Replace the line with a short numbered split. Mark each part `subagent (<agent type>)` or `here`, and end each part in its **check**: the observable result that shows it is done.

## The keep-or-fold test

Run it on each piece before naming a subagent. A piece goes to a subagent only when it passes all five steps; otherwise it stays in the main session, done inline, written as a skill, or run as a script.

1. **It earns its own context.** One of three conditions holds, and the line names it with its evidence: a token count, the separate directions, the tool that misfired.
   - *Context:* the piece reads tens of thousands of tokens and the main session needs only a short result. A few thousand does not qualify. If a grep, a page range or a filter would shrink the read, shrink it and stay here.
   - *Independence:* several fresh contexts explore separate directions in parallel, or one agent checks work without seeing how it was made.
   - *Tools:* the main session measurably picks the wrong tools for the piece, or the piece's instructions contradict the main session's.
2. **The reason is a real one.** Long instructions belong in a skill, which loads only when needed. Fixed steps belong in a script. A persona earns nothing by itself: a reader panel passes on fresh eyes, under independence, not on its voices.
3. **The pieces stand apart.** Split by context, not by kind of work. Pieces that chain on each other's results, or read the same files, stay in one context.
4. **The result passes the re-read test.** If the main session would have to re-read the files the agent read before it could use the agent's result, the piece stays here. A passing agent returns a short result the main session uses as it stands.
5. **The job is worth the tokens.** In Anthropic's research system a multi-agent run used about 15 times the tokens of a chat. Scale the count to the job: a lookup of a few tool calls stays here, a comparison takes 2 to 4 agents, and only wide research takes more.

## Verify the call

The test is a prediction. Check it against what happened:

- **After the agent returns,** note whether the main session opened the files the agent read, and whether the result's caveats reached the reply. Either miss means the piece failed the re-read test in practice: say so in the reply, and keep that shape in the main session next time.
- **For a shape that recurs,** measure once. Run one real task both ways, by subagent and in the main session, twice each, since a break can show in one run of two. Compare the result the user accepts, the main session's tokens and the wall time, and read which part changed, not only the total. Keep the subagent only when the main-session version does worse.

## Shapes that name a subagent

A subagent starts with no conversation. Consistency across files and this conversation's context are reasons to write a good brief, not reasons for `none`. Each shape below passes the keep-or-fold test.

- The same judgement pass (rewrite, style pass, review) over 3 or more files: one agent per file, the shared rules in every brief.
- Reading 5 or more papers or notes to grade, sort or extract: one read-only agent per batch.
- A wide read-only sweep whose large output should stay out of this context.
- An adversarial second read of a document or a finding.
- A design question: one agent per direction, side by side, with the results compared in the main session.
- Placing a paper in its field: two web-fetch agents on fixed URLs, one on the paper's references and one on the papers that cite it (the Semantic Scholar API serves both lists). Each returns the 5 papers that matter most.
- Finding a paper's limits: one web-fetch on its OpenReview reviews and rebuttal, returning each weakness the authors conceded.
- Deciding whether a paper applies to the project: two agents, one arguing it does and one arguing it does not, each returning its strongest points for comparison in the main session.
- Checking a figure: an agent sees only the figure and states the claim it makes. A mismatch with the paper's or post's text flags the figure or the text.
- Testing a draft on readers: one agent per audience reads the same draft and returns the first sentence where it got lost, the sentence it would attack, and a three-sentence explain-back.
- Auditing a draft's numbers: one read-only agent traces every number to its source note and returns the numbers with no source.

## Briefs

Each brief is one job with a done-condition the agent can check. It names the objective, the output format, the tools or sources to use, and where the task stops; vague briefs make parallel agents repeat each other's searches. Facts the agent cannot work without go in as named fields, not inside free text. The result comes back as a conclusion, the evidence behind it, and its caveats. Scaffold, layout and script get separate briefs. Pick the agent type with the smallest fixed context that has the tools the job needs: a small model compacts early, and its instructions and tool definitions never shrink. When an agent dies, check its files on disk before relaunching.
