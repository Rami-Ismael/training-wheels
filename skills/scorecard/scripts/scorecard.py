"""Weekly scorecard of your typed Claude Code prompts against the four writing rules.

  python3 scorecard.py [--since YYYY-MM-DD]

Runs five steps and prints the report's path:

  extract   typed prompts from ~/.claude/projects/*/*.jsonl -> prompts.jsonl
  score     unscored prompts, graded by Claude Haiku         -> scores.jsonl
  weekly    one row per ISO week                             -> weekly.csv
  rewrite   3 prompts from the last full week, revised       -> rewrites.jsonl
  report    a self-contained page                            -> report.html

Everything is written to ~/.claude/training-wheels/scorecard/ (or
$TRAINING_WHEELS_DATA). The first run fixes the start date, by default eight
weeks back, so later weeks compare against the same baseline.

What counts as a typed prompt: a user message typed in any project, 8+ words
after removing pasted blocks, code, quoted lines and image tags. Left out:
slash commands, notices, other sessions' messages, scheduled and headless
turns, and any prompt that repeats a button, suggested reply or `Ask: "..."`
line Claude wrote. Forked sessions copy prompts, so each text counts once.

Grading and rewriting run `claude -p --model haiku` with no tools, from an
empty folder, without saving a session: a saved judge session would feed its
own batches back in as prompts. Scores are cached by prompt id, so a weekly run
grades only new prompts. The judge has not been checked against your own
grades; treat a small week-to-week change as noise.
"""
import argparse
import csv
import glob
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

MIN_WORDS = 8
BATCH = 20
WORKERS = 4
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.expanduser("~/.claude/projects")
DATA = os.environ.get("TRAINING_WHEELS_DATA") or os.path.expanduser("~/.claude/training-wheels/scorecard")
PROMPTS, SCORES, WEEKLY, REWRITES, REPORT, SINCE = (
    os.path.join(DATA, f) for f in ("prompts.jsonl", "scores.jsonl", "weekly.csv", "rewrites.jsonl", "report.html", "since.txt"))
RULES = ("one_request", "pointer", "real_name", "small_words")
RULE_NAMES = {"one_request": "One request per sentence", "pointer": "Pointer words point at one thing",
              "real_name": "Real names", "small_words": "No dropped words"}
NOT_TYPED = ("<", "[SYSTEM", "Another Claude session", "This session is being continued", "Caveat:",
             "Your response above was cut off", "Generate a title")


def norm(s):
    return re.sub(r"[\s.!?]+$", "", re.sub(r"\s+", " ", s.strip().lower()))


def clean(s):
    """The person's own prose: pasted blocks, code, quoted lines and image tags removed."""
    s = re.sub(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", " ", s, flags=re.S)
    s = re.sub(r"```.*?```", " ", s, flags=re.S)
    s = "\n".join(l for l in s.splitlines() if not l.lstrip().startswith(">"))
    s = re.sub(r"\[Image #\d+\]", " ", s)
    return s.strip()


def local_day(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        return None


def load(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return [json.loads(l) for l in fh if l.strip()]


def start_date(arg):
    if arg:
        since = arg
    elif os.path.exists(SINCE):
        since = open(SINCE).read().strip()
    else:
        since = (date.today() - timedelta(weeks=8)).isoformat()
    with open(SINCE, "w") as fh:
        fh.write(since)
    return since


def extract(since):
    claude_wrote = set()        # buttons, suggested replies and Ask: lines, normalised
    candidates = []
    why = Counter()
    for path in glob.glob(os.path.join(ROOT, "*", "*.jsonl")):
        last_reply = ""
        try:
            fh = open(path, encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                msg = r.get("message") or {}
                content = msg.get("content")
                if r.get("type") == "assistant" and isinstance(content, list):
                    for b in content:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "text" and b.get("text"):
                            last_reply = b["text"]
                            for m in re.finditer(r'Ask: "([^"]+)"', b["text"]):
                                claude_wrote.add(norm(m.group(1)))
                        elif b.get("type") == "tool_use" and isinstance(b.get("input"), dict):
                            for a in b["input"].get("actions") or []:
                                if isinstance(a, dict):
                                    for k in ("message", "label"):
                                        if isinstance(a.get(k), str):
                                            claude_wrote.add(norm(a[k]))
                    continue
                if r.get("type") != "user" or not isinstance(content, str):
                    continue
                s = content.strip()
                origin = (r.get("origin") or {}).get("kind")
                if (r.get("isMeta") or r.get("isSidechain") or r.get("turnCompanion") or r.get("isCompactSummary")
                        or (origin and origin != "human") or r.get("turnOrigin") not in (None, "human")
                        or r.get("promptSource") == "system" or r.get("entrypoint") == "sdk-cli"
                        or s.startswith(NOT_TYPED)):
                    why["not typed"] += 1
                    continue
                if s.startswith("/"):
                    why["slash command"] += 1
                    continue
                day = local_day(r.get("timestamp", ""))
                if not day or day < since:
                    why["before start"] += 1
                    continue
                candidates.append((r["timestamp"], r.get("uuid"), s, last_reply[-500:]))

    seen, kept = set(), []
    for ts, uuid, raw, ctx in sorted(candidates):
        key = norm(raw)
        if key in seen:
            why["repeat (fork or rerun)"] += 1
            continue
        seen.add(key)
        if key in claude_wrote:
            why["Claude's button or Ask line"] += 1
            continue
        text = clean(raw)
        if len(text.split()) < MIN_WORDS:
            why[f"under {MIN_WORDS} words"] += 1
            continue
        kept.append({"uuid": uuid, "ts": ts, "day": local_day(ts), "text": text, "words": len(text.split()), "context": ctx})
    with open(PROMPTS, "w") as fh:
        for k in kept:
            fh.write(json.dumps(k) + "\n")
    print(f"extract: {len(kept)} typed prompts since {since}; left out {dict(why)}")


def haiku(system_file, items, schema):
    """One headless Haiku call: no tools, no settings, no saved session."""
    with tempfile.TemporaryDirectory() as tmp:
        out = subprocess.run(
            ["claude", "-p", "--model", "haiku", "--tools", "", "--no-session-persistence",
             "--setting-sources", "project", "--strict-mcp-config", "--disable-slash-commands",
             "--system-prompt-file", os.path.join(HERE, system_file),
             "--output-format", "json", "--json-schema", json.dumps(schema)],
            input=json.dumps(items, ensure_ascii=False), capture_output=True, text=True, cwd=tmp, timeout=600)
    if out.returncode:
        raise RuntimeError((out.stderr or out.stdout)[-500:])
    res = json.loads(out.stdout)
    return (res.get("structured_output") or json.loads(res.get("result") or "{}"))["results"]


def results_schema(props):
    return {"type": "object", "required": ["results"], "properties": {"results": {"type": "array", "items": {
        "type": "object", "required": ["id", *props], "properties": {"id": {"type": "string"}, **props}}}}}


JUDGE_SCHEMA = results_schema({r: {"type": "array", "items": {"type": "string"}} for r in RULES})
REWRITE_SCHEMA = results_schema({
    "rewrite": {"type": "string"},
    "changes": {"type": "array", "items": {"type": "object", "required": ["rule", "before", "after"], "properties": {
        "rule": {"type": "integer"}, "before": {"type": "string"}, "after": {"type": "string"}}}}})


def found(phrase, text):
    """A quoted phrase counts only if it appears in the prompt; the judge sometimes paraphrases."""
    squash = lambda s: re.sub(r"\W+", " ", s.lower()).strip()
    return bool(squash(phrase)) and squash(phrase) in squash(text)


def as_items(batch):
    return [{"id": p["uuid"], "reply_before": p["context"][-300:], "prompt": p["text"]} for p in batch]


def score_batch(batch):
    try:
        got = {r["id"]: r for r in haiku("judge_prompt.md", as_items(batch), JUDGE_SCHEMA)}
    except Exception as e:  # one failed batch is retried on the next run
        print(f"score: batch failed: {e}", file=sys.stderr)
        return []
    rows = []
    for p in batch:
        r = got.get(p["uuid"])
        if r:
            rows.append({"uuid": p["uuid"], "day": p["day"], **{k: [q for q in r[k] if found(q, p["text"])] for k in RULES}})
    return rows


def score():
    done = {s["uuid"] for s in load(SCORES)}
    todo = [p for p in load(PROMPTS) if p["uuid"] not in done]
    batches = [todo[i:i + BATCH] for i in range(0, len(todo), BATCH)]
    n = 0
    with ThreadPoolExecutor(WORKERS) as pool:
        for fut in as_completed([pool.submit(score_batch, b) for b in batches]):
            rows = fut.result()
            with open(SCORES, "a") as fh:       # only this thread writes
                for row in rows:
                    fh.write(json.dumps(row) + "\n")
            n += len(rows)
    print(f"score: {n} of {len(todo)} new prompts graded")


def week_of(day):
    y, w, _ = date.fromisoformat(day).isocalendar()
    return date.fromisocalendar(y, w, 1)


def weekly():
    prompts = {p["uuid"]: p for p in load(PROMPTS)}
    weeks = defaultdict(list)
    for s in load(SCORES):
        p = prompts.get(s["uuid"])
        if p:
            weeks[week_of(p["day"])].append((p, s))
    today, rows = date.today(), []
    for wk in sorted(weeks):
        pairs = weeks[wk]
        n = len(pairs)
        pct = lambda ok: round(100 * sum(ok) / n, 1)
        row = {"week": wk.isoformat(), "prompts": n, "complete": int((today - wk).days >= 7),
               "words_per_prompt": round(sum(p["words"] for p, _ in pairs) / n, 1),
               "all": pct(all(not s[r] for r in RULES) for _, s in pairs)}
        row.update({r: pct(not s[r] for _, s in pairs) for r in RULES})
        rows.append(row)
    cols = ["week", "prompts", *RULES, "all", "words_per_prompt", "complete"]
    with open(WEEKLY, "w", newline="") as fh:
        w = csv.DictWriter(fh, cols)
        w.writeheader()
        w.writerows(rows)
    print(f"weekly: {len(rows)} weeks")
    return rows


def rewrite(rows):
    """Revise the three prompts with the most breaks in the last full week, once each."""
    full = [r for r in rows if r["complete"]]
    if not full:
        return
    wk = full[-1]["week"]
    if any(r["week"] == wk for r in load(REWRITES)):
        return
    prompts = {p["uuid"]: p for p in load(PROMPTS)}
    ranked = sorted(((sum(len(s[r]) for r in RULES), s["uuid"]) for s in load(SCORES)
                     if s["uuid"] in prompts and week_of(prompts[s["uuid"]]["day"]).isoformat() == wk
                     and 12 <= prompts[s["uuid"]]["words"] <= 120), reverse=True)
    batch = [prompts[u] for n, u in ranked[:3] if n]
    if not batch:
        return
    try:
        got = haiku("rewrite_prompt.md", as_items(batch), REWRITE_SCHEMA)
    except Exception as e:
        print(f"rewrite: failed: {e}", file=sys.stderr)
        return
    with open(REWRITES, "a") as fh:
        for r in got:
            if r["id"] in prompts:
                fh.write(json.dumps({"uuid": r["id"], "week": wk, "rewrite": r["rewrite"], "changes": r["changes"]}) + "\n")
    print(f"rewrite: {len(got)} prompts from the week of {wk}")


# ---------- report ----------

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--muted:#5f6b7a;--line:#dde2e8;--good:#1f7a5a;--bad:#b4471c;
--s0:#2856a8;--s1:#b5651d;--s2:#2f8f6f;--s3:#8a3fa0;--font:"Atkinson Hyperlegible","Segoe UI",system-ui,sans-serif;
--quote:Georgia,"Times New Roman",serif;--mono:ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root{--bg:#12161c;--card:#1a2029;--ink:#e6ebf1;--muted:#9aa6b4;--line:#2c3540;
--good:#6fd1a6;--bad:#f39a72;--s0:#8db0f0;--s1:#e8a66a;--s2:#6fd1a6;--s3:#d29be6;color-scheme:dark}}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 var(--font)}
main{max-width:56rem;margin:0 auto;padding:2rem max(16px,env(safe-area-inset-left)) 4rem;display:flex;flex-direction:column;gap:1.25rem}
h1{font:600 1.8rem/1.2 var(--quote);margin:0}h2{font-size:1.05rem;margin:0 0 .5rem}p{margin:0}
.muted{color:var(--muted)}.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:1rem 1.1rem;min-width:0}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,11rem),1fr));gap:.75rem}
.big{font:400 2rem/1.1 var(--quote);font-variant-numeric:tabular-nums;margin:.25rem 0}
.up{color:var(--good)}.down{color:var(--bad)}.small{font-size:.85rem}
svg text{fill:var(--muted);font:12px var(--font)}
.pair{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,20rem),1fr));gap:.75rem;margin-top:.5rem}
.pair p{font-family:var(--quote);white-space:pre-wrap;overflow-wrap:anywhere}
.tag{font-size:.75rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:.25rem}
.box{max-height:24rem;overflow:auto}table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{text-align:left;padding:.35rem .6rem .35rem 0;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:400;position:sticky;top:0;background:var(--card)}
td.q{font-family:var(--quote);font-style:italic}td.d{font-family:var(--mono);white-space:nowrap;color:var(--muted)}
"""


def chart(rows):
    W, H, L, R, T, B = 760, 280, 40, 190, 10, 26
    if len(rows) < 2:
        return '<p class="muted">The trend appears once there are two weeks of prompts.</p>'
    weeks = [date.fromisoformat(r["week"]) for r in rows]
    t0, t1 = weeks[0].toordinal(), weeks[-1].toordinal()
    x = lambda d: L + (d.toordinal() - t0) / (t1 - t0) * (W - L - R)
    y = lambda v: T + (100 - v) / 100 * (H - T - B)
    out = [f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="Weekly share of prompts keeping each rule">']
    for v in (0, 25, 50, 75, 100):
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="var(--line)"/>'
                   f'<text x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v}%</text>')
    step = max(1, len(weeks) // 6)
    for d in weeks[::step]:
        out.append(f'<text x="{x(d):.1f}" y="{H - 6}" text-anchor="middle">{d.strftime("%b %-d")}</text>')
    labels = []
    for i, r in enumerate(RULES):
        pts = [(x(d), y(row[r]), row["complete"]) for d, row in zip(weeks, rows)]
        done, tail = [p for p in pts if p[2]], [p for p in pts if not p[2]]
        line = lambda ps: " ".join(f"{a:.1f},{b:.1f}" for a, b, _ in ps)
        out.append(f'<polyline points="{line(done)}" fill="none" stroke="var(--s{i})" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
        if tail:   # the week still filling in, dashed from the last full week
            out.append(f'<polyline points="{line(done[-1:] + tail)}" fill="none" stroke="var(--s{i})" stroke-width="2" stroke-dasharray="4 4"/>')
        labels.append([pts[-1][1], i, f"{RULE_NAMES[r]} {rows[-1][r]:.0f}%"])
    labels.sort()
    for k in range(1, len(labels)):
        labels[k][0] = max(labels[k][0], labels[k - 1][0] + 15)
    for ly, i, text in labels:
        out.append(f'<text x="{W - R + 8}" y="{ly + 4:.1f}" style="fill:var(--s{i})">{html.escape(text)}</text>')
    out.append("</svg>")
    return "".join(out)


def report(rows, since):
    esc = html.escape
    full = [r for r in rows if r["complete"]]
    head = '<p class="muted">No full week of prompts yet. Run the scorecard again after your first full week.</p>'
    cards = ""
    if full:
        a, b = full[-1], (full[-2] if len(full) > 1 else None)
        base = full[:4]
        base_all = sum(r["all"] for r in base) / len(base)
        head = (f'<p>In the week of {date.fromisoformat(a["week"]).strftime("%b %-d")}, <b>{a["all"]:.0f}%</b> of your '
                f'{a["prompts"]} typed prompts kept all four rules, against <b>{base_all:.0f}%</b> in your first '
                f'{len(base)} week{"s" if len(base) > 1 else ""}.</p>')
        for key, name in [*RULE_NAMES.items(), ("all", "All four rules")]:
            delta = "" if not b else a[key] - b[key]
            cls = "" if delta == "" or delta == 0 else ("up" if delta > 0 else "down")
            dtext = "" if delta == "" else f"{delta:+.1f} pts vs the week before"
            cards += (f'<div class="card"><div class="small">{esc(name)}</div><div class="big">{a[key]:.0f}%</div>'
                      f'<div class="small {cls}">{dtext}</div></div>')

    prompts = {p["uuid"]: p for p in load(PROMPTS)}
    pairs = ""
    rws = load(REWRITES)
    latest = rws[-1]["week"] if rws else None
    for r in [r for r in rws if r["week"] == latest]:
        p = prompts.get(r["uuid"])
        if not p:
            continue
        changes = "".join(f"<li>Rule {c['rule']}: “{esc(c['before'])}” → “{esc(c['after'])}”</li>" for c in r["changes"])
        pairs += (f'<div class="card"><div class="pair"><div><div class="tag">Yours</div><p>{esc(p["text"])}</p></div>'
                  f'<div><div class="tag">Technical-writing version</div><p>{esc(r["rewrite"])}</p></div></div>'
                  f'<ul class="small muted">{changes}</ul></div>')
    if not pairs:
        pairs = '<p class="muted">Side-by-side versions appear after your first full week.</p>'

    cutoff = (date.today() - timedelta(days=14)).isoformat()
    breaks = []
    for s in load(SCORES):
        p = prompts.get(s["uuid"])
        if p and p["day"] >= cutoff:
            breaks += [(p["day"], RULE_NAMES[r], q) for r in RULES for q in s[r]]
    breaks.sort(reverse=True)
    trs = "".join(f'<tr><td class="d">{d}</td><td>{esc(n)}</td><td class="q">“{esc(q)}”</td></tr>' for d, n, q in breaks)
    table = (f'<div class="box"><table><thead><tr><th>Day</th><th>Rule</th><th>Phrase</th></tr></thead><tbody>{trs}</tbody></table></div>'
             if trs else '<p class="muted">Nothing flagged in the last 14 days.</p>')

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Prompt writing scorecard</title>
<style>{CSS}</style></head><body><main>
<header><h1>Prompt writing scorecard</h1><p class="muted small">Your typed Claude Code prompts since {since}. Updated {datetime.now().strftime("%Y-%m-%d %H:%M")}.</p></header>
{head}
<section class="cards">{cards}</section>
<section class="card"><h2>Share of prompts that keep each rule, by week</h2>
<p class="muted small">A prompt keeps a rule when the judge finds no phrase breaking it. The current week is still filling in and is drawn dashed.</p>{chart(rows)}</section>
<section><h2>Yours beside the technical-writing version</h2>
<p class="muted small">Three prompts from the last full week with the most breaks, revised to keep the four rules. Try your own revision before you read the right column. Where your sentence could mean two things, the revision picks one, so check it against what you meant.</p>{pairs}</section>
<section class="card"><h2>What broke a rule in the last 14 days</h2>{table}</section>
<section class="card small muted"><h2>How the scores are made</h2>
<p>Claude Haiku grades each prompt against the four rules of the writing-note skill. It sees the end of the reply before each prompt, so "merge it" after one offered pull request counts as clear. Spelling, accents and capitals are not graded. The judge has not been checked against your own grades, so read a small week-to-week change as noise.</p></section>
</main></body></html>"""
    with open(REPORT, "w") as fh:
        fh.write(page)
    print(f"report: {REPORT}")


def main():
    ap = argparse.ArgumentParser(description="Weekly scorecard of your prompts against the four writing rules.")
    ap.add_argument("--since", help="first day to include, YYYY-MM-DD (fixed after the first run)")
    args = ap.parse_args()
    os.makedirs(DATA, exist_ok=True)
    since = start_date(args.since)
    extract(since)
    score()
    rows = weekly()
    rewrite(rows)
    report(rows, since)


if __name__ == "__main__":
    main()
