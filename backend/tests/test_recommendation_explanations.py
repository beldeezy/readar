"""RD-52: truthful connections and response wiring, without live AI or a DB."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from app.models import Book, OnboardingProfile, BusinessStage
from app.schemas.onboarding import OnboardingPayload
from app.schemas.recommendation import RecommendationsResponse
from app.services.recommendation_explanations import build_book_fit, fit_summary
from app.services import recommendation_engine as engine


class BookFitTests(unittest.TestCase):
    def setUp(self):
        self.reader = {"biggest_challenge": "I need more customers", "business_stage": "early-revenue"}
        self.book = SimpleNamespace(
            functional_tags=["sales"], theme_tags=[], business_stage_tags=[],
            promise="Ask better questions in customer conversations.",
        )

    def test_challenge_connection_uses_book_topics_and_actual_catalog_text(self):
        fit = build_book_fit(self.reader, self.book)
        self.assertEqual(fit["match_type"], "challenge")
        self.assertEqual(fit["priority"], self.reader["biggest_challenge"])
        self.assertEqual(fit["evidence"], self.book.promise)
        self.assertIn("sales and marketing", fit["reason"])
        self.assertIn("Look for", fit["reading_focus"])

    def test_same_reader_gets_distinct_book_evidence(self):
        other = SimpleNamespace(**{**vars(self.book), "promise": "Build a repeatable sales pipeline."})
        self.assertNotEqual(fit_summary(build_book_fit(self.reader, self.book)),
                            fit_summary(build_book_fit(self.reader, other)))

    def test_unrelated_book_does_not_promise_to_solve_challenge(self):
        self.book.functional_tags = ["finance"]
        fit = build_book_fit(self.reader, self.book)
        self.assertEqual(fit["match_type"], "general")
        self.assertIn("haven't established", fit["reason"])

    def test_goal_connection_is_labelled_as_goal_not_challenge(self):
        self.reader.update(biggest_challenge="I need more confidence", vision="Find more customers")
        fit = build_book_fit(self.reader, self.book)
        self.assertEqual(fit["match_type"], "goal")
        self.assertEqual(fit["priority"], "Find more customers")
        self.assertEqual(fit["priority_label"], "Your goal")

    def test_area_or_inferred_problem_cannot_impersonate_stated_challenge(self):
        self.reader.update(biggest_challenge="I need more confidence", areas_of_business=["sales"], problem_domains={"sales"})
        self.assertEqual(build_book_fit(self.reader, self.book)["match_type"], "general")

    def test_stage_connection_requires_matching_book_stage(self):
        self.book.functional_tags = []
        self.book.business_stage_tags = ["scaling"]
        self.assertEqual(build_book_fit(self.reader, self.book)["match_type"], "general")
        self.book.business_stage_tags = ["early-revenue"]
        fit = build_book_fit(self.reader, self.book)
        self.assertEqual(fit["match_type"], "stage")
        self.assertIn("haven't established a specific match", fit["reason"])

    def test_sparse_catalog_and_missing_profile_have_useful_fallbacks(self):
        fit = build_book_fit(self.reader, SimpleNamespace())
        self.assertIsNone(fit["evidence"])
        self.assertIn("enough book details", fit["reason"])
        fit = build_book_fit(None, self.book)
        self.assertIsNone(fit["priority"])
        self.assertEqual(fit["match_type"], "general")
        self.assertIn("general suggestion", fit["reason"])

    def test_word_boundaries_avoid_false_sales_matches(self):
        for challenge in ("Develop my leadership", "Improve my mislead detection"):
            with self.subTest(challenge=challenge):
                self.assertEqual(build_book_fit({"biggest_challenge": challenge}, self.book)["match_type"], "general")
        self.assertEqual(build_book_fit({"biggest_challenge": "Find more leads"}, self.book)["match_type"], "challenge")

    def test_topic_tags_support_connection_without_prose(self):
        self.book.promise = None
        self.assertEqual(build_book_fit(self.reader, self.book)["match_type"], "challenge")
        self.assertIsNone(build_book_fit(self.reader, self.book)["evidence"])

    def test_catalog_html_and_long_text_are_safe_to_display(self):
        self.book.promise = "<p>Ask <b>better</b> questions &amp; listen.</p>"
        self.assertEqual(build_book_fit(self.reader, self.book)["evidence"], "Ask better questions & listen.")
        self.book.promise = "A long description " * 100
        self.assertLessEqual(len(build_book_fit(self.reader, self.book)["evidence"]), 240)

    def test_legacy_paragraph_ignores_unsupported_insight(self):
        self.book.functional_tags = ["finance"]
        text = engine.build_why_this_book_v2(self.reader, self.book, [{"key": "fake", "weight": 999, "reason": "Guaranteed to solve sales"}], "fake")
        self.assertNotIn("Guaranteed", text)
        self.assertIn("haven't established", text)


class RecommendationFitWiringTests(unittest.TestCase):
    """Run real ranking and response construction; mock only database reads."""

    def setUp(self):
        self.book = Book(id=uuid4(), title="Customer Conversations", author_name="Test Author",
                         functional_tags=["sales"], theme_tags=[], business_stage_tags=["early-revenue"],
                         categories=[], promise="Ask better questions in customer conversations.")
        self.payload = OnboardingPayload(full_name="Test Reader", industry="Services", business_model="service",
                                         business_stage="early-revenue", biggest_challenge="I need more customers",
                                         vision_6_12_months="Build a repeatable pipeline")
        self.db = Mock()
        candidate = patch.object(engine, "candidate_books_query")
        self.query = candidate.start().return_value
        self.query.all.return_value = [self.book]
        self.query.order_by.return_value.limit.return_value.all.return_value = [self.book]
        self.addCleanup(candidate.stop)

    def assert_fit_survives_serialization(self, items, match_type):
        data = RecommendationsResponse(request_id="rd52-test", items=items).model_dump(mode="json")
        fit = data["items"][0]["fit"]
        self.assertEqual(fit["match_type"], match_type)
        self.assertEqual(fit["evidence"], self.book.promise)

    def test_preview_includes_grounded_fit_with_no_provider(self):
        self.assert_fit_survives_serialization(engine.get_recommendations_from_payload(self.db, self.payload), "challenge")

    def test_authenticated_response_uses_stored_profile(self):
        user_id = uuid4()
        profile = OnboardingProfile(user_id=user_id, business_stage=BusinessStage.EARLY_REVENUE,
                                    business_model="service", biggest_challenge="I need more customers")
        self.db.query.return_value.filter.return_value.one_or_none.return_value = profile
        self.db.query.return_value.filter.return_value.all.return_value = []
        self.db.query.return_value.filter.return_value.first.return_value = None
        with patch.object(engine, "_get_user", return_value=SimpleNamespace(id=user_id)), \
             patch.object(engine, "_get_user_interactions", return_value=[]), \
             patch.object(engine, "_get_user_reading_history", return_value=[]), \
             patch.object(engine, "_get_excluded_books_from_reading_history", return_value=set()):
            self.assert_fit_survives_serialization(engine.get_personalized_recommendations(self.db, user_id), "challenge")

    def test_generic_response_does_not_invent_a_reader(self):
        self.assert_fit_survives_serialization(engine.get_generic_recommendations(self.db), "general")


if __name__ == "__main__":
    unittest.main()
