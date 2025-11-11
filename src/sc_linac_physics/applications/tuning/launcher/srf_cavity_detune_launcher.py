import argparse
import sys
from typing import Optional

from sc_linac_physics.applications.tuning.tune_cavity import TuneCavity
from sc_linac_physics.applications.tuning.tuning_gui import TUNE_MACHINE
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES


def detune_cavity(cavity: TuneCavity) -> bool:
    """
    Detune a cavity by moving it to cold landing position.

    Args:
        cavity: The TuneCavity object to detune

    Returns:
        bool: True if successful, False if script is already running
    """
    if cavity.script_is_running:
        print(f"Warning: {cavity} script already running", file=sys.stderr)
        return False

    try:
        cavity.move_to_cold_landing()
        print(f"Successfully detuned {cavity}")
        return True
    except Exception as e:
        print(f"Error detuning {cavity}: {e}", file=sys.stderr)
        return False


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Detune a cavity by moving it to cold landing position"
    )
    parser.add_argument(
        "--cryomodule",
        "-cm",
        choices=ALL_CRYOMODULES,
        required=True,
        help="Cryomodule name as a string",
    )
    parser.add_argument(
        "--cavity",
        "-cav",
        required=True,
        choices=range(1, 9),
        type=int,
        metavar="1-8",
        help="Cavity number (1-8)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output",
    )

    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """
    CLI entry point for detuning a cavity.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    args = parse_args(argv)

    if args.verbose:
        print(f"Detuning cavity {args.cavity} in cryomodule {args.cryomodule}")

    try:
        cavity_obj: TuneCavity = TUNE_MACHINE.cryomodules[
            args.cryomodule
        ].cavities[args.cavity]
    except KeyError as e:
        print(
            f"Error: Could not find cavity {args.cavity} in cryomodule {args.cryomodule}: {e}",
            file=sys.stderr,
        )
        return 1

    success = detune_cavity(cavity_obj)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
