"""
Golden-set relevance harness for the recommendation engine (RD-10).

WHY THIS EXISTS
---------------
Every other recommendation test asserts *mechanics* — that a scorer returns 1.0
for a crafted input, or that two runs agree. None of them answer the only
question that matters for a relevance product: **when a real founder describes a
real problem, do we hand them the right book?**

With ~3 signups there is no traffic to A/B against, so a labelled fixture set is
the only available signal. This harness is the gate for RD-11 (challenge
matching), RD-12 (business_model signal), RD-13 (deleting the dead scorer) and
RD-16 (diversity tuning) — each of those changes ranking, and without a number
to move, "did it get better?" is unanswerable.

HOW IT WORKS
------------
17 personas (tests/fixtures/relevance_personas.json), each written the way a real
user types — sentences, not keywords. Each is scored through the real cold-start
entrypoint (`get_recommendations_from_payload`) against the real tagged canon.
A persona "hits" at N if any expected title lands in the top N.

THE RATCHET
-----------
This suite does NOT assert that relevance is good — today it is not, and a
suite that fails on arrival gets deleted or ignored. Instead it pins the CURRENT
numbers as a floor. Regressions fail. Improvements are expected to raise the
floor, deliberately, in the same commit that earns them.

To re-baseline after an intentional ranking change:
    pytest tests/test_recommendation_relevance.py -s
read the scoreboard, and update the BASELINE_* constants below IN THE SAME
COMMIT as the change, with a note saying why the number moved.

Run:
    export TEST_DATABASE_URL="postgresql://<user>@localhost:5432/test_readar"
    python -m pytest tests/test_recommendation_relevance.py -s
"""
import json
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import Book
from app.routers.reading_history import canonical_title_key
from app.schemas.onboarding import OnboardingPayload
from app.services.recommendation_engine import get_recommendations_from_payload

# ── Ratchet ──────────────────────────────────────────────────────────────────
# Measured against the tagged canon on 2026-07-16, BEFORE RD-11/RD-12 landed:
#   hit@3=8/15 (0.533)   hit@5=10/15 (0.667)   MRR=0.446
# Pinned a hair below measured so float noise cannot flake the build; a genuine
# regression moves hit@3 by >=6.7pp (one persona), far outside that slack.
# These are a floor, not a target. See "THE RATCHET" above before editing.
# RD-11 (2026-09-21): shared concept matching improves the ORIGINAL 15 to
# hit@3=13/15, hit@5=15/15, MRR=0.755556. New P16/P17 cannot mask regressions.
BASELINE_HIT_AT_3 = 0.86
BASELINE_HIT_AT_5 = 1.0
BASELINE_MRR = 0.75

# Ranks the harness reports at. TOP_N is what we ask the engine for.
TOP_N = 10

FIXTURES = Path(__file__).parent / "fixtures"
CANON_FILES = [
    "readar_canon_v1.json",
    "readar_canon_services_v1.json",
    "readar_canon_saas_v1.json",
]


def _title_key(title: str) -> str:
    """Canonical title key, reusing the catalog's own de-dup rule."""
    return canonical_title_key(title, "")[0]


def _load_canon() -> List[Dict[str, Any]]:
    """
    Load the *recommendable* canon: tagged books only.

    The expansion canons (readar_canon_expansion_v1/v2) are title+author only —
    they carry no tags until generate_tags.py runs (RD-09), and until then
    candidate_books_query filters them out entirely. Seeding them here would
    model a catalog the engine cannot actually see.
    """
    data_dir = Path(__file__).parent.parent / "app" / "data"

    insights_by_key: Dict[str, Dict[str, Any]] = {}
    for entry in json.loads((data_dir / "enriched_book_insights.json").read_text()):
        insights_by_key[_title_key(entry["title"])] = entry

    books: Dict[str, Dict[str, Any]] = {}
    for filename in CANON_FILES:
        for entry in json.loads((data_dir / filename).read_text()):
            if not (
                entry.get("functional_tags")
                or entry.get("business_stage_tags")
                or entry.get("theme_tags")
            ):
                continue  # untagged -> invisible to candidate_books_query
            key = _title_key(entry["title"])
            if key in books:
                continue  # first file wins; mirrors seed_books idempotency
            merged = dict(entry)
            # Real DB rows carry promise/core_frameworks/outcomes from generate_tags.
            # Merging the enriched insights we have keeps the fixture faithful to
            # production rather than under-representing those fields.
            merged.update(insights_by_key.get(key, {}))
            books[key] = merged
    return list(books.values())


@pytest.fixture(scope="function")
def relevance_catalog(db: Session) -> Dict[str, Book]:
    """Seed the tagged canon into the test DB. Returns {title_key: Book}."""
    catalog: Dict[str, Book] = {}
    for entry in _load_canon():
        book = Book(
            id=uuid4(),
            title=entry["title"],
            subtitle=entry.get("subtitle"),
            author_name=entry.get("author_name") or "Unknown",
            description=entry.get("promise") or entry["title"],  # NOT NULL
            published_year=entry.get("published_year"),
            categories=entry.get("categories"),
            business_stage_tags=entry.get("business_stage_tags"),
            functional_tags=entry.get("functional_tags"),
            theme_tags=entry.get("theme_tags"),
            promise=entry.get("promise"),
            best_for=entry.get("best_for"),
            core_frameworks=entry.get("core_frameworks"),
            outcomes=entry.get("outcomes"),
        )
        db.add(book)
        catalog[_title_key(entry["title"])] = book
    db.flush()
    return catalog


def _load_personas() -> List[Dict[str, Any]]:
    return json.loads((FIXTURES / "relevance_personas.json").read_text())["personas"]


def _rank_of_first_expected(ranked_titles: List[str], expected: List[str]) -> int | None:
    """1-indexed rank of the first expected title, or None if absent."""
    wanted = {_title_key(t) for t in expected}
    for i, title in enumerate(ranked_titles, start=1):
        if _title_key(title) in wanted:
            return i
    return None


def _evaluate(db: Session) -> List[Dict[str, Any]]:
    """Score every persona through the real cold-start entrypoint."""
    results = []
    for persona in _load_personas():
        payload = OnboardingPayload(**persona["payload"])
        items = get_recommendations_from_payload(db, payload, limit=TOP_N)
        ranked = [item.title for item in items]
        rank = _rank_of_first_expected(ranked, persona["expected_any_of"])
        results.append(
            {
                "id": persona["id"],
                "label": persona["label"],
                "rank": rank,
                "top3": ranked[:3],
                "expected": persona["expected_any_of"],
            }
        )
    return results


def test_every_expected_title_exists_in_catalog(relevance_catalog):
    """
    Fixture integrity: an expected title that is not in the catalog can never be
    recommended, so it would silently depress the score forever and look like an
    engine failure. Catch the typo here instead.
    """
    missing = {
        f"{p['id']}: {title}"
        for p in _load_personas()
        for title in p["expected_any_of"]
        if _title_key(title) not in relevance_catalog
    }
    assert not missing, f"Expected titles absent from the tagged canon: {sorted(missing)}"


def test_relevance_scoreboard(db: Session, relevance_catalog):
    """The ratchet. Prints the scoreboard, then asserts no regression."""
    results = _evaluate(db)
    # Keep the historical denominator fixed; evaluate new cases separately.
    original = [row for row in results if int(row["id"][1:]) <= 15]
    assert len(original) == 15
    n = len(original)

    hit_at_3 = sum(1 for r in original if r["rank"] and r["rank"] <= 3) / n
    hit_at_5 = sum(1 for r in original if r["rank"] and r["rank"] <= 5) / n
    mrr = sum(1.0 / r["rank"] for r in original if r["rank"]) / n

    print(f"\n{'':<5}{'persona':<46}{'rank':>6}   top-3 returned")
    print("-" * 110)
    for r in results:
        rank = str(r["rank"]) if r["rank"] else "MISS"
        print(f"{r['id']:<5}{r['label'][:44]:<46}{rank:>6}   {', '.join(r['top3'])[:52]}")
    print("-" * 110)
    print(
        f"catalog={len(relevance_catalog)} books | original personas={n} | "
        f"hit@3={hit_at_3:.0%} hit@5={hit_at_5:.0%} MRR={mrr:.3f}"
    )
    print(
        f"baseline: hit@3={BASELINE_HIT_AT_3:.0%} hit@5={BASELINE_HIT_AT_5:.0%} "
        f"MRR={BASELINE_MRR:.3f}"
    )

    assert hit_at_3 >= BASELINE_HIT_AT_3, f"hit@3 regressed: {hit_at_3:.0%} < {BASELINE_HIT_AT_3:.0%}"
    assert hit_at_5 >= BASELINE_HIT_AT_5, f"hit@5 regressed: {hit_at_5:.0%} < {BASELINE_HIT_AT_5:.0%}"
    assert mrr >= BASELINE_MRR, f"MRR regressed: {mrr:.3f} < {BASELINE_MRR:.3f}"


@pytest.mark.parametrize("persona_id", ["P16", "P17"])
def test_cleaning_business_preview_and_saved_profile_agree(db, relevance_catalog, persona_id):
    """The actual signed-in scorer must match preview, not a different legacy path."""
    from app.models import User, OnboardingProfile
    from app.services.recommendation_engine import get_personalized_recommendations, get_recommendations_for_user

    persona = next(p for p in _load_personas() if p["id"] == persona_id)
    payload = OnboardingPayload(**persona["payload"])
    user = User(id=uuid4(), email=f"{uuid4()}@example.test")
    db.add(user)
    db.flush()
    profile = OnboardingProfile(user_id=user.id, **persona["payload"])
    db.add(profile)
    db.commit()
    db.expire_all()
    assert db.query(OnboardingProfile).filter_by(user_id=user.id).one().biggest_challenge == payload.biggest_challenge

    preview = get_recommendations_from_payload(db, payload, limit=5)
    saved = get_personalized_recommendations(db, user.id, limit=5)
    legacy = get_recommendations_for_user(user.id, db, limit=5)
    assert [b.book_id for b in preview] == [b.book_id for b in saved] == [b.book_id for b in legacy]
    assert _rank_of_first_expected([b.title for b in saved], persona["expected_any_of"]) == 1
    assert "customer acquisition" in saved[0].fit.reason


def test_cleaning_business_goodreads_receipt_changes_picks_and_is_account_private(db, relevance_catalog):
    """Import real CSV rows, then rank with persisted history (no provider calls)."""
    import asyncio
    import csv
    from io import BytesIO, StringIO
    from fastapi import BackgroundTasks, UploadFile
    from app.models import User, OnboardingProfile, ReadingHistoryEntry
    from app.routers.reading_history import upload_reading_history_csv
    from app.services.recommendation_engine import get_personalized_recommendations

    persona = next(p for p in _load_personas() if p["id"] == "P16")
    user, other = [User(id=uuid4(), email=f"{uuid4()}@example.test") for _ in range(2)]
    db.add_all([user, other])
    db.flush()
    db.add_all([OnboardingProfile(user_id=u.id, **persona["payload"]) for u in (user, other)])
    db.commit()
    before = get_personalized_recommendations(db, user.id, limit=5)
    first_book = relevance_catalog[_title_key(before[0].title)]
    csv_text = StringIO()
    writer = csv.DictWriter(csv_text, fieldnames=["Title", "Author", "My Rating", "Exclusive Shelf"])
    writer.writeheader()
    writer.writerow({"Title": first_book.title, "Author": first_book.author_name, "My Rating": "5", "Exclusive Shelf": "read"})
    receipt = asyncio.run(upload_reading_history_csv(
        BackgroundTasks(), UploadFile(filename="goodreads.csv", file=BytesIO(csv_text.getvalue().encode())), user, db,
    ))
    assert receipt["imported_count"] == 1
    assert receipt["new_books_added"] == 0
    db.expire_all()
    history = db.query(ReadingHistoryEntry).filter_by(user_id=user.id).one()
    assert history.catalog_book_id == first_book.id
    assert history.shelf == "read"
    after = get_personalized_recommendations(db, user.id, limit=5)
    other_picks = get_personalized_recommendations(db, other.id, limit=5)
    assert str(first_book.id) not in {item.book_id for item in after}
    assert [b.book_id for b in after] != [b.book_id for b in before]
    assert _rank_of_first_expected([b.title for b in after], persona["expected_any_of"]) == 1
    assert [b.book_id for b in other_picks] == [b.book_id for b in before]
