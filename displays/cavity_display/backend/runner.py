from datetime import datetime
from time import sleep
from typing import List, Optional

from lcls_tools.common.controls.pyepics.utils import PV

from displays.cavity_display.backend.backend_cavity import BackendCavity
from displays.cavity_display.utils.utils import DEBUG, BACKEND_SLEEP_TIME
from utils.sc_linac.linac import Machine


class Runner:
    def __init__(self):
        self.watcher_pv = "PHYS:SYS0:1:SC_CAV_FAULT_HEARTBEAT"
        self._watcher_pv_obj: Optional[PV] = None
        self.backend_cavities: List[BackendCavity] = list(
            Machine(cavity_class=BackendCavity).all_iterator
        )

    @property
    def watcher_pv_obj(self):
        if not self._watcher_pv_obj:
            self._watcher_pv_obj = PV(self.watcher_pv)
        return self._watcher_pv_obj

    def check_faults(self):
        start = datetime.now()
        for cavity in self.backend_cavities:
            cavity.run_through_faults()
        if DEBUG:
            delta = (datetime.now() - start).total_seconds()
            sleep(BACKEND_SLEEP_TIME - delta if delta < BACKEND_SLEEP_TIME else 0)
        try:
            self.watcher_pv_obj.put(self.watcher_pv_obj.get() + 1)
        except TypeError as e:
            print(f"Write to watcher PV failed with error: {e}")


if __name__ == "__main__":
    runner = Runner()
    runner.watcher_pv_obj.put(0)
    while True:
        runner.check_faults()
