"""RD-11 regression checks without network, model calls or a database."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import UUID

from app.models import Book
from app.schemas.onboarding import OnboardingPayload
from app.services import challenge_matching as cm
from app.services import recommendation_engine as engine
from app.services.recommendation_explanations import build_book_fit


class ChallengeMatchingTests(unittest.TestCase):
    def test_sentence_and_tag_use_the_same_bottleneck_keys(self):
        profile = SimpleNamespace(
            business_model=None, business_stage=None, areas_of_business=[],
            biggest_challenge="Our plumbing company cannot get enough clients; lead flow is unpredictable.",
        )
        book = Book(functional_tags=["marketing"], theme_tags=["client_acquisition"],
                    promise="Build a local referral engine.")
        reader_keys = {i['key'] for i in engine._build_user_insights(profile)}
        self.assertIn("bottleneck:client_acquisition", reader_keys & engine._get_book_insight_tags(book))

    def test_words_do_not_match_inside_unrelated_words(self):
        self.assertNotIn("sales", cm.domains("I need leadership and a new bookshelf"))
        self.assertFalse(cm.concepts("Our marginsheet has the wrong pricetag font"))
        self.assertIn("client_acquisition", cm.concepts("We need more leads"))
        self.assertIn("team_leadership", cm.concepts("Improve my leadership"))

    def test_normalization_handles_tags_hyphens_case_and_html(self):
        for text in ("CLIENT_ACQUISITION", "client-acquisition", "<p>Client acquisition</p>"):
            self.assertEqual(cm.concepts(text), {"client_acquisition"})

    def test_future_goal_does_not_replace_current_challenge(self):
        ctx = {"biggest_challenge": "I need reliable lead flow", "vision": "Hire a manager and step back"}
        self.assertEqual(cm.priority_concepts(ctx), {"client_acquisition"})
        self.assertEqual(cm.priority_concepts({"vision": "Improve our pricing"}), {"pricing"})

    def test_specific_evidence_beats_generic_sales_tags(self):
        ctx = {"biggest_challenge": "Not enough leads to fill our cleaners' schedules", "problem_domains": {"sales"}}
        direct = Book(functional_tags=["marketing"], theme_tags=["local_marketing"],
                      promise="Develop repeatable client acquisition.")
        generic = Book(functional_tags=["sales", "marketing"], theme_tags=[],
                       promise="Use metaphors to explain ideas persuasively.")
        self.assertGreater(engine._score_from_problem(ctx, direct), engine._score_from_problem(ctx, generic))
        self.assertEqual(engine._score_from_problem(ctx, generic), .75)
        self.assertIn("customer acquisition", build_book_fit(ctx, direct)["reason"])

    def test_repeated_metadata_does_not_inflate_score(self):
        ctx = {"biggest_challenge": "We need leads"}
        book = Book(theme_tags=["lead_generation"])
        score = cm.specific_score(ctx, book)
        book.theme_tags *= 30
        book.promise = "Lead generation. " * 30
        self.assertEqual(cm.specific_score(ctx, book), score)

    def test_unrecognized_problem_and_sparse_book_do_not_fake_specific_fit(self):
        self.assertEqual(cm.specific_score({"biggest_challenge": "I am not sure yet"}, Book()), 0)
        fit = build_book_fit({"biggest_challenge": "I need leads"}, Book())
        self.assertEqual(fit["match_type"], "general")

    def test_fit_uses_full_priority_before_display_truncation(self):
        ctx = {"biggest_challenge": "Some background context. " * 20 + "Our biggest issue is lead generation."}
        book = Book(theme_tags=["client_acquisition"])
        fit = build_book_fit(ctx, book)
        self.assertIn("customer acquisition", fit["reason"])
        self.assertLessEqual(len(fit["priority"]), 180)

    def test_prose_promise_and_outcome_match_without_exact_sentence_containment(self):
        profile = SimpleNamespace(biggest_challenge="We cannot find enough customers to stay busy",
                                  vision_6_12_months="Get more clients from referrals")
        book = Book(promise="Build a repeatable client acquisition system.",
                    outcomes=["A stronger local referral pipeline"])
        self.assertEqual(engine.score_promise_match(book, profile), 1)
        self.assertEqual(engine.score_outcome_match(book, profile), 1)

    def test_same_stage_different_challenge_changes_top_book(self):
        books = [
            Book(id=UUID(int=1), title="Find Customers", author_name="A", functional_tags=["marketing"],
                 theme_tags=["client_acquisition"], business_stage_tags=["early-revenue"]),
            Book(id=UUID(int=2), title="Keep Your Cash", author_name="B", functional_tags=["finance"],
                 theme_tags=["cash_flow"], business_stage_tags=["early-revenue"]),
        ]
        with patch.object(engine, "candidate_books_query") as candidates:
            candidates.return_value.all.return_value = books
            def top(challenge):
                payload = OnboardingPayload(business_model="other", business_stage="early-revenue",
                                            biggest_challenge=challenge)
                return engine.get_recommendations_from_payload(Mock(), payload, limit=1)[0].title
            self.assertEqual(top("I cannot find enough customers"), "Find Customers")
            self.assertEqual(top("I never have cash to pay myself"), "Keep Your Cash")

    def test_ties_and_diversity_are_independent_of_database_row_order(self):
        books = {
            UUID(int=i): Book(id=UUID(int=i), title=title, author_name="Same Author")
            for i, title in [(1, "Beta"), (2, "Alpha"), (3, "Gamma")]
        }
        scores = [(id_, 10) for id_ in books]
        insights = {id_: "same" for id_ in books}
        forward, _ = engine._apply_diversity_penalty(scores, insights, books)
        reverse, _ = engine._apply_diversity_penalty(list(reversed(scores)), insights, books)
        self.assertEqual(forward, reverse)
        self.assertEqual(forward[0][0], UUID(int=2))

    def test_legacy_entrypoint_uses_the_authenticated_ranker(self):
        db = Mock()
        with patch.object(engine, "_get_user", return_value=object()), \
             patch.object(engine, "get_personalized_recommendations", return_value=["ranked"]) as ranker:
            self.assertEqual(engine.get_recommendations_for_user(UUID(int=1), db, limit=5), ["ranked"])
            ranker.assert_called_once_with(db=db, user_id=UUID(int=1), limit=5)


if __name__ == "__main__":
    unittest.main()
