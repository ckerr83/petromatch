from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, Select, and_, create_engine, func, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import UniqueConstraint

from app.db.base import Base

EXCLUDED_TABLES = {"alembic_version"}


@dataclass(frozen=True)
class TableCopyStats:
    table_name: str
    local: int
    existing_supabase: int
    inserted: int
    skipped: int


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy local PetroMatch PostgreSQL data into Supabase.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Connect and report what would be copied without writes.")
    mode.add_argument("--apply", action="store_true", help="Copy data into Supabase.")
    args = parser.parse_args()

    local_url = _required_env("LOCAL_DATABASE_URL")
    supabase_url = _required_env("SUPABASE_DATABASE_URL")
    local_engine = create_engine(local_url, pool_pre_ping=True)
    supabase_engine = create_engine(supabase_url, pool_pre_ping=True)

    mode_name = "apply" if args.apply else "dry-run"
    print(f"Starting PetroMatch local-to-Supabase copy in {mode_name} mode.")
    print(f"local_database={_safe_database_label(local_url)}")
    print(f"supabase_database={_safe_database_label(supabase_url)}")

    try:
        stats = copy_local_to_supabase(
            local_engine=local_engine,
            supabase_engine=supabase_engine,
            apply=args.apply,
        )
    except SQLAlchemyError as exc:
        raise SystemExit(f"Database copy failed: {type(exc).__name__}: {exc}") from exc

    print_copy_stats(stats)
    if not args.apply:
        print("Dry run complete. No rows were written.")


def copy_local_to_supabase(
    *,
    local_engine: Engine,
    supabase_engine: Engine,
    apply: bool,
) -> list[TableCopyStats]:
    tables = _application_tables()
    stats: list[TableCopyStats] = []
    planned_processed_email_ids: set[Any] = set()

    with local_engine.connect() as local_conn, supabase_engine.begin() as supabase_conn:
        for table in tables:
            local_rows = [dict(row) for row in local_conn.execute(select(table).order_by(*table.primary_key.columns)).mappings()]
            existing_count = supabase_conn.execute(select(func.count()).select_from(table)).scalar_one()
            inserted = 0
            skipped = 0

            for row in local_rows:
                if _target_has_matching_row(supabase_conn, table, row):
                    if table.name == "processed_emails" and _target_has_primary_key(supabase_conn, table, row):
                        planned_processed_email_ids.add(row["id"])
                    skipped += 1
                    continue

                if table.name == "jobs" and not _target_parent_email_exists(
                    supabase_conn,
                    row,
                    planned_processed_email_ids,
                ):
                    skipped += 1
                    continue

                if apply:
                    supabase_conn.execute(table.insert().values(**row))
                if table.name == "processed_emails":
                    planned_processed_email_ids.add(row["id"])
                inserted += 1

            stats.append(
                TableCopyStats(
                    table_name=table.name,
                    local=len(local_rows),
                    existing_supabase=existing_count,
                    inserted=inserted,
                    skipped=skipped,
                )
            )

        if apply:
            reset_postgres_sequences(supabase_conn, tables)

    return stats


def reset_postgres_sequences(connection: Any, tables: list[Any]) -> None:
    if connection.dialect.name != "postgresql":
        return

    for table in tables:
        primary_key_columns = list(table.primary_key.columns)
        if len(primary_key_columns) != 1:
            continue
        pk_column = primary_key_columns[0]
        max_id = connection.execute(select(func.max(pk_column))).scalar_one()
        if max_id is None:
            continue
        qualified_table_name = f"{table.schema}.{table.name}" if table.schema else table.name
        connection.execute(
            text(
                "SELECT setval("
                "pg_get_serial_sequence(:table_name, :column_name), "
                ":max_id, "
                "true"
                ")"
            ),
            {
                "table_name": qualified_table_name,
                "column_name": pk_column.name,
                "max_id": int(max_id),
            },
        )


def print_copy_stats(stats: list[TableCopyStats]) -> None:
    for table_stats in stats:
        print(f"{table_stats.table_name}:")
        print(f"  local: {table_stats.local}")
        print(f"  existing_supabase: {table_stats.existing_supabase}")
        print(f"  inserted: {table_stats.inserted}")
        print(f"  skipped: {table_stats.skipped}")


def _application_tables() -> list[Any]:
    return [table for table in Base.metadata.sorted_tables if table.name not in EXCLUDED_TABLES]


def _target_has_matching_row(connection: Any, table: Any, row: dict[str, Any]) -> bool:
    checks = _stable_match_checks(table, row)
    if not checks:
        return False
    query: Select[Any] = select(table.primary_key.columns.values()[0]).where(or_(*checks)).limit(1)
    return connection.execute(query).first() is not None


def _target_has_primary_key(connection: Any, table: Any, row: dict[str, Any]) -> bool:
    primary_key_columns = list(table.primary_key.columns)
    if not primary_key_columns or any(row.get(column.name) is None for column in primary_key_columns):
        return False
    query = select(primary_key_columns[0]).where(
        and_(*(column == row[column.name] for column in primary_key_columns))
    ).limit(1)
    return connection.execute(query).first() is not None


def _stable_match_checks(table: Any, row: dict[str, Any]) -> list[Any]:
    checks: list[Any] = []
    primary_key_columns = list(table.primary_key.columns)
    if primary_key_columns and all(row.get(column.name) is not None for column in primary_key_columns):
        checks.append(and_(*(column == row[column.name] for column in primary_key_columns)))

    for constraint in table.constraints:
        if not isinstance(constraint, UniqueConstraint):
            continue
        columns = list(constraint.columns)
        if not columns:
            continue
        if any(row.get(column.name) is None for column in columns):
            continue
        checks.append(and_(*(column == row[column.name] for column in columns)))

    for column in table.columns:
        if not column.unique:
            continue
        if row.get(column.name) is None:
            continue
        checks.append(column == row[column.name])

    return checks


def _target_parent_email_exists(
    connection: Any,
    job_row: dict[str, Any],
    planned_processed_email_ids: set[Any],
) -> bool:
    processed_email_id = job_row.get("processed_email_id")
    if processed_email_id is None:
        return False
    if processed_email_id in planned_processed_email_ids:
        return True
    processed_emails = Base.metadata.tables["processed_emails"]
    return (
        connection.execute(
            select(processed_emails.c.id).where(processed_emails.c.id == processed_email_id).limit(1)
        ).first()
        is not None
    )


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SystemExit(f"{name} is required.")
    return value


def _safe_database_label(url: str) -> str:
    engine = create_engine(url)
    parsed = engine.url
    host = parsed.host or "unknown-host"
    database = parsed.database or "unknown-database"
    return f"{host}/{database}"


if __name__ == "__main__":
    main()
