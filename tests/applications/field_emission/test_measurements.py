import numpy as np
import pandas as pd
import pytest

from unittest.mock import patch
from datetime import datetime

from sc_linac_physics.applications.field_emission import measurements

# Convenience: the fully-qualified module path for patching.
MOD = "sc_linac_physics.applications.field_emission.measurements"


# ===========================================================================
# Fakes for the h5py.File interface
# ---------------------------------------------------------------------------
# A real h5py file behaves like a dict of groups/datasets, supports .get(),
# indexing with [], iteration over child keys, is a context manager, and each
# group/dataset carries an .attrs mapping.
# ===========================================================================
class FakeGroup:
    """
    Mimics an h5py Group/Dataset.

    - Iterating yields child keys (like iterating a real h5py group).
    - .get(key) / [key] return children.
    - .attrs is a plain dict.
    - As a dataset, it can also hold ndarray-like `data` used by
      pd.DataFrame(dataset).
    """

    def __init__(self, children=None, attrs=None, data=None):
        self._children = children or {}
        self.attrs = attrs or {}
        self._data = data

    def get(self, key):
        return self._children.get(key)

    def __getitem__(self, key):
        return self._children[key]

    def __iter__(self):
        return iter(self._children)

    def __array__(self, dtype=None):
        # Allows pd.DataFrame(dataset) to work when used as a dataset.
        arr = np.asarray(self._data)
        if dtype is not None:
            arr = arr.astype(dtype)
        return arr


class FakeH5File:
    """
    Fakes h5py.File so we can use it as a context manager, call .get(...),
    and index into it. `root` maps top-level keys -> FakeGroup.
    """

    def __init__(self, root):
        self._root = root

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, key):
        return self._root.get(key)

    def __getitem__(self, key):
        return self._root[key]


# ===========================================================================
# match_measurement_dates
# ===========================================================================
class TestMatchMeasurementDates:
    def _file_for_cm34(self):
        """A fake h5 file with two dated subgroups under CM34."""
        cm34 = FakeGroup(
            children={
                "2025-05-01_1633": FakeGroup(),
                "2025-05-02_1000": FakeGroup(),
            }
        )
        cm35 = FakeGroup(
            children={
                "2025-05-03_0900": FakeGroup(),
            }
        )
        return FakeH5File({"CM34": cm34, "CM35": cm35})

    def test_returns_matching_records(self):
        fake_file = self._file_for_cm34()
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            result = measurements.match_measurement_dates("34")
        assert len(result) == 2
        assert all(r["cm"] == "34" for r in result)

    def test_display_starts_with_cm(self):
        fake_file = self._file_for_cm34()
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            result = measurements.match_measurement_dates("34")
        assert result[0]["display"].startswith("CM34")

    def test_record_keys_and_values(self):
        """Each returned dict has display/cm/date with the expected values."""
        fake_file = self._file_for_cm34()
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            result = measurements.match_measurement_dates("34")
        rec = result[0]
        assert set(rec.keys()) == {"display", "cm", "date"}
        assert rec["cm"] == "34"
        # date is parsed from the group name via "%Y-%m-%d_%H%M"
        assert rec["date"] == datetime(2025, 5, 1, 16, 33)
        # display combines CM number and the parsed datetime
        assert "CM34" in rec["display"]
        assert str(datetime(2025, 5, 1, 16, 33)) in rec["display"]

    def test_empty_group_returns_empty_list(self):
        """CM group exists but has no dated children."""
        fake_file = FakeH5File({"CM34": FakeGroup(children={})})
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            result = measurements.match_measurement_dates("34")
        assert result == []

    def test_preserves_order_of_matches(self):
        fake_file = self._file_for_cm34()
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            result = measurements.match_measurement_dates("34")
        assert [r["date"] for r in result] == [
            datetime(2025, 5, 1, 16, 33),
            datetime(2025, 5, 2, 10, 0),
        ]

    def test_dates_parsed_from_group_names(self):
        """Every returned date corresponds to a parsed group key."""
        fake_file = self._file_for_cm34()
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            result = measurements.match_measurement_dates("34")
        parsed = {r["date"] for r in result}
        assert parsed == {
            datetime(2025, 5, 1, 16, 33),
            datetime(2025, 5, 2, 10, 0),
        }


# ===========================================================================
# fetch_measurement_metadata
# ===========================================================================
class TestFetchMeasurementMetadata:
    def _group_with_attrs(self, **overrides):
        attrs = {
            "date": "05/01/25",
            "time_start": "16:33",
            "time_end": "17:00",
            "decarad": "1",
            "elog": "log1",
            "notes": "notes1",
        }
        attrs.update(overrides)
        return FakeGroup(attrs=attrs)

    def test_matches_cm_and_date(self):
        # find_dataframes-style path: CM34/2025-05-01_1633
        group = self._group_with_attrs()
        fake_file = FakeH5File({"CM34/2025-05-01_1633": group})
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            result = measurements.fetch_measurement_metadata(
                "34", datetime(2025, 5, 1, 16, 33)
            )
        assert result is not None
        date_str, start, stop, dec, log, notes = result
        assert start == "16:33"
        assert dec == "1"

    def test_returns_none_when_group_missing(self):
        """No group at the computed path -> None."""
        fake_file = FakeH5File({})  # .get(...) returns None
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            result = measurements.fetch_measurement_metadata(
                "99", datetime(2025, 5, 1, 16, 33)
            )
        assert result is None

    def test_formats_date_string(self):
        group = self._group_with_attrs()
        fake_file = FakeH5File({"CM34/2025-05-01_1633": group})
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            result = measurements.fetch_measurement_metadata(
                "34", datetime(2025, 5, 1, 16, 33)
            )
        date_str = result[0]
        assert "Thursday" in date_str  # 2025-05-01 was a Thursday
        assert "May" in date_str
        assert "2025" in date_str

    def test_returns_all_six_fields(self):
        group = self._group_with_attrs(elog="mylog", notes="mynotes")
        fake_file = FakeH5File({"CM34/2025-05-01_1633": group})
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            result = measurements.fetch_measurement_metadata(
                "34", datetime(2025, 5, 1, 16, 33)
            )
        assert len(result) == 6
        date_str, start, stop, dec, log, notes = result
        assert stop == "17:00"
        assert log == "mylog"
        assert notes == "mynotes"

    def test_date_differs_returns_none(self):
        """Right cryomodule, wrong time -> path won't exist -> None."""
        group = self._group_with_attrs()
        fake_file = FakeH5File({"CM34/2025-05-01_1633": group})
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            result = measurements.fetch_measurement_metadata(
                "34", datetime(2025, 5, 1, 9, 0)  # different time
            )
        assert result is None

    def test_path_is_built_from_cm_and_formatted_date(self):
        """The lookup key is CM{cm}/{%Y-%m-%d_%H%M}."""
        group = self._group_with_attrs(decarad="2", elog="log2", notes="notes2")
        fake_file = FakeH5File({"CM34/2025-05-02_1000": group})
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            result = measurements.fetch_measurement_metadata(
                "34", datetime(2025, 5, 2, 10, 0)
            )
        assert result is not None
        assert result[3] == "2"  # decarad from the matched group


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


class FakeH5FileIndexed:
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
        fake_file = FakeH5FileIndexed({key: dataset})

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
        fake_file = FakeH5FileIndexed({key: dataset})

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
        cav = [
            True,
            False,
            True,
            True,
            False,
            False,
            False,
            False,
        ]  # cavs 1,3,4
        for c in (1, 3, 4):
            datasets[f"CM34/{stamp}/CAV{c}/average"] = FakeDataset(
                [[5.0, 0.1], [7.0, 0.2]], columns
            )
        fake_file = FakeH5FileIndexed(datasets)

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
        fake_file = FakeH5FileIndexed({key: dataset})

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
        fake_file = FakeH5FileIndexed(datasets)

        cav = [True, True] + [False] * 6
        with patch(f"{MOD}.h5py.File", return_value=fake_file):
            dfs, title, num = measurements.find_dataframes(
                "34", fixed_date, cav, "Average"
            )
        assert title == "ACCL:L1B:03x0"


# ===========================================================================
# get_columns
# ===========================================================================
class TestGetColumns:
    @pytest.fixture
    def dset(self):
        return pd.DataFrame(
            {
                "amps": [3.0, 7.0, 5.0, 2.0],
                "ch1": [0.0, 0.4, 1.6, 2.4],
                "ch2": [0.4, 0.4, 0.8, 1.6],
                "ch3": [0.8, 2.4, 1.6, 1.2],
            }
        )

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
        assert amp.iloc[0] == 4.0  # exactly 4 -> kept
        assert np.isnan(amp.iloc[1])  # 3.9 -> masked
