"""Read-only catalog evidence for RD-28; never imports application settings.

Snapshot requires READAR_BASELINE_DATABASE_URL explicitly. Reports contain
counts, schema and hashes, not connection details or customer/book records.
"""

import argparse
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sys

import psycopg2
from psycopg2 import sql


TABLES = ("books", "book_sources")
FORMAT_VERSION = 1


def capture(connection, label):
    # One consistent snapshot, enforced by PostgreSQL, even with a writable role.
    connection.set_session(readonly=True, isolation_level="REPEATABLE READ")
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL statement_timeout = '30s'")
        cursor.execute("SET LOCAL timezone = 'UTC'")
        cursor.execute("SELECT transaction_timestamp(), current_setting('server_version')")
        observed_at, postgres_version = cursor.fetchone()
        cursor.execute("SELECT to_regclass('public.alembic_version')")
        revisions = None
        if cursor.fetchone()[0] is not None:
            cursor.execute("SELECT version_num FROM public.alembic_version ORDER BY version_num")
            revisions = [row[0] for row in cursor.fetchall()]

        tables = {}
        for table in TABLES:
            cursor.execute("""
                SELECT column_name, udt_name, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            columns = [list(row) for row in cursor.fetchall()]
            if not columns:
                raise ValueError(f"Missing required catalog table: {table}")
            # Stable ID ordering and JSON escaping distinguish every stored value.
            # Hash all catalog columns, including tags, insights, covers and dates.
            cursor.execute(sql.SQL("SELECT to_jsonb(t)::text FROM public.{} t ORDER BY id")
                           .format(sql.Identifier(table)))
            digest = hashlib.sha256()
            count = 0
            for (row_json,) in cursor:
                digest.update(row_json.encode("utf-8") + b"\n")
                count += 1
            tables[table] = {"rows": count, "sha256": digest.hexdigest(), "columns": columns}

        cursor.execute("""
            SELECT count(*) FILTER (WHERE knowledge_level IS NOT NULL),
                   count(*) FILTER (WHERE knowledge_level BETWEEN 1 AND 5),
                   count(*) FILTER (WHERE topic_fit = 'off_topic'),
                   count(*) FILTER (WHERE topic_fit IS NULL),
                   count(*) FILTER (WHERE coalesce(cardinality(functional_tags), 0) > 0),
                   count(*) FILTER (WHERE nullif(btrim(cover_image_url), '') IS NOT NULL
                                       OR nullif(btrim(thumbnail_url), '') IS NOT NULL)
            FROM public.books
        """)
        coverage = dict(zip(("knowledge_level_present", "knowledge_level_valid",
                             "off_topic", "unscreened", "functional_tags_present",
                             "cover_url_present"), cursor.fetchone()))
    return {"format_version": FORMAT_VERSION, "label": label,
            "observed_at": observed_at.isoformat(), "postgres_version": postgres_version,
            "migration_revisions": revisions, "tables": tables, "coverage": coverage}


def differences(source, target):
    """Fail closed on incomplete evidence, not just unequal row counts."""
    for report in (source, target):
        if report.get("format_version") != FORMAT_VERSION:
            raise ValueError("Unsupported or missing report format")
        if not report.get("migration_revisions"):
            raise ValueError("Migration revision is missing; catalog parity is unverified")
        if set(report.get("tables", {})) != set(TABLES):
            raise ValueError("Report must describe both catalog tables")
        for table in TABLES:
            item = report["tables"][table]
            if not isinstance(item.get("rows"), int) or item["rows"] < 0:
                raise ValueError("Invalid catalog row count")
            fingerprint = item.get("sha256", "")
            if len(fingerprint) != 64 or any(c not in "0123456789abcdef" for c in fingerprint):
                raise ValueError("Invalid catalog fingerprint")
            if not item.get("columns"):
                raise ValueError("Catalog column metadata is missing")
    changes = []
    if source["migration_revisions"] != target["migration_revisions"]:
        changes.append("migration_revisions")
    for table in TABLES:
        for key in ("columns", "rows", "sha256"):
            if source["tables"][table][key] != target["tables"][table][key]:
                changes.append(f"{table}.{key}")
    return changes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    snapshot = commands.add_parser("snapshot", help="Read catalog state without changing the database")
    snapshot.add_argument("--label", required=True, help="Non-secret name, e.g. live-catalog")
    snapshot.add_argument("--output", type=Path, required=True)
    compare = commands.add_parser("compare", help="Compare two saved reports; mismatch exits 1")
    compare.add_argument("source", type=Path)
    compare.add_argument("target", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            changes = differences(json.loads(args.source.read_text()), json.loads(args.target.read_text()))
            print(json.dumps({"matches": not changes, "differences": changes}, indent=2))
            return int(bool(changes))
        dsn = os.environ.get("READAR_BASELINE_DATABASE_URL")
        if not dsn:
            raise ValueError("Set READAR_BASELINE_DATABASE_URL explicitly; DATABASE_URL is not used")
        with closing(psycopg2.connect(dsn, connect_timeout=10)) as connection:
            report = capture(connection, args.label)
        # Exclusive creation avoids overwriting earlier evidence.
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
            output.write("\n")
        print(f"Saved catalog baseline: {args.output}")
        return 0
    except psycopg2.Error as error:
        # libpq errors can include host/user details; emit only the error class.
        print(f"Catalog read failed ({type(error).__name__}); check access and schema", file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Catalog baseline failed: {error}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
