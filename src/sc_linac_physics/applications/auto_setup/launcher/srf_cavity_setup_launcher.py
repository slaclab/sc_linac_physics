import argparse
import sys

from sc_linac_physics.applications.auto_setup.backend.setup_cavity import (
    SetupCavity,
)
from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SETUP_MACHINE,
)
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES


def setup_cavity(cavity: SetupCavity, args: argparse.Namespace):
    if cavity.script_is_running:
        cavity.status_message = f"{cavity} script already running"
        return

    if args.shutdown:
        cavity.shut_down()

    else:
        cavity.setup()


def main():
    """Main entry point for the cavity setup CLI."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Setup or shutdown a specific cavity",
        epilog="Example: sc-linac-setup-cavity -cm 01 -cav 1",
    )
    parser.add_argument(
        "--cryomodule",
        "-cm",
        choices=ALL_CRYOMODULES,
        required=True,
        help="Cryomodule name (e.g., 01, 02, H1, H2, etc.)",
    )
    parser.add_argument(
        "--cavity",
        "-cav",
        required=True,
        choices=range(1, 9),
        type=int,
        help="Cavity number as an int (1-8)",
    )
    parser.add_argument(
        "--shutdown",
        "-off",
        action="store_true",
        help="Turn off cavity and SSA (default: turn on)",
    )

    parsed_args: argparse.Namespace = parser.parse_args()

    try:
        cm_name = parsed_args.cryomodule
        cav_num = parsed_args.cavity

        cavity_obj: SetupCavity = SETUP_MACHINE.cryomodules[cm_name].cavities[
            cav_num
        ]

        setup_cavity(cavity_obj, parsed_args)

    except KeyError as e:
        print(
            f"Error: Invalid cryomodule or cavity number: {e}", file=sys.stderr
        )
        sys.exit(1)
    except Exception as e:
        print(f"Error during cavity setup: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
