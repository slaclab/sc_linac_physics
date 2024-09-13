import argparse
from time import sleep

from lcls_tools.superconducting.sc_linac_utils import ALL_CRYOMODULES

from setup_linac import SETUP_MACHINE, SetupCryomodule, SetupCavity


def setup_cavity(cavity_object: SetupCavity):
    if cavity_object.script_is_running:
        cavity_object.status_message = f"{cavity_object} script already running"
        return

    if args.shutdown:
        cavity_object.trigger_shutdown()

    else:
        cavity_object.ssa_cal_requested = cm_object.ssa_cal_requested
        cavity_object.auto_tune_requested = cm_object.auto_tune_requested
        cavity_object.cav_char_requested = cm_object.cav_char_requested
        cavity_object.rf_ramp_requested = cm_object.rf_ramp_requested

        cavity_object.trigger_setup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--cryomodule",
        "-cm",
        choices=ALL_CRYOMODULES,
        required=True,
        help=f"Cryomodule name as a string",
    )

    parser.add_argument(
        "--shutdown", "-off", action="store_true", help="Turn off cavity and SSA"
    )

    args = parser.parse_args()
    print(args)
    cm_name = args.cryomodule

    cm_object: SetupCryomodule = SETUP_MACHINE.cryomodules[cm_name]

    for cavity in cm_object.cavities.values():
        setup_cavity(cavity)
        sleep(0.1)
