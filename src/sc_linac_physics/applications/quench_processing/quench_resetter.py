from time import sleep
from typing import List

from lcls_tools.common.controls.pyepics.utils import PVInvalidError, PV
from lcls_tools.superconducting.sc_linac_utils import (
    HW_MODE_ONLINE_VALUE,
    CavityFaultError,
)
from numpy.linalg import LinAlgError

from sc_linac_physics.applications.quench_processing.quench_cavity import (
    QuenchCavity,
)  # noqa: E402
from sc_linac_physics.applications.quench_processing.quench_cryomodule import (  # noqa: E402
    QUENCH_MACHINE,
)


def check_cavities(cavity_list: List[QuenchCavity], watcher_pv: PV):
    logger = None
    try:
        # Flag to know if we tried to reset a false quench
        issued_reset = False
        for quench_cav in cavity_list:
            logger = quench_cav.cryomodule.logger
            if quench_cav.hw_mode == HW_MODE_ONLINE_VALUE and not quench_cav.turned_off:
                if quench_cav.is_quenched:
                    issued_reset = quench_cav.reset_quench()

        # Since the resetter doesn't wait anymore, want to wait in case
        # we keep hammering one faulted cavity
        if issued_reset:
            sleep(3)

        watcher_pv.put(watcher_pv.get() + 1)

    except (
        TypeError,
        LinAlgError,
        IndexError,
        CavityFaultError,
        PVInvalidError,
    ) as e:
        if logger:
            logger.error(e)
        else:
            print(e)


if __name__ == "__main__":
    WATCHER_PV: PV = PV("PHYS:SYS0:1:SC_CAV_QNCH_RESET_HEARTBEAT")
    WATCHER_PV.put(0)
    cavities: List[QuenchCavity] = list(QUENCH_MACHINE.all_iterator)
    while True:
        check_cavities(cavities, WATCHER_PV)
