import numpy as np
import pandas as pd
import pytest

from unittest.mock import patch
from datetime import datetime

from sc_linac_physics.applications.field_emission import measurements


# Convenience: the fully-qualified module path for patching.
MOD = "sc_linac_physics.applications.field_emission.measurements"


# ===========================================================================
# match_measurement_dates
# ===========================================================================
class TestMatchMeasurementDates:
    def test_returns_matching_records(self):
        fake_rows = [
            ("34", "1", datetime(2025, 5, 1, 16, 33), datetime(2025, 5, 1, 17, 33), "stamp1"),
            ("34", "2", datetime(2025, 5, 2, 10, 0), datetime(2025, 5, 2, 11, 0), "stamp2"),
            ("35", "1", datetime(2025, 5, 3, 9, 0), datetime(2025, 5, 3, 10, 0), "stamp3"),
        ]
        with patch(f"{MOD}.read_from_csv", return_value=fake_rows):
            result = measurements.match_measurement_dates("34")
        assert len(result) == 2
        assert all(r["cm"] == "34" for r in result)

    def test_display_starts_with_cm(self):
        fake_rows = [
            ("34", "1", datetime(2025, 5, 1, 16, 33), datetime(2025, 5, 1, 17, 33), "stamp"),
        ]
        with patch(f"{MOD}.read_from_csv", return_value=fake_rows):
            result = measurements.match_measurement_dates("34")
        assert result[0]["display"].startswith("CM34")

    def test_empty_when_no_matches(self):
        fake_rows = [
            ("34", "1", datetime.now(), datetime.now(), "stamp"),
        ]
        with patch(f"{MOD}.read_from_csv", return_value=fake_rows):
            result = measurements.match_measurement_dates("99")
        assert result == []

    def test_record_keys_and_values(self):
        """Each returned dict has display/cm/date with the expected values."""
        start = datetime(2025, 5, 1, 16, 33)
        fake_rows = [("34", "1", start, datetime(2025, 5, 1, 17, 33), "stamp")]
        with patch(f"{MOD}.read_from_csv", return_value=fake_rows):
            result = measurements.match_measurement_dates("34")
        rec = result[0]
        assert set(rec.keys()) == {"display", "cm", "date"}
        assert rec["cm"] == "34"
        assert rec["date"] == start
        # display combines CM number and start
        assert "CM34" in rec["display"]
        assert str(start) in rec["display"]

    def test_empty_csv_returns_empty_list(self):
        with patch(f"{MOD}.read_from_csv", return_value=[]):
            result = measurements.match_measurement_dates("34")
        assert result == []

    def test_preserves_order_of_matches(self):
        s1 = datetime(2025, 5, 1, 16, 33)
        s2 = datetime(2025, 5, 2, 10, 0)
        fake_rows = [
            ("34", "1", s1, datetime(2025, 5, 1, 17, 33), "a"),
            ("34", "2", s2, datetime(2025, 5, 2, 11, 0), "b"),
        ]
        with patch(f"{MOD}.read_from_csv", return_value=fake_rows):
            result = measurements.match_measurement_dates("34")
        assert [r["date"] for r in result] == [s1, s2]

    def test_string_vs_int_cryomodule_no_match(self):
        """Comparison is by equality, so int 34 won't match string '34'."""
        fake_rows = [("34", "1", datetime.now(), datetime.now(), "stamp")]
        with patch(f"{MOD}.read_from_csv", return_value=fake_rows):
            result = measurements.match_measurement_dates(34)  # int, not str
        assert result == []


# ===========================================================================
# fetch_measurement_metadata
# ===========================================================================
class TestFetchMeasurementMetadata:
    def test_matches_cm_and_date(self):
        fake_rows = [
            ("34", "05/01/25", "16:33", "17:00", "1", "log1", "notes1"),
            ("34", "05/02/25", "10:00", "11:00", "2", "log2", "notes2"),
        ]
        with patch(f"{MOD}.read_raw_data", return_value=fake_rows):
            result = measurements.fetch_measurement_metadata(
                "34", datetime(2025, 5, 1, 16, 33)
            )
        assert result is not None
        date_str, start, stop, dec, log, notes = result
        assert start == "16:33"
        assert dec == "1"

    def test_returns_none_when_no_cm_match(self):
        fake_rows = [
            ("34", "05/01/25", "16:33", "17:00", "1", "log", "notes"),
        ]
        with patch(f"{MOD}.read_raw_data", return_value=fake_rows):
            result = measurements.fetch_measurement_metadata(
                "99", datetime(2025, 5, 1, 16, 33)
            )
        assert result is None

    def test_formats_date_string(self):
        fake_rows = [
            ("34", "05/01/25", "16:33", "17:00", "1", "log", "notes"),
        ]
        with patch(f"{MOD}.read_raw_data", return_value=fake_rows):
            result = measurements.fetch_measurement_metadata(
                "34", datetime(2025, 5, 1, 16, 33)
            )
        date_str = result[0]
        assert "Thursday" in date_str  # 2025-05-01 was a Thursday
        assert "May" in date_str
        assert "2025" in date_str

    def test_returns_all_six_fields(self):
        fake_rows = [
            ("34", "05/01/25", "16:33", "17:00", "1", "mylog", "mynotes"),
        ]
        with patch(f"{MOD}.read_raw_data", return_value=fake_rows):
            result = measurements.fetch_measurement_metadata(
                "34", datetime(2025, 5, 1, 16, 33)
            )
        assert len(result) == 6
        date_str, start, stop, dec, log, notes = result
        assert stop == "17:00"
        assert log == "mylog"
        assert notes == "mynotes"

    def test_cm_matches_but_date_differs_returns_none(self):
        """Right cryomodule, wrong time -> None (exercises the 'continue')."""
        fake_rows = [
            ("34", "05/01/25", "16:33", "17:00", "1", "log", "notes"),
        ]
        with patch(f"{MOD}.read_raw_data", return_value=fake_rows):
            result = measurements.fetch_measurement_metadata(
                "34", datetime(2025, 5, 1, 9, 0)  # different time
            )
        assert result is None

    def test_finds_second_row_when_first_cm_matches_but_date_wrong(self):
        """First row matches cm but not date; second row is the real match."""
        fake_rows = [
            ("34", "05/01/25", "16:33", "17:00", "1", "log1", "notes1"),
            ("34", "05/02/25", "10:00", "11:00", "2", "log2", "notes2"),
        ]
        with patch(f"{MOD}.read_raw_data", return_value=fake_rows):
            result = measurements.fetch_measurement_metadata(
                "34", datetime(2025, 5, 2, 10, 0)
            )
        assert result is not None
        assert result[3] == "2"  # dec from the second row

    def test_empty_raw_data_returns_none(self):
        with patch(f"{MOD}.read_raw_data", return_value=[]):
            result = measurements.fetch_measurement_metadata(
                "34", datetime(2025, 5, 1, 16, 33)
            )
        assert result is None


# ===========================================================================
# find_dataframes
# ---------------------------------------------------------------------------
# Helper to fake an h5py.File used as `with h5py.File(...) as h5f:` then h5f[key]
# ===========================================================================
class FakeDataset(np.ndarray):
    """
    Mimics an h5py dataset: it *is* a real ndarray (so pd.DataFrame(dataset)
    works), and it carries an .attrs dict like a real h5py dataset.
    """
    def __new__(cls, data, columns):
        obj = np.asarray(data).view(cls)
        obj.attrs = {"columns": columns}
        return obj

    def __array_finalize__(self, obj):
        if obj is None:
            return
        self.attrs = getattr(obj, "attrs", {})


class FakeH5File:
    """
    Fakes h5py.File so we can use it as a context manager and index into it.
    `datasets` maps the internal filepath string -> FakeDataset.
    """
    def __init__(self, datasets):
        self._datasets = datasets

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __getitem__(self, key):
        return self._datasets[key]


@pytest.fixture
def fixed_date():
    return datetime(2025, 5, 1, 16, 33)


@pytest.fixture
def stamp(fixed_date):
    # matches the format used inside find_dataframes
    return datetime.strftime(fixed_date, "%Y-%m-%d_%H%M")


class TestFindDataframes:
    def test_no_cavities_returns_empty(self, fixed_date):
        cav = [False] * 8
        result = measurements.find_dataframes("34", fixed_date, cav, "Average")
        assert result == ({}, "", 0)

    def test_single_cavity_builds_one_dataframe(self, fixed_date, stamp):
        columns = ["ACCL:L1B:0310:AMP", "CH1", "CH2"]
        dataset = FakeDataset([[5.0, 0.1, 0.2], [7.0, 0.3, 0.4]], columns)
        key = f"CM34/{stamp}/CAV1/average"
        fake_file = FakeH5File({key: dataset})

        cav = [True] + [False] * 7  # only cavity 1
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            dfs, title, num = measurements.find_dataframes(
                "34", fixed_date, cav, "Average"
            )

        assert num == 1
        assert list(dfs.keys()) == [1]
        assert isinstance(dfs[1], pd.DataFrame)
        assert dfs[1].shape == (2, 3)

    def test_readout_is_lowercased(self, fixed_date, stamp):
        """'Average' -> 'average' when building the h5 path."""
        columns = ["ACCL:L1B:0310:AMP"]
        dataset = FakeDataset([[5.0]], columns)
        key = f"CM34/{stamp}/CAV1/average"
        fake_file = FakeH5File({key: dataset})

        cav = [True] + [False] * 7
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            # If lowercasing failed, the key lookup would KeyError
            dfs, title, num = measurements.find_dataframes(
                "34", fixed_date, cav, "AVERAGE"
            )
        assert num == 1

    def test_multiple_cavities(self, fixed_date, stamp):
        columns = ["ACCL:L1B:0310:AMP", "CH1"]
        datasets = {}
        cav = [True, False, True, True, False, False, False, False]  # cavs 1,3,4
        for c in (1, 3, 4):
            datasets[f"CM34/{stamp}/CAV{c}/average"] = FakeDataset(
                [[5.0, 0.1], [7.0, 0.2]], columns
            )
        fake_file = FakeH5File(datasets)

        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            dfs, title, num = measurements.find_dataframes(
                "34", fixed_date, cav, "Average"
            )
        assert num == 3
        assert sorted(dfs.keys()) == [1, 3, 4]

    def test_title_is_first_three_colon_parts(self, fixed_date, stamp):
        """Single cavity -> title is first 3 colon-delimited parts of amp label."""
        columns = ["ACCL:L1B:0310:AMP:SETPOINT"]
        dataset = FakeDataset([[5.0]], columns)
        key = f"CM34/{stamp}/CAV1/average"
        fake_file = FakeH5File({key: dataset})

        cav = [True] + [False] * 7
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            dfs, title, num = measurements.find_dataframes(
                "34", fixed_date, cav, "Average"
            )
        assert title == "ACCL:L1B:0310"

    def test_title_regex_applied_for_multiple_cavities(self, fixed_date, stamp):
        """
        With >1 cavity, the regex re.sub(r"(:\\d+)(\\d)0", r"\\1x0", title)
        replaces the trailing cavity digit with an 'x'.
        For '0310' -> group1=':031', group2='1', trailing '0' -> ':03x0'
        so 'ACCL:L1B:0310' becomes 'ACCL:L1B:03x0'.
        """
        columns = ["ACCL:L1B:0310:AMP"]
        datasets = {
            f"CM34/{stamp}/CAV1/average": FakeDataset([[5.0]], columns),
            f"CM34/{stamp}/CAV2/average": FakeDataset([[5.0]], columns),
        }
        fake_file = FakeH5File(datasets)

        cav = [True, True] + [False] * 6
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            dfs, title, num = measurements.find_dataframes(
                "34", fixed_date, cav, "Average"
            )
        assert title == "ACCL:L1B:03x0"

    def test_missing_dataset_raises_keyerror(self, fixed_date):
        """If the requested h5 path doesn't exist, indexing raises KeyError."""
        fake_file = FakeH5File({})  # no datasets at all
        cav = [True] + [False] * 7
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            with pytest.raises(KeyError):
                measurements.find_dataframes("34", fixed_date, cav, "Average")

    def test_cavity_list_uses_one_based_indexing(self, fixed_date, stamp):
        """cav[0]=True should map to CAV1 (1-based)."""
        columns = ["ACCL:L1B:0310:AMP"]
        # Only provide CAV1; if code asked for CAV0 this would KeyError
        key = f"CM34/{stamp}/CAV1/average"
        fake_file = FakeH5File({key: FakeDataset([[5.0]], columns)})
        cav = [True] + [False] * 7
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            dfs, title, num = measurements.find_dataframes(
                "34", fixed_date, cav, "Average"
            )
        assert list(dfs.keys()) == [1]


# ===========================================================================
# get_columns
# ===========================================================================
class TestGetColumns:
    @pytest.fixture
    def dset(self):
        return pd.DataFrame({
            "amps": [3.0, 7.0, 5.0, 2.0],
            "ch1": [0.0, 0.4, 1.6, 2.4],
            "ch2": [0.4, 0.4, 0.8, 1.6],
            "ch3": [0.8, 2.4, 1.6, 1.2],
        })

    def test_masks_by_threshold(self, dset):
        r_chan = [False, True, False, False, False, False, False, False]
        amp, rad = measurements.get_columns(dset, r_chan)
        assert np.isnan(amp.iloc[0])  # 3.0 < 4 -> masked
        assert amp.iloc[1] == 7.0
        assert amp.iloc[2] == 5.0
        assert np.isnan(amp.iloc[3])  # 2.0 < 4 -> masked

    def test_gets_correct_single_column(self, dset):
        r_chan = [False, True, False, False, False, False, False, False]
        amp, rad = measurements.get_columns(dset, r_chan)
        assert rad.shape[1] == 1

    def test_selects_multiple_channels(self, dset):
        # channels 1 and 3 -> columns index 1 (ch1) and 3 (ch3)
        r_chan = [True, False, True, False, False, False, False, False]
        amp, rad = measurements.get_columns(dset, r_chan)
        assert rad.shape[1] == 2
        assert list(rad.columns) == ["ch1", "ch3"]

    def test_no_channels_selected_returns_empty_rad(self, dset):
        r_chan = [False] * 8
        amp, rad = measurements.get_columns(dset, r_chan)
        assert rad.shape[1] == 0
        # amplitude column is still returned
        assert amp.shape[0] == 4

    def test_rad_values_masked_same_as_amp(self, dset):
        """Rows below threshold are masked across the whole row, incl. rad cols."""
        r_chan = [True, False, False, False, False, False, False, False]  # ch1
        amp, rad = measurements.get_columns(dset, r_chan)
        # row 0 (amp 3.0) and row 3 (amp 2.0) are below threshold -> NaN in rad too
        assert np.isnan(rad.iloc[0, 0])
        assert np.isnan(rad.iloc[3, 0])
        assert rad.iloc[1, 0] == 0.4
        assert rad.iloc[2, 0] == 1.6

    def test_amplitude_column_is_always_first(self, dset):
        r_chan = [False, False, True, False, False, False, False, False]
        amp, rad = measurements.get_columns(dset, r_chan)
        # amp comes from column index 0 ("amps")
        assert amp.name == "amps"

    def test_threshold_boundary_value_not_masked(self):
        """Value exactly at the threshold (4) is NOT masked (mask is < 4)."""
        df = pd.DataFrame({"amps": [4.0, 3.9], "ch1": [1.0, 2.0]})
        r_chan = [True] + [False] * 7
        amp, rad = measurements.get_columns(df, r_chan)
        assert amp.iloc[0] == 4.0       # exactly 4 -> kept
        assert np.isnan(amp.iloc[1])    # 3.9 -> masked
