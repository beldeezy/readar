"""Regression: a visible summary must not leave its confirmation at a discovery stage."""
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.config.nepq import HANDOFF_MESSAGE, SUMMARY_QUESTION
from app.services.nepq_conversation import next_turn, OnboardingUnavailableError


SUMMARY = (
    "Great — I've got what I need. Let me make sure I'm tracking this right: "
    "you run a residential cleaning business and want to make paid ads profitable. "
    "You want practical steps with small-business examples that show the whole system. "
    "Does that fit, or did I miss something?"
)


def response(message, ui=None, complete=False):
    return SimpleNamespace(content=[SimpleNamespace(text=json.dumps({
        "message": message, "ui": ui, "stage_complete": complete,
    }))])


class SummaryConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.provider = Mock()
        self.patcher = patch("app.services.nepq_conversation._client", return_value=self.provider)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.history = [
            {"role": "user", "content": "I run a cleaning business and need profitable leads."},
            {"role": "assistant", "content": "Would the full picture of pricing and ads help?"},
            {"role": "user", "content": "I'd like to know the full picture."},
        ]

    def test_reported_summary_confirmation_resumes_without_another_generated_question(self):
        history = self.history + [
            {"role": "assistant", "content": SUMMARY},
            {"role": "user", "content": "That's right"},
        ]
        original = copy.deepcopy(history)
        # Previously these two acknowledgement-only replies exhausted the rewrite
        # and returned the exact 503 reported by the reader.
        self.provider.messages.create.side_effect = [
            response("Great, let me find your books."), response("I've got what I need."),
        ]
        result = next_turn(history, 5)
        self.assertTrue(result["done"])
        self.assertEqual(result["stage_index"], 6)
        self.assertEqual(result["message"], HANDOFF_MESSAGE)
        self.assertEqual(history, original)
        self.provider.messages.create.assert_not_called()

    def test_early_visible_summary_gets_canonical_question_and_buttons(self):
        for stage in (4, 5):
            for ui in (None, "confirm"):
                with self.subTest(stage=stage, ui=ui):
                    self.provider.messages.create.return_value = response(SUMMARY, ui=ui)
                    result = next_turn(self.history, stage)
                    self.assertEqual(result["stage_index"], 6)
                    self.assertEqual(result["ui"], "confirm")
                    self.assertTrue(result["message"].endswith(SUMMARY_QUESTION))
                    self.assertFalse(result["done"])

    def test_corrections_to_legacy_summary_are_not_silently_accepted(self):
        for answer in ("Yes, but margins matter more than leads", "No", "I'm not sure"):
            with self.subTest(answer=answer):
                history = self.history + [{"role": "assistant", "content": SUMMARY},
                                          {"role": "user", "content": answer}]
                self.provider.messages.create.return_value = response(
                    "You want practical examples for improving cleaning margins. Is that right?", "confirm")
                result = next_turn(history, 5)
                self.assertFalse(result["done"])
                self.assertEqual(result["stage_index"], 6)
                self.assertEqual(result["ui"], "confirm")
                self.assertIn(history[-1], self.provider.messages.create.call_args.kwargs["messages"])
                self.assertIn("final summary", self.provider.messages.create.call_args.kwargs["system"])

    def test_missing_ui_flag_does_not_reject_a_final_summary(self):
        self.provider.messages.create.return_value = response(
            "You want practical examples to make cleaning ads profitable. Is that right?")
        result = next_turn(self.history, 6)
        self.assertEqual(result["ui"], "confirm")
        self.assertTrue(result["message"].endswith(SUMMARY_QUESTION))
        self.assertFalse(result["done"])
        self.assertEqual(self.provider.messages.create.call_count, 1)

    def test_final_stage_does_not_turn_acknowledgements_into_fake_summaries(self):
        self.provider.messages.create.side_effect = [response("Great."), response("Let me get your books.")]
        with self.assertRaises(OnboardingUnavailableError):
            next_turn(self.history, 6)
        self.assertEqual(self.provider.messages.create.call_count, 2)

    def test_canonical_summary_with_an_older_stage_can_resume(self):
        history = self.history + [
            {"role": "assistant", "content": "You want practical examples for profitable ads.\n\n" + SUMMARY_QUESTION},
            {"role": "user", "content": "That's right"},
        ]
        for stage in (4, 5, 6):
            self.assertTrue(next_turn(history, stage)["done"])
        self.provider.messages.create.assert_not_called()

    def test_repair_can_align_an_early_summary_with_the_final_stage(self):
        self.provider.messages.create.side_effect = [
            response("Understood."), response(SUMMARY, "confirm"),
        ]
        result = next_turn(self.history, 4)
        self.assertEqual(result["stage_index"], 6)
        self.assertEqual(result["ui"], "confirm")
        self.assertFalse(result["done"])

    def test_yes_to_a_regular_question_is_not_summary_confirmation(self):
        history = self.history + [
            {"role": "assistant", "content": "You mentioned practical examples. Does that sound right?"},
            {"role": "user", "content": "That's right"},
        ]
        self.provider.messages.create.return_value = response(SUMMARY, "confirm")
        result = next_turn(history, 5)
        self.assertFalse(result["done"])
        self.provider.messages.create.assert_called_once()

    def test_matching_summary_words_cannot_skip_early_discovery(self):
        history = self.history + [{"role": "assistant", "content": SUMMARY},
                                  {"role": "user", "content": "That's right"}]
        self.provider.messages.create.return_value = response("What have you tried to generate leads?")
        result = next_turn(history, 1)
        self.assertFalse(result["done"])
        self.assertEqual(result["stage_index"], 1)

    def test_provider_failure_on_a_correction_remains_retryable(self):
        history = self.history + [{"role": "assistant", "content": SUMMARY},
                                  {"role": "user", "content": "No, margins are the problem."}]
        original = copy.deepcopy(history)
        self.provider.messages.create.side_effect = TimeoutError("test provider outage")
        with self.assertRaises(OnboardingUnavailableError):
            next_turn(history, 5)
        self.assertEqual(history, original)


if __name__ == "__main__":
    unittest.main()
