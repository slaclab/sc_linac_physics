import argparse
import sys
from time import sleep
from typing import Optional

from sc_linac_physics.applications.tuning.tune_cavity import TuneCavity
from sc_linac_physics.applications.tuning.tune_rack import TuneRack
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


def detune_rack(
    rack: TuneRack,
    sleep_interval: float = DEFAULT_SLEEP_INTERVAL,
    verbose: bool = False,
) -> tuple[int, int]:
    """
    Detune all cavities in a rack.

    Args:
        rack: The TuneRack object containing cavities to detune
        sleep_interval: Time to sleep between cavity operations (seconds)
        verbose: Enable verbose output

    Returns:
        tuple: (successful_count, failed_count)
    """
    successful = 0
    failed = 0

    if verbose:
        print(f"Detuning {len(rack.cavities)} cavities in rack")

    for cavity in rack.cavities.values():
        if detune_cavity(cavity):
            successful += 1
        else:
            failed += 1
        sleep(sleep_interval)

    return successful, failed


def get_rack(cryomodule: Cryomodule, rack_name: str) -> TuneRack:
    """
    Get the specified rack from a cryomodule.

    Args:
        cryomodule: The Cryomodule object
        rack_name: Either "A" or "B"

    Returns:
        TuneRack: The requested rack object
    """
    return cryomodule.rack_a if rack_name == "A" else cryomodule.rack_b


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Detune all cavities in a specified rack"
    )
    parser.add_argument(
        "--cryomodule",
        "-cm",
        choices=ALL_CRYOMODULES,
        required=True,
        help="Cryomodule name",
    )
    parser.add_argument(
        "--rack",
        "-r",
        choices=["A", "B"],
        required=True,
        help="Rack name (A or B)",
    )
    parser.add_argument(
        "--sleep-interval",
        "-s",
        type=float,
        default=DEFAULT_SLEEP_INTERVAL,
        help=f"Sleep interval between cavities in seconds (default: {DEFAULT_SLEEP_INTERVAL})",
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
    CLI entry point for detuning all cavities in a rack.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    args = parse_args(argv)

    if args.verbose:
        print(f"Detuning rack {args.rack} in cryomodule {args.cryomodule}")

    try:
        cm_object: Cryomodule = TUNE_MACHINE.cryomodules[args.cryomodule]
    except KeyError as e:
        print(
            f"Error: Could not find cryomodule {args.cryomodule}: {e}",
            file=sys.stderr,
        )
        return 1

    rack_obj = get_rack(cm_object, args.rack)

    successful, failed = detune_rack(
        rack_obj, args.sleep_interval, args.verbose
    )

    print(f"\nCompleted: {successful} successful, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
