"""One browser per person, so their logins last across their conversations.

Docs: https://docs.langchain.com/langsmith/python/managed-deep-agents-browser-use
"""

from managed_deepagents import define_browser

browser = define_browser(scope="user", idle_ttl_seconds=900)
