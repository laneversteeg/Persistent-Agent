"""Slack DMs as one continuous conversation, plus browser and connect links in Slack.

Three jobs, all on private hooks pinned to managed-deepagents 0.10.5 (see `install`):

- Routing: every message and thread reply in a DM shares one agent thread, while
  answers still post where the person wrote.
- Browser links: in a one-to-one DM, the link goes in the reply where the model
  wrote `{browser_link}`; from anywhere else it goes to the asker's DM. The model
  never sees the link.
- Connect links: a DM run paused to connect an app posts the connect links.

tests/test_slack_conversation.py fails if an SDK upgrade changes the hooks.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from functools import wraps
from typing import Any

from managed_deepagents._channel import Channel
from managed_deepagents._channels import assistant_text
from managed_deepagents._channels.schedule_delivery import (
    is_trusted_schedule_delivery_run,
)
from managed_deepagents._log import logger

__all__ = [
    "BROWSER_LINK",
    "UNSENT",
    "ContinuousDirectMessages",
    "continuous_dm",
    "dm_link",
    "install",
    "is_trusted_schedule_delivery_run",
    "route_event",
]

#: What the model writes where the browser link goes.
BROWSER_LINK = "{browser_link}"
#: Added to a channel reply whose browser link couldn't be sent to the asker's DM.
UNSENT = "I couldn't DM you the browser link. Message me directly and ask again."


def _handoff_text(url: str) -> str:
    return (
        f"<{url}|Open the browser>: it's yours for 15 minutes. Click *Hand back* when "
        "you're done. Anyone with this link can use the browser, so don't share it."
    )


def _connect_text(links: list[str]) -> str:
    return (
        f"I need access to your account for that. Connect {', '.join(links)}, "
        "then message me again and I'll pick it up."
    )


_TIMESTAMP = re.compile(r"\d+\.\d+\Z")
_SLACK_USER = re.compile(r"[UW][A-Z0-9]+\Z")


def _timestamp(value: object) -> str | None:
    return value if isinstance(value, str) and _TIMESTAMP.fullmatch(value) else None


def _field(value: object, name: str, default: Any = None) -> Any:
    """`value[name]` for a mapping, `value.name` for an object."""
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


# --- Routing: one conversation per DM ------------------------------------------------


@dataclass(frozen=True)
class ThreadKey:
    """A Slack thread key: `slack:v1:<team>:<app>:<conversation>:<thread>`.

    A DM's conversation ID starts with "D". The whole DM is thread "0".
    """

    team: str
    app: str
    conversation: str
    thread: str

    @classmethod
    def parse(cls, key: object) -> ThreadKey | None:
        parts = key.split(":") if isinstance(key, str) else []
        if len(parts) != 6 or parts[:2] != ["slack", "v1"]:
            return None
        return cls(*parts[2:])

    def whole_dm(self) -> ThreadKey:
        return replace(self, thread="0")

    def __str__(self) -> str:
        return f"slack:v1:{self.team}:{self.app}:{self.conversation}:{self.thread}"


def _dm(key: ThreadKey | None, address: object) -> str | None:
    """The DM's conversation ID, if `key` is a DM thread that matches `address`."""
    conversation = _field(address, "conversation_id")
    if key is None or not isinstance(conversation, str):
        return None
    if key.conversation != conversation or not conversation.startswith("D"):
        return None
    return conversation


def route_event(event: object) -> object:
    """Share a DM's backend conversation without changing its Slack reply address."""
    if not isinstance(event, dict):
        return event
    key = ThreadKey.parse(event.get("source_thread_key"))
    if (conversation := _dm(key, event.get("address"))) is None:
        return event
    routed = {**event, "source_thread_key": str(key.whole_dm())}
    if event.get("type") != "message":
        return routed
    raw = event.get("raw_event")
    if not isinstance(raw, dict) or not (ts := _timestamp(raw.get("ts"))):
        return event
    root = _timestamp(raw.get("thread_ts")) or ts
    routed["address"] = {**event["address"], "thread_id": root}
    if isinstance(text := raw.get("text"), str):
        # Only the new message: the agent thread already holds the conversation.
        message = {
            "role": "user",
            "content": text,
            "id": f"slack:{conversation}:{ts}",
            "additional_kwargs": {
                "slack_message": {
                    "channel_id": conversation,
                    "message_ts": ts,
                    "thread_ts": root,
                }
            },
        }
        routed["input"] = {"messages": [message]}
    return routed


class ContinuousDirectMessages(Channel):
    """The stock Slack channel, with DM events routed to one conversation."""

    kind = "slack"
    transport = "trigger_server"

    def __init__(self, delegate: Channel) -> None:
        self._delegate = delegate

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    async def events(self, ctx: Mapping[str, Any]) -> Any:
        context = dict(ctx)
        body = context.get("raw_body")
        if body is None:
            body = await context["request"].body()
        context["raw_body"] = body
        try:
            event = json.loads(body)
        except (TypeError, ValueError, UnicodeDecodeError):
            pass
        else:
            if (routed := route_event(event)) is not event:
                context["raw_body"] = json.dumps(routed)
        return await self._delegate.events(context)


def continuous_dm(binding: object) -> str | None:
    """The DM's conversation ID, only for this channel's whole-DM conversation."""
    if not (
        _field(binding, "name") == "slack"
        and _field(binding, "provider") == "slack"
        and _field(binding, "transport") == "trigger_server"
        and isinstance(target := _field(binding, "target"), Mapping)
    ):
        return None
    key = ThreadKey.parse(_field(binding, "source_thread_key"))
    if key is None or key.thread != "0":
        return None
    return _dm(key, target.get("address"))


def _latest_slack_message(messages: list, conversation: str) -> Mapping | None:
    """The newest person's message in the run that came from this DM."""
    for message in reversed(messages):
        if _field(message, "type", _field(message, "role")) not in {"human", "user"}:
            continue
        source = (_field(message, "additional_kwargs") or {}).get("slack_message")
        if (
            isinstance(source, Mapping)
            and source.get("channel_id") == conversation
            and _timestamp(source.get("message_ts"))
        ):
            return source
    return None


def _reply_binding(binding: Any, values: Mapping, config: Mapping) -> Any:
    """Post scheduled DM updates at top level; respect explicit human thread replies."""
    if (conversation := continuous_dm(binding)) is None:
        return binding
    address = {"conversation_id": conversation}
    if not is_trusted_schedule_delivery_run(
        config.get("configurable"), config.get("metadata")
    ):
        source = _latest_slack_message(values.get("messages", []), conversation)
        if source is None:
            return binding
        root = _timestamp(source.get("thread_ts"))
        if root and root != source["message_ts"]:
            address["thread_id"] = root
    return {**binding, "target": {**binding["target"], "address": address}}


# --- Browser links ------------------------------------------------------------------


@dataclass(frozen=True)
class Handoff:
    """A browser handoff: the link, and the agent's instructions for the person."""

    url: str
    reason: str = ""


@dataclass(frozen=True)
class ReplyLinks:
    """What the reply being posted needs: the link to fill in, or a note it wasn't sent."""

    url: str | None = None
    unsent: str | None = None


_NO_LINKS = ReplyLinks()
_REPLY_LINKS: ContextVar[ReplyLinks] = ContextVar("reply_links", default=_NO_LINKS)


@contextmanager
def _reply_links(links: ReplyLinks) -> Iterator[None]:
    token = _REPLY_LINKS.set(links)
    try:
        yield
    finally:
        _REPLY_LINKS.reset(token)


def _handoff(messages: object, after_id: str | None) -> Handoff | None:
    """The latest browser handoff this run made, if any.

    MDA keeps the link in the tool result's artifact, out of the model's sight.
    """
    if not isinstance(messages, list):
        return None
    start = assistant_text._run_start(messages, after_id)
    if start is None:
        start = assistant_text._last_user_message(messages)
    for message in reversed(messages[start:]):
        artifact = _field(message, "artifact")
        if isinstance(artifact, Mapping) and artifact.get("type") == "browser_handoff":
            reason = artifact.get("message")
            return Handoff(
                artifact.get("url"), reason if isinstance(reason, str) else ""
            )
    return None


def _with_browser_link(text: str, links: ReplyLinks) -> str:
    """Fill the model's `{browser_link}` with the link, or drop it without one.

    A reply that has none gets the link after it, or alone in place of `[quiet]`.
    """
    if BROWSER_LINK in text or not links.url:
        link = f"<{links.url}|browser link>" if links.url else ""
        text = text.replace(BROWSER_LINK, link).strip()
        return f"{text}\n\n{links.unsent}".strip() if links.unsent else text
    if text.strip() in {"", assistant_text.QUIET_REPLY}:
        return _handoff_text(links.url)
    return f"{text}\n\n{_handoff_text(links.url)}"


def _slack_sender(binding: object) -> str | None:
    """The Slack user whose message started this run, from the raw Slack event."""
    user = _field(_field(binding, "raw_event"), "user")
    return user if isinstance(user, str) and _SLACK_USER.match(user) else None


async def dm_link(binding: Mapping, user: str, url: str, reason: str = "") -> bool:
    """Post a handoff link, after the agent's `reason`, to `user`'s DM with the app.

    Returns whether it was posted. The post names only the person, never the channel
    thread the run came from, so it cannot land there.
    """
    from managed_deepagents._channels.trigger.client import create_trigger_client
    from managed_deepagents._channels.trigger.transport import TriggerTransport

    try:
        if (client := create_trigger_client()) is None:
            return False
        await TriggerTransport(client).post(
            message={
                "type": "content",
                "content": f"{reason.strip()}\n\n{_handoff_text(url)}".strip(),
            },
            target={
                "channel_id": binding["target"]["channel_id"],
                "address": {"conversation_id": user},
                "source_thread_key": "",
            },
            new_thread=True,
        )
    except Exception as error:  # noqa: BLE001 - the channel reply says it wasn't sent
        logger.warning("browser link DM failed (%s)", type(error).__name__)
        return False
    return True


async def _browser_links(origin: object, handoff: Handoff | None) -> ReplyLinks:
    """Where this run's browser link goes.

    It lets whoever holds it drive the browser, so it goes in the reply only in a
    one-to-one DM, and from anywhere else to the asker's own DM.
    """
    if handoff is None:
        return _NO_LINKS
    if continuous_dm(origin) is not None:
        return ReplyLinks(url=handoff.url)
    user = _slack_sender(origin)
    sent = user is not None and await dm_link(origin, user, handoff.url, handoff.reason)
    return _NO_LINKS if sent else ReplyLinks(unsent=UNSENT)


# --- Connect links ------------------------------------------------------------------


def _connect_links(pending: list) -> str | None:
    """What to post for a run paused until its person connects an app, if it is."""
    links = []
    for item in pending:
        value = getattr(item, "value", None)
        if _field(value, "type") != "credential_authorization_required":
            continue
        for credential in _field(value, "credentials") or []:
            url = _field(credential, "connect_url")
            if isinstance(url, str) and url.startswith("https://"):
                name = (
                    _field(credential, "provider")
                    or _field(credential, "slug")
                    or "account"
                )
                links.append(f"<{url}|{name}>")
    return _connect_text(links) if links else None


# --- Installing the hooks -----------------------------------------------------------


def _patch(module: object, name: str, wrap: Any) -> None:
    """Replace `module.name` with `wrap(original)`; already patched, do nothing."""
    original = getattr(module, name)
    if getattr(original, "_persistent_agent", False) is True:
        return
    patched = wraps(original)(wrap(original))
    patched._persistent_agent = True
    setattr(module, name, patched)


def install() -> None:
    """Wrap the pinned SDK's reply and pause delivery for continuous DMs and links."""
    from managed_deepagents._channels import delivery

    def extract_reply_text(original):
        def extract(run, *, after_id=None):
            return _with_browser_link(
                original(run, after_id=after_id), _REPLY_LINKS.get()
            )

        return extract

    def deliver_answer(original):
        async def deliver(run, config, final, boundary, *, opening, deliver_to):
            links = _NO_LINKS
            if opening is None:
                values = final.values if isinstance(final.values, Mapping) else {}
                if (
                    binding := _reply_binding(run.origin, values, config)
                ) is not run.origin:
                    run = replace(run, origin=binding)
                messages = values.get("messages")
                handoff = _handoff(messages, delivery.run_boundary(boundary, messages))
                links = await _browser_links(run.origin, handoff)
            with _reply_links(links):
                return await original(
                    run, config, final, boundary, opening=opening, deliver_to=deliver_to
                )

        return deliver

    def deliver_pause(original):
        async def deliver(run, config, opening, pending):
            # The stock pause card doesn't reach a continuous DM, so post the connect
            # links as a reply. Only a one-to-one DM: each link is that person's.
            conversation = continuous_dm(run.origin) if opening is None else None
            if conversation and (text := _connect_links(pending)) is not None:
                target = {
                    **run.origin["target"],
                    "address": {"conversation_id": conversation},
                }
                origin = {**run.origin, "target": target}
                await delivery._post_trigger(origin, text, delivery.run_id_of(config))
            return await original(run, config, opening, pending)

        return deliver

    _patch(delivery, "extract_reply_text", extract_reply_text)
    _patch(delivery, "_deliver_answer", deliver_answer)
    _patch(delivery, "_deliver_pause", deliver_pause)
