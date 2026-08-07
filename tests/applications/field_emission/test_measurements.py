import numpy as np
import pandas as pd

from unittest.mock import patch
from datetime import datetime
from sc_linac_physics.applications.field_emission import measurements


def test_match_measurement_dates_returns_matching_records():
    """Only records with matching cryomodule are returned."""
    fake_rows = [
        ("34", "1", datetime(2025, 5, 1, 16, 33), datetime(2025, 5, 1, 17, 33), "stamp1"),
        ("34", "2", datetime(2025, 5, 2, 10, 00), datetime(2025, 5, 2, 11, 00), "stamp2"),
        ("35", "1", datetime(2025, 5, 3, 9, 00), datetime(2025, 5, 3, 10, 00), "stamp3"),
    ]

    with patch("sc_linac_physics.applications.field_emission.measurements.read_from_csv",
               return_value=fake_rows):
        result = measurements.match_measurement_dates("34")

    # Only 2 records match cryomodule 34
    assert len(result) == 2
    # All returned records have cm=="34"
    assert all(r["cm"] == "34" for r in result)


def test_match_measurement_dates_display_starts_with_cm():
    """Display string starts with 'CM' followed by cryomodule number."""
    fake_rows = [
        ("34", "1", datetime(2025, 5, 1, 16, 33), datetime(2025, 5, 1, 17, 33), "stamp"),
    ]
    with patch("sc_linac_physics.applications.field_emission.measurements.read_from_csv",
               return_value=fake_rows):
        result = measurements.match_measurement_dates("34")

    assert result[0]["display"].startswith("CM34")


def test_match_measurement_dates_empty_when_no_matches():
    """Returns an empty list when no cryomodule matches."""
    fake_rows = [
        ("34", "1", datetime.now(), datetime.now(), "stamp"),
    ]
    with patch("sc_linac_physics.applications.field_emission.measurements.read_from_csv",
               return_value=fake_rows):
        result = measurements.match_measurement_dates("99")  # doesn't exist

    assert result == []


def test_fetch_measurement_metadata_matches_cm_and_date():
    """Returns metadata only when both cm and date match a row."""
    fake_rows = [
        # (csv_cryo, csv_date, csv_start, csv_stop, csv_dec, csv_log, csv_notes)
        ("34", "05/01/25", "16:33", "17:00", "1", "log1", "notes1"),
        ("34", "05/02/25", "10:00", "11:00", "2", "log2", "notes2"),
    ]

    with patch("sc_linac_physics.applications.field_emission.measurements.read_raw_data",
               return_value=fake_rows):
        result = measurements.fetch_measurement_metadata(
            "34", datetime(2025, 5, 1, 16, 33)
        )

    assert result is not None
    date_str, start, stop, dec, log, notes = result
    assert start == "16:33"
    assert dec == "1"


def test_fetch_measurement_metadata_returns_none_when_no_match():
    """Returns None when no row matches."""
    fake_rows = [
        ("34", "05/01/25", "16:33", "17:00", "1", "log", "notes"),
    ]
    with patch("sc_linac_physics.applications.field_emission.measurements.read_raw_data",
               return_value=fake_rows):
        result = measurements.fetch_measurement_metadata(
            "99", datetime(2025, 5, 1, 16, 33)
        )

    assert result is None


def test_fetch_measurement_metadata_formats_date_string():
    """Returned date string is in 'Weekday, Month D, YYYY' format."""
    fake_rows = [
        ("34", "05/01/25", "16:33", "17:00", "1", "log", "notes"),
    ]
    with patch("sc_linac_physics.applications.field_emission.measurements.read_raw_data",
               return_value=fake_rows):
        result = measurements.fetch_measurement_metadata(
            "34", datetime(2025, 5, 1, 16, 33)
        )

    date_str = result[0]
    assert "Thursday" in date_str  # May 1 2025 was a Thursday
    assert "May" in date_str
    assert "2025" in date_str


def test_get_columns_masks_by_threshold():
    # threshold set to 4(MV)
    dset = pd.DataFrame({
        "amps": [3.0, 7.0, 5.0, 2.0],
        "ch1": [0.0, 0.4, 1.6, 2.4],
        "ch2": [0.4, 0.4, 0.8, 1.6],
        "ch3": [0.8, 2.4, 1.6, 1.2]
    })
    r_chan = [False, True, False, False, False, False, False, False]
    amp, rad = measurements.get_columns(dset, r_chan)
    assert np.isnan(amp.iloc[0])
    assert amp.iloc[1] == 7.0
    assert amp.iloc[2] == 5.0
    assert np.isnan(amp.iloc[3])


def test_get_columns_gets_correct_column():
    dset = pd.DataFrame({
        "amps": [3.0, 7.0, 5.0, 2.0],
        "ch1": [0.0, 0.4, 1.6, 2.4],
        "ch2": [0.4, 0.4, 0.8, 1.6],
        "ch3": [0.8, 2.4, 1.6, 1.2]
    })
    r_chan = [False, True, False, False, False, False, False, False]
    amp, rad = measurements.get_columns(dset, r_chan)
    assert rad.shape[1] == 1
