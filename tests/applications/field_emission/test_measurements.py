import numpy as np
import pandas as pd
import pytest

from unittest.mock import patch
from datetime import datetime

from sc_linac_physics.applications.field_emission import measurements
from sc_linac_physics.applications.field_emission.run_cache import Run

# Convenience: the fully-qualified module path for patching.
MOD = "sc_linac_physics.applications.field_emission.measurements"


# ===========================================================================
# Run list and cache stand-ins
# ===========================================================================
def _run(cm, start, **kw):
    return Run(
        cm=cm,
        start=start,
        end=kw.get("end", start),
        decarad=kw.get("decarad", "1"),
        elog=kw.get("elog", "http://elog.example"),
        notes=kw.get("notes", ""),
        start_text=kw.get("start_text", start.strftime("%H:%M")),
        end_text=kw.get("end_text", "17:00"),
    )


RUNS = [
    _run("34", datetime(2025, 5, 1, 16, 33)),
    _run("34", datetime(2025, 5, 2, 10, 0)),
    _run("35", datetime(2025, 5, 3, 9, 0)),
]


@pytest.fixture
def run_list():
    with patch(f"{MOD}.read_run_list", return_value=list(RUNS)):
        yield


# ===========================================================================
# match_measurement_dates
# ===========================================================================
class TestMatchMeasurementDates:
    def test_returns_only_that_cryomodule(self, run_list):
        result = measurements.match_measurement_dates("34")
        assert [r["date"] for r in result] == [
            datetime(2025, 5, 1, 16, 33),
            datetime(2025, 5, 2, 10, 0),
        ]
        assert all(r["cm"] == "34" for r in result)

    def test_display_text_unchanged(self, run_list):
        result = measurements.match_measurement_dates("34")
        assert result[0]["display"] == "CM34    2025-05-01 16:33:00"

    def test_unknown_cryomodule_returns_empty(self, run_list):
        assert measurements.match_measurement_dates("99") == []


# ===========================================================================
# fetch_measurement_metadata
# ===========================================================================
class TestFetchMeasurementMetadata:
    def test_returns_six_display_fields(self, run_list):
        labels = measurements.fetch_measurement_metadata(
            "34", datetime(2025, 5, 1, 16, 33)
        )
        assert labels == (
            "Thursday, May 01, 2025",
            "16:33",
            "17:00",
            "1",
            "http://elog.example",
            "",
        )

    def test_unknown_run_returns_none(self, run_list):
        assert (
            measurements.fetch_measurement_metadata(
                "34", datetime(2025, 5, 1, 9, 0)
            )
            is None
        )


# ===========================================================================
# find_dataframes
# ===========================================================================
def _run_data(cav_nums, readout="average", cm="03"):
    data = {}
    for c in cav_nums:
        columns = [f"ACCL:L1B:{cm}{c}0:AACTMEAN"] + [
            f"RADM:SYS0:100:{h:02d}:GAMMAAVE" for h in range(1, 11)
        ]
        data[c, readout] = (np.full((3, 11), float(c)), columns)
    return data


class TestFindDataframes:
    START = datetime(2025, 5, 1, 16, 33)

    def test_no_cavity_selected_skips_fetch(self, run_list):
        with patch(f"{MOD}.load_run") as load:
            result = measurements.find_dataframes(
                "34", self.START, [False] * 8, "Average"
            )
        assert result == ({}, "", 0)
        load.assert_not_called()

    def test_unknown_run_skips_fetch(self, run_list):
        with patch(f"{MOD}.load_run") as load:
            result = measurements.find_dataframes(
                "34", datetime(2020, 1, 1), [True] + [False] * 7, "Average"
            )
        assert result == ({}, "", 0)
        load.assert_not_called()

    def test_selected_cavities_with_integer_columns(self, run_list):
        cav = [True, False, True] + [False] * 5
        with patch(f"{MOD}.load_run", return_value=_run_data([1, 3])) as load:
            dfs, title, num = measurements.find_dataframes(
                "34", self.START, cav, "Average"
            )
        load.assert_called_once_with(RUNS[0])
        assert sorted(dfs) == [1, 3] and num == 2
        # plot_amp_vs_rad numbers channels by integer column label
        assert list(dfs[1].columns) == list(range(11))
        assert dfs[3].iloc[0, 0] == 3.0

    def test_title_for_one_cavity(self, run_list):
        with patch(f"{MOD}.load_run", return_value=_run_data([1])):
            _, title, _ = measurements.find_dataframes(
                "34", self.START, [True] + [False] * 7, "Average"
            )
        assert title == "ACCL:L1B:0310"

    def test_title_for_several_cavities(self, run_list):
        cav = [True, True] + [False] * 6
        with patch(f"{MOD}.load_run", return_value=_run_data([1, 2])):
            _, title, _ = measurements.find_dataframes(
                "34", self.START, cav, "Average"
            )
        assert title == "ACCL:L1B:03x0"

    def test_instant_readout(self, run_list):
        data = _run_data([1], readout="instant")
        with patch(f"{MOD}.load_run", return_value=data):
            dfs, _, _ = measurements.find_dataframes(
                "34", self.START, [True] + [False] * 7, "Instant"
            )
        assert list(dfs) == [1]


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


# ===========================================================================
# fetch_plot_data
# ---------------------------------------------------------------------------
# fetch_plot_data(cavity, measurement, readout_type) aggregates find_dataframes
# results into a list of dicts:
#   {"measurement": <meas>, "dataframes": <selected>, "label": <label>}
# It returns {} early when no measurements OR no cavities are selected.
# ===========================================================================
SAMPLE_MEASUREMENTS = [
    {
        "cm": "34",
        "date": datetime(2025, 5, 1, 16, 33),
        "display": "CM34    2025-05-01 16:33:00",
    },
    {
        "cm": "34",
        "date": datetime(2025, 5, 2, 10, 0),
        "display": "CM34    2025-05-02 10:00:00",
    },
]


class TestFetchPlotData:
    def test_empty_when_no_measurement(self):
        """No measurements selected -> {} (falsy list)."""
        result = measurements.fetch_plot_data(
            [True] + [False] * 7, [], "Average"
        )
        assert result == {}

    def test_empty_when_measurement_is_none(self):
        """A None/empty measurement arg -> {}."""
        result = measurements.fetch_plot_data([True], None, "Average")
        assert result == {}

    def test_empty_when_no_cavity_checked(self):
        """No cavities checked -> {} even with measurements present."""
        result = measurements.fetch_plot_data(
            [False] * 8, list(SAMPLE_MEASUREMENTS), "Average"
        )
        assert result == {}

    def test_one_result_per_measurement(self):
        selected = {1: pd.DataFrame({"a": [1, 2]})}
        with patch.object(
            measurements,
            "find_dataframes",
            return_value=(selected, "Label", 1),
        ) as mock_find:
            result = measurements.fetch_plot_data(
                [True] + [False] * 7, list(SAMPLE_MEASUREMENTS), "Average"
            )
        assert isinstance(result, list)
        assert len(result) == 2  # two measurements -> two results
        assert mock_find.call_count == 2

    def test_result_dict_shape(self):
        selected = {1: pd.DataFrame({"a": [1, 2]})}
        with patch.object(
            measurements,
            "find_dataframes",
            return_value=(selected, "MyLabel", 1),
        ):
            result = measurements.fetch_plot_data(
                [True] + [False] * 7, [SAMPLE_MEASUREMENTS[0]], "Average"
            )
        assert len(result) == 1
        entry = result[0]
        assert set(entry.keys()) == {"measurement", "dataframes", "label"}
        assert entry["measurement"] == SAMPLE_MEASUREMENTS[0]
        assert entry["dataframes"] is selected
        assert entry["label"] == "MyLabel"

    def test_forwards_args_to_find_dataframes(self):
        selected = {1: pd.DataFrame({"a": [1]})}
        cav = [True, False, True] + [False] * 5
        with patch.object(
            measurements,
            "find_dataframes",
            return_value=(selected, "Label", 1),
        ) as mock_find:
            measurements.fetch_plot_data(
                cav, [SAMPLE_MEASUREMENTS[0]], "Instant"
            )
        cm_arg, date_arg, cav_arg, readout_arg = mock_find.call_args.args
        assert cm_arg == "34"
        assert date_arg == SAMPLE_MEASUREMENTS[0]["date"]
        assert cav_arg == cav
        assert readout_arg == "Instant"

    def test_calls_find_dataframes_once_per_measurement_with_correct_dates(
        self,
    ):
        """Each measurement's cm/date is forwarded in order."""
        selected = {1: pd.DataFrame({"a": [1]})}
        with patch.object(
            measurements,
            "find_dataframes",
            return_value=(selected, "Label", 1),
        ) as mock_find:
            measurements.fetch_plot_data(
                [True] + [False] * 7, list(SAMPLE_MEASUREMENTS), "Average"
            )
        forwarded_dates = [call.args[1] for call in mock_find.call_args_list]
        assert forwarded_dates == [
            SAMPLE_MEASUREMENTS[0]["date"],
            SAMPLE_MEASUREMENTS[1]["date"],
        ]

    def test_preserves_measurement_order(self):
        """Results come back in the same order the measurements were given."""
        with patch.object(
            measurements,
            "find_dataframes",
            side_effect=lambda cm, date, cav, read: (
                {1: pd.DataFrame({"a": [1]})},
                str(date),
                1,
            ),
        ):
            result = measurements.fetch_plot_data(
                [True] + [False] * 7, list(SAMPLE_MEASUREMENTS), "Average"
            )
        assert [r["measurement"] for r in result] == SAMPLE_MEASUREMENTS
        assert [r["label"] for r in result] == [
            str(SAMPLE_MEASUREMENTS[0]["date"]),
            str(SAMPLE_MEASUREMENTS[1]["date"]),
        ]
