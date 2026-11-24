"""Direct API callers need a LangSmith API key; channel users are identified by their channel.

Docs: https://docs.langchain.com/langsmith/python/managed-deep-agents-identity
"""

from managed_deepagents import auth, define_identity

identity = define_identity(auth=auth.langsmith_api_key())
