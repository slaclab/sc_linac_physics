"""The packaged H1/H2 tuner response curves: one per cavity, in order."""

from pathlib import Path

import numpy as np
import pandas as pd

import sc_linac_physics
from sc_linac_physics.utils.sc_linac.linac_utils import (
    L1BHL,
    build_cavity_pv_prefix,
)

CSV = (
    Path(sc_linac_physics.__file__).parent
    / "utils/sc_linac/data/hl_tuner_response.csv"
)
BIN_HZ = 10e3  # fit_curves.py bin width
TOP_HZ = 50e3  # curves run from DF_COLD up to +50 kHz


def test_packaged_csv_has_16_monotonic_curves():
    d = pd.read_csv(CSV, comment="#")
    assert list(d.columns) == [
        "cavity_pv_prefix",
        "real_detune_hz",
        "usteps_from_cold",
        "covered",
    ]
    expected = {
        build_cavity_pv_prefix("L1B", cm, n)
        for cm in L1BHL
        for n in range(1, 9)
    }
    assert set(d.cavity_pv_prefix) == expected
    for prefix, g in d.groupby("cavity_pv_prefix"):
        assert (np.diff(g.real_detune_hz) == BIN_HZ).all(), prefix
        assert (np.diff(g.usteps_from_cold) > 0).all(), prefix
        assert g.real_detune_hz.iloc[-1] == TOP_HZ, prefix
        assert g.covered.dtype == bool, prefix
