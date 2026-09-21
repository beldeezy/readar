"""RD-51: preserve reader intent and recover from provider failures.

These tests mock the model provider and require neither live AI nor a database.
They can also run directly with python -m unittest discover -s tests -p test_nepq_handoff.py.
"""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services.nepq_conversation import (
    OnboardingUnavailableError,
    extract_profile,
    next_turn,
)


class OnboardingHandoffTests(unittest.TestCase):
    def setUp(self):
        self.provider = Mock()
        patcher = patch("app.services.nepq_conversation._client", return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.history = [{"role": "user", "content": "I want predictable sales and practical checklists."}]
        self.profile = {
            "business_stage": "early-revenue",
            "business_model": "service",
            "biggest_challenge": "Unpredictable sales",
            "future_vision": "Predictable sales without working every evening",
            "ideal_book_description": "Practical checklists",
        }

    def respond(self, data):
        self.provider.messages.create.return_value = SimpleNamespace(
            content=[SimpleNamespace(text=json.dumps(data))]
        )

    def test_goal_and_reading_preferences_survive_extraction(self):
        self.respond(self.profile)
        result = extract_profile(self.history)
        self.assertEqual(result["vision_6_12_months"], self.profile["future_vision"])
        self.assertEqual(result["future_vision"], self.profile["future_vision"])
        self.assertEqual(result["ideal_book_description"], "Practical checklists")
        self.assertEqual(result["biggest_challenge"], "Unpredictable sales")

    def test_existing_goal_is_not_overwritten(self):
        self.respond({**self.profile, "vision_6_12_months": "Hire a sales lead"})
        self.assertEqual(extract_profile(self.history)["vision_6_12_months"], "Hire a sales lead")

    def test_unknown_goal_is_not_invented(self):
        self.respond({**self.profile, "future_vision": None})
        self.assertIsNone(extract_profile(self.history)["vision_6_12_months"])

    def test_incomplete_profiles_are_retryable_not_successful(self):
        for data in ({}, [], None, {**self.profile, "business_stage": "unknown"},
                     {**self.profile, "biggest_challenge": " "},
                     {**self.profile, "business_model": None}):
            with self.subTest(data=data):
                self.respond(data)
                with self.assertRaises(OnboardingUnavailableError):
                    extract_profile(self.history)

    def test_provider_failure_can_retry_the_same_transcript(self):
        self.provider.messages.create.side_effect = TimeoutError("test outage")
        with self.assertRaises(OnboardingUnavailableError):
            extract_profile(self.history)
        first_request = self.provider.messages.create.call_args.kwargs["messages"]
        self.provider.messages.create.side_effect = None
        self.respond(self.profile)
        result = extract_profile(self.history)
        self.assertEqual(first_request, self.provider.messages.create.call_args.kwargs["messages"])
        self.assertEqual(result["biggest_challenge"], self.profile["biggest_challenge"])

    def test_chat_failure_does_not_turn_into_a_request_to_repeat(self):
        self.provider.messages.create.side_effect = TimeoutError("test outage")
        # At the final stage's cap, a failed request previously completed the
        # chat with a fabricated request for more detail.
        with self.assertRaises(OnboardingUnavailableError):
            next_turn(self.history, stage_index=6, turns_in_stage=2)


if __name__ == "__main__":
    unittest.main()
