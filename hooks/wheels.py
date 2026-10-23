"""UserPromptSubmit hook: points Claude at each enabled training wheel.

A wheel is a skill that adds one visible coaching line to Claude's reply. This
hook decides only when the wheels fire; what each line says lives in the
wheel's skill. It adds context and never blocks a prompt.

Settings live in ~/.claude/training-wheels/config.json, created on first run:

  {"subagent-check": {"enabled": true, "every_prompt_until": "YYYY-MM-DD"},
   "writing-note":   {"enabled": true, "every_prompt_until": "YYYY-MM-DD"}}

Until `every_prompt_until`, the line goes on every task prompt, including the
"none" and "clean" verdicts, so the habit forms. After that date it appears
only when it has something to say. Set "enabled": false to take a wheel off.

Skipped: slash commands, prompts under MIN_WORDS words (short replies such as
"yes" or "go"), and every prompt while TRAINING_WHEELS=off.
TRAINING_WHEELS_DATE=YYYY-MM-DD stands in for today's date, for testing.
"""
import json
import os
import sys
from datetime import date, timedelta

MIN_WORDS = 8
FIRST_RUN_DAYS = 14
CONFIG = os.path.expanduser("~/.claude/training-wheels/config.json")

# Each wheel: the context line while it fires on every task prompt, then after.
WHEELS = {
    "subagent-check": (
        "Subagent check (training-wheels): if this prompt is a task, apply the training-wheels:subagent-check skill: "
        "open with the 'Subagent:' line, 'none' included, or the numbered split for 3+ parts.",
        "Subagent check (training-wheels): if this prompt is a task, apply the training-wheels:subagent-check skill, "
        "writing the line only when a subagent fits.",
    ),
    "writing-note": (
        "Writing note (training-wheels): if the user typed this task prompt, apply the training-wheels:writing-note skill: "
        "write one 'Writing:' line after any Subagent line, 'clean' included.",
        "Writing note (training-wheels): if the user typed this task prompt, apply the training-wheels:writing-note skill, "
        "writing the 'Writing:' line only when a rule breaks.",
    ),
}


def load_config(today):
    try:
        with open(CONFIG) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        pass
    until = (today + timedelta(days=FIRST_RUN_DAYS)).isoformat()
    config = {name: {"enabled": True, "every_prompt_until": until} for name in WHEELS}
    try:
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        with open(CONFIG, "w") as fh:
            json.dump(config, fh, indent=2)
    except OSError:
        pass
    return config


def main():
    try:
        prompt = str(json.load(sys.stdin).get("prompt") or "").strip()
    except ValueError:
        return
    if (os.environ.get("TRAINING_WHEELS") == "off" or not prompt or prompt.startswith("/")
            or len(prompt.split()) < MIN_WORDS):
        return
    today = date.fromisoformat(os.environ.get("TRAINING_WHEELS_DATE") or date.today().isoformat())
    config = load_config(today)
    lines = []
    for name, (every, sparse) in WHEELS.items():
        wheel = config.get(name) or {}
        if not wheel.get("enabled", True):
            continue
        until = wheel.get("every_prompt_until") or ""
        lines.append(every if today.isoformat() <= until else sparse)
    if lines:
        json.dump({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                          "additionalContext": "\n".join(lines)}}, sys.stdout)


if __name__ == "__main__":
    main()
