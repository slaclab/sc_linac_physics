from datetime import datetime
from unittest.mock import patch

import pandas as pd
import pytest

from sc_linac_physics.applications.field_emission.amp_vs_radiation import (
    align_pvs_to_common_time,
    amplitude_pvs,
    fetch_run,
    rad_readout_pvs,
)

MOD = "sc_linac_physics.applications.field_emission.amp_vs_radiation"


def series(pv, points):
    """Series of (minute, value) points, as get_series returns them"""
    index = pd.DatetimeIndex(
        [pd.Timestamp("2024-01-01", tz="America/Los_Angeles")]
    ).repeat(len(points)) + pd.to_timedelta([m for m, _ in points], unit="m")
    return pd.Series([v for _, v in points], index=index, name=pv)


def test_amplitude_pvs_use_the_cavity_model():
    assert amplitude_pvs("01") == [
        f"ACCL:L0B:01{cav}0:AACTMEAN" for cav in range(1, 9)
    ]
    assert amplitude_pvs("H1")[7] == "ACCL:L1B:H180:AACTMEAN"


def test_rad_readout_pvs_use_the_decarad_model():
    assert rad_readout_pvs("2", "average")[0] == "RADM:SYS0:200:01:GAMMAAVE"
    assert rad_readout_pvs("1", "instant")[9] == (
        "RADM:SYS0:100:10:GAMMA_DOSE_RATE"
    )
    with pytest.raises(ValueError):
        rad_readout_pvs("1", "peak")


def test_align_carries_forward_and_drops_leading_rows():
    aligned = align_pvs_to_common_time(
        {
            "AMP": series("AMP", [(1, 5.0), (3, 6.0)]),
            "RAD": series("RAD", [(0, 0.1), (0, 0.9), (2, 0.2)]),
        }
    )
    assert aligned["AMP"].tolist() == [5.0, 5.0, 6.0]
    # the repeated minute-0 RAD sample keeps its first value
    assert aligned["RAD"].tolist() == [0.1, 0.2, 0.2]


def test_fetch_run_fetches_each_pv_once_and_returns_every_frame():
    def fake_get_series(pvs, start, end):
        return {pv: series(pv, [(0, 1.0), (1, 2.0)]) for pv in pvs}

    with patch(f"{MOD}.get_series", side_effect=fake_get_series) as get:
        frames = fetch_run(
            "02", datetime(2024, 1, 1, 9, 30), datetime(2024, 1, 1, 10), "1"
        )

    get.assert_called_once()
    pvs = get.call_args.args[0]
    assert len(pvs) == len(set(pvs)) == 28

    assert len(frames) == 16
    assert (8, "instant") in frames
    assert frames[3, "average"].columns.tolist() == [
        "ACCL:L1B:0230:AACTMEAN",
    ] + [f"RADM:SYS0:100:{h:02d}:GAMMAAVE" for h in range(1, 11)]
