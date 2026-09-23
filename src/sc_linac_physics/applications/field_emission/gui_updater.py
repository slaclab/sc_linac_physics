import csv
import re

from datetime import datetime
from sc_linac_physics.applications.field_emission.amp_vs_radiation import (
    generate_amp_vs_rad_csvs,
)
from sc_linac_physics.applications.field_emission.update_h5py import (
    receive_metadata_input,
    parse_csv,
    convert_to_h5,
)
from sc_linac_physics.applications.field_emission.constants import (
    VALID_CMS_LIST,
    ELOG_PATTERN,
    STANDARD_DATE_FORMAT,
    CSV_DATE_FORMAT,
)
from PyQt5.QtCore import QObject, pyqtSignal


def validate_emission_data(input_row):
    """validation of dialog entries for single cryomodule emission data"""
    cm = _validate_cryomodule(input_row[0])
    d_start, d_end = _validate_dates(
        input_row[1], input_row[2], input_row[3], input_row[4]
    )
    dec = _validate_decarad(input_row[5])
    elog = _validate_elog(input_row[6])
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
    cm_str = cryomodule.strip().zfill(2).upper()
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


def read_from_csv(filepath):
    """yield formatted data for columns of each valid csv row"""
    with open(filepath) as file:
        reader = csv.reader(file)
        next(reader)  # skip header row
        for row in reader:
            if "#" in row[0]:  # skip commented rows
                continue
            cm = row[0].strip().zfill(2).upper().removeprefix("CM")
            try:
                start_date = datetime.strptime(
                    f"{row[1]} {row[2]}", STANDARD_DATE_FORMAT
                )
            except (ValueError, IndexError):
                continue

            if row[3] == "":
                end_date = datetime.strptime(
                    f"{row[1]} {row[4]}", STANDARD_DATE_FORMAT
                )
            else:
                end_date = datetime.strptime(
                    f"{row[3]} {row[4]}", STANDARD_DATE_FORMAT
                )
            timestamp = start_date.strftime(CSV_DATE_FORMAT)
            decarad = row[5] if row[5] is not None else ""
            yield cm, start_date, end_date, decarad, timestamp


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
                self.single_update(*self.args)
            elif self.mode == "multi":
                self.multi_update(*self.args)
        except Exception as e:
            self.error.emit(str(e))
            return
        self.finished.emit("File successfully updated!")

    def single_update(self, valid, input_row):
        """process a single row of cryomodule field emission data"""
        self.progress.emit("Creating CSVs...")
        generate_amp_vs_rad_csvs(
            valid["cryomodule"], valid["start"], valid["end"], valid["decarad"]
        )
        self.progress.emit("Updating hdf5...")
        lookup = receive_metadata_input(input_row)
        convert_to_h5(lookup)

    def multi_update(self, input_csv):
        """process multiple rows of cryomodule field emission data"""
        self.progress.emit("Creating CSVs...")
        for cryo, date_s, date_e, rad, stamp in read_from_csv(input_csv):
            generate_amp_vs_rad_csvs(cryo, date_s, date_e, rad)
        self.progress.emit("Updating hdf5...")
        lookup = parse_csv(input_csv)
        convert_to_h5(lookup)
