"""Field emission runs: the run list, and the archiver data for each run.

The run list is field_emission_runs.csv, committed to git, plus
ADDED_RUNS_PATH, which operators add to from the display. A run's data is
read through the shared ArchiverStore (utils/archiver_store.py), which
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
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import numpy as np

from sc_linac_physics.applications.field_emission.amp_vs_radiation import (
    fetch_run,
    run_pvs,
)
from sc_linac_physics.applications.field_emission.constants import (
    ADDED_RUNS_PATH,
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


RUN_LIST_HEADER = [
    "Cryomodule",
    "Start Date",
    "Start Time",
    "End Date",
    "End Time",
    "Decarad #",
    "Link to Measurement",
    "Notes",
    "Recharacterization",
    "Multipacting",
    "Commissioning",
]


def read_run_list(
    path: Path = RUN_LIST_PATH, added_path: Path = ADDED_RUNS_PATH
) -> List[Run]:
    """Committed and added runs, oldest first.

    Skips "#" rows, malformed rows, and added runs the committed list
    already has (same cryomodule and start).
    """
    runs = {}
    for list_path in (path, added_path):
        for run in _read_one_list(list_path):
            runs.setdefault((run.cm, run.start), run)
    return sorted(runs.values(), key=lambda run: (run.start, run.cm))


def _read_one_list(path: Path) -> Iterable[Run]:
    if not path.exists():
        return
    with open(path, newline="") as file:
        reader = csv.reader(file)
        next(reader, None)  # header
        for row in reader:
            if not row or "#" in row[0]:
                continue
            try:
                yield parse_row(row)
            except (ValueError, IndexError):
                print(f"Skipping malformed run list row: {row}")


def add_runs(
    rows: Iterable[List[str]],
    path: Path = RUN_LIST_PATH,
    added_path: Path = ADDED_RUNS_PATH,
) -> List[Run]:
    """Append rows (run list columns) to the added list.

    Returns the runs that were new. Rows that don't parse raise ValueError
    before anything is written; rows already listed are skipped.
    """
    known = {(run.cm, run.start) for run in read_run_list(path, added_path)}
    new_rows, new_runs = [], []
    for row in rows:
        try:
            run = parse_row(row)
        except (ValueError, IndexError) as e:
            raise ValueError(f"Bad run list row {row}: {e}") from e
        if (run.cm, run.start) in known:
            continue
        known.add((run.cm, run.start))
        new_rows.append(row)
        new_runs.append(run)

    if new_rows:
        added_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not added_path.exists()
        # CHECK: appends from two operators at once on NFS can interleave
        with open(added_path, "a", newline="") as file:
            writer = csv.writer(file)
            if write_header:
                writer.writerow(RUN_LIST_HEADER)
            writer.writerows(new_rows)
    return new_runs


def parse_row(row: List[str]) -> Run:
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


def fill_cache(
    runs: Iterable[Run],
    progress: Callable[[int, int, Run], None] = lambda done, total, run: None,
    store: Optional[ArchiverStore] = None,
) -> int:
    """Fetch every run not cached yet, one at a time. Returns how many.

    Stops at the first failed fetch and raises it, so an archiver outage
    doesn't mean one timeout per remaining run.
    """
    store = store or ArchiverStore()
    missing = [run for run in runs if not is_cached(run, store)]
    for done, run in enumerate(missing):
        progress(done, len(missing), run)
        load_run(run, store)
    return len(missing)


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
