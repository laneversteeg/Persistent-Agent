"""Exercise programmatic reset with the pinned SDK's real personal-memory backend."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from deepagents.backends.protocol import DeleteResult, LsResult
from managed_deepagents._memory.user_memory import APPROVED_USER

from tools.reset import _user_memory, clear_me


class ResetTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.entry = SimpleNamespace(_context_root=str(self.root))
        self.auth = {
            "configurable": {
                "langgraph_auth_user": {
                    "identity": "deployment-owner",
                    "permissions": [],
                    "mda_user_id": "alice",
                }
            }
        }
        for target, kwargs in [
            ("tools.reset.import_module", {"return_value": self.entry}),
            ("tools.reset.private", {"return_value": True}),
            (
                "managed_deepagents._identity_runtime.get_config",
                {"side_effect": lambda: self.auth},
            ),
        ]:
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        token = APPROVED_USER.set("alice")
        self.addCleanup(APPROVED_USER.reset, token)
        self.runtime = SimpleNamespace(
            server_info=SimpleNamespace(principal=SimpleNamespace(kind="person")),
            schedules=SimpleNamespace(
                list=AsyncMock(return_value={"items": []}), delete=AsyncMock()
            ),
        )

    async def test_reset_erases_nested_memory_and_all_schedules_for_only_this_person(
        self,
    ):
        for path in [
            "/AGENTS.md",
            "/buffer.md",
            "/goals/launch.md",
            "/playbooks/brief.md",
        ]:
            result = await _user_memory().awrite(path, "personal note")
            self.assertIsNone(result.error)
        other = self.root / "__users__" / "another-person" / "AGENTS.md"
        other.parent.mkdir(parents=True)
        other.write_text("Keep this")
        shared = self.root / "AGENTS.md"
        shared.write_text("Shared instructions")
        self.runtime.schedules.list.side_effect = [
            {"items": [{"id": str(i)} for i in range(100)]},
            {"items": [{"id": "100"}]},
            {"items": []},
        ]

        result = await clear_me.coroutine(self.runtime)

        self.assertEqual(
            result, "Cancelled 101 schedules and cleared your personal memory."
        )
        self.assertEqual(self.runtime.schedules.delete.await_count, 101)
        for call in self.runtime.schedules.list.await_args_list:
            self.assertEqual(call.kwargs, {"owner": {"type": "user"}, "limit": 100})
        for call in self.runtime.schedules.delete.await_args_list:
            self.assertEqual(call.kwargs, {"owner": {"type": "user"}})
        self.assertEqual((await _user_memory().als("/")).entries, [])
        self.assertEqual(other.read_text(), "Keep this")
        self.assertEqual(shared.read_text(), "Shared instructions")
        self.runtime.schedules.list.side_effect = None
        self.assertIn("cleared", await clear_me.coroutine(self.runtime))

    async def test_shared_or_nonperson_calls_leave_memory_and_schedules_untouched(self):
        await _user_memory().awrite("/AGENTS.md", "Keep this")
        for kind, private in [("person", False), ("service", True)]:
            self.runtime.server_info.principal.kind = kind
            with patch("tools.reset.private", return_value=private):
                self.assertIn("Only", await clear_me.coroutine(self.runtime))
        self.runtime.schedules.list.assert_not_awaited()
        self.assertIsNone((await _user_memory().aread("/AGENTS.md")).error)

    async def test_unapproved_or_different_caller_is_denied_by_sdk(self):
        for approved in [None, "bob"]:
            token = APPROVED_USER.set(approved)
            try:
                with self.assertRaisesRegex(ValueError, "allowed caller"):
                    await clear_me.coroutine(self.runtime)
            finally:
                APPROVED_USER.reset(token)
        self.runtime.schedules.list.assert_not_awaited()

    async def test_missing_generated_configuration_refuses_reset(self):
        del self.entry._context_root
        with self.assertRaisesRegex(RuntimeError, "compiled memory configuration"):
            await clear_me.coroutine(self.runtime)
        self.runtime.schedules.list.assert_not_awaited()

    async def test_cloud_configuration_uses_caller_scoped_backend(self):
        self.entry._context_repo = "test-deployment"
        with patch("managed_deepagents._memory.user_memory.ContextHubBackend") as hub:
            hub.return_value.als = AsyncMock(return_value=LsResult(entries=[]))
            await clear_me.coroutine(self.runtime)
        handles = [call.args[0] for call in hub.call_args_list]
        self.assertEqual(len(handles), 2)
        self.assertEqual(handles[0], handles[1])
        self.assertTrue(handles[0].startswith("test-deployment--u--"))

    async def test_memory_failures_never_report_success(self):
        for listing, deletion, verification in [
            (LsResult(), DeleteResult(), LsResult(entries=[])),
            (LsResult(entries=[]), DeleteResult(), LsResult()),
            (LsResult(error="unavailable"), DeleteResult(), LsResult(entries=[])),
            (
                LsResult(entries=[{"path": "/AGENTS.md", "is_dir": False}]),
                DeleteResult(error="unavailable"),
                LsResult(entries=[]),
            ),
            (LsResult(entries=[]), DeleteResult(), LsResult(error="unavailable")),
            (
                LsResult(entries=[]),
                DeleteResult(),
                LsResult(entries=[{"path": "/new.md", "is_dir": False}]),
            ),
        ]:
            backend = SimpleNamespace(
                als=AsyncMock(side_effect=[listing, verification]),
                adelete=AsyncMock(return_value=deletion),
            )
            with patch("tools.reset._user_memory", return_value=backend):
                with self.assertRaisesRegex(RuntimeError, "reset did not complete"):
                    await clear_me.coroutine(self.runtime)

    async def test_schedule_failure_leaves_memory_untouched(self):
        await _user_memory().awrite("/AGENTS.md", "Keep this")
        self.runtime.schedules.list.side_effect = RuntimeError("Schedules unavailable")
        with self.assertRaisesRegex(RuntimeError, "Schedules unavailable"):
            await clear_me.coroutine(self.runtime)
        self.assertIsNone((await _user_memory().aread("/AGENTS.md")).error)
