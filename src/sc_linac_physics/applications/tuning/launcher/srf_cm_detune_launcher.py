import argparse
import logging
import sys
from time import sleep
from typing import Optional

from sc_linac_physics.applications.tuning.tune_cavity import TuneCavity
from sc_linac_physics.applications.tuning.tune_utils import TUNE_LOG_DIR
from sc_linac_physics.applications.tuning.tuning_gui import TUNE_MACHINE
from sc_linac_physics.utils.logger import custom_logger
from sc_linac_physics.utils.sc_linac.cryomodule import Cryomodule
from sc_linac_physics.utils.sc_linac.linac_utils import (
    ALL_CRYOMODULES,
    CavityAbortError,
)

DEFAULT_SLEEP_INTERVAL = 0.1

logger = custom_logger(
    name=__name__,
    log_filename="detune_cryomodule",
    level=logging.DEBUG,  # Changed from INFO to DEBUG
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
    except CavityAbortError as e:
        logger.error(str(e))
    except Exception as e:
        logger.exception(
            f"Error triggering {cavity_object}",
            extra={
                "extra_data": {"cavity": str(cavity_object), "error": str(e)}
            },
        )
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

    logger.debug(
        "Starting cryomodule detune operation",
        extra={
            "extra_data": {
                "cryomodule": str(cryomodule),
                "cavity_count": len(cryomodule.cavities),
                "sleep_interval": DEFAULT_SLEEP_INTERVAL,
            }
        },
    )

    for cavity in cryomodule.cavities.values():
        if detune_cavity(cavity):
            successful += 1
        else:
            failed += 1
        sleep(DEFAULT_SLEEP_INTERVAL)

    logger.info(
        "Cryomodule detune operation completed",
        extra={
            "extra_data": {
                "cryomodule": str(cryomodule),
                "successful": successful,
                "failed": failed,
                "total": successful + failed,
            }
        },
    )

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

    logger.info(
        "Starting cryomodule detune script",
        extra={"extra_data": {"cryomodule": args.cryomodule}},
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

    successful, failed = detune_cryomodule(cm_object)

    logger.info(
        "Detune cryomodule script completed",
        extra={
            "extra_data": {
                "cryomodule": args.cryomodule,
                "successful": successful,
                "failed": failed,
                "total": successful + failed,
            }
        },
    )

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
