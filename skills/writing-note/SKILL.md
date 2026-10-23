---
name: writing-note
description: Training wheel that adds one coaching line on the prose of each task prompt the user typed, graded against four technical-writing rules. Use when the training-wheels hook names it, or when the user asks how a prompt of theirs could read more clearly.
---

# Writing note

The user is practising technical writing in their prompts, because a prompt a reader can parse one way gets better output. Each task prompt gets one coaching line on its prose. The user writes the revision; the line coaches, it never supplies the rewritten sentence.

## Which prompts

Task prompts the user typed. A prompt that repeats a button, a suggested reply or an `Ask:` line Claude wrote is Claude's prose and gets no note; so does pasted text.

## The line

Written after any Subagent line, before the first tool call:

`Writing: rule <n>. "<the user's exact phrase>" <what a reader can't tell, in one clause>. Try <a direction>.`

Pick the one break that costs a reader most. Quote it exactly, name what a reader cannot tell, and point a direction. A prompt that breaks no rule gets `Writing: clean.` Then do the task as the user meant it.

Example: `Writing: rule 2. "update it with the new numbers" doesn't say whether "it" is the chart or the table. Try naming the file.`

## The four rules

1. **One request per sentence.** A sentence asking for two separate actions breaks it. A numbered list of requests keeps it.
2. **Pointer words point at one thing.** Every "this", "these", "it" and "that" names one thing a reader could point to, in the prompt or in Claude's reply just before it.
3. **Real names.** A skill, file, note, PR, branch, command or run goes by its actual name, spelled right.
4. **No dropped words.** No missing verb, "to", "the" or "is" that stops the sentence from parsing ("we might need add" lacks "to").

Spelling, typos, accents, capitals and tone sit outside the rules.

The rules are condensed from the `technical-writing` skill in Pstack by Lauren Tan (MIT; see `NOTICE.md`). The scorecard's judge grades the same four rules in `skills/scorecard/scripts/judge_prompt.md`; change both together.
