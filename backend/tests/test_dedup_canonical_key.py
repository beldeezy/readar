"""Unit tests for the catalog de-duplication key (canonical_title_key).

This key powers both import de-dup and the dedupe_books cleanup script, so
edition/subtitle/parenthetical variants of the same book must collapse together.
Pure function — no database required.
"""
from app.routers.reading_history import canonical_title_key


def test_subtitle_variants_collapse():
    """A title and its 'Title: subtitle' variant map to the same key."""
    base = canonical_title_key("$100M Leads", "Alex Hormozi")
    with_sub = canonical_title_key(
        "$100M Leads: How to Get Strangers To Want To Buy Your Stuff", "Alex Hormozi"
    )
    assert base == with_sub
    assert base == ("100m leads", "alex hormozi")


def test_parenthetical_variants_collapse():
    """Series/edition parentheticals are stripped."""
    base = canonical_title_key("$100M Leads", "Alex Hormozi")
    with_paren = canonical_title_key(
        "$100M Leads (Acquisition.com $100M Series)", "Alex Hormozi"
    )
    assert base == with_paren


def test_case_and_punctuation_normalized():
    """Casing and punctuation differences don't matter."""
    a = canonical_title_key("The E-Myth Revisited", "Michael E. Gerber")
    b = canonical_title_key("the e myth revisited", "michael e gerber")
    assert a == b


def test_author_punctuation_normalized():
    """Author punctuation (periods, ampersands) is normalized away."""
    a = canonical_title_key("Built to Last", "Jim Collins & Jerry I. Porras")
    b = canonical_title_key("Built to Last", "Jim Collins  Jerry I Porras")
    assert a == b


def test_distinct_titles_have_distinct_keys():
    """Genuinely different books must not collide."""
    a = canonical_title_key("Traction", "Gabriel Weinberg & Justin Mares")
    b = canonical_title_key("Traction", "Gino Wickman")
    assert a != b  # same title, different author -> different key


def test_whitespace_collapsed_and_stripped():
    extra_ws = canonical_title_key("  Deep   Work  ", "  Cal  Newport ")
    assert extra_ws == ("deep work", "cal newport")


def test_handles_empty_and_none_safely():
    assert canonical_title_key("", "") == ("", "")
    assert canonical_title_key(None, None) == ("", "")
