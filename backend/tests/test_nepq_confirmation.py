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

# Wording observed in the September 26 public onboarding review. It was shown
# as an ordinary question, so agreement continued discovery and eventually 503ed.
LIVE_SUMMARY = (
    "That makes sense — you want a book that'll help you evaluate channels and "
    "pick the right one for a cleaning company your size, then show you how to "
    "build it. I've got what I need. Here's what I'm hearing: you run an 8-person "
    "residential cleaning operation doing $50k/month mostly through referrals. "
    "Lead inconsistency is costing you your best cleaners and forcing you into "
    "shift work. You want a practical marketing system you can start yourself "
    "and hand to your office manager — no theory, just examples you can run "
    "with. You read about 15 minutes a day, and you're open on which channel "
    "to focus on as long as the book helps you decide and execute. "
    "Does that land right, or should I adjust anything?"
)
LIVE_AGREEMENT = "Yes, that accurately describes my situation and goal."


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
        result = next_turn(self.history, 6)
        self.assertFalse(result["done"])
        self.assertEqual(result["ui"], "confirm")
        self.assertIn(self.history[0]["content"], result["message"])
        self.assertIn(self.history[-1]["content"], result["message"])
        self.assertNotIn("Let me get your books.", result["message"])
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

    def test_live_wording_at_summary_boundary_gets_confirmation_controls(self):
        for ui in (None, "confirm"):
            with self.subTest(ui=ui):
                self.provider.reset_mock()
                self.provider.messages.create.return_value = response(
                    LIVE_SUMMARY, ui=ui, complete=True)
                result = next_turn(self.history, 3)
                self.assertEqual(result["stage_index"], 6)
                self.assertEqual(result["ui"], "confirm")
                self.assertTrue(result["message"].endswith(SUMMARY_QUESTION))
                self.assertFalse(result["done"])
                self.provider.messages.create.assert_called_once()

    def test_live_summary_and_agreement_resume_without_a_provider_call(self):
        history = self.history + [
            {"role": "assistant", "content": LIVE_SUMMARY},
            {"role": "user", "content": LIVE_AGREEMENT},
        ]
        original = copy.deepcopy(history)
        for stage in (4, 5, 6):
            with self.subTest(stage=stage):
                self.provider.messages.create.side_effect = [
                    response("Great, let me find your books."), response("I've got what I need."),
                ]
                result = next_turn(history, stage)
                self.assertTrue(result["done"])
                self.assertEqual(result["message"], HANDOFF_MESSAGE)
                self.assertEqual(history, original)
        self.provider.messages.create.assert_not_called()

    def test_natural_agreement_to_controlled_summary_does_not_need_ai(self):
        self.provider.messages.create.side_effect = RuntimeError("Confirmed summary must not call AI")
        for answer in (LIVE_AGREEMENT, "That accurately describes my situation and goal.",
                       "Yes, that sums it up.", "That's an accurate summary."):
            with self.subTest(answer=answer):
                history = self.history + [
                    {"role": "assistant", "content": "You want practical marketing steps. " + SUMMARY_QUESTION},
                    {"role": "user", "content": answer},
                ]
                result = next_turn(history, 6)
                self.assertTrue(result["done"])
                self.assertEqual(result["message"], HANDOFF_MESSAGE)
        self.provider.messages.create.assert_not_called()

    def test_natural_agreement_with_a_correction_still_requires_review(self):
        for answer in (
            "Yes, that accurately describes my situation and goal, but cash flow matters more.",
            "That accurately describes my situation and goal, except I have no office manager.",
            "Yes, that sums it up, although I'm not sure about the goal.",
            "That's an accurate summary, but change the reading time to 30 minutes.",
        ):
            with self.subTest(answer=answer):
                self.provider.messages.create.return_value = response(SUMMARY, "confirm")
                history = self.history + [{"role": "assistant", "content": LIVE_SUMMARY},
                                          {"role": "user", "content": answer}]
                result = next_turn(history, 5)
                self.assertFalse(result["done"])
                self.assertEqual(result["ui"], "confirm")
                self.assertIn(history[-1], self.provider.messages.create.call_args.kwargs["messages"])

    def test_generated_book_suggestions_are_repaired_before_display(self):
        suggestion = (
            "Here are three books that fit what you're after: The Referral Engine, "
            "DotCom Secrets and Traction. My pick for you is The Referral Engine. "
            "Which of these sounds closest to what you're looking for?"
        )
        self.provider.messages.create.side_effect = [
            response(suggestion), response(SUMMARY, "confirm"),
        ]
        result = next_turn(self.history, 4)
        self.assertEqual(result["ui"], "confirm")
        self.assertNotIn("The Referral Engine", result["message"])
        self.assertEqual(self.provider.messages.create.call_count, 2)

    def test_reading_history_discussion_is_not_a_generated_suggestion(self):
        message = "You've already read The Referral Engine. Which part was useful to you?"
        self.provider.messages.create.return_value = response(message)
        result = next_turn(self.history, 2)
        self.assertEqual(result["message"], message)
        self.provider.messages.create.assert_called_once()


if __name__ == "__main__":
    unittest.main()
