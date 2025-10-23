import argparse
from time import sleep

from sc_linac_physics.applications.auto_setup.backend.setup_cryomodule import (
    SetupCryomodule,
)
from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SETUP_MACHINE,
)
from sc_linac_physics.utils.sc_linac.linac_utils import LINAC_CM_DICT


def setup_cryomodule(
    cryomodule_object: SetupCryomodule, args: argparse.Namespace
):
    """
    Setup or shutdown a single cryomodule within a linac.

    Args:
        cryomodule_object: SetupCryomodule object to operate on
        args: Parsed command-line arguments
    """
    if args.shutdown:
        cryomodule_object.trigger_shutdown()

    else:
        cryomodule_object.ssa_cal_requested = (
            cryomodule_object.linac.ssa_cal_requested
        )
        cryomodule_object.auto_tune_requested = (
            cryomodule_object.linac.auto_tune_requested
        )
        cryomodule_object.cav_char_requested = (
            cryomodule_object.linac.cav_char_requested
        )
        cryomodule_object.rf_ramp_requested = (
            cryomodule_object.linac.rf_ramp_requested
        )

        cryomodule_object.trigger_setup()


def main():
    """Main entry point for the linac setup CLI."""
    parser = argparse.ArgumentParser(
        description="Setup or shutdown all cryomodules in a specific linac",
        epilog="Example: sc-linac-setup-linac -l 0",
    )
    parser.add_argument(
        "--linac",
        "-l",
        required=True,
        choices=range(4),
        type=int,
        help="Linac number as an int (0-3)",
    )

    parser.add_argument(
        "--shutdown",
        "-off",
        action="store_true",
        help="Turn off all cavities and SSAs in the linac",
    )

    args = parser.parse_args()
    print(args)
    linac_number: int = args.linac

    cryomodule_list = LINAC_CM_DICT[linac_number]
    print(
        f"Setting up {len(cryomodule_list)} cryomodules in Linac {linac_number}"
    )

    for cm_name in cryomodule_list:
        cm_object: SetupCryomodule = SETUP_MACHINE.cryomodules[cm_name]
        setup_cryomodule(cm_object, args)
        sleep(0.5)


if __name__ == "__main__":
    main()
