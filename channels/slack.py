"""Slack in watch mode: every message starts a run; the agent replies `[quiet]` to skip.

Each message that starts a run also gets an emoji reaction a small, fast model picks,
or none. It runs alongside the reply, never delaying it; MDA falls back to :eyes: if
the model errors or takes over 5 seconds. Standard emoji only, so it works in any
workspace.

Docs: https://docs.langchain.com/langsmith/python/managed-deep-agents-channels-slack
"""

import os
import re
from functools import lru_cache

from langchain.chat_models import init_chat_model
from managed_deepagents import channels

from slack_conversation import ContinuousDirectMessages

REACTION_PROMPT = """\
You're the office jokester. React to this Slack message with one emoji. Reply
with only its Slack name, no colons, or none.

Message:
"""
HAIKU = "langsmith:anthropic/claude-haiku-5-5"
_NAME = re.compile(r"[a-z0-9_+-]+")


def reaction_model() -> str:
    """REACTION_MODEL if set; else AGENT_MODEL if it calls a provider directly (so no
    other key is needed); else Haiku through the LLM Gateway."""
    agent = os.environ.get("AGENT_MODEL", "")
    direct = agent if agent and not agent.startswith("langsmith:") else ""
    return os.environ.get("REACTION_MODEL") or direct or HAIKU


@lru_cache(maxsize=1)
def _model():
    return init_chat_model(reaction_model(), max_tokens=50)


async def choose_reaction(context: dict) -> str | None:
    """The emoji the model picks for this message, or None for no reaction."""
    reply = await _model().ainvoke(REACTION_PROMPT + context["text"][:2000])
    name = reply.text.strip().strip(":").lower()
    return name if name != "none" and _NAME.fullmatch(name) else None


channel = channels.slack(
    icon="assets/icon.png",
    trigger_mode="all",
    reactions=choose_reaction,
    status=False,
)
channel = ContinuousDirectMessages(channel)
