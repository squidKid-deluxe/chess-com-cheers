# Cheers HTML Cards — Design (2026-10-03)

## Goal
Replace the janky single-table `out.html` with a dark, static, per-giver
thank-you helper page. Must make "5 cheers last week vs 10 yesterday"
visually separable so already-thanked gifts aren't re-mentioned.

## 1. Architecture / data flow
- `cheers_by_user.py --html` stays the only generator. Same fetch path:
  `GET /callback/awards/<user>/community` → per-`trophy_id`
  `GET /callback/user/trophy/<user>/<trophy_id>/0` → group by `from_user`.
- New render step: `group_by_user()` → `cluster_by_date()` → `write_html()`.
- Output is one self-contained `out.html`: inline CSS, zero JS, no external
  assets except hotlinked chess.com `custom_image_url` + `from_user_avatar`.
- No backend, no localStorage, no build step.
- Default behavior: running `python3 cheers_by_user.py <user>` with no flags
  writes `<user>-cheers.html` into the current working directory. `--html path`
  overrides, `--no-html` suppresses. JSON stays opt-in via `--json`.

## 2. Card layout (dark mode required)
- One card per giver, ordered most-cheers-first then A–Z (matches terminal).
- Card header: avatar (`from_user_avatar`), giver name, total-count badge.
- Body: date clusters newest-first; newest cluster `<details open>`, older
  collapsed.
- Cheer row: trophy thumbnail (`custom_image_url`), trophy name, date
  `YYYY-MM-DD`, description as hover `title`.
- Page header: `Cheers for <user> — N cheers from M givers` + top-5 giver
  leaderboard with anchor links to cards.
- Styling: forced dark theme (dark background, light text, chess.com-ish
  green accents), card grid, responsive single column on mobile.

## 3. Smart date clustering
- Per giver, sort cheers newest-first (UTC `create_date`), split into a new
  cluster whenever the difference between consecutive `create_date` values
  exceeds 3×86400 seconds.
- Groups 23 vs 30 days ago (7-day gap) stay separate; same-day bursts stay
  together.
- Cluster label shows true range + count: single day
  `2026-10-02 — 10 cheers`; span `2026-09-20 to 2026-09-23 — 5 cheers`.
- Single-cheer clusters render as one row without extra nesting.
- Missing/bad timestamps → `Unknown date` cluster at the bottom.
- No persistence: reload re-renders from fresh fetch; "already thanked" is
  eyeballed by cluster.

## 4. Errors, edge cases, verification
- Missing avatar/image URL → omit `<img>`, keep text row (no broken icons).
- Empty giver name → `(unknown)`.
- Zero cheers → header + "No cheers found", no cards.
- One `trophy_id` fetch fails → stderr warning, keep other types.
- Verification: regenerate for `squidkid-deluxe`; confirm 230 cheers / 9
  givers match terminal count; open HTML and check dark theme, 9 cards,
  cluster labels show real ranges, newest cluster open / rest collapsed, no
  external requests except chess.com images.
