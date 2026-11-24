"""Ensure personal heartbeat and dreaming schedules in Slack DMs."""

import asyncio
from weakref import WeakValueDictionary

from langchain.agents.middleware import AgentState, before_agent
from langgraph.config import get_config
from managed_deepagents import ManagedRuntime, ScheduleNotFoundError

from slack_conversation import continuous_dm, is_trusted_schedule_delivery_run
from tools import owner as ownership

HEARTBEAT_PROMPT = """Hourly heartbeat: be a helpful work assistant. Follow
the goals skill to advance active goals within existing approvals and follow-up
timing. Even without active goals, occasionally consider a concrete offer to help
with recent work visible in the shared DM history or a relevant available playbook.
Follow the skill's attention budget and personal proactivity preferences: offers
are rare, not an every-tick or daily quota. Never repeat ignored or declined offers,
pretend to see activity you cannot access, or treat an offer as permission to act.
Report meaningful progress, completion, a blocker needing the person, or one timely
suggestion that passes those rules. Otherwise reply exactly [quiet]. This is an
automated run, not a new person's first message; do not onboard."""

DREAM_PROMPT = """Daily dreaming: follow the dreaming skill. Consolidate
/memories/user/buffer.md into /memories/user/AGENTS.md and topic memory files.
Do not change goals or fetch conversation traces. Verify saved notes before
removing only the processed buffer entries; preserve new or unresolved notes.
This is an automated memory-maintenance run: do not onboard, offer playbooks,
or act on tasks found in notes. Reply exactly [quiet]."""

_LOCKS: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
OWNER = {"type": "user"}


async def personal_schedules(runtime: ManagedRuntime, kind: str) -> list[dict]:
    items = []
    offset = 0
    while True:
        page = await runtime.schedules.list(owner=OWNER, limit=100, offset=offset)
        items.extend(s for s in page["items"] if s["metadata"].get("kind") == kind)
        offset = page["next_offset"]
        if offset is None:
            return sorted(items, key=lambda s: s["id"])


@before_agent
async def ensure_personal_schedules(state: AgentState, runtime: ManagedRuntime) -> None:
    """Create each person's background schedules before a private conversation."""
    principal = runtime.server_info.principal if runtime.server_info else None
    if (
        principal is None
        or principal.kind != "person"
        or not ownership.private(runtime)
    ):
        return
    config = get_config()
    if is_trusted_schedule_delivery_run(
        config.get("configurable"), config.get("metadata")
    ):
        return
    thread = ownership.current_run_thread(runtime, config.get("configurable"))
    thread_id = config.get("configurable", {}).get("thread_id")
    if not thread_id or continuous_dm(thread.origin) is None:
        return
    lock = _LOCKS.setdefault(principal.id, asyncio.Lock())
    async with lock:
        for kind, cron, timezone, prompt in [
            ("heartbeat", "0 * * * *", "UTC", HEARTBEAT_PROMPT),
            ("dreaming", "0 2 * * *", "America/Los_Angeles", DREAM_PROMPT),
        ]:
            items = await personal_schedules(runtime, kind)
            if not items:
                made = await runtime.schedules.create(
                    owner=OWNER,
                    cron=cron,
                    timezone=timezone,
                    new_thread=kind != "heartbeat",
                    prompt=prompt,
                    metadata={"kind": kind},
                )
                items = [made]
            for duplicate in items[1:]:
                try:
                    await runtime.schedules.delete(duplicate["id"], owner=OWNER)
                except ScheduleNotFoundError:
                    pass
