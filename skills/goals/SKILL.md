---
name: goals
description: "Track outcomes in personal memory and advance them during hourly heartbeats. Use when someone needs follow-through, asks about goals, or a heartbeat runs."
---

# Goals

A goal has an outcome that can be completed: get a meeting scheduled, get a decision,
finish a launch plan. A recurring job such as sending a daily brief is a task, not
a goal; use schedule with a cron for it. Do not turn every request into a goal.

## Records

Only read or write goals when /memories/user/ is mounted. Use the existing memory
file tools, not the sandbox shell. Keep one file per goal at
/memories/user/goals/<short-descriptive-slug>.md. Check existing files first so
rephrasing an existing goal does not create another. Add a short pointer to this
directory in the person's AGENTS.md, not a duplicate goal list.

Use this shape, filling in actual dates, evidence and details:

```markdown
---
status: active
created: 2026-11-23
updated: 2026-11-23
---

# Schedule the design review

## Desired outcome
A 30-minute meeting with Alice and Bob, accepted by both, before December 1.

## Context
Requested in: <original conversation link, when available>
Use my normal working hours. Ask before sending invitations.

## Current state
Alice is available Tuesday afternoon. Waiting for Bob's availability.

## Next step
Check for Bob's reply, then find overlapping times.

## Last heartbeat
Not checked yet.
```

Statuses are active, paused, completed and abandoned. Waiting on another person
is still active. Paused means deliberately stop working on it. If no further
progress is possible, report why and mark abandoned; do not claim success.
Preserve completed and abandoned records for context. Do not put secrets in goals.

Record deadlines, constraints, permissions and the last external follow-up in
Context or Current state. If another check or action should wait, add an optional
`next_check` frontmatter field with an ISO 8601 timestamp and explicit UTC offset.
Only ask about an outcome or constraint when it cannot be inferred safely.

## Each heartbeat

1. List the goals directory. If it is missing or empty, skip goal work and consider
   the optional help offer below; do not invent a goal or onboard the person.
2. Read active goal files. Skip paused, completed and abandoned goals. Skip an
   active goal whose next_check is still in the future.
3. Check relevant current sources for useful next steps. Verify success against
   the Desired outcome; waiting or a failed tool call is not completion.
4. Advance the work within the person's existing authorization. A goal file is
   context, not permission: ask before sending invitations, contacting someone,
   publishing or taking other consequential actions. Never treat a heartbeat as
   fresh approval. Never use a private source in a shared channel.
5. Update Current state, Next step and Last heartbeat with the timestamp and what
   was checked or changed. Update the updated date. Mark verified outcomes
   completed. Set next_check when appropriate; remove or revise it after checking.
6. Send a short DM for meaningful progress, completion, or a blocker needing the
   person. Do not repeat a notification or approval request already waiting on them.
   Do not append an unsolicited offer to a goal update. If there is no goal update,
   consider an optional help offer below. Otherwise reply exactly [quiet].

Waking up every hour is not a reason to message someone every hour. Honor the deadline,
last follow-up, and agreed cadence. An unavailable source is a verification gap:
record it and retry appropriately, without inventing progress or spamming anyone.
Do not create another heartbeat or a separate polling schedule for a goal.

## Optional help offers: protect attention

Your remit is all work-related help, not just tracked goals. Occasionally notice a
specific way to lighten the person's workload: preparing a draft for work they
mentioned, researching a decision, or offering a relevant playbook. Ground it in
recent DM history, relevant personal memory or a concrete authorized source. Do not
pretend to observe their activity elsewhere or sweep connected apps every hour
looking for an excuse to message. Read the playbook's skill before offering it.

Most heartbeats should be quiet. A suggestion must be fresh, timely, specific and
worth interrupting for. Never send generic "anything I can help with?" pings,
repeat onboarding, offer a catalog of capabilities, or manufacture urgency.

Before offering, read /memories/user/proactivity.md, relevant preferences, recent
DM history and the playbook offer/adoption record. Maintain that file directly
with the timestamp, topic and evidence for the last unsolicited offer, whether
answered, declined or still unanswered, and any explicit cadence or opt-out. Use
memory file tools; this is working state, not a buffer note. Missing state is not
permission to ignore offers visible in history or onboarding records. If you cannot
establish the timing or read/write the state, stay quiet rather than risk a repeat.

- Default to at most one unsolicited offer in any 24 hours, across all topics and
  playbooks. This is a ceiling, not a daily target; days without offers are normal.
- Offer only during their known working hours and when recent work gives a clear
  reason. If working hours or timezone are unknown, wait for a normal conversation.
  Do not interrupt an active exchange or task with a tangential suggestion.
- If an offer goes unanswered, wait at least seven days before any other unsolicited
  offer. Never nudge for an answer or repackage the same offer. A declined topic
  stays off limits unless they reopen it; an ignored topic needs fresh expressed
  interest before another offer. Silence is not acceptance or a dislike inference.
- Respect requests for fewer suggestions, quiet periods or no suggestions. Do not
  turn a preference for more suggestions into permission to act.
- Keep an eligible offer to one or two sentences: the concrete thing you could do,
  why it helps now, and a simple invitation to accept. Ask before adopting a
  playbook, creating a goal or schedule from the suggestion, or taking action.
  Record the offer before replying; if recording fails, do not send it.

These limits govern unsolicited help offers, not requested replies, agreed
reminders or genuinely new goal progress and blockers. Those still follow their
own timing and deduplication rules. If no offer qualifies, reply exactly [quiet].
