import argparse
from time import sleep

from sc_linac_physics.applications.auto_setup.backend.setup_cavity import (
    SetupCavity,
)
from sc_linac_physics.applications.auto_setup.backend.setup_cryomodule import (
    SetupCryomodule,
)
from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SETUP_MACHINE,
)
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES


def setup_cavity(cavity_object: SetupCavity, args):
    """
    Setup or shutdown a single cavity within a cryomodule.

    Args:
        cavity_object: SetupCavity object to operate on
        args: Parsed command-line arguments
    """
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

        cavity_object.trigger_start()


def main():
    """Main entry point for the cryomodule setup CLI."""
    parser = argparse.ArgumentParser(
        description="Setup or shutdown all cavities in a cryomodule",
        epilog="Example: sc-setup-cm -cm 01",
    )
    parser.add_argument(
        "--cryomodule",
        "-cm",
        choices=ALL_CRYOMODULES,
        required=True,
        help="Cryomodule name (e.g., 01, 02, H1, H2, etc.)",
    )

    parser.add_argument(
        "--shutdown",
        "-off",
        action="store_true",
        help="Turn off all cavities and SSAs in the cryomodule",
    )

    parsed_args = parser.parse_args()
    cm_name = parsed_args.cryomodule

    cm: SetupCryomodule = SETUP_MACHINE.cryomodules[cm_name]
    print(f"{cm.ssa_cal_requested_pv}: {cm.ssa_cal_requested}")
    print(f"{cm.auto_tune_requested_pv}: {cm.auto_tune_requested}")
    print(f"{cm.cav_char_requested_pv}: {cm.cav_char_requested}")
    print(f"{cm.rf_ramp_requested_pv}: {cm.rf_ramp_requested}")

    for cavity in cm.cavities.values():
        setup_cavity(cavity, parsed_args)
        sleep(0.1)


if __name__ == "__main__":
    main()
