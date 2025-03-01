import argparse
import sys
from time import sleep

sys.path.append("/home/physics/srf/sc_linac_physics")

from applications.auto_setup.backend.setup_cavity import SetupCavity  # noqa: E402
from applications.auto_setup.backend.setup_cryomodule import (  # noqa: E402
    SetupCryomodule,
)
from applications.auto_setup.backend.setup_machine import SETUP_MACHINE  # noqa: E402
from utils.sc_linac.linac_utils import ALL_CRYOMODULES  # noqa: E402


def setup_cavity(cavity_object: SetupCavity, args):
    if cavity_object.script_is_running:
        cavity_object.status_message = f"{cavity_object} script already running"
        return

    if args.shutdown:
        cavity_object.trigger_shutdown()

    else:
        cm: SetupCryomodule = cavity_object.cryomodule
        cavity_object.ssa_cal_requested = cm.ssa_cal_requested
        cavity_object.auto_tune_requested = cm.auto_tune_requested
        cavity_object.cav_char_requested = cm.cav_char_requested
        cavity_object.rf_ramp_requested = cm.rf_ramp_requested

        cavity_object.trigger_setup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cryomodule",
        "-cm",
        choices=ALL_CRYOMODULES,
        required=True,
        help="Cryomodule name as a string",
    )

    parser.add_argument(
        "--shutdown", "-off", action="store_true", help="Turn off cavity and SSA"
    )

    parsed_args = parser.parse_args()
    cm_name = parsed_args.cryomodule

    cm_object: SetupCryomodule = SETUP_MACHINE.cryomodules[cm_name]

    for cavity in cm_object.cavities.values():
        setup_cavity(cavity, parsed_args)
        sleep(0.1)
