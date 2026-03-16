import json
import sqlite3

from sc_linac_physics.applications.tuning.state import tune_status_poll


def test_parse_tune_config_variants():
    code, label = tune_status_poll.parse_tune_config(None)
    assert code is None
    assert label == "Not connected"

    code, label = tune_status_poll.parse_tune_config("1")
    assert code == 1
    assert label == "Cold landing"

    code, label = tune_status_poll.parse_tune_config("Parked")
    assert code == 2
    assert label == "Parked"

    code, label = tune_status_poll.parse_tune_config("mystery")
    assert code is None
    assert label == "mystery"


def test_main_writes_db_and_snapshot(monkeypatch, tmp_path):
    cavity_id = "ACCL:L0B:0110"

    def fake_iter_cavity_ids():
        yield cavity_id

    def fake_caget_values(*args, **kwargs):
        names = tune_status_poll.pv_names(cavity_id)
        return {
            names["tune_config"]: "Cold landing",
            names["df_cold"]: "12.5",
        }

    monkeypatch.setattr(
        tune_status_poll, "iter_cavity_ids", fake_iter_cavity_ids
    )
    monkeypatch.setattr(tune_status_poll, "caget_values", fake_caget_values)

    exit_code = tune_status_poll.main(["--base-dir", str(tmp_path)])
    assert exit_code == 0

    db_path = tmp_path / "tune_status.sqlite"
    json_path = tmp_path / "tune_status.json"
    assert db_path.exists()
    assert json_path.exists()

    with json_path.open("r", encoding="utf-8") as stream:
        snapshot = json.load(stream)

    assert len(snapshot) == 1
    assert snapshot[0]["cavity_id"] == cavity_id
    assert snapshot[0]["tune_config_code"] == 1
    assert snapshot[0]["tune_config_label"] == "Cold landing"
    assert snapshot[0]["df_cold"] == 12.5

    conn = sqlite3.connect(db_path)
    state_row = conn.execute(
        "select cavity_id, tune_config_code, tune_config_label, df_cold from cavity_state"
    ).fetchone()
    tune_row = conn.execute(
        "select cavity_id, tune_config_code from tune_config_version"
    ).fetchone()
    df_row = conn.execute(
        "select cavity_id, df_cold from df_cold_version"
    ).fetchone()
    conn.close()

    assert state_row == (cavity_id, 1, "Cold landing", 12.5)
    assert tune_row == (cavity_id, 1)
    assert df_row == (cavity_id, 12.5)


def test_caget_values_uses_epics_batch(monkeypatch):
    calls = []

    def fake_get_values(pv_names, timeout):
        calls.append((list(pv_names), timeout))
        return ["Parked", 12.5]

    monkeypatch.setattr(
        tune_status_poll.PVBatch,
        "get_values",
        staticmethod(fake_get_values),
    )

    values = tune_status_poll.caget_values(
        pvs=["PV:TUNE", "PV:DF"],
        caget_timeout_sec=3,
        command_timeout_sec=60,
        batch_size=2,
        caget_command="caget",
    )

    assert values == {"PV:TUNE": "Parked", "PV:DF": 12.5}
    assert calls == [(["PV:TUNE", "PV:DF"], 3.0)]
