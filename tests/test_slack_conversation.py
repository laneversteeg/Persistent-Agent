"""Exercise continuous DM routing and final delivery through the pinned SDK."""

import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain.messages import AIMessage, HumanMessage, ToolMessage
from managed_deepagents._channels import delivery
from managed_deepagents._managed_thread import RunThread

import slack_conversation
from slack_conversation import (
    UNSENT,
    ContinuousDirectMessages,
    dm_link,
    install,
    route_event,
)


class ConversationTests(unittest.IsolatedAsyncioTestCase):
    def event(self, *, conversation="D123", workspace="T123", root=None, ts="2.0"):
        return {
            "type": "message",
            "source_thread_key": f"slack:v1:{workspace}:A123:{conversation}:{root or ts}",
            "address": {"conversation_id": conversation, "thread_id": root or ts},
            "raw_event": {
                "ts": ts,
                "text": "yes",
                **({"thread_ts": root} if root else {}),
            },
            "input": {"messages": [{"role": "user", "content": "old transcript"}]},
            "sender": {"id": "U123"},
        }

    def binding(self, *, conversation="D123", canonical=True):
        return {
            "name": "slack",
            "provider": "slack",
            "transport": "trigger_server",
            "source_thread_key": f"slack:v1:T123:A123:{conversation}:{'0' if canonical else '1.0'}",
            "target": {
                "address": {"conversation_id": conversation, "thread_id": "1.0"}
            },
        }

    async def test_dm_turns_share_history_without_repeating_slack_transcripts(self):
        delegate = SimpleNamespace(events=AsyncMock(return_value="accepted"))
        channel = ContinuousDirectMessages(delegate)
        seen = []
        for event in [self.event(), self.event(root="2.0", ts="3.0")]:
            original = deepcopy(event)
            self.assertEqual(
                await channel.events({"raw_body": json.dumps(event)}), "accepted"
            )
            routed = json.loads(delegate.events.call_args.args[0]["raw_body"])
            seen.append(routed["source_thread_key"])
            self.assertEqual(routed["raw_event"], original["raw_event"])
            self.assertEqual(routed["sender"], original["sender"])
            self.assertEqual(len(routed["input"]["messages"]), 1)
            message = routed["input"]["messages"][0]
            self.assertEqual(message["content"], "yes")
            self.assertEqual(message["id"], f"slack:D123:{event['raw_event']['ts']}")
            self.assertEqual(
                message["additional_kwargs"]["slack_message"]["thread_ts"],
                event["address"]["thread_id"],
            )
            self.assertEqual(event, original)
        self.assertEqual(seen, ["slack:v1:T123:A123:D123:0"] * 2)

    async def test_rooms_and_workspaces_stay_separate_and_malformed_events_pass_through(
        self,
    ):
        keys = {
            route_event(event)["source_thread_key"]
            for event in [
                self.event(),
                self.event(conversation="D456"),
                self.event(workspace="T456"),
                {**self.event(), "source_thread_key": "slack:v1:T123:A456:D123:2.0"},
            ]
        }
        self.assertEqual(len(keys), 4)
        mismatch = self.event()
        mismatch["address"]["conversation_id"] = "D456"
        for event in [
            self.event(conversation="C123"),
            self.event(conversation="G123"),
            mismatch,
            {},
            None,
            {**self.event(), "raw_event": {}},
        ]:
            self.assertIs(route_event(event), event)
        delegate = SimpleNamespace(events=AsyncMock())
        await ContinuousDirectMessages(delegate).events({"raw_body": b"not json"})
        self.assertEqual(delegate.events.call_args.args[0]["raw_body"], b"not json")

    async def deliver(
        self, *, text="Done", root=None, scheduled=False, binding=None, handoff=None
    ):
        binding = self.binding() if binding is None else binding
        original = deepcopy(binding)
        config = {
            "configurable": {"langgraph_auth_user": {"mda_scheduled_run": scheduled}},
            "metadata": {"mda_managed": scheduled},
        }
        human = HumanMessage(
            "Please help",
            id="person-message",
            additional_kwargs={
                "slack_message": {
                    "channel_id": "D123",
                    "message_ts": "2.0",
                    "thread_ts": root or "2.0",
                }
            },
        )
        messages = [human]
        if scheduled:
            messages.append(HumanMessage("Hourly heartbeat", id="tick"))
        if handoff is not None:
            messages.append(
                ToolMessage(
                    "The browser is with the user.",
                    tool_call_id="call",
                    id="handoff",
                    artifact={
                        "type": "browser_handoff",
                        "message": "Log in",
                        "url": handoff,
                    },
                )
            )
        messages.append(AIMessage(text, id="answer"))
        run = RunThread(thread=SimpleNamespace(id="agent-thread"), origin=binding)
        with (
            patch.object(delivery, "_deliver_answer", delivery._deliver_answer),
            patch.object(delivery, "channel_auto_replies_for_name", return_value=True),
            patch.object(delivery, "_post_trigger", new_callable=AsyncMock) as post,
        ):
            install()
            installed = delivery._deliver_answer
            install()
            self.assertIs(delivery._deliver_answer, installed)
            await delivery._deliver_answer(
                run,
                config,
                SimpleNamespace(values={"messages": messages}),
                None,
                opening=None,
                deliver_to=None,
            )
        self.assertEqual(binding, original)
        return post

    async def test_human_answers_default_to_top_level_but_explicit_threads_stay_threaded(
        self,
    ):
        post = await self.deliver()
        self.assertEqual(
            post.await_args.args[0]["target"]["address"], {"conversation_id": "D123"}
        )
        post = await self.deliver(root="1.0")
        self.assertEqual(
            post.await_args.args[0]["target"]["address"],
            {
                "conversation_id": "D123",
                "thread_id": "1.0",
            },
        )
        self.assertEqual(post.await_args.args[1], "Done")

    async def test_heartbeat_posts_top_level_even_after_a_threaded_human_turn_and_quiet_stays_quiet(
        self,
    ):
        post = await self.deliver(root="1.0", scheduled=True)
        self.assertEqual(
            post.await_args.args[0]["target"]["address"], {"conversation_id": "D123"}
        )
        post = await self.deliver(text="[quiet]", scheduled=True)
        post.assert_not_awaited()

    async def test_other_conversations_keep_their_existing_delivery(self):
        for binding in [
            self.binding(conversation="C123"),
            self.binding(canonical=False),
        ]:
            post = await self.deliver(binding=binding, scheduled=True)
            self.assertEqual(post.await_args.args[0], binding)

    async def test_browser_link_goes_where_the_model_wrote_it_only_in_its_dm(self):
        url = "https://browser.example/act/secret"
        cases = [
            # (reply, handoff, binding, posted)
            (
                "Go: {browser_link}, then Hand back.",
                url,
                None,
                f"Go: <{url}|browser link>, then Hand back.",
            ),
            (
                [{"type": "text", "text": "Go: {browser_link}"}],
                url,
                None,
                f"Go: <{url}|browser link>",
            ),
            ("Go: {browser_link}", None, None, "Go:"),
            (
                "Go: {browser_link}",
                url,
                self.binding(conversation="C123"),
                f"Go:\n\n{UNSENT}",
            ),
            ("Done", None, None, "Done"),
        ]
        for reply, handoff, binding, posted in cases:
            post = await self.deliver(text=reply, handoff=handoff, binding=binding)
            self.assertEqual(post.await_args.args[1], posted)
        # A reply without the placeholder, even [quiet], still carries the link.
        for reply, prefix in [("Done", "Done\n\n<"), ("[quiet]", "<")]:
            text = (await self.deliver(text=reply, handoff=url)).await_args.args[1]
            self.assertTrue(text.startswith(prefix))
            self.assertIn(url, text)

    async def test_a_dm_paused_for_a_connection_gets_the_connect_link(self):
        url = "https://connect.example/google"
        gate = SimpleNamespace(
            id="gate",
            value={
                "type": "credential_authorization_required",
                "credentials": [
                    {"slug": "google", "provider": "Google", "connect_url": url}
                ],
            },
        )
        approval = SimpleNamespace(id="hitl", value={"action_requests": []})
        config = {"configurable": {"run_id": "run-1"}, "metadata": {}}
        for binding, pending, posted in [
            (self.binding(), [gate], True),
            (self.binding(), [approval], False),
            (self.binding(conversation="C123"), [gate], False),
        ]:
            run = RunThread(thread=SimpleNamespace(id="agent-thread"), origin=binding)
            with (
                patch.object(delivery, "_deliver_answer", delivery._deliver_answer),
                patch.object(
                    delivery, "_deliver_pause", new_callable=AsyncMock
                ) as stock,
                patch.object(delivery, "_post_trigger", new_callable=AsyncMock) as post,
            ):
                install()
                await delivery._deliver_pause(run, config, None, pending)
            stock.assert_awaited_once()
            self.assertEqual(post.await_count, 1 if posted else 0)
            if posted:
                target, text = post.await_args.args[:2]
                self.assertEqual(
                    target["target"]["address"], {"conversation_id": "D123"}
                )
                self.assertIn(f"<{url}|Google>", text)

    async def test_a_channel_handoff_sends_the_link_to_the_askers_dm_only(self):
        url = "https://browser.example/act/secret"
        channel = {
            **self.binding(conversation="C123"),
            "raw_event": {"user": "U777", "channel": "C123"},
        }
        channel["target"]["channel_id"] = "trigger-channel"
        with patch.object(
            slack_conversation, "dm_link", AsyncMock(return_value=True)
        ) as dm:
            post = await self.deliver(
                text="Sent it to your DM.", handoff=url, binding=channel
            )
        self.assertEqual(dm.await_args.args[1:], ("U777", url, "Log in"))
        self.assertEqual(post.await_args.args[1], "Sent it to your DM.")

        client = SimpleNamespace(post_action=AsyncMock(return_value={"id": "m1"}))
        with patch(
            "managed_deepagents._channels.trigger.client.create_trigger_client",
            return_value=client,
        ):
            self.assertTrue(
                await dm_link(channel, "U777", url, "Log in, then Hand back.")
            )
        channel_id, body = client.post_action.await_args.args
        self.assertEqual(channel_id, "trigger-channel")
        self.assertEqual(body["address"], {"conversation_id": "U777"})
        self.assertNotIn("source_thread_key", body)
        self.assertTrue(
            body["message"]["text"].startswith("Log in, then Hand back.\n\n<")
        )
        self.assertIn(url, body["message"]["text"])
