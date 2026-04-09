import dataclasses
import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from PyQt5.QtCore import QThread, pyqtSignal

from sc_linac_physics.displays.cavity_display.backend.fault import (
    FaultCounter,
)


@dataclasses.dataclass
class CavityFaultResult:
    """Fault counts for a single cavity, broken down by TLC."""

    cm_name: str
    cavity_num: int
    fault_counts_by_tlc: Optional[Dict[str, FaultCounter]] = None
    error: Optional[str] = None

    def _sum_tlc_field(self, field: str) -> int:
        if not self.fault_counts_by_tlc:
            return 0
        return sum(getattr(c, field) for c in self.fault_counts_by_tlc.values())

    @property
    def alarm_count(self) -> int:
        return self._sum_tlc_field("alarm_count")

    @property
    def warning_count(self) -> int:
        return self._sum_tlc_field("warning_count")

    @property
    def invalid_count(self) -> int:
        return self._sum_tlc_field("invalid_count")

    @property
    def ok_count(self) -> int:
        return self._sum_tlc_field("ok_count")

    @property
    def is_error(self) -> bool:
        return self.error is not None

    def to_fault_counter(self) -> FaultCounter:
        return FaultCounter(
            alarm_count=self.alarm_count,
            warning_count=self.warning_count,
            invalid_count=self.invalid_count,
            ok_count=self.ok_count,
        )


class FaultDataFetcher(QThread):
    """Fetches fault counts for all cavities in a background thread."""

    progress = pyqtSignal(int, int)
    cavity_result = pyqtSignal(object)
    finished_all = pyqtSignal(object)
    fetch_error = pyqtSignal(str)

    def __init__(
        self,
        machine,
        start_time: datetime,
        end_time: datetime,
        cavity_filter: Optional[Set[Tuple[str, int]]] = None,
        cm_whitelist: Optional[Set[str]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._machine = machine
        self._start_time = start_time
        self._end_time = end_time
        self._cavity_filter = cavity_filter
        self._cm_whitelist = cm_whitelist
        self._abort_event = threading.Event()

    def abort(self) -> None:
        self._abort_event.set()

    @property
    def is_abort_requested(self) -> bool:
        return self._abort_event.is_set()

    def _collect_cavities(self) -> List[Tuple[str, int, Any]]:
        cavities = []
        for linac in self._machine.linacs:
            for cm_name, cm in linac.cryomodules.items():
                if (
                    self._cm_whitelist is not None
                    and cm_name not in self._cm_whitelist
                ):
                    continue
                for cav_num, cavity in cm.cavities.items():
                    if (
                        self._cavity_filter is None
                        or (cm_name, cav_num) in self._cavity_filter
                    ):
                        cavities.append((cm_name, cav_num, cavity))
        return cavities

    MAX_WORKERS = 8

    def run(self) -> None:
        try:
            cavities = self._collect_cavities()
        except Exception as e:
            self.fetch_error.emit(f"Failed to enumerate cavities: {e}")
            return

        total = len(cavities)
        if total == 0:
            self.fetch_error.emit("No cavities found in machine")
            return

        all_results: List[CavityFaultResult] = []

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures: Dict[Future, Tuple[str, int]] = {}
            for cm_name, cav_num, cavity in cavities:
                if self._abort_event.is_set():
                    break
                future = executor.submit(
                    self._fetch_single_cavity,
                    cm_name,
                    cav_num,
                    cavity,
                )
                futures[future] = (cm_name, cav_num)

            for future in as_completed(futures):
                result = future.result()
                all_results.append(result)
                self.cavity_result.emit(result)
                self.progress.emit(len(all_results), total)

                if self._abort_event.is_set():
                    for f in futures:
                        f.cancel()
                    break

        self.finished_all.emit(all_results)

    def _fetch_single_cavity(
        self, cm_name: str, cavity_num: int, cavity
    ) -> CavityFaultResult:
        if self._abort_event.is_set():
            return CavityFaultResult(
                cm_name=cm_name,
                cavity_num=cavity_num,
                error="Aborted",
            )

        try:
            fault_counts = cavity.get_fault_counts(
                self._start_time, self._end_time
            )
        except Exception as e:
            return CavityFaultResult(
                cm_name=cm_name,
                cavity_num=cavity_num,
                error=str(e),
            )

        return CavityFaultResult(
            cm_name=cm_name,
            cavity_num=cavity_num,
            fault_counts_by_tlc=dict(fault_counts),
        )
