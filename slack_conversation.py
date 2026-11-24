"""One continuous conversation per Slack DM, on private hooks pinned to MDA 0.10.5."""

import json
import re
from collections.abc import Mapping
from contextvars import ContextVar
from dataclasses import replace
from functools import wraps

from managed_deepagents._channel import Channel
from managed_deepagents._channels import assistant_text
from managed_deepagents._channels.schedule_delivery import (
    is_trusted_schedule_delivery_run,
)
from managed_deepagents._log import logger

_TIMESTAMP = re.compile(r"\d+\.\d+\Z")


def _timestamp(value):
    return value if isinstance(value, str) and _TIMESTAMP.fullmatch(value) else None


def _conversation(key, address):
    if not isinstance(key, str) or not isinstance(address, Mapping):
        return None
    conversation = address.get("conversation_id")
    parts = key.split(":")
    if (
        isinstance(conversation, str)
        and conversation.startswith("D")
        and len(parts) == 6
        and parts[:2] == ["slack", "v1"]
        and parts[4] == conversation
    ):
        return conversation
    return None


def route_event(event):
    """Share a DM's backend conversation without changing its Slack reply address."""
    if not isinstance(event, dict):
        return event
    conversation = _conversation(event.get("source_thread_key"), event.get("address"))
    if conversation is None:
        return event
    routed = {
        **event,
        "source_thread_key": ":".join(
            [*event["source_thread_key"].split(":")[:-1], "0"]
        ),
    }
    if event.get("type") == "message":
        raw = event.get("raw_event")
        if not isinstance(raw, dict) or not (ts := _timestamp(raw.get("ts"))):
            return event
        root = _timestamp(raw.get("thread_ts")) or ts
        routed["address"] = {**event["address"], "thread_id": root}
        if isinstance(text := raw.get("text"), str):
            routed["input"] = {
                "messages": [
                    {
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
                ]
            }
    return routed


class ContinuousDirectMessages(Channel):
    """Delegate Slack authentication and lifecycle delivery to the stock channel."""

    kind = "slack"
    transport = "trigger_server"

    def __init__(self, delegate):
        self._delegate = delegate

    def __getattr__(self, name):
        return getattr(self._delegate, name)

    async def events(self, ctx):
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
            routed = route_event(event)
            if routed is not event:
                context["raw_body"] = json.dumps(routed)
        return await self._delegate.events(context)


def continuous_dm(binding):
    """Return the DM ID only for this channel's canonical continuous conversation."""
    if not isinstance(binding, Mapping):
        return None
    target = binding.get("target")
    key = binding.get("source_thread_key")
    if (
        binding.get("name") == "slack"
        and binding.get("provider") == "slack"
        and binding.get("transport") == "trigger_server"
        and isinstance(target, Mapping)
        and isinstance(key, str)
        and key.endswith(":0")
    ):
        return _conversation(key, target.get("address"))
    return None


def _field(value, name, default=None):
    return (
        value.get(name, default)
        if isinstance(value, Mapping)
        else getattr(value, name, default)
    )


def reply_binding(binding, values, config):
    """Post scheduled DM updates at top level; respect explicit human thread replies."""
    if (conversation := continuous_dm(binding)) is None:
        return binding
    address = {"conversation_id": conversation}
    if not is_trusted_schedule_delivery_run(
        config.get("configurable"), config.get("metadata")
    ):
        for message in reversed(values.get("messages", [])):
            if _field(message, "type", _field(message, "role")) not in {
                "human",
                "user",
            }:
                continue
            source = (_field(message, "additional_kwargs", {}) or {}).get(
                "slack_message"
            )
            if (
                not isinstance(source, Mapping)
                or source.get("channel_id") != conversation
            ):
                continue
            if not (ts := _timestamp(source.get("message_ts"))):
                continue
            if (root := _timestamp(source.get("thread_ts"))) and root != ts:
                address["thread_id"] = root
            break
        else:
            return binding
    return {**binding, "target": {**binding["target"], "address": address}}


def handoff_link(messages, after_id=None):
    """The latest browser handoff this run made, as ``(url, reason)``, if any.

    MDA keeps the link in the tool result's artifact, out of the model's sight, and
    only clients such as Studio render it; Slack gets the answer text alone.
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
            return artifact.get("url"), reason if isinstance(reason, str) else ""
    return None


#: What the model writes where the browser link goes; it never sees the link itself.
BROWSER_LINK = "{browser_link}"
#: The link of the run being delivered, set only for a one-to-one DM.
_HANDOFF_URL = ContextVar("handoff_url", default=None)
#: Added to a channel reply whose browser link couldn't be sent to the person's DM.
_UNSENT_NOTE = ContextVar("unsent_note", default=None)
UNSENT = "I couldn't DM you the browser link. Message me directly and ask again."
_SLACK_USER = re.compile(r"[UW][A-Z0-9]+\Z")


def handoff_text(url):
    return (
        f"<{url}|Open the browser>: it's yours for 15 minutes. Click *Hand back* when "
        "you're done. Anyone with this link can use the browser, so don't share it."
    )


def with_browser_link(text, url, unsent=None):
    """Fill the model's ``{browser_link}`` with ``url``, or drop it without one.

    A reply that has none gets the link after it, or alone in place of ``[quiet]``.
    ``unsent`` is added when the link should have gone to a DM and didn't.
    """
    if BROWSER_LINK in text or not url:
        text = text.replace(
            BROWSER_LINK, f"<{url}|browser link>" if url else ""
        ).strip()
        return f"{text}\n\n{unsent}".strip() if unsent else text
    if text.strip() in {"", assistant_text.QUIET_REPLY}:
        return handoff_text(url)
    return f"{text}\n\n{handoff_text(url)}"


def slack_sender(binding):
    """The Slack user whose message started this run, from the raw Slack event."""
    raw = binding.get("raw_event") if isinstance(binding, Mapping) else None
    user = raw.get("user") if isinstance(raw, Mapping) else None
    return user if isinstance(user, str) and _SLACK_USER.match(user) else None


async def dm_link(binding, user, url, reason=""):
    """Post a handoff link, after the agent's ``reason``, to ``user``'s DM with the
    app; whether it was posted.

    The post names only the person, never the channel thread the run came from,
    so it cannot land there.
    """
    from managed_deepagents._channels.trigger.client import create_trigger_client
    from managed_deepagents._channels.trigger.transport import TriggerTransport

    try:
        target = {
            "channel_id": binding["target"]["channel_id"],
            "address": {"conversation_id": user},
            "source_thread_key": "",
        }
        client = create_trigger_client()
        if client is None:
            return False
        await TriggerTransport(client).post(
            message={
                "type": "content",
                "content": f"{reason.strip()}\n\n{handoff_text(url)}".strip(),
            },
            target=target,
            new_thread=True,
        )
    except Exception as error:  # noqa: BLE001 - the channel reply says it wasn't sent
        logger.warning("browser link DM failed (%s)", type(error).__name__)
        return False
    return True


def connect_text(pending):
    """What to post for a run paused until its person connects an account, if it is."""
    links = []
    for item in pending:
        value = getattr(item, "value", None)
        if not (
            isinstance(value, Mapping)
            and value.get("type") == "credential_authorization_required"
        ):
            continue
        for credential in value.get("credentials") or []:
            url = (
                credential.get("connect_url")
                if isinstance(credential, Mapping)
                else None
            )
            if isinstance(url, str) and url.startswith("https://"):
                name = credential.get("provider") or credential.get("slug") or "account"
                links.append(f"<{url}|{name}>")
    if not links:
        return None
    return (
        f"I need access to your account for that. Connect {', '.join(links)}, "
        "then message me again and I'll pick it up."
    )


def install():
    """Wrap the pinned SDK's answer and pause delivery until session and reply routes
    are separate."""
    from managed_deepagents._channels import delivery

    original = delivery._deliver_answer
    if getattr(original, "_persistent_agent_dm", False) is True:
        return
    reply_text = getattr(
        delivery.extract_reply_text, "__wrapped__", delivery.extract_reply_text
    )

    @wraps(reply_text)
    def extract_reply_text(run, *, after_id=None):
        text = reply_text(run, after_id=after_id)
        return with_browser_link(text, _HANDOFF_URL.get(), _UNSENT_NOTE.get())

    @wraps(original)
    async def deliver_answer(run, config, final, boundary, *, opening, deliver_to):
        url = unsent = None
        if opening is None:
            values = final.values if isinstance(final.values, Mapping) else {}
            binding = reply_binding(run.origin, values, config)
            if binding is not run.origin:
                run = replace(run, origin=binding)
            messages = values.get("messages")
            handoff = handoff_link(messages, delivery.run_boundary(boundary, messages))
            # The link lets whoever holds it drive the browser: it goes in the reply
            # only in a one-to-one DM, and from anywhere else to the asker's DM.
            if handoff and continuous_dm(run.origin) is not None:
                url = handoff[0]
            elif handoff and not (
                (user := slack_sender(run.origin))
                and await dm_link(run.origin, user, *handoff)
            ):
                unsent = UNSENT
        tokens = _HANDOFF_URL.set(url), _UNSENT_NOTE.set(unsent)
        try:
            return await original(
                run, config, final, boundary, opening=opening, deliver_to=deliver_to
            )
        finally:
            _HANDOFF_URL.reset(tokens[0])
            _UNSENT_NOTE.reset(tokens[1])

    pause = getattr(delivery._deliver_pause, "__wrapped__", delivery._deliver_pause)

    @wraps(pause)
    async def deliver_pause(run, config, opening, pending):
        # The stock pause card doesn't reach a continuous DM, so post the connect
        # links as a reply. Only a one-to-one DM: each link is that person's.
        if opening is None and (conversation := continuous_dm(run.origin)):
            if (text := connect_text(pending)) is not None:
                address = {"conversation_id": conversation}
                origin = {
                    **run.origin,
                    "target": {**run.origin["target"], "address": address},
                }
                await delivery._post_trigger(origin, text, delivery.run_id_of(config))
        return await pause(run, config, opening, pending)

    deliver_answer._persistent_agent_dm = True
    delivery._deliver_answer = deliver_answer
    delivery._deliver_pause = deliver_pause
    delivery.extract_reply_text = extract_reply_text
