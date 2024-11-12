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
    QUENCH_MACHINE,
)
from applications.quench_processing.quench_cavity import QuenchCavity  # noqa: E402


def check_cavities(cavity_list: List[QuenchCavity], watcher_pv: PV):
    # Flag to know if we tried to reset a false quench
    issued_reset = False
    for quench_cav in cavity_list:
        if quench_cav.hw_mode == HW_MODE_ONLINE_VALUE and quench_cav.is_on:
            if quench_cav.is_quenched:
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
        watcher_pv.put(watcher_pv.get() + 1)
    except PVInvalidError as e:
        print(e)


if __name__ == "__main__":
    WATCHER_PV: PV = PV("PHYS:SYS0:1:SC_CAV_QNCH_RESET_HEARTBEAT")
    WATCHER_PV.put(0)
    cavities: List[QuenchCavity] = list(QUENCH_MACHINE.all_iterator)
    while True:
        check_cavities(cavities, WATCHER_PV)
