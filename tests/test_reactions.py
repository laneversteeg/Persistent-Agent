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


class ReactionModel(unittest.TestCase):
    def model(self, **env):
        with patch.dict(os.environ, env, clear=True):
            return slack.reaction_model()

    def test_haiku_by_default(self):
        self.assertEqual(self.model(), slack.HAIKU)

    def test_haiku_when_the_agent_uses_the_gateway(self):
        agent = "langsmith:anthropic/claude-opus-5-5"
        self.assertEqual(self.model(AGENT_MODEL=agent), slack.HAIKU)

    def test_the_agents_model_when_it_skips_the_gateway(self):
        agent = "anthropic:claude-opus-5-5"
        self.assertEqual(self.model(AGENT_MODEL=agent), agent)

    def test_reaction_model_overrides(self):
        env = {
            "AGENT_MODEL": "openai:gpt-6.2-sol",
            "REACTION_MODEL": "openai:gpt-6-luna",
        }
        self.assertEqual(self.model(**env), "openai:gpt-6-luna")


if __name__ == "__main__":
    unittest.main()
