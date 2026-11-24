---
name: morning-brief
description: "Playbook: a short brief of someone's day before their first meeting: meetings, clashes, a line of prep for the ones that matter, and what they owe today. Read-only. Use when someone asks for a brief of their day, or a scheduled run names this playbook."
---

# Morning Brief

Follow the playbooks skill to offer, adopt, change or stop this on a schedule.
Run it once on request without adopting anything.

**Needs:** a calendar. Optional: email, Slack, docs, GitHub, Linear.
**Default schedule:** `30 7 * * 1-5`, about half an hour before their usual first meeting.
**Never:** posts anywhere but their DM; accepts, declines or sends anything; replays the
calendar; sends a brief after the morning is gone.

**Preferences:** `send_time`; `skip_meetings` (recurring meetings they never need prep for,
learned); `what_lands` (parts they act on, skip or correct, learned).
**State:** `last_run`, when the last brief was completed.

## Each run
1. If their first meeting has started, skip today: a stale brief is worse than none.
2. Today's meetings in their timezone, with who's in them and links. Flag clashes, back-to-backs
   and invites they haven't answered.
3. One line of prep for each meeting that matters: what changed since last contact, what's owed,
   the one thing worth raising. Skip `skip_meetings` and anything obvious.
4. What they owe today or is overdue, and anything waiting on them.

Read the thread or record behind every claim; say when a source couldn't be checked.

## What it sends
One short DM: their actions first, then meetings with their prep line. Drop empty parts. A clear day
is one line. End with one line inviting corrections.

## Learns
Use their feedback and observed actions to update `what_lands` and `skip_meetings`; do not infer
disinterest from silence. Record a completed brief in `last_run`.
