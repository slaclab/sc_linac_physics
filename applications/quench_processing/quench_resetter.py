from time import sleep

from numpy.linalg import LinAlgError

from lcls_tools.common.controls.pyepics.utils import PVInvalidError, PV
from lcls_tools.superconducting.sc_linac_utils import (
    ALL_CRYOMODULES,
    HW_MODE_ONLINE_VALUE,
    CavityFaultError,
)
from quench_linac import QUENCH_MACHINE, QuenchCryomodule

WATCHER_PV: PV = PV("PHYS:SYS0:1:SC_CAV_QNCH_RESET_HEARTBEAT")
WATCHER_PV.put(0)


while True:
    # Flag to know if we tried to reset a false quench
    issued_reset = False

    for cryomoduleName in ALL_CRYOMODULES:
        quench_cm: QuenchCryomodule = QUENCH_MACHINE.cryomodules[cryomoduleName]
        for quench_cav in quench_cm.cavities.values():
            if quench_cav.hw_mode == HW_MODE_ONLINE_VALUE:
                if (
                    not quench_cav.quench_latch_invalid
                    and quench_cav.quench_latch_pv_obj.get() == 1
                ):
                    try:
                        is_real = quench_cav.validate_quench(wait_for_update=True)

                        if not is_real:
                            quench_cm.logger.info(
                                f"{quench_cav} FAKE quench detected, resetting"
                            )
                            quench_cav.reset_interlocks()
                            issued_reset = True

                        else:
                            quench_cm.logger.warning(
                                f"{quench_cav} REAL quench detected, not resetting"
                            )

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
        issued_reset = False

    try:
        WATCHER_PV.put(WATCHER_PV.get() + 1)
    except PVInvalidError as e:
        print(e)
