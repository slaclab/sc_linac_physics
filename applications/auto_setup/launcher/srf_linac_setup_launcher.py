import argparse
import sys
from time import sleep

sys.path.append("/home/physics/srf/sc_linac_physics")
from applications.auto_setup.backend.setup_cryomodule import (  # noqa: E402
    SetupCryomodule,
)
from applications.auto_setup.backend.setup_machine import SETUP_MACHINE  # noqa: E402
from utils.sc_linac.linac_utils import LINAC_CM_DICT  # noqa: E402


def setup_cryomodule(cryomodule_object: SetupCryomodule):
    if args.shutdown:
        cryomodule_object.trigger_shutdown()

    else:
        cryomodule_object.ssa_cal_requested = cryomodule_object.linac.ssa_cal_requested
        cryomodule_object.auto_tune_requested = (
            cryomodule_object.linac.auto_tune_requested
        )
        cryomodule_object.cav_char_requested = (
            cryomodule_object.linac.cav_char_requested
        )
        cryomodule_object.rf_ramp_requested = cryomodule_object.linac.rf_ramp_requested

        cryomodule_object.trigger_setup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--linac",
        "-l",
        required=True,
        choices=range(4),
        type=int,
        help="Linac number as an int",
    )

    parser.add_argument(
        "--shutdown", "-off", action="store_true", help="Turn off cavity and SSA"
    )

    args = parser.parse_args()
    print(args)
    linac_number: int = args.linac

    for cm_name in LINAC_CM_DICT[linac_number]:
        cm_object: SetupCryomodule = SETUP_MACHINE.cryomodules[cm_name]
        setup_cryomodule(cm_object)
        sleep(0.5)
