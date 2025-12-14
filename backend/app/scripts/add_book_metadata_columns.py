# backend/app/scripts/add_book_metadata_columns.py

from sqlalchemy import text
from app.database import engine

DDL_STATEMENTS = [
    "ALTER TABLE books ADD COLUMN IF NOT EXISTS language VARCHAR",
    "ALTER TABLE books ADD COLUMN IF NOT EXISTS isbn_10 VARCHAR",
    "ALTER TABLE books ADD COLUMN IF NOT EXISTS isbn_13 VARCHAR",
    "ALTER TABLE books ADD COLUMN IF NOT EXISTS average_rating DOUBLE PRECISION",
    "ALTER TABLE books ADD COLUMN IF NOT EXISTS ratings_count INTEGER",
]


def main() -> None:
    print("Running manual migration to add book metadata columns...")
    with engine.begin() as conn:
        for stmt in DDL_STATEMENTS:
            print(f"Executing: {stmt}")
            conn.execute(text(stmt))
    print("Finished adding book metadata columns.")


if __name__ == "__main__":
    main()

