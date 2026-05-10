"""Additional comprehensive tests for tune_status_poll."""

import json
import sqlite3

from sc_linac_physics.applications.tuning.state import tune_status_poll


def test_parse_float_valid():
    """Test parse_float with valid float values."""
    assert tune_status_poll.parse_float("12.5") == 12.5
    assert tune_status_poll.parse_float(12.5) == 12.5
    assert tune_status_poll.parse_float("0") == 0.0
    assert tune_status_poll.parse_float("-5.5") == -5.5


def test_parse_float_invalid():
    """Test parse_float with invalid values."""
    assert tune_status_poll.parse_float(None) is None
    assert tune_status_poll.parse_float("not_a_number") is None
    assert tune_status_poll.parse_float("") is None


def test_pv_names_structure():
    """Test pv_names returns correct PV name structure."""
    cavity_id = "ACCL:L0B:0110"
    names = tune_status_poll.pv_names(cavity_id)

    assert isinstance(names, dict)
    assert "tune_config" in names
    assert "df_cold" in names
    assert cavity_id in names["tune_config"]
    assert cavity_id in names["df_cold"]


def test_parse_args_defaults():
    """Test parse_args uses correct defaults."""
    args = tune_status_poll.parse_args([])

    assert args.caget_timeout == 5
    assert args.command_timeout == 60
    assert args.batch_size == 100
    assert args.caget_command == "caget"
    assert args.verbose is False


def test_parse_args_custom_values():
    """Test parse_args with custom values."""
    args = tune_status_poll.parse_args(
        [
            "--base-dir",
            "/custom/path",
            "--caget-timeout",
            "10",
            "--command-timeout",
            "120",
            "--batch-size",
            "16",
            "--caget-command",
            "custom_caget",
            "--verbose",
        ]
    )

    assert args.base_dir.name == "path"
    assert args.caget_timeout == 10
    assert args.command_timeout == 120
    assert args.batch_size == 16
    assert args.caget_command == "custom_caget"
    assert args.verbose is True


def test_init_db_creates_tables(tmp_path):
    """Test init_db creates necessary database tables."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    tune_status_poll.init_db(conn)

    # Verify tables exist
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    assert "cavity_state" in tables
    assert "tune_config_version" in tables
    assert "df_cold_version" in tables

    conn.close()


def test_init_db_creates_indices(tmp_path):
    """Test init_db creates indices."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    tune_status_poll.init_db(conn)

    # Verify indices are created
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    indices = {row[0] for row in cursor.fetchall()}
    # Indices should be created for cavity_id lookups
    assert len(indices) > 0

    conn.close()


def test_init_db_idempotent(tmp_path):
    """Test init_db can be called multiple times safely."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)

    tune_status_poll.init_db(conn)
    tune_status_poll.init_db(conn)  # Should not raise

    conn.close()


def test_parse_tune_config_code_variants():
    """Test parse_tune_config recognizes code formats."""
    # By code number
    code, label = tune_status_poll.parse_tune_config("1")
    assert code == 1
    assert label == "Cold landing"

    code, label = tune_status_poll.parse_tune_config("2")
    assert code == 2
    assert label == "Parked"


def test_parse_tune_config_label_variants():
    """Test parse_tune_config recognizes label formats."""
    code, label = tune_status_poll.parse_tune_config("Parked")
    assert code == 2
    assert label == "Parked"

    code, label = tune_status_poll.parse_tune_config("On resonance")
    assert code == 0
    assert label == "On resonance"


def test_parse_tune_config_case_insensitive():
    """Test parse_tune_config is case-insensitive."""
    code, label = tune_status_poll.parse_tune_config("parked")
    assert code == 2
    assert label == "Parked"

    code, label = tune_status_poll.parse_tune_config("COLD LANDING")
    assert code == 1
    assert label == "Cold landing"


def test_parse_tune_config_unknown():
    """Test parse_tune_config with unknown values."""
    code, label = tune_status_poll.parse_tune_config("unknown_state")
    assert code is None
    assert label == "unknown_state"


def test_parse_tune_config_none():
    """Test parse_tune_config with None."""
    code, label = tune_status_poll.parse_tune_config(None)
    assert code is None
    assert label == "Not connected"


def test_main_returns_zero_on_success(monkeypatch, tmp_path):
    """Test main() returns 0 on successful execution."""

    def fake_iter_cavity_ids():
        return []

    def fake_caget_values(*args, **kwargs):
        return {}

    monkeypatch.setattr(
        tune_status_poll, "iter_cavity_ids", fake_iter_cavity_ids
    )
    monkeypatch.setattr(tune_status_poll, "caget_values", fake_caget_values)

    exit_code = tune_status_poll.main(["--base-dir", str(tmp_path)])
    assert exit_code == 0


def test_main_creates_json_file(monkeypatch, tmp_path):
    """Test main() creates JSON snapshot file."""
    cavity_id = "ACCL:L0B:0110"

    def fake_iter_cavity_ids():
        yield cavity_id

    def fake_caget_values(*args, **kwargs):
        names = tune_status_poll.pv_names(cavity_id)
        return {
            names["tune_config"]: "Cold landing",
            names["df_cold"]: "10.0",
        }

    monkeypatch.setattr(
        tune_status_poll, "iter_cavity_ids", fake_iter_cavity_ids
    )
    monkeypatch.setattr(tune_status_poll, "caget_values", fake_caget_values)

    exit_code = tune_status_poll.main(["--base-dir", str(tmp_path)])
    assert exit_code == 0

    json_path = tmp_path / "json" / "tune_status.json"
    assert json_path.exists()

    with json_path.open("r") as f:
        snapshot = json.load(f)

    assert len(snapshot) > 0
    assert snapshot[0]["cavity_id"] == cavity_id
