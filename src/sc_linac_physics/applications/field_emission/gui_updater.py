import csv
import re

from datetime import datetime
from sc_linac_physics.applications.field_emission.run_cache import (
    parse_row,
    add_runs,
    fill_cache,
    read_run_list,
)
from sc_linac_physics.applications.field_emission.constants import (
    VALID_CMS_LIST,
    ELOG_PATTERN,
    STANDARD_DATE_FORMAT,
)
from PyQt5.QtCore import QObject, pyqtSignal


def validate_emission_data(input_row, require_elog=True):
    """validation of dialog entries for single cryomodule emission data

    require_elog=False lets an empty eLog link through, as 7 of the runs in
    field_emission_runs.csv have. A link that is given is still checked.
    """
    cm = _validate_cryomodule(input_row[0])
    d_start, d_end = _validate_dates(
        input_row[1], input_row[2], input_row[3], input_row[4]
    )
    dec = _validate_decarad(input_row[5])
    elog = input_row[6]
    if elog or require_elog:
        elog = _validate_elog(elog)
    filters = _validate_filters(input_row[8:])
    return {
        "cryomodule": cm,
        "start": d_start,
        "end": d_end,
        "decarad": dec,
        "elog": elog,
        "filters": filters,
    }


def _validate_cryomodule(cryomodule):
    """format cryomodule string and check if requested cryomodule is available"""
    # "CM04" as the run list writes it, or "4"/"04" as typed in the dialog
    cm_str = cryomodule.strip().upper().removeprefix("CM").zfill(2)
    if cm_str not in VALID_CMS_LIST:
        raise ValueError(f"Invalid cryomodule {cryomodule}")
    return cm_str


def _validate_dates(date_start, time_start, date_end, time_end):
    """format and validate dates"""
    d_start = f"{date_start} {time_start}"  # 10/3/26 3:58
    if date_end == "":
        d_end = f"{date_start} {time_end}"
    else:
        d_end = f"{date_end} {time_end}"
    try:
        d_start_fmt = datetime.strptime(
            d_start, STANDARD_DATE_FORMAT
        )  # 2026-10-03 03:58:00
    except ValueError:
        raise ValueError(
            f"Start time does not match {STANDARD_DATE_FORMAT} format: {d_start}"
        )
    try:
        d_end_fmt = datetime.strptime(d_end, STANDARD_DATE_FORMAT)
    except ValueError:
        raise ValueError(
            f"End time does not match {STANDARD_DATE_FORMAT} format: {d_end}"
        )
    if d_start_fmt > d_end_fmt:
        raise ValueError("End date is before start date")
    return d_start_fmt, d_end_fmt


def _validate_decarad(decarad):
    """validate decarad choice"""
    if decarad != "1" and decarad != "2":
        raise ValueError(f"Invalid decarad {decarad}")
    return decarad


def _validate_elog(elog):
    """check if elog url formatting matches link"""
    match = re.fullmatch(ELOG_PATTERN, elog)
    if not match:
        raise ValueError(
            "eLog link does not match expected pattern. Please check your link"
        )
    return elog


def _validate_filters(filters):
    """check if filters are set up correctly"""
    # assumption that filters are at end of string in case of future additions
    clean_filters = []
    for fil in filters:
        fil_up = fil.upper().strip()
        if fil_up != "Y" and fil_up != "N":
            raise ValueError(f"Invalid filter {fil}, Y/N?")
        clean_filters.append(fil_up)
    return clean_filters


class UpdateWorker(QObject):
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    finished = pyqtSignal(str)

    def __init__(self, mode, *args):
        super().__init__()
        self.mode = mode
        self.args = args

    def run(self):
        """ "modes (single vs multiple by csv) of new data entry"""
        try:
            if self.mode == "single":
                message = self.single_update(*self.args)
            elif self.mode == "multi":
                message = self.multi_update(*self.args)
        except Exception as e:
            self.error.emit(str(e))
            return
        self.finished.emit(message)

    def single_update(self, valid, input_row):
        """add one run from the dialog and fetch it into the cache"""
        row = [f"CM{valid['cryomodule']}", *input_row[1:]]
        return self._add_and_fetch([row])

    def multi_update(self, input_csv):
        """add every run in a CSV laid out like the run list, and fetch them

        Every row is checked before add_runs writes any. A row that gets into
        added_runs.csv and then fails to fetch (unknown cryomodule, decarad
        3) would stop the fill on open at that run on every open after.
        """
        rows = []
        with open(input_csv, newline="") as file:
            reader = csv.reader(file)
            next(reader, None)  # header
            for line, row in enumerate(reader, start=2):
                if not row or "#" in row[0]:
                    continue
                try:
                    validate_emission_data(row, require_elog=False)
                except (ValueError, IndexError) as e:
                    raise ValueError(f"{input_csv} line {line}: {e}") from e
                rows.append(row)
        return self._add_and_fetch(rows)

    def _add_and_fetch(self, rows):
        self.progress.emit("Adding to the run list...")
        added = add_runs(rows)
        wanted = {(run.cm, run.start) for run in map(parse_row, rows)}
        runs = [r for r in read_run_list() if (r.cm, r.start) in wanted]
        fetched = fill_cache(runs, self._report)
        return (
            f"{len(added)} run(s) added, {fetched} fetched from the archiver."
        )

    def _report(self, done, total, run):
        self.progress.emit(
            f"Fetching {done + 1}/{total}: CM{run.cm} {run.start:%m/%d/%y %H:%M}"
        )
