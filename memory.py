"""Each person's memory (/memories/user/), mounted only in their Slack DMs.

Docs: https://docs.langchain.com/langsmith/python/managed-deep-agents-memory
"""

from collections.abc import Mapping

from managed_deepagents import MemoryLayer, define_memory


def _get(value: object, name: str) -> object:
    return value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)


def is_private(context: object) -> bool:
    """Whether this run is a one-to-one conversation. MDA has checked it's a person."""
    channel = _get(context, "channel")
    if _get(channel, "provider") != "slack":
        return False
    channel_type = _get(_get(channel, "raw_event"), "channel_type")
    if channel_type:
        return channel_type == "im"
    # A scheduled run has no Slack event, only where it posts; Slack DM ids start with D.
    conversation = _get(_get(_get(channel, "target"), "address"), "conversation_id")
    return isinstance(conversation, str) and conversation.startswith("D")


memory = define_memory(user=MemoryLayer(allow=is_private))
