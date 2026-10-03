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
    python3 cheers_by_user.py squidkid-deluxe --no-html
    python3 cheers_by_user.py squidkid-deluxe --no-progress

    Writes <username>-cheers.html by default; use --no-html to suppress.

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
    # Order givers by most recent cheer first, then most cheers, then A–Z.
    # Within each user: newest first (non-numeric/missing dates sort last).
    def giver_key(kv):
        giver, items = kv
        items.sort(key=_sort_key, reverse=True)
        latest = _sort_key(items[0])  # newest cheer after sort
        return (-latest[0], -latest[1], -len(items), giver.lower())

    return dict(sorted(grouped.items(), key=giver_key))


def _sort_key(c):
    ts = c.get("create_date")
    if isinstance(ts, bool):
        return (0, 0)
    if isinstance(ts, (int, float)):
        return (1, int(ts))
    try:
        return (1, int(ts))
    except (TypeError, ValueError):
        return (0, 0)


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
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"user": username, "by_giver": grouped}, f, indent=2)


def collapse_repeats(members):
    """Collapse identical cheers (same trophy+image+description), newest-first."""
    groups = []
    index = {}
    for c in members:
        key = (
            c.get("trophy"),
            (c.get("custom_image_url") or "").strip(),
            c.get("description") or "",
        )
        if key in index:
            groups[index[key]][1].append(c)
        else:
            index[key] = len(groups)
            groups.append((key, [c]))
    return groups


def write_html(path, username, grouped):
    total = sum(len(v) for v in grouped.values())
    safe_user = html.escape(username)
    if not grouped:
        doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cheers for {safe_user} by giver</title>
<style>body{{background:#121212;color:#e8e8e8;font-family:sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem}}h1{{font-size:1.4rem}}</style>
</head><body><h1>Cheers for {safe_user} — 0 cheers</h1><p>No cheers found.</p></body></html>"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(doc)
        return
    cards = []
    for giver, cheers in grouped.items():
        anchor = f"giver-{html.escape(giver.lower().replace(' ', '-'))}"
        avatar = next(filter(None, ((c.get("from_user_avatar") or "").strip() for c in cheers)), "")
        avatar_tag = (
            f'<img src="{html.escape(avatar, quote=True)}" alt="" width="40" height="40" loading="lazy">'
            if avatar
            else ""
        )
        parts = [f'<section class="card" id="{anchor}"><header>{avatar_tag}<h2>{html.escape(giver)}</h2><span class="badge">{len(cheers)}</span></header>']
        for idx, (label, members) in enumerate(cluster_by_date(cheers)):
            rows = []
            for (_trophy, _img, _desc), items in collapse_repeats(members):
                img_tag = (
                    f'<img src="{html.escape(_img, quote=True)}" alt="" width="48" height="48" loading="lazy">'
                    if _img
                    else ""
                )
                desc = html.escape(str(_desc))
                n = len(items)
                count = f'<b class="count">×{n}</b>' if n > 1 else ""
                first = fmt_date(items[0].get("create_date"))
                last = fmt_date(items[-1].get("create_date"))
                span = first if first == last or n == 1 else f"{last} – {first}"
                rows.append(
                    f'<li title="{desc}">{img_tag}<span>{html.escape(str(_trophy or "?"))}</span>{count}<time>{html.escape(span)}</time></li>'
                )
            open_attr = " open" if idx == 0 else ""
            if len(rows) > 3:
                body = (
                    f"<ul>{''.join(rows[:3])}</ul>"
                    f'<details class="more"><summary>Show all {len(rows)}</summary>'
                    f"<ul>{''.join(rows[3:])}</ul></details>"
                )
            else:
                body = f"<ul>{''.join(rows)}</ul>"
            parts.append(
                f'<details{open_attr}><summary>{html.escape(label)}</summary>{body}</details>'
            )
        parts.append("</section>")
        cards.append("".join(parts))
    doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cheers for {safe_user} by giver</title>
<style>body{{background:#121212;color:#e8e8e8;font-family:sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem}}a{{color:#7ab648}}.grid{{display:grid;gap:1rem;grid-template-columns:1fr}}.card{{background:#1e1e1e;border:1px solid #333;border-radius:8px;padding:1rem;margin:0}}.card header{{display:flex;align-items:center;gap:.75rem}}.card img{{border-radius:50%}}.badge{{background:#7ab648;color:#121212;border-radius:999px;padding:.1rem .6rem;font-weight:bold}}.count{{background:#333;border-radius:6px;padding:.1rem .4rem;font-size:.85rem;white-space:nowrap}}details{{margin-top:.75rem}}summary{{cursor:pointer}}.more summary{{font-size:.85rem;color:#999}}ul{{list-style:none;padding:0}}li{{display:flex;align-items:center;gap:.5rem;padding:.25rem 0}}time{{color:#999;margin-left:auto}}@media(max-width:600px){{body{{margin:1rem auto}}}}@media(min-width:900px){{body{{max-width:70%}}.grid{{grid-template-columns:repeat(auto-fill,minmax(320px,1fr))}}}}</style>
</head><body><h1>Cheers for {safe_user} — {total} cheers from {len(grouped)} givers</h1><div class="grid">{''.join(cards)}</div></body></html>"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)


def main(argv):
    username = "squidkid-deluxe"
    json_out = html_out = None
    args = [a for a in argv[1:] if a]
    # very small arg parser: [username] [--json path] [--html path] [--no-html] [--no-progress]
    positional = [a for a in args if not a.startswith("--")]
    if positional:
        username = positional[0]
    if "--json" in args:
        json_out = args[args.index("--json") + 1]
    if "--html" in args:
        html_out = args[args.index("--html") + 1]
    show_progress = "--no-progress" not in args
    no_html = "--no-html" in args

    cheers = collect_cheers(username, show_progress=show_progress)
    grouped = group_by_user(cheers)
    print_report(username, grouped)
    if json_out:
        write_json(json_out, username, grouped)
        print(f"Wrote {json_out}", file=sys.stderr)
    if not no_html:
        html_path = html_out or f"{username}-cheers.html".lower()
        write_html(html_path, username, grouped)
        print(f"Wrote {html_path}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv)
