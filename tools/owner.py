"""Whose schedule it is: the person who asked, so each person has their own.

Docs: https://docs.langchain.com/langsmith/python/managed-deep-agents-schedules
"""

from langgraph.config import get_config
from managed_deepagents import ManagedDeepAgentRuntime

# Not public yet: the run's route, which memory's allow(context) also gets. Pinned with
# managed-deepagents in pyproject.toml; check it on upgrade.
from managed_deepagents._managed_thread import current_run_thread

from memory import is_private


def owner(runtime: ManagedDeepAgentRuntime) -> dict:
    """The person in this run, or the agent when there's none."""
    info = runtime.server_info
    principal = info.principal if info else None
    if principal is not None and principal.kind == "person":
        return {"type": "user"}
    return {"type": "agent"}


def private(runtime: ManagedDeepAgentRuntime) -> bool:
    """Whether this run is someone's one-on-one conversation, as memory decides it.

    runtime.thread.origin.channel hides where the conversation posts. A scheduled run
    or a Studio resume has no live event, so it needs that target to tell a DM from a
    group. The run's route keeps it.
    """
    route = current_run_thread(runtime, get_config().get("configurable")).origin
    return route is not None and is_private({"channel": route})
