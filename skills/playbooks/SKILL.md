---
name: playbooks
description: "How playbooks (skills whose description starts with \"Playbook:\") are offered, adopted on a schedule, changed, stopped and run with someone's personal settings. Use when suggesting, setting up, changing or stopping one, or when someone wants a new shared one."
---

# Playbooks

A playbook is a shared skill for a repeatable job; its description starts with
"Playbook:". Running one on request needs nothing else. Adopting one gives a person
a schedule and a small settings file; the skill itself stays shared, so improvements
reach everyone on their next run after a redeploy.

Only adopt, change or stop playbooks in a DM, where /memories/user/ is mounted. Use
the memory file tools, not the sandbox shell.

## Settings file

One per adoption at `/memories/user/playbooks/<name>.md`, where `<name>` is the
playbook (`morning-brief`) or, for one with several adoptions, the playbook and a
slug (`watchlist-release-prs`). It holds only what is personal:

```yaml
---
playbook: morning-brief
preferences:
  skip_meetings: [Daily standup]
  format: Five bullets max
state:
  last_run: "2026-11-23T15:30:00Z"
---
```

`preferences` holds the person's inputs and differences from the skill's defaults;
every playbook also accepts `format`. `state` is working data between runs. Never copy
the skill's steps, defaults or rules here. Preferences override defaults, never the
skill's **Never** list or approval rules. Record explicit corrections directly; label
inferred preferences with their evidence. Silence is not evidence of dislike.

The schedule is the only record of timing: find it with list_schedules, which shows
each playbook schedule's `<name>`. Don't copy its ID, cron or timezone into memory.

Keep one dated line per playbook under `## Playbooks` in AGENTS.md: offered,
declined, adopted or stopped. It is the offer history, not a copy of the settings.

## Adopt
On their yes:
1. Check the playbook's **Needs** with `tools_search_tools`; send a connect link and
   stop if something required is missing.
2. Write the settings file with what you already know and empty state.
3. Call schedule with a cron (the skill's default unless they said otherwise), their
   timezone in `tz`, `playbook=<name>`, and the task "Run the <playbook> playbook
   with the settings in /memories/user/playbooks/<name>.md." Ask their timezone only
   if you don't know it.
4. Record it as adopted in AGENTS.md and tell them when it runs. Run it once now if
   that's still useful.

If scheduling fails, keep the settings but say it isn't scheduled. Check list_schedules
first so you never schedule the same `<name>` twice.

## Change, stop, run
- **Change.** Edit preferences in the settings file. To change timing, cancel the
  `<name>` schedule and create a new one the same way; if that fails, say it isn't
  scheduled.
- **Stop.** Cancel the `<name>` schedule and record it as stopped. Keep the settings
  file for resuming.
- **Run.** Read the playbook's skill and the settings file, apply the preferences and
  do the work within existing approvals. Update only state and preferences that
  changed. If the skill is gone or a preference no longer fits it, say what needs
  fixing instead of guessing.

## Offering
Suggest playbooks in someone's first DM (the onboarding skill), when they ask what you
can do, or when they've as good as asked: a cadence ("every Friday") or the same ask at
the same time twice. A heartbeat may offer one only within the goals skill's attention
budget. Never mid-task, in a shared channel, during other scheduled runs, or again after
an unanswered or declined offer. Suggesting one isn't adopting it: wait for a yes.

## New playbooks
No playbook fits a recurring job? Offer an ordinary recurring schedule for them. If they
want it shared with everyone, draft a new `skills/<name>/SKILL.md` in the shape of the
built-in ones, without their private names, sources or accounts, for a teammate to add
through code review and redeploy. You can't publish one yourself, and a personal request
doesn't authorize changing everyone's agent.
