# backend/app/scripts/add_book_purchase_url_column.py

from sqlalchemy import text
from app.database import engine

DDL_STATEMENTS = [
    "ALTER TABLE books ADD COLUMN IF NOT EXISTS purchase_url VARCHAR",
]


def main() -> None:
    print("Running manual migration to add purchase_url to books...")
    with engine.begin() as conn:
        for stmt in DDL_STATEMENTS:
            print(f"Executing: {stmt}")
            conn.execute(text(stmt))
    print("Finished adding purchase_url column.")


if __name__ == "__main__":
    main()

