import argparse

from sc_linac_physics.applications.auto_setup.backend.setup_cryomodule import (
    SetupCryomodule,
)
from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SetupMachine,
    SETUP_MACHINE,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    ALL_CRYOMODULES_NO_HL,
    ALL_CRYOMODULES,
)


def setup_cryomodule(
    cryomodule_object: SetupCryomodule,
    args: argparse.Namespace,
    machine: SetupMachine,
):
    """
    Setup or shutdown a single cryomodule.

    Args:
        cryomodule_object: SetupCryomodule object to operate on
        args: Parsed command-line arguments
        machine: SetupMachine object containing global settings
    """
    if args.shutdown:
        cryomodule_object.trigger_shutdown()

    else:
        cryomodule_object.ssa_cal_requested = machine.ssa_cal_requested
        cryomodule_object.auto_tune_requested = machine.auto_tune_requested
        cryomodule_object.cav_char_requested = machine.cav_char_requested
        cryomodule_object.rf_ramp_requested = machine.rf_ramp_requested

        cryomodule_object.trigger_setup()


def main():
    """Main entry point for the global (machine-wide) setup CLI."""
    parser = argparse.ArgumentParser(
        description="Setup or shutdown all cryomodules in the machine",
        epilog="Example: sc-setup-all --no_hl",
    )
    parser.add_argument(
        "--no_hl",
        "-no_hl",
        action="store_true",
        help="Exclude HLs (Harmonic Linearizer) cryomodules from setup script",
    )

    parser.add_argument(
        "--shutdown",
        "-off",
        action="store_true",
        help="Turn off all cavities and SSAs",
    )

    args = parser.parse_args()
    machine: SetupMachine = SetupMachine()
    print(args)

    print(f"{machine.ssa_cal_requested_pv}: {machine.ssa_cal_requested}")
    print(f"{machine.auto_tune_requested_pv}: {machine.auto_tune_requested}")
    print(f"{machine.cav_char_requested_pv}: {machine.cav_char_requested}")
    print(f"{machine.rf_ramp_requested_pv}: {machine.rf_ramp_requested}")

    if args.no_hl:
        cryomodule_list = ALL_CRYOMODULES_NO_HL
        print(f"Setting up {len(cryomodule_list)} cryomodules (excluding HL)")
    else:
        cryomodule_list = ALL_CRYOMODULES
        print(f"Setting up {len(cryomodule_list)} cryomodules (all)")

    for cm_name in cryomodule_list:
        cm_object: SetupCryomodule = SETUP_MACHINE.cryomodules[cm_name]
        setup_cryomodule(cm_object, args, machine)


if __name__ == "__main__":
    main()
