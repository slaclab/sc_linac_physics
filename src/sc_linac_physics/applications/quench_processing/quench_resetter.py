from time import sleep
from typing import List

from lcls_tools.common.controls.pyepics.utils import PVInvalidError, PV
from numpy.linalg import LinAlgError

from sc_linac_physics.applications.quench_processing.quench_cavity import (
    QuenchCavity,
)
from sc_linac_physics.applications.quench_processing.quench_cryomodule import (
    QUENCH_MACHINE,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    HW_MODE_ONLINE_VALUE,
    CavityFaultError,
)


def check_cavities(cavity_list: List[QuenchCavity], watcher_pv: PV):
    logger = None
    try:
        # Flag to know if we tried to reset a false quench
        issued_reset = False
        for quench_cav in cavity_list:
            logger = quench_cav.cryomodule.logger
            if (
                quench_cav.hw_mode == HW_MODE_ONLINE_VALUE
                and not quench_cav.turned_off
            ):
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


def main():
    # Initialize watcher PV
    print("Resetting heartbeat to 0")
    WATCHER_PV: PV = PV("PHYS:SYS0:1:SC_CAV_QNCH_RESET_HEARTBEAT")
    WATCHER_PV.put(0)

    # Get cavity list
    print("Loading cavity list from QUENCH_MACHINE...")
    cavities: List[QuenchCavity] = list(QUENCH_MACHINE.all_iterator)
    print(f"Monitoring {len(cavities)} cavities")

    # Main loop
    print("Starting continuous monitoring (Ctrl+C to stop)...")
    try:
        while True:
            check_cavities(cavities, WATCHER_PV)
    except KeyboardInterrupt:
        print("\nStopping quench processing...")


if __name__ == "__main__":
    main()
