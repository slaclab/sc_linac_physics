import sqlite3

from sc_linac_physics.applications.tuning.state import tune_status_query


def test_execute_query_prints_rows(tmp_path, capsys):
    db_path = tmp_path / "tune_status.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("create table cavity_state (cavity_id text, df_cold real)")
    conn.execute(
        "insert into cavity_state (cavity_id, df_cold) values (?, ?)",
        ("ACCL:L0B:0110", 12.5),
    )
    conn.commit()
    conn.close()

    tune_status_query.execute_query(
        db_path,
        "select cavity_id, df_cold from cavity_state order by cavity_id",
    )

    output = capsys.readouterr().out
    assert "cavity_id | df_cold" in output
    assert "ACCL:L0B:0110 | 12.5" in output
    assert "1 rows returned" in output
