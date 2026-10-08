import logging
import os
from csv import DictReader
from typing import Dict, List

from sc_linac_physics.utils.logger import BASE_LOG_DIR, custom_logger
from sc_linac_physics.utils.platform_paths import is_macos

CAV_LOG_DIR = str(BASE_LOG_DIR / "cavity_display")

# Basic OS detection
DEBUG = is_macos()
BACKEND_SLEEP_TIME = 10 if DEBUG else 0

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


cavity_fault_logger = custom_logger(
    name="cavity.fault.runner",
    log_filename="cavity_fault_runner",
    log_dir=CAV_LOG_DIR,
    level=logging.DEBUG if DEBUG else logging.INFO,
)
