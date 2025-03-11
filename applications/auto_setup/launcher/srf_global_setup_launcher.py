import argparse
import sys

from applications.auto_setup.backend.setup_cavity import SetupCavity

sys.path.append("/home/physics/srf/sc_linac_physics")
from applications.auto_setup.backend.setup_machine import (  # noqa: E402
    SETUP_MACHINE,
)


def trigger_cavity(cavity_obj: SetupCavity):
    if args.shutdown:
        cavity_obj.trigger_shutdown()

    else:
        cavity_obj.ssa_cal_requested = SETUP_MACHINE.ssa_cal_requested
        cavity_obj.auto_tune_requested = SETUP_MACHINE.auto_tune_requested
        cavity_obj.cav_char_requested = SETUP_MACHINE.cav_char_requested
        cavity_obj.rf_ramp_requested = SETUP_MACHINE.rf_ramp_requested

        cavity_obj.trigger_setup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no_hl", "-no_hl", action="store_true", help="Exclude HLs from setup script"
    )

    parser.add_argument(
        "--shutdown", "-off", action="store_true", help="Turn off cavity and SSA"
    )

    args = parser.parse_args()
    print(args)

    if args.no_hl:
        for non_hl_cavity in SETUP_MACHINE.non_hl_iterator:
            trigger_cavity(non_hl_cavity)

    else:
        for cavity in SETUP_MACHINE.all_iterator:
            trigger_cavity(cavity)
