"""October 1 local-review regressions; no live model or customer data is used."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import anthropic
import httpx

from app.config.nepq import HANDOFF_MESSAGE, SUMMARY_QUESTION
from app.services.nepq_conversation import next_turn, OnboardingUnavailableError


REPORTED_SUMMARY = (
    "Makes sense — lead flow first, then the bigger scaling picture. Let me pull together "
    "what I'm hearing so I can find you the right fit: you've got word-of-mouth working "
    "but it's not enough to keep two subs consistently booked, you want to build a "
    "repeatable lead machine that doesn't drain cash like Thumbtack did, and you're "
    "drawn to stories from people in similar shoes paired with frameworks you can "
    "actually implement. You're open to paid channels if they work, but the goal is "
    "something self-sustaining. Does that capture it, or should I adjust anything?"
)


def response(message, ui=None, complete=False):
    return SimpleNamespace(content=[SimpleNamespace(text=json.dumps({
        "message": message, "ui": ui, "stage_complete": complete,
    }))])


class OnboardingRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.provider = Mock()
        patcher = patch("app.services.nepq_conversation._client", return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.history = [
            {"role": "user", "content": "I run a cleaning business with two subcontractors."},
            {"role": "assistant", "content": "What have you tried for leads?"},
            {"role": "user", "content": "Referrals work but aren't enough. Thumbtack seems expensive."},
            {"role": "assistant", "content": "What would you want instead?"},
            {"role": "user", "content": 'I want a "lead machine" for the business itself.'},
        ]

    def test_reported_summary_gets_controls_even_without_model_ui_flag(self):
        self.provider.messages.create.return_value = response(REPORTED_SUMMARY)
        result = next_turn(self.history, 4)
        self.assertEqual(result["stage_index"], 6)
        self.assertEqual(result["ui"], "confirm")
        self.assertTrue(result["message"].endswith(SUMMARY_QUESTION))

    def test_reported_thats_perfect_finishes_saved_summary_without_ai(self):
        history = self.history + [{"role": "assistant", "content": REPORTED_SUMMARY},
                                  {"role": "user", "content": "That's perfect"}]
        self.provider.messages.create.side_effect = TimeoutError("must not call provider")
        for stage in (4, 5, 6):
            result = next_turn(history, stage)
            self.assertTrue(result["done"])
            self.assertEqual(result["message"], HANDOFF_MESSAGE)
        self.provider.messages.create.assert_not_called()

    def test_perfect_with_correction_does_not_finish(self):
        history = self.history + [{"role": "assistant", "content": REPORTED_SUMMARY},
                                  {"role": "user", "content": "That's perfect, but margins matter more."}]
        self.provider.messages.create.return_value = response(
            "You want practical help with cleaning margins. Is that right?", "confirm")
        result = next_turn(history, 5)
        self.assertFalse(result["done"])
        self.assertEqual(result["ui"], "confirm")

    def test_unusable_replies_advance_to_guided_question_without_repeating_answer(self):
        original = copy.deepcopy(self.history)
        self.provider.messages.create.side_effect = [response("Got it."), response("Let me find books.")]
        result = next_turn(self.history, 2)
        self.assertEqual(result["stage_index"], 3)
        self.assertEqual(result["message"].count("?"), 1)
        self.assertIn("stories", result["message"])
        self.assertFalse(result["done"])
        self.assertEqual(self.history, original)
        self.assertEqual(self.provider.messages.create.call_count, 2)

    def test_invalid_output_cannot_jump_to_summary_before_preferences(self):
        self.provider.messages.create.return_value = response("Done!", "confirm", True)
        result = next_turn(self.history, 1)
        self.assertEqual(result["stage_index"], 2)
        self.assertIsNone(result["ui"])
        self.assertFalse(result["done"])

    def test_final_fallback_quotes_user_answers_and_correction_not_rejected_drafts(self):
        history = self.history + [{"role": "assistant", "content": REPORTED_SUMMARY},
                                  {"role": "user", "content": "Actually, I have three subcontractors now."}]
        self.provider.messages.create.return_value = response("You earn a million dollars.")
        result = next_turn(history, 6)
        for entry in history:
            if entry["role"] == "user":
                self.assertIn(entry["content"], result["message"])
        self.assertNotIn("million dollars", result["message"])
        self.assertIn("latest corrections", result["message"])
        self.assertEqual(result["ui"], "confirm")
        self.assertFalse(result["done"])
        confirmed = next_turn(history + [{"role": "assistant", "content": result["message"]},
                                         {"role": "user", "content": "Yes, that's right"}], 6)
        self.assertTrue(confirmed["done"])
        self.assertEqual(self.provider.messages.create.call_count, 2)

    def test_request_to_change_summary_gets_a_correction_question(self):
        history = self.history + [{"role": "assistant", "content": REPORTED_SUMMARY},
                                  {"role": "user", "content": "I'd like to change something"}]
        self.provider.messages.create.return_value = response("Thanks.")
        result = next_turn(history, 6)
        self.assertFalse(result["done"])
        self.assertIsNone(result["ui"])
        self.assertIn("change", result["message"])

    def test_transient_timeout_recovers_inside_the_same_request(self):
        question = "Would practical examples or stories help you most?"
        self.provider.messages.create.side_effect = [TimeoutError("temporary"), response(question)]
        result = next_turn(self.history, 2)
        self.assertEqual(result["message"], question)
        calls = self.provider.messages.create.call_args_list
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].kwargs["messages"], calls[1].kwargs["messages"])
        self.assertEqual(calls[0].kwargs["system"], calls[1].kwargs["system"])

    def test_provider_status_retry_is_bounded_and_only_for_transient_errors(self):
        for status in (400, 401, 403, 429, 500, 503, 529):
            with self.subTest(status=status):
                self.provider.reset_mock()
                error = anthropic.APIStatusError("fixture", response=httpx.Response(
                    status, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")), body=None)
                self.provider.messages.create.side_effect = [error, response("Would stories help?")]
                if status < 429:
                    with self.assertRaises(OnboardingUnavailableError):
                        next_turn(self.history, 2)
                    self.assertEqual(self.provider.messages.create.call_count, 1)
                else:
                    self.assertEqual(next_turn(self.history, 2)["message"], "Would stories help?")
                    self.assertEqual(self.provider.messages.create.call_count, 2)

    def test_sustained_outage_remains_honest_and_preserves_answers(self):
        original = copy.deepcopy(self.history)
        self.provider.messages.create.side_effect = TimeoutError("outage")
        with self.assertRaises(OnboardingUnavailableError):
            next_turn(self.history, 2)
        self.assertEqual(self.provider.messages.create.call_count, 2)
        self.assertEqual(self.history, original)

    def test_transient_retry_and_repair_share_a_two_call_budget(self):
        self.provider.messages.create.side_effect = [TimeoutError("temporary"), response("Got it.")]
        result = next_turn(self.history, 2)
        self.assertTrue(result["message"].endswith("?"))
        self.assertFalse(result["done"])
        self.assertEqual(self.provider.messages.create.call_count, 2)

    def test_guided_conversation_reaches_confirmed_handoff_with_invalid_model_output(self):
        history, stage, turns = [], 0, 0
        answers = ["I want steady leads.", "A cleaning company.", "Referrals aren't enough.",
                   "Stories and practical frameworks.", "A repeatable lead machine.", "The sooner the better."]
        self.provider.messages.create.return_value = response("Got it.")
        for answer in answers:
            result = next_turn(history, stage, turns)
            history += [{"role": "assistant", "content": result["message"]},
                        {"role": "user", "content": answer}]
            stage, turns = result["stage_index"], result["turns_in_stage"]
        result = next_turn(history, stage, turns)
        self.assertEqual(result["ui"], "confirm")
        history += [{"role": "assistant", "content": result["message"]},
                    {"role": "user", "content": "That's perfect"}]
        self.assertTrue(next_turn(history, result["stage_index"])["done"])

    def test_empty_and_non_json_output_use_the_same_guided_recovery(self):
        self.provider.messages.create.side_effect = [SimpleNamespace(content=[]),
                                                     SimpleNamespace(content=[SimpleNamespace(text="not JSON")])]
        result = next_turn(self.history, 2)
        self.assertEqual(result["stage_index"], 3)
        self.assertFalse(result["done"])
        self.assertEqual(self.provider.messages.create.call_count, 2)

    def test_http_turn_recovers_and_confirmed_handoff_never_returns_retry_error(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.routers.onboarding import router
        app = FastAPI()
        app.include_router(router, prefix="/api")
        client = TestClient(app)
        self.provider.messages.create.return_value = response("Let me fetch your books.")
        result = client.post("/api/onboarding/chat", json={"history": self.history, "stage_index": 6})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["ui"], "confirm")
        self.assertFalse(result.json()["done"])
        history = self.history + [{"role": "assistant", "content": result.json()["message"]},
                                  {"role": "user", "content": "That's perfect"}]
        result = client.post("/api/onboarding/chat", json={"history": history, "stage_index": 6})
        self.assertEqual(result.status_code, 200)
        self.assertTrue(result.json()["done"])
        self.assertEqual(self.provider.messages.create.call_count, 2)


if __name__ == "__main__":
    unittest.main()
