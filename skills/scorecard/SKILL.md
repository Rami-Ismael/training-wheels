---
name: scorecard
description: Build the weekly prompt-writing scorecard from the user's own Claude Code transcripts and show where it is.
disable-model-invocation: true
---

# Prompt writing scorecard

1. Run `python3 -I scripts/scorecard.py` from this skill's base directory with Bash, timeout 600000 ms. Pass `--since YYYY-MM-DD` only when the user names a start date. The first run grades every prompt since the start date and can take 20 minutes for a thousand prompts; later runs grade only new ones. It is done when it prints a `report:` line.
2. Reply with the report's path from that line, as a link the user can open, and the headline: the last full week's share of prompts that kept all four rules, against the first weeks. If it printed `batch failed`, say how many prompts were left ungraded and that the next run retries them.

The judge's grades have not been checked against the user's own grades. Say so beside any trend.
