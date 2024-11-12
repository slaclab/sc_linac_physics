import sys
from time import sleep
from typing import List

from lcls_tools.common.controls.pyepics.utils import PVInvalidError, PV
from lcls_tools.superconducting.sc_linac_utils import (
    HW_MODE_ONLINE_VALUE,
    CavityFaultError,
)
from numpy.linalg import LinAlgError

sys.path.append("/home/physics/srf/sc_linac_physics")
from applications.quench_processing.quench_cryomodule import (  # noqa: E402
    QuenchCryomodule,
)
from applications.quench_processing.quench_cavity import QuenchCavity
from quench_cryomodule import QUENCH_MACHINE  # noqa: E402

WATCHER_PV: PV = PV("PHYS:SYS0:1:SC_CAV_QNCH_RESET_HEARTBEAT")
WATCHER_PV.put(0)

cavities: List[QuenchCavity] = list(QUENCH_MACHINE.all_iterator)


def check_cavities():
    # Flag to know if we tried to reset a false quench
    issued_reset = False
    for quench_cav in cavities:
        if quench_cav.hw_mode == HW_MODE_ONLINE_VALUE and quench_cav.is_on:
            if (
                not quench_cav.quench_latch_invalid
                and quench_cav.quench_latch_pv_obj.get() == 1
            ):
                quench_cm: QuenchCryomodule = quench_cav.cryomodule
                try:
                    issued_reset = quench_cav.reset_quench()

                except (
                    TypeError,
                    LinAlgError,
                    IndexError,
                    CavityFaultError,
                    PVInvalidError,
                ) as e:
                    quench_cm.logger.error(f"{quench_cav} error: {e}")
    # Since the resetter doesn't wait anymore, want to wait in case
    # we keep hammering one faulted cavity
    if issued_reset:
        sleep(3)
    try:
        WATCHER_PV.put(WATCHER_PV.get() + 1)
    except PVInvalidError as e:
        print(e)


if __name__ == "__main__":
    while True:
        check_cavities()
