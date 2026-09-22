"""RD-71: actionable turns, bounded repair and reader-controlled confirmation.

Provider responses are fixtures; these tests do not claim live-model tone quality.
"""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.config.nepq import HANDOFF_MESSAGE, SUMMARY_QUESTION, NEPQ_STAGES
from app.services.nepq_conversation import next_turn, OnboardingUnavailableError


def response(message, complete=False, ui=None):
    return SimpleNamespace(content=[SimpleNamespace(text=json.dumps({
        "message": message, "stage_complete": complete, "ui": ui,
    })[1:])])


class ClearQuestionTests(unittest.TestCase):
    def setUp(self):
        self.provider = Mock()
        patcher = patch("app.services.nepq_conversation._client", return_value=self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.history = [
            {"role": "assistant", "content": "What would you like a book to help with?"},
            {"role": "user", "content": "I run a cleaning company. I need steady leads to fill my cleaners' schedules."},
        ]

    def replies(self, *replies):
        self.provider.messages.create.side_effect = list(replies)

    def test_acknowledgement_is_rewritten_on_next_objective_without_losing_answers(self):
        original = copy.deepcopy(self.history)
        question = "What have you tried to keep your cleaners' schedules full?"
        self.replies(response("Perfect — that tells me exactly what you need.", True), response(question))
        result = next_turn(self.history, 2)
        self.assertEqual(result["message"], question)
        self.assertEqual(result["stage_index"], 3)
        self.assertEqual(result["turns_in_stage"], 0)
        self.assertEqual(self.history, original)
        calls = self.provider.messages.create.call_args_list
        self.assertEqual(calls[0].kwargs["messages"], calls[1].kwargs["messages"])
        self.assertIn(NEPQ_STAGES[3]["goal"], calls[1].kwargs["system"])
        self.assertNotIn("Perfect —", str(calls[1].kwargs["messages"]))

    def test_valid_question_is_preserved_in_one_request(self):
        question = "Would practical examples of filling cleaning schedules help?"
        self.replies(response(question, ui="yes_no"))
        result = next_turn(self.history, 2)
        self.assertEqual(result["message"], question)
        self.assertEqual(result["ui"], "yes_no")
        self.assertFalse(result["done"])
        self.assertEqual(self.provider.messages.create.call_count, 1)

    def test_open_question_does_not_show_yes_no_buttons(self):
        self.replies(response("Which would help you more: examples, exercises or stories?", ui="yes_no"))
        self.assertIsNone(next_turn(self.history, 2)["ui"])

    def test_bad_questions_are_repaired_before_display(self):
        for bad in ("I've got enough to point you somewhere useful.",
                    "What keeps you up at night?", "What's keeping you up at night?",
                    "What made you try referrals?", "How many leads? What have you tried?",
                    "What would you like a book to help with?", "Would examples help? Let me know."):
            with self.subTest(bad=bad):
                self.replies(response(bad), response("What have you tried to generate steady cleaning leads?"))
                result = next_turn(self.history, 2)
                self.assertEqual(result["message"], "What have you tried to generate steady cleaning leads?")
                self.assertFalse(result["done"])

    def test_repair_is_bounded_and_remains_retryable_without_changing_history(self):
        original = copy.deepcopy(self.history)
        self.replies(response("I have what I need."), response("Great."))
        with self.assertRaises(OnboardingUnavailableError):
            next_turn(self.history, 2)
        self.assertEqual(self.provider.messages.create.call_count, 2)
        self.assertEqual(self.history, original)

    def test_malformed_json_gets_one_repair(self):
        self.replies(SimpleNamespace(content=[SimpleNamespace(text="not JSON")]),
                     response("What have you tried to generate steady leads?"))
        result = next_turn(self.history, 2)
        self.assertTrue(result["message"].endswith("?"))
        self.assertEqual(result["stage_index"], 2)

    def test_string_false_does_not_advance(self):
        self.replies(response("What is making it difficult to get steady cleaning leads?", "false"))
        self.assertEqual(next_turn(self.history, 2)["stage_index"], 2)

    def test_turn_budget_repairs_acknowledgement_on_next_objective(self):
        self.replies(response("Understood."), response("Would examples or exercises help you apply a book?"))
        result = next_turn(self.history, 2, turns_in_stage=1)
        self.assertEqual(result["stage_index"], 3)
        self.assertFalse(result["done"])

    def test_final_summary_requires_confirmation_even_when_model_says_done(self):
        self.replies(response("You want steady leads and practical steps. Is that right?", True, "confirm"))
        result = next_turn(self.history, 5, turns_in_stage=1)
        self.assertEqual(result["stage_index"], 6)
        self.assertFalse(result["done"])
        self.assertEqual(result["ui"], "confirm")
        self.assertEqual(result["message"], "You want steady leads and practical steps.\n\n" + SUMMARY_QUESTION)

    def test_confirmed_summary_has_explicit_handoff_without_provider(self):
        for answer in ("Yes", "Yes, that's right", "Yes, that’s right!", "Looks good."):
            history = self.history + [
                {"role": "assistant", "content": "You want steady cleaning leads.\n\n" + SUMMARY_QUESTION},
                {"role": "user", "content": answer},
            ]
            result = next_turn(history, 6)
            self.assertTrue(result["done"])
            self.assertEqual(result["message"], HANDOFF_MESSAGE)
        self.provider.messages.create.assert_not_called()

    def test_corrections_and_uncertainty_always_get_a_new_summary(self):
        for answer in ("Yes, but margins matter more than leads", "No", "I'm not sure", "I'd like to change something"):
            with self.subTest(answer=answer):
                history = self.history + [
                    {"role": "assistant", "content": "You want steady leads.\n\n" + SUMMARY_QUESTION},
                    {"role": "user", "content": answer},
                ]
                self.replies(response("You need a practical book for your cleaning business. Is that right?", True, "confirm"))
                result = next_turn(history, 6, turns_in_stage=20)
                self.assertFalse(result["done"])
                self.assertEqual(result["ui"], "confirm")
                self.assertIn(history[-1], self.provider.messages.create.call_args.kwargs["messages"])

    def test_agreement_without_a_reviewable_summary_cannot_finish(self):
        history = self.history + [{"role": "assistant", "content": "I have enough to help."},
                                  {"role": "user", "content": "Yes"}]
        self.replies(response("You want practical steps for steady cleaning leads. Is that right?", True, "confirm"))
        self.assertFalse(next_turn(history, 6)["done"])

    def test_persona_details_reach_the_model_and_questions_preserve_them(self):
        cases = [
            ("I don't have a business yet; I'm curious about opening a bakery.", "What would you enjoy learning about opening a bakery?"),
            ("I'm just curious about how founders think.", "Would you prefer founders' stories or practical exercises?"),
            ("I launched a cleaning service last month and need my first clients.", "What have you tried to find your first cleaning clients?"),
            ("I run an established cleaning company; inconsistent leads make it hard to retain cleaners.", "What have you tried to make cleaning bookings more consistent?"),
        ]
        for answer, question in cases:
            with self.subTest(answer=answer):
                history = [{"role": "user", "content": answer}]
                self.replies(response(question))
                self.assertEqual(next_turn(history, 2)["message"], question)
                call = self.provider.messages.create.call_args.kwargs
                self.assertIn(history[0], call["messages"])
                self.assertIn("Never inject emotions, stakes, or assumptions", call["system"])


if __name__ == "__main__":
    unittest.main()
