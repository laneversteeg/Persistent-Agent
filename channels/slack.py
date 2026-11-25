"""Slack in watch mode: every message starts a run; the agent replies `[quiet]` to skip.

Each message that starts a run also gets an emoji reaction a small, fast model picks,
or none. It runs alongside the reply, never delaying it; MDA falls back to :eyes: if
the model errors or takes over 5 seconds.

Docs: https://docs.langchain.com/langsmith/python/managed-deep-agents-channels-slack
"""

import os
import re
from functools import lru_cache

from langchain.chat_models import init_chat_model
from managed_deepagents import channels

from slack_conversation import ContinuousDirectMessages

# Standard emoji only. If you connect the Slack integration, you can prompt it here to
# use your workspace's custom Slack emoji too.
REACTION_PROMPT = """\
React to this Slack message with one emoji. Be creative. Reply with only its name,
like tada, or none.

Message:
"""

# Haiku from the agent's provider; another provider's model reacts with itself.
HAIKU = {
    "anthropic": "anthropic:claude-haiku-5-5",
    "langsmith": "langsmith:anthropic/claude-haiku-5-5",
}


def reaction_model() -> str:
    """REACTION_MODEL if set, else a small model from AGENT_MODEL's provider."""
    agent = os.environ.get("AGENT_MODEL", "langsmith:anthropic/claude-opus-5-5")
    return os.environ.get("REACTION_MODEL") or HAIKU.get(agent.split(":")[0], agent)


@lru_cache(maxsize=1)
def _model():
    return init_chat_model(reaction_model(), max_tokens=50)


async def choose_reaction(context: dict) -> str | None:
    """The emoji the model picks for this message, or None for no reaction."""
    reply = await _model().ainvoke(REACTION_PROMPT + context["text"][:2000])
    name = reply.text.strip().strip(":").lower()
    return name if name != "none" and re.fullmatch(r"[a-z0-9_+-]+", name) else None


channel = channels.slack(
    icon="assets/icon.png",
    trigger_mode="all",
    reactions=choose_reaction,
    status=False,
)
channel = ContinuousDirectMessages(channel)
