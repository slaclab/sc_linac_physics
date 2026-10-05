from datetime import datetime

import h5py
import numpy as np
import pytest

from sc_linac_physics.applications.field_emission.update_h5py import (
    find_missing_runs,
)

RUN_A = ("01", datetime(2023, 10, 2, 9, 13), datetime(2023, 10, 2, 10), "1", "")
RUN_B = ("H1", datetime(2024, 1, 5, 8, 0), datetime(2024, 1, 5, 9), "2", "")


def _write_run(h5f, run, rows=3, skip=()):
    """write a run's 16 datasets, leaving out any (cav, readout) in skip"""
    cm, start = run[0], run[1]
    date = start.strftime("%Y-%m-%d_%H%M")
    for cav in range(1, 9):
        for readout in ("average", "instant"):
            if (cav, readout) in skip:
                continue
            h5f.create_dataset(
                f"CM{cm}/{date}/CAV{cav}/{readout}", data=np.zeros((rows, 11))
            )


@pytest.fixture
def cache(tmp_path):
    return tmp_path / "field_emission_data.hdf5"


def test_no_cache_file_means_every_run_is_missing(cache):
    assert find_missing_runs([RUN_A, RUN_B], cache) == [RUN_A, RUN_B]


def test_complete_run_is_skipped(cache):
    with h5py.File(cache, "w") as h5f:
        _write_run(h5f, RUN_A)

    assert find_missing_runs([RUN_A, RUN_B], cache) == [RUN_B]


def test_half_written_run_is_fetched_again(cache):
    """an interrupted convert leaves some datasets; the run is not cached"""
    with h5py.File(cache, "w") as h5f:
        _write_run(h5f, RUN_A, skip={(8, "instant")})

    assert find_missing_runs([RUN_A], cache) == [RUN_A]


def test_group_without_datasets_is_fetched_again(cache):
    with h5py.File(cache, "w") as h5f:
        h5f.require_group("CM01/2023-10-02_0913")

    assert find_missing_runs([RUN_A], cache) == [RUN_A]


def test_empty_datasets_still_count_as_cached(cache):
    """archiver returning no samples is a result; do not re-fetch forever"""
    with h5py.File(cache, "w") as h5f:
        _write_run(h5f, RUN_A, rows=0)

    assert find_missing_runs([RUN_A], cache) == []
