"""An on-disk cache of archived PV data, one Parquet file per PV per month.

Raw pulls of a year or more don't fit in memory (see docs/utils/archiver.md),
and analyses re-read the same past months many times. This keeps each month
the archiver has finished with on disk, so it is fetched once, then read in
pieces.

Layout: ``<root>/<pv>/<YYYY-MM>.parquet``, months in UTC. Columns are
archiver.COLUMNS less ``valid``, which is derived on read.

Why Parquet: it is columnar and compressed (about 12 bytes per scalar sample
with zstd, against 99 in the archiver's JSON; measured 2026-10-12 on 550k
samples), and pandas, polars, DuckDB and MATLAB read it directly. Files are
written whole and never edited, so a shared cache needs no locks: each file
is written to a temporary name and renamed into place. HDF5's file locking is
unreliable on NFS. CHECK: is /home/physics/srf NFS on the control-room
machines?
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Tuple
from urllib.parse import quote

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from sc_linac_physics.utils import archiver
from sc_linac_physics.utils.epics.config import EPICS_INVALID_VAL
from sc_linac_physics.utils.platform_paths import get_srf_base_dir

# A month is written once it ended this long ago; until then it is fetched
# fresh on every read. Archived data doesn't change once written (Lisa
# Zacarias, 2026-10-12), so this only leaves time for samples still on their
# way in when a month ends. It delays caching only the month just finished.
SETTLE = timedelta(days=1)

STORED_COLUMNS = [c for c in archiver.COLUMNS if c != "valid"]

logger = logging.getLogger(__name__)


def get_archiver_cache_dir() -> Path:
    """The shared cache: /home/physics/srf/archiver_cache on Linux."""
    return get_srf_base_dir() / "archiver_cache"


class ArchiverStore:
    """Archived samples for PVs, read through a cache of finished months.

    Reads return what archiver.get_values_over_time_range would: samples from
    start to end, which may start with the last sample before start.
    """

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else get_archiver_cache_dir()

    def iter_months(
        self, pv: str, start: datetime, end: datetime
    ) -> Iterator[pd.DataFrame]:
        """Yield the PV's samples from start to end, one month at a time.

        Finished months come from the cache, filled from the archiver the
        first time. Frames are in time order, never empty, with no sample
        twice. Naive datetimes are read as America/Los_Angeles.
        Raises archiver.PVNotArchivedError if the archiver does not know the
        PV.
        """
        start = archiver._aware(start).astimezone(timezone.utc)
        end = archiver._aware(end).astimezone(timezone.utc)
        before: Optional[pd.DataFrame] = None
        last = None
        for month_start, month_end in _months(start, end):
            frame = self._month(pv, month_start, month_end, start, end)
            # A month can start with the sample before it, which the month
            # before already returned.
            if last is not None:
                frame = frame[frame["timestamp"] > last]
            if frame.empty:
                continue
            last = frame["timestamp"].iloc[-1]
            times = frame["timestamp"]
            if (times <= start).any():
                before = frame[times <= start].iloc[[-1]]
            body = frame[(times > start) & (times <= end)]
            if body.empty:
                continue
            if before is not None:
                body = pd.concat([before, body])
                before = None
            yield _with_valid(body)
        if before is not None:
            yield _with_valid(before)

    def read(self, pv: str, start: datetime, end: datetime) -> pd.DataFrame:
        """The PV's samples from start to end as one DataFrame."""
        frames = list(self.iter_months(pv, start, end))
        if not frames:
            return _with_valid(_empty())
        return pd.concat(frames, ignore_index=True)

    def fill(
        self,
        pvs: Iterable[str],
        start: datetime,
        end: datetime,
        max_workers: int = archiver.MAX_WORKERS,
    ) -> None:
        """Cache every finished month of each PV from start to end.

        Up to max_workers PVs at once, months one after another. Raises
        archiver.PVNotArchivedError naming every unknown PV once all finish.
        """
        pvs = list(pvs)
        start = archiver._aware(start).astimezone(timezone.utc)
        end = archiver._aware(end).astimezone(timezone.utc)

        def fill_one(pv: str) -> bool:
            try:
                for month_start, month_end in _months(start, end):
                    if _settled(month_end):
                        self._month(pv, month_start, month_end, start, end)
            except archiver.PVNotArchivedError:
                return False
            return True

        found = archiver._map_in_daemon_threads(fill_one, pvs, max_workers)
        missing = [pv for pv, ok in zip(pvs, found) if not ok]
        if missing:
            raise archiver.PVNotArchivedError(missing)

    def path(self, pv: str, month_start: datetime) -> Path:
        return self.root / quote(pv, safe=":") / f"{month_start:%Y-%m}.parquet"

    def _month(
        self,
        pv: str,
        month_start: datetime,
        month_end: datetime,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """One month's samples, from the cache when the month is settled.

        A month not yet settled is fetched only where it overlaps start..end,
        and not written. If the cache can't be written (no permission, disk
        full), the month is fetched without it: the cache only saves time.
        """
        path = self.path(pv, month_start)
        if path.exists():
            return pq.read_table(path).to_pandas()
        if not _settled(month_end):
            lo, hi = max(month_start, start), min(month_end, end)
            return _join(archiver.iter_range_chunks(pv, lo, hi))
        try:
            _write_atomically(
                path, archiver.iter_range_chunks(pv, month_start, month_end)
            )
        except OSError as e:
            logger.warning(
                "archiver cache: cannot write %s (%s); fetching %s without it",
                path,
                e,
                pv,
            )
            return _join(archiver.iter_range_chunks(pv, month_start, month_end))
        return pq.read_table(path).to_pandas()


def _write_atomically(path: Path, chunks: Iterator[pd.DataFrame]) -> None:
    """Write chunks to path as row groups, all or nothing.

    A chunk is written as it arrives, so memory stays at about one chunk.
    If the fetch fails partway, the temporary file is removed and path is
    left as it was.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    writer: Optional[pq.ParquetWriter] = None
    try:
        for chunk in chunks:
            table = pa.Table.from_pandas(
                chunk[STORED_COLUMNS], preserve_index=False
            )
            if writer is None:
                writer = pq.ParquetWriter(tmp, table.schema, compression="zstd")
            writer.write_table(table.cast(writer.schema))
        if writer is None:
            # Nothing archived that month: record it, so it isn't asked again.
            empty = pa.Table.from_pandas(_empty(), preserve_index=False)
            pq.write_table(empty, tmp, compression="zstd")
        else:
            writer.close()
            writer = None
        os.replace(tmp, path)
    finally:
        if writer is not None:
            writer.close()
        tmp.unlink(missing_ok=True)


def _months(start: datetime, end: datetime) -> List[Tuple[datetime, datetime]]:
    """UTC calendar months overlapping start..end, as (start, end) pairs."""
    months = []
    month = start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while month < end:
        following = (month + timedelta(days=32)).replace(day=1)
        months.append((month, following))
        month = following
    return months


def _join(chunks: Iterator[pd.DataFrame]) -> pd.DataFrame:
    frames = list(chunks)
    return pd.concat(frames, ignore_index=True) if frames else _empty()


def _settled(month_end: datetime) -> bool:
    return month_end <= datetime.now(timezone.utc) - SETTLE


def _empty() -> pd.DataFrame:
    return archiver._to_frame([])[STORED_COLUMNS]


def _with_valid(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.reset_index(drop=True)
    frame["valid"] = frame["severity"] != EPICS_INVALID_VAL
    return frame[archiver.COLUMNS]
