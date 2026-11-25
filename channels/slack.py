"""Slack in watch mode: every message starts a run; the agent replies `[quiet]` to skip.

Each message that starts a run gets an emoji reaction the agent's model picks, or
none. It runs alongside the reply, never delaying it; MDA falls back to :eyes: if
the model errors or takes over 5 seconds. Standard emoji only: to use your
workspace's custom emoji, have `choose_reaction` search them (Slack's emoji search
through Tool Gateway, connected for the agent) and offer the matches to the model.

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
_NAME = re.compile(r"[a-z0-9_+-]+")


@lru_cache(maxsize=1)
def _model():
    # A small, fast model: Haiku through the LLM Gateway, or the agent's own model when
    # AGENT_MODEL calls a provider directly. REACTION_MODEL overrides both.
    model = os.environ.get("REACTION_MODEL") or os.environ.get(
        "AGENT_MODEL", "langsmith:anthropic/claude-haiku-5-5"
    )
    return init_chat_model(model, max_tokens=50)


async def choose_reaction(context: dict) -> str | None:
    """The emoji the agent's model picks for this message, or None for no reaction."""
    reply = await _model().ainvoke(REACTION_PROMPT + context["text"][:2000])
    name = reply.text.strip().strip(":").lower()
    if name == "none" or not _NAME.fullmatch(name):
        return None
    return name


channel = channels.slack(
    icon="assets/icon.png",
    trigger_mode="all",
    reactions=choose_reaction,
    status=False,
)
channel = ContinuousDirectMessages(channel)
