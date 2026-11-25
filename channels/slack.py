"""Slack in watch mode: every message starts a run; the agent replies `[quiet]` to skip.

Each message that starts a run also gets an emoji reaction a small, fast model picks.
It runs alongside the reply, never delaying it; :eyes: when the model's answer isn't a
standard emoji, and MDA's fallback when it errors or takes over 5 seconds.

Docs: https://docs.langchain.com/langsmith/python/managed-deep-agents-channels-slack
"""

import os
from functools import lru_cache

from emoji_data_python import emoji_data
from langchain.chat_models import init_chat_model
from managed_deepagents import channels

from slack_conversation import ContinuousDirectMessages

# Standard emoji only. If you connect the Slack integration, you can prompt it here to
# use your workspace's custom Slack emoji too.
REACTION_PROMPT = """\
React to this Slack message with one emoji. Be creative. Reply with only the emoji.

Message:
"""

# Slack's name for each standard emoji (Slack uses the emoji-data set): 🤔 -> thinking_face.
SLACK_NAMES = {e.char.replace("\ufe0f", ""): e.short_name for e in emoji_data}

# Haiku from the agent's provider; another provider's model reacts with itself.
HAIKU = {
    "anthropic": "anthropic:claude-haiku-5-5",
    "langsmith": "langsmith:anthropic/claude-haiku-5-5",
}


def reaction_model() -> str:
    """REACTION_MODEL if set, else a small model from AGENT_MODEL's provider."""
    agent = (
        os.environ.get("AGENT_MODEL") or "anthropic:claude-opus-5-5"
    )  # as in agent.py
    return os.environ.get("REACTION_MODEL") or HAIKU.get(agent.split(":")[0], agent)


@lru_cache(maxsize=1)
def _model():
    return init_chat_model(reaction_model(), max_tokens=50)


async def choose_reaction(context: dict) -> str:
    """Slack's name for the emoji the model picks, or eyes if it isn't a standard emoji."""
    reply = await _model().ainvoke(REACTION_PROMPT + context["text"][:2000])
    return SLACK_NAMES.get(reply.text.strip().replace("\ufe0f", ""), "eyes")


channel = channels.slack(
    icon="assets/icon.png",
    trigger_mode="all",
    reactions=choose_reaction,
    status=False,
)
channel = ContinuousDirectMessages(channel)
