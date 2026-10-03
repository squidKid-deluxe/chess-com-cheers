# Cheers HTML Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-table HTML output with a dark, static, per-giver card page with smart date clusters.

**Architecture:** Single-file change to `cheers_by_user.py`: add a pure `cluster_by_date()` helper, rewrite `write_html()` to render dark cards with `<details>` clusters, and make `main()` write HTML by default. No new dependencies, no JS.

**Tech Stack:** Python 3.10 stdlib only (`html`, `json`, `sys`, `urllib.request`, `collections`, `datetime`); output is self-contained HTML with inline CSS.

## Global Constraints

- Output is one self-contained HTML file: inline CSS, zero JS, no external assets except hotlinked chess.com `custom_image_url` + `from_user_avatar`.
- No backend, no localStorage, no build step.
- Forced dark theme (dark background, light text, chess.com-ish green accents), responsive single column on mobile.
- Cards ordered most-cheers-first then A–Z (matches terminal output).
- Newest date cluster renders `<details open>`, older clusters collapsed.
- Missing avatar/image URL → omit `<img>`, keep text row (no broken icons).
- Zero cheers → header + "No cheers found", no cards.
- One `trophy_id` fetch failure → stderr warning, keep other types.

---

## File Structure

- Modify: `/workspace/cheers_by_user.py` — add `cluster_by_date()`, rewrite `write_html()`, update `main()` defaults. Single responsibility preserved: this file is the only fetcher + renderer.
- Create: `/workspace/tests/test_cluster.py` — stdlib-only unit tests for `cluster_by_date()`, runnable with `python3` (no pytest in this env, and YAGNI says don't add a test framework for one pure function).
- Generated (verification only, not committed): `<user>-cheers.html` in cwd.

---

### Task 1: Smart date clustering helper

**Files:**
- Modify: `/workspace/cheers_by_user.py` (insert `cluster_by_date()` after `group_by_user()`, before `fmt_date()`)
- Test: `/workspace/tests/test_cluster.py`

**Interfaces:**
- Consumes: cheer dicts shaped like `{"id": int, "create_date": int, "trophy": str, ...}` (same shape as `collect_cheers()` output); `fmt_date(ts: int) -> str` already exists in the same file.
- Produces: `cluster_by_date(cheers: list[dict]) -> list[tuple[str, list[dict]]]` — input list in any order; output clusters newest-first, each tuple is `(label, cheers_newest_first)`. Labels: single day `"2026-10-02 — 10 cheers"`, span `"2026-09-20 to 2026-09-23 — 5 cheers"`, single cheer `"2026-10-02 — 1 cheer"`, bad/missing timestamps `"Unknown date"`. Split rule: sort newest-first by `create_date`, start a new cluster when the difference between consecutive `create_date` values exceeds 259200 seconds (3×86400). Non-numeric/missing `create_date` values go in the trailing `"Unknown date"` cluster, newest-first by `id`.

- [ ] **Step 1: Write the failing test**

```python
"""Stdlib-only tests for cluster_by_date(). Run: python3 tests/test_cluster.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cheers_by_user import cluster_by_date

DAY = 86400
BASE = 1791000000  # fixed reference timestamp, no wall-clock dependence

# Two bursts 7 days apart must stay separate (the 23-vs-30-days-ago case).
cheers = [
    {"id": 1, "create_date": BASE},
    {"id": 2, "create_date": BASE - 100},
    {"id": 3, "create_date": BASE - 7 * DAY},
    {"id": 4, "create_date": BASE - 7 * DAY - 200},
    {"id": 5, "create_date": "not-a-timestamp"},
    {"id": 6},
]


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"ok - {msg}")


clusters = cluster_by_date(cheers)
check(len(clusters) == 3, f"3 clusters, got {len(clusters)}")
check(len(clusters[0][1]) == 2, "newest burst has 2 cheers")
check(len(clusters[1][1]) == 2, "older burst has 2 cheers")
check(clusters[2][0] == "Unknown date", "bad timestamps grouped as Unknown date")
check(len(clusters[2][1]) == 2, "unknown cluster has 2 cheers")
check(" to " not in clusters[0][0], f"same-day label has no range: {clusters[0][0]!r}")
check("2 cheers" in clusters[0][0], f"count in label: {clusters[0][0]!r}")

single = cluster_by_date([{"id": 9, "create_date": BASE}])
check(single[0][0].endswith("1 cheer"), f"singular label: {single[0][0]!r}")

print("all cluster tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tests/test_cluster.py`
Expected: FAIL with `ImportError: cannot import name 'cluster_by_date'` (function does not exist yet).

- [ ] **Step 3: Write minimal implementation**

Insert after `group_by_user()`, before `fmt_date()` in `/workspace/cheers_by_user.py`:

```python
GAP_SECONDS = 3 * 86400


def cluster_by_date(cheers):
    """Group cheers into time clusters. Returns [(label, cheers)] newest-first."""
    dated = []
    undated = []
    for c in cheers:
        ts = c.get("create_date")
        if isinstance(ts, bool) or not isinstance(ts, (int, float)):
            try:
                ts = int(ts)
            except (TypeError, ValueError):
                undated.append(c)
                continue
        dated.append((int(ts), c))
    dated.sort(key=lambda pair: pair[0], reverse=True)
    undated.sort(key=lambda c: c.get("id", 0), reverse=True)
    clusters = []
    current = []
    prev_ts = None
    for ts, c in dated:
        if prev_ts is not None and prev_ts - ts > GAP_SECONDS:
            clusters.append(current)
            current = []
        current.append((ts, c))
        prev_ts = ts
    if current:
        clusters.append(current)
    result = []
    for group in clusters:
        members = [c for _, c in group]
        stamps = [ts for ts, _ in group]
        start = fmt_date(min(stamps))
        end = fmt_date(max(stamps))
        n = len(members)
        noun = "1 cheer" if n == 1 else f"{n} cheers"
        label = f"{start} — {noun}" if start == end else f"{start} to {end} — {noun}"
        result.append((label, members))
    if undated:
        n = len(undated)
        noun = "1 cheer" if n == 1 else f"{n} cheers"
        result.append((f"Unknown date — {noun}", undated))
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 tests/test_cluster.py`
Expected: PASS, last line `all cluster tests passed`.

- [ ] **Step 5: Commit**

```bash
git add cheers_by_user.py tests/test_cluster.py
git commit -m "feat: add cluster_by_date with gap-based grouping"
```

---

### Task 2: Dark card HTML renderer

**Files:**
- Modify: `/workspace/cheers_by_user.py` (rewrite `write_html()` in place, same signature)

**Interfaces:**
- Consumes: `grouped: dict[str, list[dict]]` from `group_by_user()` (already ordered most-cheers-first then A–Z); `cluster_by_date()` from Task 1; `fmt_date()`; cheer fields `from_user_avatar`, `custom_image_url`, `trophy`, `description`, `create_date`, `id`.
- Produces: `write_html(path: str, username: str, grouped: dict[str, list[dict]]) -> None` — same signature as before, new dark card output. Zero cheers writes header + `No cheers found` paragraph and no cards.

- [ ] **Step 1: Write the failing check**

```python
"""Render check: dark cards, clusters, no broken images. Run: python3 tests/test_render.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cheers_by_user import write_html

grouped = {
    "B giver": [
        {"id": 2, "create_date": 1791000000, "trophy": "Pizza Order",
         "description": "yum", "custom_image_url": "",
         "from_user_avatar": ""},
        {"id": 1, "create_date": 1791000000 - 30 * 86400, "trophy": "Taco",
         "description": "", "custom_image_url": "https://img/x.png",
         "from_user_avatar": "https://img/a.png"},
    ],
}


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"ok - {msg}")


out = "/tmp/render-check.html"
write_html(out, "SomeUser", grouped)
doc = open(out).read()
check("background" in doc and "#121212" in doc, "forced dark background present")
check("<script" not in doc.lower(), "zero JS in output")
check(doc.count("<details") == 2, "two clusters rendered as details")
check("<details open>" in doc, "newest cluster open")
check("to" in doc or "— 1 cheer" in doc, "cluster label with range/count")
check("https://img/x.png" in doc and "https://img/a.png" in doc, "images kept when present")
check(doc.count("<img") == 2, f"no img tags for empty urls (found {doc.count('<img')})")
check('id="giver-b-giver"' in doc, "card anchor id present")
check("Top givers" in doc, "leaderboard present")

write_html("/tmp/render-empty.html", "Nobody", {})
empty = open("/tmp/render-empty.html").read()
check("No cheers found" in empty, "empty state message")

print("all render checks passed")
```

- [ ] **Step 2: Run check to verify it fails**

Run: `python3 tests/test_render.py`
Expected: FAIL — `test_render.py` does not exist yet (`can't open file`), and even if it did, current `write_html()` emits a light `<table>` with no `<details>` or `#121212`.

- [ ] **Step 3: Write minimal implementation**

Replace the existing `write_html()` body in `/workspace/cheers_by_user.py` with:

```python
def write_html(path, username, grouped):
    total = sum(len(v) for v in grouped.values())
    safe_user = html.escape(username)
    if not grouped:
        doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cheers for {safe_user} by giver</title>
<style>body{{background:#121212;color:#e8e8e8;font-family:sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem}}h1{{font-size:1.4rem}}</style>
</head><body><h1>Cheers for {safe_user} — 0 cheers</h1><p>No cheers found.</p></body></html>"""
        with open(path, "w") as f:
            f.write(doc)
        return
    top = list(grouped.items())[:5]
    links = "".join(
        f'<li><a href="#giver-{html.escape(g.lower().replace(" ", "-"))}">{html.escape(g)} ({len(v)})</a></li>'
        for g, v in top
    )
    cards = []
    for giver, cheers in grouped.items():
        anchor = f"giver-{html.escape(giver.lower().replace(' ', '-'))}"
        avatar = (cheers[0].get("from_user_avatar") if cheers else "") or ""
        avatar_tag = (
            f'<img src="{html.escape(avatar, quote=True)}" alt="" width="40" height="40" loading="lazy">'
            if avatar
            else ""
        )
        parts = [f'<section class="card" id="{anchor}"><header>{avatar_tag}<h2>{html.escape(giver)}</h2><span class="badge">{len(cheers)}</span></header>']
        for idx, (label, members) in enumerate(cluster_by_date(cheers)):
            rows = []
            for c in members:
                img = c.get("custom_image_url") or ""
                img_tag = (
                    f'<img src="{html.escape(img, quote=True)}" alt="" width="48" height="48" loading="lazy">'
                    if img
                    else ""
                )
                desc = html.escape(str(c.get("description") or ""))
                rows.append(
                    f'<li title="{desc}">{img_tag}<span>{html.escape(str(c.get("trophy", "?")))}</span><time>{html.escape(fmt_date(c.get("create_date")))}</time></li>'
                )
            open_attr = " open" if idx == 0 else ""
            parts.append(
                f'<details{open_attr}><summary>{html.escape(label)}</summary><ul>{"".join(rows)}</ul></details>'
            )
        parts.append("</section>")
        cards.append("".join(parts))
    doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cheers for {safe_user} by giver</title>
<style>body{{background:#121212;color:#e8e8e8;font-family:sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem}}a{{color:#7ab648}}.card{{background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:1rem;margin:1rem 0}}.card header{{display:flex;align-items:center;gap:.75rem}}.card img{{border-radius:50%}}.badge{{background:#7ab648;color:#121212;border-radius:999px;padding:.1rem .6rem;font-weight:bold}}details{{margin-top:.75rem}}summary{{cursor:pointer}}ul{{list-style:none;padding:0}}li{{display:flex;align-items:center;gap:.5rem;padding:.25rem 0}}time{{color:#999;margin-left:auto}}@media(max-width:600px){{body{{margin:1rem auto}}}}</style>
</head><body><h1>Cheers for {safe_user} — {total} cheers from {len(grouped)} givers</h1><nav><h2>Top givers</h2><ol>{links}</ol></nav>{''.join(cards)}</body></html>"""
    with open(path, "w") as f:
        f.write(doc)
```

- [ ] **Step 4: Run check to verify it passes**

Run: `python3 tests/test_render.py`
Expected: PASS, last line `all render checks passed`.

- [ ] **Step 5: Commit**

```bash
git add cheers_by_user.py tests/test_render.py
git commit -m "feat: dark per-giver card HTML with date clusters"
```

---

### Task 3: HTML-by-default CLI behavior

**Files:**
- Modify: `/workspace/cheers_by_user.py` (`main()` only)

**Interfaces:**
- Consumes: `argv: list[str]` with optional positional `username`, `--html path`, `--no-html`, `--json path`, `--no-progress`.
- Produces: side effects only — default writes `<username>-cheers.html` into cwd; `--html path` overrides; `--no-html` suppresses; `--json path` unchanged and orthogonal.

- [ ] **Step 1: Write the failing check**

```python
"""CLI default check. Run: python3 tests/test_cli_default.py"""
import os
import subprocess
import sys


def run(args, cwd="/tmp"):
    return subprocess.run(
        [sys.executable, "/workspace/cheers_by_user.py", *args, "--no-progress"],
        capture_output=True, text=True, cwd=cwd, timeout=120,
    )


# Default run must produce HTML without --html (network-dependent; skips on failure).
r = run(["squidkid-deluxe"])
if r.returncode != 0:
    print(f"SKIP - network fetch failed: {r.stderr[-300:]}")
    raise SystemExit(0)
assert os.path.exists("/tmp/squidkid-deluxe-cheers.html"), "default html written to cwd"
doc = open("/tmp/squidkid-deluxe-cheers.html").read()
assert "Cheers for squidkid-deluxe" in doc, "username in default html"
assert "cheers from" in doc, "counts rendered (exact totals change over time, so match the pattern)"
print("all cli default checks passed")
```

- [ ] **Step 2: Run check to verify it fails**

Run: `python3 tests/test_cli_default.py`
Expected: FAIL — test file missing, and current `main()` writes no HTML without `--html`.

- [ ] **Step 3: Write minimal implementation**

In `main()` in `/workspace/cheers_by_user.py`, replace the output section with:

```python
    show_progress = "--no-progress" not in args
    no_html = "--no-html" in args

    cheers = collect_cheers(username, show_progress=show_progress)
    grouped = group_by_user(cheers)
    print_report(username, grouped)
    if json_out:
        write_json(json_out, username, grouped)
        print(f"Wrote {json_out}", file=sys.stderr)
    if not no_html:
        html_path = html_out or f"{username}-cheers.html"
        write_html(html_path, username, grouped)
        print(f"Wrote {html_path}", file=sys.stderr)
```

Keep existing `username`, `--json`, `--html` parsing lines untouched; add `no_html = "--no-html" in args` alongside them. Also update the module docstring `Usage:` block to document the default plus `--no-html`.

- [ ] **Step 4: Run checks to verify nothing regressed**

Run: `python3 tests/test_cluster.py && python3 tests/test_render.py`
Expected: both PASS (`all cluster tests passed`, `all render checks passed`).

Then run: `python3 tests/test_cli_default.py`
Expected: PASS (`all cli default checks passed`) or clean `SKIP` on network failure. On pass, confirm the generated HTML card count matches the terminal `N cheers from M givers` line (at time of writing: 230 from 9).

- [ ] **Step 5: Commit**

```bash
git add cheers_by_user.py tests/test_cli_default.py
git commit -m "feat: write HTML by default with --no-html opt-out"
```
