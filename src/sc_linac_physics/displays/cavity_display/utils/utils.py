import os
from csv import DictReader
from datetime import datetime, timedelta
from typing import Dict, List

from lcls_tools.common.data.archiver import ArchiveDataHandler

DEBUG = False
BACKEND_SLEEP_TIME = 10

STATUS_SUFFIX = "CUDSTATUS"
SEVERITY_SUFFIX = "CUDSEVR"
DESCRIPTION_SUFFIX = "CUDDESC"
RF_STATUS_SUFFIX = "RFSTATE"


def parse_csv() -> List[Dict]:
    this_dir = os.path.dirname(__file__)
    path = os.path.join(this_dir, "faults.csv")
    faults: List[Dict] = []
    for row in DictReader(open(path, encoding="utf-8-sig")):
        if row["PV Suffix"]:
            faults.append(row)
    return faults


def display_hash(
    rack: str,
    fault_condition: str,
    ok_condition: str,
    tlc: str,
    suffix: str,
    prefix: str,
):
    return (
        hash(rack)
        ^ hash(fault_condition)
        ^ hash(ok_condition)
        ^ hash(tlc)
        ^ hash(suffix)
        ^ hash(prefix)
    )


class SpreadsheetError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)


def severity_of_fault(timestamp: datetime, severities: ArchiveDataHandler):
    sevr = None
    for severity_timestamp, severity in zip(
        severities.timestamps, severities.values
    ):
        try:
            rounded_ts = severity_timestamp.replace(
                microsecond=round(severity_timestamp.microsecond / 10000)
                * 10000
            )
        except ValueError:
            rounded_ts = severity_timestamp + timedelta(seconds=1)
        if (timestamp - rounded_ts).total_seconds() >= 0:
            sevr = severity
        else:
            break
    return sevr
