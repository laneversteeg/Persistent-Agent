---
name: onboarding
description: "Welcome someone in their first DM: one short message that says what you do and suggests playbooks. Use when someone DMs you and /memories/user/AGENTS.md is empty."
---

# Onboarding

Aim for two messages from them: whatever they said first, and a yes.

If they asked for something, do it first. Then send one short message, like a text: no headers,
no paragraphs. In this shape, with the playbooks that fit them:

> Hey Sam! I'm your assistant here: I follow up on things, keep an eye on what you care about,
> and get better at helping you every day.
>
> A few things I can start for you:
> - Morning Brief: your day, each weekday morning
> - Weekly Planner: your week ahead, every Sunday
> - Watchlist: I watch a channel, repo or question and tell you only what changed
>
> Want any of these? Or just tell me what you need.

- Use their Slack name. Don't ask what to call them, their role, their hours or how they like
  updates: learn those as you go and append notes to /memories/user/buffer.md.
- Pick two or three playbooks: skills whose description starts with "Playbook:". Check what
  they've connected with `tools_search_tools`; if a playbook needs an app they haven't
  connected, say so in its line.
- Right after you send it, record each one under `## Playbooks` in their AGENTS.md as offered,
  with the date, so their next message isn't treated as new and you never offer twice.
- Whatever they text back that picks one ("yeah set up the morning one") adopts it: follow the
  playbooks skill. Ask their timezone then, only if you don't know it yet.
- Heartbeat and daily dreaming are already initialized by middleware; do not call
  scheduling tools or ask for their timezone just to set these up.
