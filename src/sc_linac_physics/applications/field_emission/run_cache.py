"""Field emission runs: the run list, and the archiver data for each run.

The run list (field_emission_runs.csv) says which runs exist. A run's data
is read through the shared ArchiverStore (utils/archiver_store.py), which
caches each PV's samples for the run's exact window on disk the first time.
A cached run stays viewable when the archiver is down, and is shared by
everyone using that cache.

The cache holds the archiver's samples, not the aligned frames, so the
alignment in amp_vs_radiation.fetch_run runs on every load. A change to it
applies to cached runs too.
"""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from sc_linac_physics.applications.field_emission.amp_vs_radiation import (
    fetch_run,
    run_pvs,
)
from sc_linac_physics.applications.field_emission.constants import (
    RUN_LIST_PATH,
    STANDARD_DATE_FORMAT,
)
from sc_linac_physics.utils.archiver import series_from_frames
from sc_linac_physics.utils.archiver_store import ArchiverStore

# (cavity number, readout) -> (values, column PV names). values has the
# amplitude in column 0 and decarad heads 1-10 after it, as the old bundled
# HDF5 stored them.
RunData = Dict[Tuple[int, str], Tuple[np.ndarray, List[str]]]


@dataclass(frozen=True)
class Run:
    """One row of the run list. Times are naive Pacific, as written."""

    cm: str  # "01", "H1"
    start: datetime
    end: datetime
    decarad: str  # "1" or "2"
    elog: str
    notes: str
    start_text: str  # as written in the run list, for display
    end_text: str


def read_run_list(path: Path = RUN_LIST_PATH) -> List[Run]:
    """Runs in the list, oldest first. Skips "#" rows and malformed rows."""
    runs = []
    with open(path, newline="") as file:
        reader = csv.reader(file)
        next(reader)  # header
        for row in reader:
            if not row or "#" in row[0]:
                continue
            try:
                runs.append(_parse_row(row))
            except (ValueError, IndexError):
                print(f"Skipping malformed run list row: {row}")
    return sorted(runs, key=lambda run: (run.start, run.cm))


def _parse_row(row: List[str]) -> Run:
    start_date, start_time, end_date, end_time = row[1:5]
    start = datetime.strptime(
        f"{start_date} {start_time}", STANDARD_DATE_FORMAT
    )
    # A run with no end date ends on its start date
    end = datetime.strptime(
        f"{end_date or start_date} {end_time}", STANDARD_DATE_FORMAT
    )
    return Run(
        cm=row[0].strip().upper().removeprefix("CM").zfill(2),
        start=start,
        end=end,
        decarad=row[5].strip(),
        elog=row[6].strip(),
        notes=row[7].strip(),
        start_text=start_time.strip(),
        end_text=end_time.strip(),
    )


def find_run(cm: str, start: datetime, runs: List[Run]) -> Optional[Run]:
    """The run for a cryomodule starting at start, or None."""
    return next(
        (run for run in runs if run.cm == cm and run.start == start), None
    )


def is_cached(run: Run, store: Optional[ArchiverStore] = None) -> bool:
    """Whether load_run can read the run from disk alone."""
    store = store or ArchiverStore()
    return all(
        store.has_window(pv, run.start, run.end)
        for pv in run_pvs(run.cm, run.decarad)
    )


def load_run(run: Run, store: Optional[ArchiverStore] = None) -> RunData:
    """A run's data, aligned per cavity and readout.

    Reads through the store, so the first load fetches from the archiver and
    later ones come from disk. Fetching blocks; keep it off the Qt main
    thread.
    """
    store = store or ArchiverStore()

    def fetch(pvs, start, end):
        return series_from_frames(store.read_windows(pvs, start, end))

    frames = fetch_run(run.cm, run.start, run.end, run.decarad, fetch=fetch)
    return {
        key: (frame.to_numpy(dtype="float64"), [str(c) for c in frame.columns])
        for key, frame in frames.items()
    }
