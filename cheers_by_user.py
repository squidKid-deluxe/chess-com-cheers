#!/usr/bin/env python3
"""List chess.com cheers grouped by giver.

Fetches:
  1. https://www.chess.com/callback/awards/<user>/community
     -> list of award types (trophy_id, name, count)
  2. https://www.chess.com/callback/user/trophy/<user>/<trophy_id>/0
     -> individual cheers with from_user, create_date, etc.

Groups cheers by from_user and prints ordered by user.

Usage:
    python3 cheers_by_user.py [username]
    python3 cheers_by_user.py squidkid-deluxe --json out.json
    python3 cheers_by_user.py squidkid-deluxe --html out.html
    python3 cheers_by_user.py squidkid-deluxe --no-progress

    Progress bar uses tqdm if installed (pip install tqdm),
    otherwise a simple [i/N] fallback to stderr.
"""

import html
import json
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone


BASE = "https://www.chess.com"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.chess.com/",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
    ),
}


def fetch_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def get_award_types(username):
    url = f"{BASE}/callback/awards/{username}/community"
    data = fetch_json(url)
    return data.get("data", [])


def get_cheers_for_trophy(username, trophy_id):
    url = f"{BASE}/callback/user/trophy/{username}/{trophy_id}/0"
    data = fetch_json(url)
    return data if isinstance(data, list) else []


def collect_cheers(username, show_progress=True):
    award_types = get_award_types(username)
    all_cheers = []
    iterator = award_types
    use_tqdm = False
    if show_progress:
        try:
            from tqdm import tqdm

            iterator = tqdm(award_types, desc="Fetching cheers", unit="type")
            use_tqdm = True
        except ImportError:
            pass
    for i, award in enumerate(iterator):
        tid = award.get("trophy_id")
        if tid is None:
            continue
        if show_progress and not use_tqdm:
            print(
                f"[{i + 1}/{len(award_types)}] trophy {tid}...",
                file=sys.stderr,
                flush=True,
            )
        try:
            cheers = get_cheers_for_trophy(username, tid)
        except Exception as exc:  # keep going if one type fails
            print(f"warning: trophy {tid} fetch failed: {exc}", file=sys.stderr)
            continue
        all_cheers.extend(cheers)
    return all_cheers


def group_by_user(cheers):
    grouped = defaultdict(list)
    for cheer in cheers:
        giver = cheer.get("from_user") or "(unknown)"
        grouped[giver].append(cheer)
    # Order users: most cheers first, then alphabetically (case-insensitive).
    ordered = dict(
        sorted(grouped.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))
    )
    # Within each user: newest first.
    for giver in ordered:
        ordered[giver].sort(key=lambda c: c.get("create_date", 0), reverse=True)
    return ordered


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


def fmt_date(ts):
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def print_report(username, grouped):
    total = sum(len(v) for v in grouped.values())
    print(f"Cheers received by {username}: {total} from {len(grouped)} users\n")
    print(f"{'giver':<24}{'cheers':>8}  breakdown")
    print("-" * 60)
    for giver, cheers in grouped.items():
        counts = Counter(c.get("trophy", "?") for c in cheers)
        breakdown = ", ".join(f"{n} x {t}" for t, n in counts.most_common())
        print(f"{giver:<24}{len(cheers):>8}  {breakdown}")
    print("\n--- detail (grouped by giver) ---\n")
    for giver, cheers in grouped.items():
        print(f"== {giver} ({len(cheers)}) ==")
        for c in cheers:
            print(f"  - {fmt_date(c.get('create_date'))} | {c.get('trophy')} (id {c.get('id')})")
        print()


def write_json(path, username, grouped):
    with open(path, "w") as f:
        json.dump({"user": username, "by_giver": grouped}, f, indent=2)


def write_html(path, username, grouped):
    rows = []
    for giver, cheers in grouped.items():
        counts = Counter(c.get("trophy", "?") for c in cheers)
        breakdown = ", ".join(
            f"{n} &times; {html.escape(str(t))}" for t, n in counts.most_common()
        )
        detail = "".join(
            f"<li>{html.escape(str(fmt_date(c.get('create_date'))))} — "
            f"{html.escape(str(c.get('trophy')))}</li>"
            for c in cheers
        )
        rows.append(
            f"<tr><td>{html.escape(giver)}</td><td>{len(cheers)}</td>"
            f"<td>{breakdown}<ul>{detail}</ul></td></tr>"
        )
    doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Cheers for {html.escape(username)} by giver</title>
<style>body{{font-family:sans-serif;max-width:900px;margin:2rem auto}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccc;padding:.5rem;text-align:left}}ul{{margin:.25rem 0}}</style>
</head><body><h1>Cheers for {html.escape(username)} — grouped by giver</h1>
<table><tr><th>Giver</th><th>Count</th><th>Cheers</th></tr>{''.join(rows)}</table></body></html>"""
    with open(path, "w") as f:
        f.write(doc)


def main(argv):
    username = "squidkid-deluxe"
    json_out = html_out = None
    args = [a for a in argv[1:] if a]
    # very small arg parser: [username] [--json path] [--html path]
    positional = [a for a in args if not a.startswith("--")]
    if positional:
        username = positional[0]
    if "--json" in args:
        json_out = args[args.index("--json") + 1]
    if "--html" in args:
        html_out = args[args.index("--html") + 1]
    show_progress = "--no-progress" not in args

    cheers = collect_cheers(username, show_progress=show_progress)
    grouped = group_by_user(cheers)
    print_report(username, grouped)
    if json_out:
        write_json(json_out, username, grouped)
        print(f"Wrote {json_out}", file=sys.stderr)
    if html_out:
        write_html(html_out, username, grouped)
        print(f"Wrote {html_out}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv)
