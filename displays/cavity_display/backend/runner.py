from datetime import datetime
from time import sleep

from lcls_tools.common.controls.pyepics.utils import PV

from displays.cavity_display.backend.backend_cavity import BackendCavity
from displays.cavity_display.utils.utils import DEBUG, BACKEND_SLEEP_TIME
from utils.sc_linac.cryomodule import Cryomodule
from utils.sc_linac.linac import Machine
from utils.sc_linac.linac_utils import ALL_CRYOMODULES

WATCHER_PV: PV = PV("PHYS:SYS0:1:SC_CAV_FAULT_HEARTBEAT")
WATCHER_PV.put(0)

DISPLAY_MACHINE = Machine(cavity_class=BackendCavity)

while True:
    start = datetime.now()
    for cryomoduleName in ALL_CRYOMODULES:
        cryomodule: Cryomodule = DISPLAY_MACHINE.cryomodules[cryomoduleName]
        for cavity in cryomodule.cavities.values():
            cavity.run_through_faults()
    if DEBUG:
        delta = (datetime.now() - start).total_seconds()
        sleep(BACKEND_SLEEP_TIME - delta if delta < BACKEND_SLEEP_TIME else 0)

    try:
        WATCHER_PV.put(WATCHER_PV.get() + 1)
    except TypeError as e:
        print(f"Write to watcher PV failed with error: {e}")
