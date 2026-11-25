"""connect_apps: which apps the person has connected, and sign-in links for the rest.

Asks Tool Gateway's connections API for the kit, as the person in the run, the way MDA
calls Tool Gateway for their tools: the deployment's key and X-LangSmith-Identity. The
links come back to the model, so it can put them in its reply without pausing the run.
Only in the person's one-on-one DM: a link connects whoever opens it as this person.

Docs: https://docs.langchain.com/langsmith/tool-gateway-call-tools#connect-when-a-call-asks
"""

import asyncio
import re

import httpx
from langchain.tools import tool
from managed_deepagents import ManagedDeepAgentRuntime
from managed_deepagents._credential_gate import connecting_caller
from managed_deepagents._tool_gateway.auth import (
    langsmith_headers,
    tool_gateway_context,
)

from tools.mcp import TOOLS_MCP_URL
from tools.owner import private

KIT_ID = (re.search(r"/kits/([^/?]+)/mcp", TOOLS_MCP_URL) or [None, ""])[1]


@tool
async def connect_apps(runtime: ManagedDeepAgentRuntime) -> str:
    """List the apps the person has connected, and a sign-in link for each one they haven't.

    Put the links in your reply as is; each one is for this person only. Works only in
    their DM.
    """
    if not KIT_ID:
        return "No tool kit is set up (TOOLS_MCP_URL)."
    if not private(runtime):
        return "Sign-in links only go out in the person's DM."
    if (caller := connecting_caller(runtime)) is None:
        return "There's no person in this run to connect apps for."
    context = tool_gateway_context(caller.context)
    headers = langsmith_headers(context, None)
    url = f"{context.base_url.rstrip('/')}/v1/managed-tools/kits/{KIT_ID}/connections"

    async with httpx.AsyncClient(headers=headers, timeout=20) as client:
        servers, cursor = [], None
        while True:
            params = {"page_size": 100} | ({"cursor": cursor} if cursor else {})
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return f"Couldn't check connections: HTTP {response.status_code}."
            page = response.json()
            servers += page.get("items") or []
            if not (cursor := page.get("next_cursor")):
                break

        missing = [s for s in servers if not s.get("connected")]
        started = await asyncio.gather(
            *(client.post(f"{url}/{s['id']}") for s in missing)
        )

    connected = [s["name"] for s in servers if s.get("connected")]
    links: dict[str, tuple[str, list[str]]] = {}  # connection slug -> (link, app names)
    failed = []
    for server, response in zip(missing, started, strict=True):
        if response.status_code == 204:
            connected.append(server["name"])
        elif response.status_code == 201 and (session := response.json()).get(
            "verification_url"
        ):
            # Apps that share one account (all of Google) share one sign-in.
            entry = links.setdefault(session["slug"], (session["verification_url"], []))
            entry[1].append(server["name"])
        else:
            failed.append(f"{server['name']} (HTTP {response.status_code})")

    lines = [f"Connected: {', '.join(sorted(connected)) or 'none'}."]
    lines += [
        f"Sign in to {' / '.join(names)}: {link}" for link, names in links.values()
    ]
    if failed:
        lines.append(f"Couldn't get a link for: {', '.join(failed)}.")
    return "\n".join(lines)
