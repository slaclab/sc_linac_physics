import argparse
import sys
from time import sleep
from typing import Optional

from sc_linac_physics.applications.tuning.tune_cavity import TuneCavity
from sc_linac_physics.applications.tuning.tuning_gui import TUNE_MACHINE
from sc_linac_physics.utils.sc_linac.cryomodule import Cryomodule
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES

DEFAULT_SLEEP_INTERVAL = 0.1


def detune_cavity(cavity_object: TuneCavity) -> bool:
    """
    Trigger the start of cavity detuning.

    Args:
        cavity_object: The TuneCavity object to detune

    Returns:
        bool: True if triggered successfully, False if script already running
    """
    if cavity_object.script_is_running:
        print(
            f"Warning: {cavity_object} script already running", file=sys.stderr
        )
        return False

    try:
        cavity_object.trigger_start()
        print(f"Triggered detuning for {cavity_object}")
        return True
    except Exception as e:
        print(f"Error triggering {cavity_object}: {e}", file=sys.stderr)
        return False


def detune_cryomodule(cryomodule: Cryomodule) -> tuple[int, int]:
    """
    Detune all cavities in a cryomodule.

    Args:
        cryomodule: The Cryomodule object containing cavities to detune

    Returns:
        tuple: (successful_count, failed_count)
    """
    successful = 0
    failed = 0

    for cavity in cryomodule.cavities.values():
        if detune_cavity(cavity):
            successful += 1
        else:
            failed += 1
        sleep(DEFAULT_SLEEP_INTERVAL)

    return successful, failed


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Detune all cavities in a specified cryomodule"
    )
    parser.add_argument(
        "--cryomodule",
        "-cm",
        choices=ALL_CRYOMODULES,
        required=True,
        help="Cryomodule name",
    )

    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """
    CLI entry point for detuning all cavities in a cryomodule.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    args = parse_args(argv)

    print(f"Detuning cryomodule {args.cryomodule}")

    try:
        cm_object: Cryomodule = TUNE_MACHINE.cryomodules[args.cryomodule]
    except KeyError as e:
        print(
            f"Error: Could not find cryomodule {args.cryomodule}: {e}",
            file=sys.stderr,
        )
        return 1

    successful, failed = detune_cryomodule(cm_object)

    print(f"\nCompleted: {successful} successful, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
