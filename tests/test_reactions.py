"""The emoji reaction the model picks, cleaned up for Slack."""

import asyncio
import os
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
    def test_uses_slacks_name_for_the_emoji(self):
        self.assertEqual(pick("🤔"), "thinking_face")
        self.assertEqual(pick("🪀"), "yo-yo")
        self.assertEqual(pick("👍"), "+1")

    def test_ignores_space_and_variation_selectors(self):
        self.assertEqual(pick(" 🐿️\n"), "chipmunk")

    def test_anything_else_is_eyes(self):
        for answer in ("thinking", "none", "I'd go with 🔥", ""):
            self.assertEqual(pick(answer), "eyes")


class ReactionModel(unittest.TestCase):
    def model(self, **env):
        with patch.dict(os.environ, env, clear=True):
            return slack.reaction_model()

    def test_haiku_from_anthropic_by_default(self):
        self.assertEqual(self.model(), slack.HAIKU["anthropic"])

    def test_haiku_on_the_gateway(self):
        agent = "langsmith:anthropic/claude-opus-5-5"
        self.assertEqual(self.model(AGENT_MODEL=agent), slack.HAIKU["langsmith"])

    def test_haiku_from_anthropic_directly(self):
        self.assertEqual(
            self.model(AGENT_MODEL="anthropic:claude-opus-5-5"),
            slack.HAIKU["anthropic"],
        )

    def test_another_providers_model_reacts_with_itself(self):
        self.assertEqual(
            self.model(AGENT_MODEL="openai:gpt-6.2-sol"), "openai:gpt-6.2-sol"
        )

    def test_reaction_model_overrides(self):
        env = {
            "AGENT_MODEL": "openai:gpt-6.2-sol",
            "REACTION_MODEL": "openai:gpt-6-luna",
        }
        self.assertEqual(self.model(**env), "openai:gpt-6-luna")


if __name__ == "__main__":
    unittest.main()
