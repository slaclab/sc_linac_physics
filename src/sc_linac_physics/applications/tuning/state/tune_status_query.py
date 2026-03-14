"""Interactive SQLite query tool for tuning state database."""

import argparse
import sqlite3
from pathlib import Path

from sc_linac_physics.applications.tuning.state.common import (
    DEFAULT_BASE_DIR,
    DEFAULT_DB_PATH,
    connect_db,
    resolve_db_path,
)


def execute_query(db_path: Path, query: str, params=None) -> None:
    """Execute a query and print results."""
    with connect_db(db_path, row_factory=sqlite3.Row) as conn:
        try:
            if params:
                cursor = conn.execute(query, params)
            else:
                cursor = conn.execute(query)

            rows = cursor.fetchall()

            if not rows:
                print("No results")
                return

            headers = rows[0].keys()
            print(" | ".join(headers))
            print(
                "-"
                * (
                    sum(len(header) for header in headers)
                    + 3 * (len(headers) - 1)
                )
            )

            for row in rows:
                print(" | ".join(str(row[header]) for header in headers))

            print(f"\n{len(rows)} rows returned")

        except sqlite3.Error as exc:
            print(f"Error: {exc}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the query tool."""
    parser = argparse.ArgumentParser(
        description="Query tuning state SQLite database interactively or with inline SQL.",
    )
    parser.add_argument(
        "query",
        nargs="*",
        help="SQL query to execute. If omitted, enters interactive mode.",
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        default=DEFAULT_BASE_DIR,
        help=f"Base directory for tuning state database (default: {DEFAULT_BASE_DIR})",
    )
    parser.add_argument(
        "--db",
        "--db-path",
        dest="db_path_override",
        type=Path,
        default=None,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    return parser.parse_args(argv)


def interactive_mode(db_path: Path) -> None:
    """Run a REPL-like interactive SQL prompt."""
    print("SQLite Query Tool")
    print(f"Database: {db_path}")
    print("Enter SQL queries (end with ; then press Enter)")
    print("Type 'quit' to exit\n")

    query_buffer = []

    while True:
        try:
            if query_buffer:
                line = input("   ...> ").strip()
            else:
                line = input("sqlite> ").strip()

            if line.lower() in ("quit", "exit", "q"):
                break

            if not line:
                continue

            query_buffer.append(line)

            if line.endswith(";"):
                full_query = " ".join(query_buffer)
                execute_query(db_path, full_query)
                print()
                query_buffer = []

        except EOFError:
            break
        except KeyboardInterrupt:
            print("\nInterrupted")
            query_buffer = []


def main(argv: list[str] | None = None) -> None:
    """Entry point for tuning state database query CLI."""
    args = parse_args(argv)
    query = " ".join(args.query).strip()
    db_path = resolve_db_path(args.base_dir, args.db_path_override)

    if query:
        execute_query(db_path, query)
    else:
        interactive_mode(db_path)


if __name__ == "__main__":
    main()
