"""Tests for the recommendation topic gate (RD-23)."""
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models import (
    Book,
    TOPIC_FIT_ADJACENT,
    TOPIC_FIT_CORE,
    TOPIC_FIT_OFF,
)
from app.services.recommendation_engine import candidate_books_query


def _book(db: Session, title: str, topic_fit=None, tags=("strategy",)) -> Book:
    book = Book(
        id=uuid4(),
        title=title,
        author_name="Test Author",
        description="A test book",
        functional_tags=list(tags) if tags else None,
        topic_fit=topic_fit,
    )
    db.add(book)
    db.flush()
    return book


def _titles(db: Session):
    return {b.title for b in candidate_books_query(db).all()}


def test_off_topic_books_are_excluded(db: Session):
    _book(db, "Real Business Book", topic_fit=TOPIC_FIT_CORE)
    _book(db, "Calculus for the Practical Man", topic_fit=TOPIC_FIT_OFF)

    titles = _titles(db)
    assert "Real Business Book" in titles
    assert "Calculus for the Practical Man" not in titles


def test_gate_fails_open_for_unscreened_books(db: Session):
    """
    The critical safety property. NULL means "not yet screened", and the whole
    catalog is NULL until the screening script runs — if NULL were filtered out,
    deploying the migration would empty every user's recommendations.
    """
    _book(db, "Unscreened Book", topic_fit=None)
    assert "Unscreened Book" in _titles(db)


def test_adjacent_books_are_kept(db: Session):
    """
    Adjacent is the reason the verdict is three-way rather than boolean: much of
    the curated canon is not about business at all.
    """
    _book(db, "Atomic Habits", topic_fit=TOPIC_FIT_ADJACENT)
    assert "Atomic Habits" in _titles(db)


def test_untagged_stub_still_excluded_regardless_of_topic_fit(db: Session):
    """The pre-existing tag filter must survive alongside the new gate."""
    _book(db, "Tagless Stub", topic_fit=TOPIC_FIT_CORE, tags=None)
    assert "Tagless Stub" not in _titles(db)


@pytest.mark.parametrize("fit", [TOPIC_FIT_CORE, TOPIC_FIT_ADJACENT, None])
def test_only_off_topic_is_filtered(db: Session, fit):
    _book(db, f"Book {fit}", topic_fit=fit)
    assert f"Book {fit}" in _titles(db)
