"""The emoji reaction the model picks, cleaned up for Slack."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from channels import slack


def pick(answer: str) -> str | None:
    model = SimpleNamespace(
        ainvoke=AsyncMock(return_value=SimpleNamespace(text=answer))
    )
    with patch.object(slack, "_model", return_value=model):
        return asyncio.run(slack.choose_reaction({"text": "ship it"}))


class ChooseReaction(unittest.TestCase):
    def test_uses_the_models_emoji(self):
        self.assertEqual(pick("squirrel"), "squirrel")

    def test_strips_colons_space_and_case(self):
        self.assertEqual(pick(" :Melting_Face: \n"), "melting_face")

    def test_none_skips_the_reaction(self):
        self.assertIsNone(pick("none"))

    def test_anything_but_a_name_skips_the_reaction(self):
        self.assertIsNone(pick("🔥"))
        self.assertIsNone(pick("I'd go with fire"))
        self.assertIsNone(pick(""))


if __name__ == "__main__":
    unittest.main()
