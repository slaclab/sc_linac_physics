import argparse
import logging
import sys
from time import sleep
from typing import Optional

from sc_linac_physics.applications.tuning.tune_cavity import TuneCavity
from sc_linac_physics.applications.tuning.tune_rack import TuneRack
from sc_linac_physics.applications.tuning.tune_utils import TUNE_LOG_DIR
from sc_linac_physics.applications.tuning.tuning_gui import TUNE_MACHINE
from sc_linac_physics.utils.logger import custom_logger
from sc_linac_physics.utils.sc_linac.cryomodule import Cryomodule
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES

DEFAULT_SLEEP_INTERVAL = 0.1

logger = custom_logger(
    name=__name__,
    log_filename="detune_rack",
    level=logging.INFO,
    log_dir=str(TUNE_LOG_DIR),
)


def detune_cavity(cavity_object: TuneCavity) -> bool:
    """
    Trigger the start of cavity detuning.

    Args:
        cavity_object: The TuneCavity object to detune

    Returns:
        bool: True if triggered successfully, False if script already running
    """
    if cavity_object.script_is_running:
        logger.warning(
            "Script already running",
            extra={"extra_data": {"cavity": str(cavity_object)}},
        )
        return False

    try:
        cavity_object.trigger_start()
        logger.info(
            "Triggered cavity detuning",
            extra={"extra_data": {"cavity": str(cavity_object)}},
        )
        return True
    except Exception as e:
        logger.exception(
            f"Error triggering {cavity_object}",
            extra={
                "extra_data": {"cavity": str(cavity_object), "error": str(e)}
            },
        )
        return False


def detune_rack(
    rack: TuneRack,
    sleep_interval: float = DEFAULT_SLEEP_INTERVAL,
) -> tuple[int, int]:
    """
    Detune all cavities in a rack.

    Args:
        rack: The TuneRack object containing cavities to detune
        sleep_interval: Time to sleep between cavity operations (seconds)

    Returns:
        tuple: (successful_count, failed_count)
    """
    successful = 0
    failed = 0

    logger.debug(
        "Starting rack detune operation",
        extra={
            "extra_data": {
                "rack": str(rack),
                "cavity_count": len(rack.cavities),
                "sleep_interval": sleep_interval,
            }
        },
    )

    for cavity in rack.cavities.values():
        if detune_cavity(cavity):
            successful += 1
        else:
            failed += 1
        sleep(sleep_interval)

    logger.info(
        "Rack detune operation completed",
        extra={
            "extra_data": {
                "rack": str(rack),
                "successful": successful,
                "failed": failed,
                "total": successful + failed,
            }
        },
    )

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
        help="Enable verbose output (sets DEBUG level)",
    )

    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """
    CLI entry point for detuning all cavities in a rack.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    args = parse_args(argv)

    # Adjust log level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.debug(
        "Starting rack detune script",
        extra={
            "extra_data": {
                "cryomodule": args.cryomodule,
                "rack": args.rack,
                "sleep_interval": args.sleep_interval,
            }
        },
    )

    try:
        cm_object: Cryomodule = TUNE_MACHINE.cryomodules[args.cryomodule]
    except KeyError as e:
        logger.error(
            "Could not find cryomodule",
            extra={
                "extra_data": {"cryomodule": args.cryomodule, "error": str(e)}
            },
        )
        return 1

    rack_obj = get_rack(cm_object, args.rack)

    successful, failed = detune_rack(rack_obj, args.sleep_interval)

    # Always log the summary at INFO level
    logger.info(
        "Detune rack script completed",
        extra={
            "extra_data": {
                "cryomodule": args.cryomodule,
                "rack": args.rack,
                "successful": successful,
                "failed": failed,
                "total": successful + failed,
            }
        },
    )

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
