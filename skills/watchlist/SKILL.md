---
name: watchlist
description: "Playbook: keep an eye on a channel, repo, project or question and say only what changed or needs the person. Read-only. Use when someone asks you to watch something for them, or a scheduled run names this playbook."
---

# Watchlist

Follow the playbooks skill to offer, adopt, change or stop this on a schedule.
Each watch is its own adoption: settings file `watchlist-<slug>.md`, where `<slug>`
names what it watches, and its own schedule. When adopting, ask only what you can't
infer: what to watch and what's worth telling them.

**Needs:** whatever it watches. Optional: Slack, GitHub, Linear, docs, email.
**Default schedule:** `0 9,15 * * 1-5`, twice a weekday.
**Never:** posts, comments or reacts in what it watches; pads a quiet run; reuses an old number
instead of re-checking; puts private sources in a channel.

**Preferences:** `question` (what it watches or answers, in their words); `sources` (the
channels, repos, projects or searches it reads, with links); `needs_them` (what's worth telling
them: mentioned, a review or decision waiting, something broke).
**State:** `last_pass`, when the last run looked, so the next one reads only what's new.

## Each run
Read `sources` since `last_pass`. Tell them only what matches `needs_them`, then update
`last_pass` after checking the sources. Do not advance past unreadable sources without
recording the gap for a retry.

## What it sends
A short DM of what changed or needs them, each with a link. Nothing new: reply `[quiet]`.

## Learns
Use feedback and observed actions to refine `needs_them` and `sources`, not silence alone.
