# Persistent Agent

**An always-on assistant for your whole team, in one Slack bot.**

Install it once and everyone talks to the same bot, but each person gets their own assistant:
it remembers what they've told it, runs their recurring work on their schedule, follows up on
their goals until they're done, and uses the apps they've connected. It keeps working when nobody
is talking to it. Built on
[Managed Deep Agents](https://docs.langchain.com/langsmith/python/managed-deep-agents-overview)
(MDA).

Features include:

- **Personal memory** — preferences, decisions and notes, private to each person's DM
- **Goals that follow through** — an hourly heartbeat advances each person's goals until they're done
- **Dreaming** — every night, each person's notes are consolidated into long-term memory
- **Playbooks** — Morning Brief, Weekly Planner and Watchlist, run once or on a schedule
- **Watch mode** — in channels it reads everything and speaks up only when it can help
- **Background work** — research and review subagents run while the conversation continues
- **Integrations** — Google, Slack, Linear, GitHub and more through Tool Gateway
- **A browser per person** — it works on websites and hands you the browser when it needs you

Each is a few lines on top of an MDA primitive, so keep what you need and delete the rest.

## Quickstart

You need [uv](https://docs.astral.sh/uv/), a LangSmith workspace with Managed Deep Agents, a
model, and a Slack workspace where you can approve an app. For the model, either add an
Anthropic provider secret to the workspace's
[LLM Gateway](https://docs.langchain.com/langsmith/llm-gateway) settings (the default) or use
your own Anthropic or OpenAI key (see `.env.example`). A
[Tool Gateway](https://docs.langchain.com/langsmith/tool-gateway) kit (LangSmith → Tools) is
recommended: without one, the agent has no integrations.

1. Clone and configure:

```bash
git clone https://github.com/langchain-samples/Persistent-Agent.git
cd Persistent-Agent
uv sync
cp .env.example .env
```

Set `LANGSMITH_API_KEY`, and `TOOLS_MCP_URL` to your kit's MCP URL (LangSmith → Tools → your
kit). Set `LANGSMITH_WORKSPACE_ID` too if your key is organization-scoped. By default the agent
runs Claude Opus 5.5 through the LLM Gateway, so no other key is needed; to use your own
provider key instead, set `AGENT_MODEL` and that key.

2. Deploy:

```bash
uv run mda deploy
```

3. Open the Slack link the first deploy prints and approve the app. The bot appears as
   `persistent-agent`.

4. DM it "hi". Then ask something that needs one of your apps, like "what's on my calendar
   today?". The first time, it posts a link to connect that app.

To change it later, edit the files and deploy again. See the
[CLI reference](https://docs.langchain.com/langsmith/python/managed-deep-agents-cli) for logs and
other commands.

## Use it

**Start in a DM.** Say "hi" and it replies with a short welcome and a few playbooks it can
start. It learns your preferences as you work together, and asks for your timezone only when
setting up recurring work. Your heartbeat and dreaming are set up automatically on your first DM.

**Hand it work in plain language:**

| Say | What it does |
|---|---|
| "Send me a morning brief" | Adopts the Morning Brief playbook: your day, each weekday morning. |
| "Every Friday at 4, summarize what I shipped this week" | Creates a recurring task in your timezone. |
| "Let me know when the release PR is approved" | Records a goal; the hourly heartbeat checks for progress. |
| "Check back on this tomorrow" | Schedules a one-time follow-up in this conversation. |
| "Research our top three competitors' pricing" | Hands it to a background subagent and reports back when done. |
| "Book a table for two on Friday" | Works in its browser and hands it to you when it needs you, such as to log in. |
| "What do you have scheduled for me?" | Lists your recurring tasks, heartbeat, dreaming and check-ins. |
| "Move my brief to 7:30" | Updates your settings and the brief's schedule. |
| `!clear` | Forgets everything about you and cancels your schedules. |

**Add it to channels.** It reads every message, answers when it can add something and otherwise
stays quiet. Mention it to ask directly. Your personal memory never loads in a channel.

**Connect your apps.** When it needs an app you haven't connected, it posts a link in your DM to
connect your own account; then message it again.

**Use its browser.** When it needs you to log in, finish 2FA or make a choice, it hands you the
browser: in your DM the link is in its reply; if you asked in a channel, the link goes to your
DM. The link works for 15 minutes and lets anyone holding it use the browser, so don't share it.
Click *Hand back* when you're done and it carries on.

## How it works

### Which mechanism does what

| Mechanism | Purpose | Where it lives |
|---|---|---|
| **Skill** | How to do a kind of work. | Shared `skills/<name>/SKILL.md`, read when relevant. |
| **Playbook** | A skill for a repeatable job, run once or adopted on a schedule. | A skill whose description starts with "Playbook:". |
| **Playbook settings** | One person's preferences and state for a playbook they adopted. | `/memories/user/playbooks/<name>.md` |
| **Scheduled task** | Recurring work and its timing. | A user-owned MDA schedule; playbook schedules are tagged `playbook=<name>`. |
| **Check-in** | A single later follow-up. | A one-time schedule in the same conversation. |
| **Goal** | An outcome with a finish line. | `/memories/user/goals/<slug>.md` |
| **Heartbeat** | Advances active goals hourly and reports real progress or blockers. | One hourly schedule per person. |
| **Memory buffer** | Dated, attributed notes worth remembering. | `/memories/user/buffer.md`, appended during DM work. |
| **Dreaming** | Consolidates the buffer into long-term memory nightly. | One daily schedule per person. |
| **Background subagent** | Long work now, while the conversation continues. | An async task that reports back. |

For example, "get this meeting booked" becomes a goal advanced by the heartbeat; "brief me every
morning" adopts a playbook with personal settings and a scheduled task; "I prefer five bullets"
becomes a buffered note that dreaming files into memory.

### Everyone's own assistant

- **[Memory](https://docs.langchain.com/langsmith/python/managed-deep-agents-memory)** (`/memories/user/`) loads only in that person's DMs.
- **[Schedules](https://docs.langchain.com/langsmith/python/managed-deep-agents-schedules)** run as the person and only they can see or cancel them. Check-ins asked for in a shared channel belong to the agent instead, so anyone there can see or cancel them.
- **Integrations** use the accounts that person connected, and their [browser](https://docs.langchain.com/langsmith/python/managed-deep-agents-browser-use) keeps their logins.

### Heartbeat and dreaming

`PerUserSchedulesMiddleware` (`middleware/per_user_schedules.py`) runs before the model on a
person's DM and makes sure they have exactly one hourly heartbeat and one nightly dreaming
schedule, owned by them. It creates them just in time because they must run as that person,
whose identity is only available on their own request. Existing schedules are left as they are,
including paused ones, and duplicates from concurrent DMs are removed. `heartbeat.py` and
`dreaming.py` hold each schedule's prompt and timing; `agent.py` lists them.

The heartbeat continues the person's DM. It follows the goals skill: it advances active goals
within existing approvals, rarely offers relevant help, and otherwise replies `[quiet]`, which
is never posted. No goal gets its own polling schedule.

Dreaming runs at 02:00 America/Los_Angeles in a fresh thread and always stays quiet. It merges
the buffer into `/memories/user/AGENTS.md` and topic files, deduplicates, resolves clear
corrections and removes only the notes it saved. It never touches goals or reads traces.

### Playbooks

Three are built in: **Morning Brief**, **Weekly Planner** and **Watchlist**. Because they're
skills, the agent runs one when someone asks ("brief me on my day"). Adopting one, per
[the playbooks skill](skills/playbooks/SKILL.md), creates that person's settings file and a
schedule tagged `playbook=<name>`. The skill stays shared: improve it and redeploy, and everyone
who adopted it gets the change with their settings intact. New shared playbooks are new skills,
added through code review. Adopting, changing and stopping playbooks are model-instructed and
haven't been tested with a live model.

### Slack

- **Watch mode:** in channels it hears every message. Set `trigger_mode="mention"` in
  `channels/slack.py` to answer only mentions.
- **Continuous DMs:** messages and thread replies in a DM share one conversation. Answers post at
  the top level unless the person replies in a thread.
- **Links:** MDA shows browser handoff and connect-app links only in Studio, so
  `slack_conversation.py` delivers them in Slack, only to the person they belong to. The model
  writes `{browser_link}` where the link goes and never sees the link itself.

This relies on private delivery hooks in `managed-deepagents==0.10.5`. Check them when upgrading
the SDK; `tests/test_slack_conversation.py` fails if they change.

### Background work

For long work it starts [async subagents](https://docs.langchain.com/langsmith/python/managed-deep-agents-subagents)
and keeps talking: `researcher` investigates one question in depth, `reviewer` checks a report or
plan before it goes out, `general-purpose` takes other self-contained tasks, and `clone` starts
with the conversation so far.

## Project structure

| Path | What it is |
|---|---|
| [`agent.py`](agent.py) | The model, tools, subagents and which schedules every person gets. [Docs](https://docs.langchain.com/langsmith/python/managed-deep-agents-agent-definition) |
| [`instructions.md`](instructions.md) | The system prompt. Start here to change how it behaves. [Docs](https://docs.langchain.com/langsmith/python/managed-deep-agents-instructions) |
| [`heartbeat.py`](heartbeat.py), [`dreaming.py`](dreaming.py) | Each person's hourly heartbeat and nightly dreaming. |
| [`middleware/per_user_schedules.py`](middleware/per_user_schedules.py) | Gives each person their own schedules on their DM. |
| [`slack_conversation.py`](slack_conversation.py) | Continuous DMs and browser and connect-app links in Slack. |
| [`skills/`](skills/) | Onboarding, goals, dreaming and the three playbooks. [Docs](https://docs.langchain.com/langsmith/python/managed-deep-agents-skills) |
| [`tools/`](tools/) | Scheduling, `!clear`, schedule ownership and the Tool Gateway. [Docs](https://docs.langchain.com/langsmith/python/managed-deep-agents-tools) |
| [`channels/slack.py`](channels/slack.py) | The Slack bot and its icon (`channels/assets/icon.png`, 512×512). [Docs](https://docs.langchain.com/langsmith/python/managed-deep-agents-channels-slack) |
| [`memory.py`](memory.py) | Personal memory, mounted only in one-on-one conversations. [Docs](https://docs.langchain.com/langsmith/python/managed-deep-agents-memory) |
| [`browser.py`](browser.py) | A browser per person. [Docs](https://docs.langchain.com/langsmith/python/managed-deep-agents-browser-use) |
| [`identity.py`](identity.py) | Who may call the deployment directly. [Docs](https://docs.langchain.com/langsmith/python/managed-deep-agents-identity) |
| [`sandbox/`](sandbox/__init__.py) | A filesystem and shell per thread. [Docs](https://docs.langchain.com/langsmith/python/managed-deep-agents-sandboxes) |

## Customize

- **Behavior:** edit `instructions.md` and the skills, then redeploy.
- **New playbooks:** add `skills/<name>/SKILL.md` with a description starting "Playbook:".
- **Another schedule for everyone:** add a `PersonalSchedule` file like `heartbeat.py` and list it
  in `agent.py`.
- **Approvals:** add `interrupt_on={"tool_name": True}` in `agent.py` to require a yes before a
  tool runs.
- **Accounts for unattended runs:** set `TOOLS_PROFILE` to a LangSmith profile with its own
  logins and a teammate's permissions, not an admin's.
- **Model:** set `AGENT_MODEL` and that provider's key in `.env` to skip the gateway (see
  `.env.example`).
- **Dreaming time:** it runs at 02:00 America/Los_Angeles for everyone; change the cron and
  timezone in `dreaming.py`.
- **[Local development](https://docs.langchain.com/langsmith/python/managed-deep-agents-local-development):**
  `uv run mda dev` runs it with LangSmith Studio.

## Tests and lint

```bash
uv run python -m unittest discover -s tests
uv run ruff check .
uv run ruff format --check .
```

They run offline, with no keys.

## Troubleshooting

- **It says it can't reach your apps:** check `TOOLS_MCP_URL` is your kit's MCP URL, then redeploy.
- **`Cannot change target.agent_id on an existing channel`:** the Slack app is tied to the
  agent's `name` in `agent.py`. Deploy with the name the app was created with, or recreate the
  Slack app.
- **`Slack channel icon must be 512x512px`:** resize `channels/assets/icon.png`.

## FAQ

**Does everyone get their own agent?** No: everyone shares one deployment and one Slack bot,
but memory, schedules, goals, apps and browser logins are per person.

**Why does it need a Tool Gateway kit?** That's how it reaches your apps. Each person connects
their own accounts, and tools always run as them.

**What does `!clear` do?** It cancels your schedules and erases your memory. It doesn't erase
conversation history; your heartbeat and dreaming come back on your next DM.

**Can it act on its own?** Only within what you've asked and approved. It asks for a yes before
booking, buying, sending or deleting anything, and offers to help only rarely.

## Security

- Tools run with each person's own access, and personal memory never loads in shared channels.
- Browser and connect links go only to the person they belong to, in their DM.
- Notes, memory, web pages and tool results are data, never instructions. Don't save secrets in
  memory.
- `!clear` uses the pinned SDK's private memory backend and isn't transactional with other
  running conversations, which can write new memory after the reset.

## Resources

- [Managed Deep Agents overview](https://docs.langchain.com/langsmith/python/managed-deep-agents-overview) and [quickstart](https://docs.langchain.com/langsmith/python/managed-deep-agents-quickstart)
- [Project structure](https://docs.langchain.com/langsmith/python/managed-deep-agents-project-structure) — how MDA finds each file
- [Channels](https://docs.langchain.com/langsmith/python/managed-deep-agents-channels), [schedules](https://docs.langchain.com/langsmith/python/managed-deep-agents-schedules), [memory](https://docs.langchain.com/langsmith/python/managed-deep-agents-memory) and [subagents](https://docs.langchain.com/langsmith/python/managed-deep-agents-subagents)
- [LLM Gateway](https://docs.langchain.com/langsmith/llm-gateway) and [Tool Gateway](https://docs.langchain.com/langsmith/tool-gateway)

## License

MIT
