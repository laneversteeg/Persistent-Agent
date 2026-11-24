"""Slack in watch mode: every message starts a run; the agent replies `[quiet]` to skip.

Docs: https://docs.langchain.com/langsmith/python/managed-deep-agents-channels-slack
"""

from managed_deepagents import channels

from slack_conversation import ContinuousDirectMessages

channel = channels.slack(
    icon="assets/icon.png",
    trigger_mode="all",
    reactions=False,
    status=False,
)
channel = ContinuousDirectMessages(channel)
