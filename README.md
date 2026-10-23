# training-wheels

Coaching lines that teach you to prompt Claude Code better, with a date when they come off.

A training wheel is one visible line Claude adds to its reply on each task you type. The line shows a decision you are learning to make yourself. After the date you set, the line appears only when it has something to say, and later you take the wheel off.

This plugin has two wheels:

| Wheel | The line | What you learn |
|---|---|---|
| `subagent-check` | `Subagent: tests → Explore: wide read-only sweep. Ask: "…"` or a numbered split for big tasks | Which part of a task a subagent should take, and what a delegation prompt has to name |
| `writing-note` | `Writing: rule 2. "update it" doesn't say whether "it" is the chart or the table. Try naming the file.` | Four technical-writing rules for prompts, so Claude reads your prompt one way |

The writing note coaches; it never writes the new sentence for you. You revise.

## The four writing rules

1. One request per sentence.
2. Every "this", "these", "it" and "that" points at one thing a reader can name.
3. Things go by their real name: the skill, file, PR or command.
4. Every verb and small word is present.

Spelling, accents and capitals are not graded. The rules are condensed from the `technical-writing` skill in [Pstack](https://github.com/cursor/plugins/tree/main/pstack) by Lauren Tan; see [NOTICE.md](NOTICE.md).

## The scorecard

Type `/training-wheels:scorecard` to see whether your writing improves. It reads the prompts you typed in Claude Code (from `~/.claude/projects/`), has Claude Haiku grade each against the four rules, and writes a page to `~/.claude/training-wheels/scorecard/report.html` with:

- the share of your prompts that kept each rule, week by week,
- three of last week's prompts beside a version revised to keep the rules,
- every phrase flagged in the last 14 days.

Nothing leaves your machine except the prompts sent to Haiku through your own `claude` login. The first run grades eight weeks of prompts and can take about 20 minutes per thousand; later runs grade only new ones. To refresh it weekly, ask Claude to `/schedule` the scorecard for Monday mornings.

The judge has not been validated against human grades yet. Read a small change from one week to the next as noise.

## Install

```
/plugin marketplace add Rami-Ismael/training-wheels
/plugin install training-wheels@training-wheels
```

Requires `python3` on your PATH.

## Settings

The first prompt after installing creates `~/.claude/training-wheels/config.json`:

```json
{
  "subagent-check": {"enabled": true, "every_prompt_until": "2026-11-06"},
  "writing-note":   {"enabled": true, "every_prompt_until": "2026-11-06"}
}
```

Until `every_prompt_until` (14 days after install), a wheel's line appears on every task, including `Subagent: none` and `Writing: clean`, so you see the decision made each time. After that date it appears only when it has something to say. Set `"enabled": false` to take a wheel off. Start Claude with `TRAINING_WHEELS=off` to silence both for one session.

The wheels skip slash commands and short replies under eight words.

## License

MIT. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
