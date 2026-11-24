"""A filesystem and shell per thread. Add sandbox/setup.sh to customize the image.

Docs: https://docs.langchain.com/langsmith/python/managed-deep-agents-sandboxes
"""

from managed_deepagents import define_sandbox

sandbox = define_sandbox(idle_ttl_seconds=1800, default_timeout=600)
