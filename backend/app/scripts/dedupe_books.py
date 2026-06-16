# backend/app/scripts/dedupe_books.py
"""
Merge duplicate catalog books that are edition/subtitle variants of the same
work (e.g. "$100M Leads" vs "$100M Leads: How to... (Acquisition.com Series)").

Grouping uses the same canonical key as the import de-dup, so this cleanup and
the preventive ingest logic stay in sync.

For each group of duplicates it keeps the most complete record and repoints all
references (interactions, statuses, reading history, recommendation events) to
the keeper, then deletes the duplicates (BookSource rows cascade).

DRY RUN by default — pass --apply to actually write.

    python -m app.scripts.dedupe_books            # preview
    python -m app.scripts.dedupe_books --apply    # execute
"""
import argparse
import logging
from collections import defaultdict
from typing import List

from app.database import SessionLocal
from app.models import (
    Book,
    UserBookInteraction,
    RecommendationEvent,
    ReadingHistoryEntry,
    UserBookStatusModel,
)
from app.routers.reading_history import canonical_title_key

logger = logging.getLogger("dedupe_books")
logging.basicConfig(level=logging.INFO)

PLACEHOLDER_PREFIX = "Imported from Goodreads"


def _created_ts(book: Book) -> float:
    """Sortable timestamp; tolerant of naive/aware/None created_at."""
    try:
        return book.created_at.timestamp() if book.created_at else 0.0
    except Exception:
        return 0.0


def _completeness_score(book: Book) -> int:
    """Higher = more complete; used to choose which duplicate to keep."""
    score = 0
    if book.cover_image_url:
        score += 2
    desc = book.description or ""
    if desc and not desc.startswith(PLACEHOLDER_PREFIX) and desc != "No description available.":
        score += 2
    if getattr(book, "promise", None):
        score += 1
    score += len(book.functional_tags or []) + len(book.business_stage_tags or [])
    return score


def _pick_keeper(group: List[Book]) -> Book:
    # Most complete first; earliest created_at as the stable tie-breaker.
    return sorted(group, key=lambda b: (-_completeness_score(b), _created_ts(b)))[0]


def dedupe(apply: bool = False) -> None:
    db = SessionLocal()
    try:
        all_books = db.query(Book).all()
        groups = defaultdict(list)
        for b in all_books:
            if b.title and b.author_name:
                groups[canonical_title_key(b.title, b.author_name)].append(b)

        dup_groups = {k: v for k, v in groups.items() if len(v) > 1}
        logger.info(
            "Catalog: %d books, %d canonical groups, %d with duplicates",
            len(all_books), len(groups), len(dup_groups),
        )

        total_merged = 0
        for key, group in dup_groups.items():
            keeper = _pick_keeper(group)
            dupes = [b for b in group if b.id != keeper.id]
            logger.info(
                "Group %s: keep '%s' (%s); merging %d dupe(s): %s",
                key, keeper.title, keeper.id, len(dupes),
                [str(d.id) for d in dupes],
            )

            if not apply:
                total_merged += len(dupes)
                continue

            # Pre-load users that already have a status row for the keeper.
            keeper_status_users = {
                r.user_id for r in db.query(UserBookStatusModel.user_id)
                .filter(UserBookStatusModel.book_id == str(keeper.id)).all()
            }

            for dupe in dupes:
                # UUID-FK references → repoint to keeper
                db.query(UserBookInteraction).filter(
                    UserBookInteraction.book_id == dupe.id
                ).update({UserBookInteraction.book_id: keeper.id}, synchronize_session=False)

                db.query(RecommendationEvent).filter(
                    RecommendationEvent.book_id == dupe.id
                ).update({RecommendationEvent.book_id: keeper.id}, synchronize_session=False)

                db.query(ReadingHistoryEntry).filter(
                    ReadingHistoryEntry.catalog_book_id == dupe.id
                ).update({ReadingHistoryEntry.catalog_book_id: keeper.id}, synchronize_session=False)

                # user_book_status: string book_id with UNIQUE(user_id, book_id)
                for r in db.query(UserBookStatusModel).filter(
                    UserBookStatusModel.book_id == str(dupe.id)
                ).all():
                    if r.user_id in keeper_status_users:
                        db.delete(r)  # keeper already has a status for this user
                    else:
                        r.book_id = str(keeper.id)
                        keeper_status_users.add(r.user_id)

                # Delete the duplicate book (BookSource rows cascade)
                db.delete(dupe)
                total_merged += 1

            db.commit()

        if apply:
            logger.info("Done. Merged %d duplicate book(s).", total_merged)
        else:
            logger.info("DRY RUN — would merge %d duplicate book(s). Re-run with --apply.", total_merged)
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Merge duplicate catalog books.")
    parser.add_argument("--apply", action="store_true", help="Execute the merge (default is dry-run).")
    args = parser.parse_args()
    dedupe(apply=args.apply)
