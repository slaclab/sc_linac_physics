"""Tests for tune_status_query CLI."""

import sqlite3
from pathlib import Path

from sc_linac_physics.applications.tuning.state import tune_status_query


def test_execute_query_prints_rows(tmp_path, capsys):
    """Test that execute_query prints formatted output."""
    db_path = tmp_path / "tune_status.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("create table cavity_state (cavity_id text, df_cold real)")
    conn.execute(
        "insert into cavity_state (cavity_id, df_cold) values (?, ?)",
        ("ACCL:L0B:0110", 12.5),
    )
    conn.commit()
    conn.close()

    result = tune_status_query.execute_query(
        db_path,
        "select cavity_id, df_cold from cavity_state order by cavity_id",
    )

    assert result is True
    output = capsys.readouterr().out
    assert "cavity_id | df_cold" in output
    assert "ACCL:L0B:0110 | 12.5" in output
    assert "1 rows returned" in output


def test_execute_query_handles_no_results(tmp_path, capsys):
    """Test that execute_query handles empty result sets."""
    db_path = tmp_path / "tune_status.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("create table cavity_state (cavity_id text, df_cold real)")
    conn.commit()
    conn.close()

    result = tune_status_query.execute_query(
        db_path,
        "select * from cavity_state",
    )

    assert result is True
    output = capsys.readouterr().out
    assert "No results" in output


def test_execute_query_handles_sql_errors(tmp_path, capsys):
    """Test that execute_query handles SQL errors gracefully."""
    db_path = tmp_path / "tune_status.sqlite"
    conn = sqlite3.connect(db_path)
    conn.close()

    result = tune_status_query.execute_query(
        db_path,
        "select * from nonexistent_table",
    )

    assert result is False
    output = capsys.readouterr().out
    assert "Error:" in output


def test_parse_args_query_mode():
    """Test parse_args with a SQL query."""
    args = tune_status_query.parse_args(["select", "*", "from", "cavity_state"])
    assert args.query == ["select", "*", "from", "cavity_state"]


def test_parse_args_interactive_mode():
    """Test parse_args with no arguments (interactive mode)."""
    args = tune_status_query.parse_args([])
    assert args.query == []


def test_parse_args_with_base_dir():
    """Test parse_args with custom base directory."""
    args = tune_status_query.parse_args(
        ["--base-dir", "/custom/path", "select", "1"]
    )
    assert args.base_dir == Path("/custom/path")
    assert args.query == ["select", "1"]


def test_parse_args_with_db_path():
    """Test parse_args with custom database path."""
    args = tune_status_query.parse_args(
        ["--db", "/custom/db.sqlite", "select", "1"]
    )
    assert args.db_path_override == Path("/custom/db.sqlite")


def test_main_one_shot_query(tmp_path):
    """Test main() with a one-shot query."""
    db_path = tmp_path / "tune_status.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("create table test (id int)")
    conn.execute("insert into test values (1)")
    conn.commit()
    conn.close()

    exit_code = tune_status_query.main(
        ["--db", str(db_path), "select count(*) from test"]
    )

    assert exit_code == 0


def test_main_one_shot_query_with_error(tmp_path):
    """Test main() with a query that fails."""
    db_path = tmp_path / "tune_status.sqlite"
    conn = sqlite3.connect(db_path)
    conn.close()

    exit_code = tune_status_query.main(
        ["--db", str(db_path), "select * from nonexistent"]
    )

    assert exit_code == 1
