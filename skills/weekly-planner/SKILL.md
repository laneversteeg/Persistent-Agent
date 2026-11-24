---
name: weekly-planner
description: "Playbook: a short look at someone's coming week: the meetings and deadlines that shape it, clashes and invites to sort, and what you'll get ready ahead of time. Read-only. Use when someone asks to plan their week, or a scheduled run names this playbook."
---

# Weekly Planner

Follow the playbooks skill to offer, adopt, change or stop this on a schedule.
Run it once on request without adopting anything.

**Needs:** a calendar. Optional: email, Slack, docs, GitHub, Linear.
**Default schedule:** `0 18 * * 0`, Sunday around 6pm their time.
**Never:** posts anywhere but their DM; accepts, declines or moves anything; lists routine
meetings; promises prep it doesn't track.

**Preferences:** `send_time`; `routine_meetings` (recurring meetings to leave out, learned).
**State:** `prep_promised`, what you said you'd get ready and for which meeting.

## Each run
1. The week's meetings that shape it (not `routine_meetings`), deadlines, clashes and unanswered
   invites.
2. What you'll prepare ahead of time, and for which meeting. On a scheduled run, write it to
   `prep_promised` and set a check-in to do it before that meeting.

## What it sends
One short DM: what shapes the week, what to sort out, what you'll get ready. A light week is
one line.

## Learns
Use feedback to update `routine_meetings`. Keep every promise in `prep_promised`, and clear it
once delivered.
