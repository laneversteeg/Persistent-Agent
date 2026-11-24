"""The Tool Gateway kit: the team's tools, searched rather than all loaded.

Kit tools run as the person talking, with their accounts; TOOLS_PROFILE runs them as a
profile's accounts instead. Without TOOLS_MCP_URL, the agent runs without it.

Docs:
- https://docs.langchain.com/langsmith/python/managed-deep-agents-mcp-connectors
- https://docs.langchain.com/langsmith/tool-gateway
"""

import os

from managed_deepagents import define_mcp

TOOLS_MCP_URL = os.environ.get("TOOLS_MCP_URL", "")
TOOLS_PROFILE = os.environ.get("TOOLS_PROFILE", "")

servers = {}
if TOOLS_MCP_URL:
    servers["tools"] = {
        "transport": "http",
        "url": f"{TOOLS_MCP_URL.split('?')[0]}?mode=search",
        "auth": {"type": "langsmith", "profile": TOOLS_PROFILE}
        if TOOLS_PROFILE
        else "langsmith",
    }

mcp = define_mcp(servers=servers)
