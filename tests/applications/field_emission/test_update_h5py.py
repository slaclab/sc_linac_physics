from datetime import datetime

import h5py
import numpy as np
import pandas as pd
import pytest

from sc_linac_physics.applications.field_emission import update_h5py
from sc_linac_physics.applications.field_emission.update_h5py import (
    convert_to_h5,
    find_missing_runs,
    parse_csv,
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


# ---------------------------------------------------------------------------
# convert_to_h5
# ---------------------------------------------------------------------------
RUN_LIST = (
    "Cryomodule,Start Date,Start Time,End Date,End Time,Decarad #,"
    "Link to Measurement,Notes,Recharacterization,Multipacting,Commissioning\n"
    "CM01,10/2/23,9:13,,10:00,1,https://elog,,Y,N,N\n"
)
CSV_NAME = "cm01_23_10_02_09_13_cavity1_average.csv"
DATASET = "CM01/2023-10-02_0913/CAV1/average"


@pytest.fixture
def cache_dirs(tmp_path, monkeypatch):
    csv_dir = tmp_path / "archiver_csvs"
    csv_dir.mkdir()
    h5_path = tmp_path / "cache.hdf5"
    monkeypatch.setattr(update_h5py, "CSV_OUTPUT_DIR", csv_dir)
    monkeypatch.setattr(update_h5py, "H5_PATH", h5_path)
    run_list = tmp_path / "runs.csv"
    run_list.write_text(RUN_LIST)
    return csv_dir, h5_path, parse_csv(run_list)


def _write_archiver_csv(csv_dir, rows):
    df = pd.DataFrame(
        {"timestamps": range(rows), "ACCL:L0B:0110:AACTMEAN": [5.0] * rows}
    )
    for ch in range(1, 11):
        df[f"RADM:SYS0:100:{ch:02d}:GAMMAAVE"] = 0.1
    df.to_csv(csv_dir / CSV_NAME, index=False)


def test_convert_writes_dataset_and_deletes_csv(cache_dirs):
    csv_dir, h5_path, lookup = cache_dirs
    _write_archiver_csv(csv_dir, rows=4)

    convert_to_h5(lookup)

    with h5py.File(h5_path, "r") as h5f:
        assert h5f[DATASET].shape == (4, 11)
    assert not (csv_dir / CSV_NAME).exists()


def test_refetched_run_with_new_row_count_replaces_dataset(cache_dirs):
    csv_dir, h5_path, lookup = cache_dirs
    _write_archiver_csv(csv_dir, rows=4)
    convert_to_h5(lookup)

    _write_archiver_csv(csv_dir, rows=7)
    convert_to_h5(lookup)

    with h5py.File(h5_path, "r") as h5f:
        assert h5f[DATASET].shape == (7, 11)


def test_csv_without_run_list_entry_is_kept(cache_dirs):
    csv_dir, h5_path, _ = cache_dirs
    _write_archiver_csv(csv_dir, rows=4)

    convert_to_h5({})

    assert (csv_dir / CSV_NAME).exists()
