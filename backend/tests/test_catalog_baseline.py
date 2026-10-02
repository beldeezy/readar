"""Prove stale catalogs cannot pass just because their counts match."""

from copy import deepcopy
from contextlib import closing
from datetime import datetime, timezone
import json
import os
from uuid import uuid4

import psycopg2
import pytest
from sqlalchemy import text

from scripts.catalog_baseline import capture, differences, main


def report():
    return {"format_version": 1, "label": "synthetic", "migration_revisions": ["review-head"],
            "tables": {name: {"rows": 1, "sha256": "a" * 64,
                              "columns": [["id", "uuid", "NO"]]}
                       for name in ("books", "book_sources")}}


def test_compare_ignores_capture_time_and_label():
    source = report()
    target = deepcopy(source)
    target.update(label="local", observed_at="2026-09-27T22:00:00Z")
    assert differences(source, target) == []


@pytest.mark.parametrize("table,key,value", [
    ("books", "sha256", "b" * 64),
    ("book_sources", "sha256", "c" * 64),
    ("books", "rows", 2),
    ("books", "columns", [["id", "text", "NO"]]),
])
def test_compare_detects_content_counts_and_schema_changes(table, key, value):
    source = report()
    target = deepcopy(source)
    target["tables"][table][key] = value
    assert differences(source, target) == [f"{table}.{key}"]


def test_compare_detects_migration_difference():
    source = report()
    target = deepcopy(source)
    target["migration_revisions"] = ["older-head"]
    assert differences(source, target) == ["migration_revisions"]


@pytest.mark.parametrize("bad", [{}, {"format_version": 1},
                                   {"format_version": 1, "migration_revisions": ["head"], "tables": {}}])
def test_missing_evidence_cannot_match(bad):
    with pytest.raises(ValueError):
        differences(bad, bad)


def test_cli_refuses_implicit_app_database(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("READAR_BASELINE_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused/app")
    assert main(["snapshot", "--label", "test", "--output", str(tmp_path / "report.json")]) == 2
    assert "DATABASE_URL is not used" in capsys.readouterr().err
    assert not (tmp_path / "report.json").exists()


def test_cli_mismatch_returns_nonzero(tmp_path):
    source, target = report(), report()
    target["tables"]["books"]["sha256"] = "b" * 64
    paths = [tmp_path / "source.json", tmp_path / "target.json"]
    for path, content in zip(paths, (source, target)):
        path.write_text(json.dumps(content))
    assert main(["compare", *map(str, paths)]) == 1


def test_postgres_snapshot_is_readonly_and_detects_same_count_edit(engine):
    book_id = uuid4()
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO books (id, title, author_name, description, knowledge_level)
            VALUES (:id, 'Synthetic RD-28 book', 'Fixture Author', 'Fixture only', 1)
        """), {"id": book_id})
    try:
        with closing(psycopg2.connect(os.environ["TEST_DATABASE_URL"])) as connection:
            before = capture(connection, "synthetic-before")
            with connection.cursor() as cursor:
                cursor.execute("SHOW transaction_read_only")
                assert cursor.fetchone()[0] == "on"
                with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
                    cursor.execute("UPDATE books SET knowledge_level = 5 WHERE id = %s", (str(book_id),))
        with engine.begin() as connection:
            connection.execute(text("UPDATE books SET knowledge_level = 2 WHERE id = :id"), {"id": book_id})
        with closing(psycopg2.connect(os.environ["TEST_DATABASE_URL"])) as connection:
            after = capture(connection, "synthetic-after")
        assert before["tables"]["books"]["rows"] == after["tables"]["books"]["rows"]
        assert before["tables"]["books"]["sha256"] != after["tables"]["books"]["sha256"]
        assert before["tables"]["book_sources"] == after["tables"]["book_sources"]
        assert "Synthetic RD-28 book" not in json.dumps(before)
        assert datetime.fromisoformat(before["observed_at"]).tzinfo == timezone.utc
    finally:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM books WHERE id = :id"), {"id": book_id})
