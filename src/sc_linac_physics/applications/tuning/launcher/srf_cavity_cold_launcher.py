import argparse
import logging
import sys
from typing import Optional

from sc_linac_physics.applications.tuning.tune_cavity import TuneCavity
from sc_linac_physics.applications.tuning.tune_utils import TUNE_LOG_DIR
from sc_linac_physics.applications.tuning.tuning_gui import TUNE_MACHINE
from sc_linac_physics.utils.logger import custom_logger
from sc_linac_physics.utils.sc_linac.linac_utils import (
    ALL_CRYOMODULES,
    CavityAbortError,
)

logger = custom_logger(
    name=__name__,
    log_filename="detune_cavity",
    level=logging.DEBUG,
    log_dir=str(TUNE_LOG_DIR),
)


def detune_cavity(cavity: TuneCavity, use_rf: bool = True) -> bool:
    """
    Detune a cavity by moving it to cold landing position.

    Args:
        cavity: The TuneCavity object to detune
        use_rf: If True, use RF for detuning. If False, detune without RF.

    Returns:
        bool: True if successful, False if script is already running
    """
    if cavity.script_is_running:
        logger.warning(
            "Script already running",
            extra={"extra_data": {"cavity": str(cavity)}},
        )
        return False

    try:
        cavity.move_to_cold_landing()
        logger.info(
            "Successfully detuned cavity",
            extra={
                "extra_data": {
                    "cavity": str(cavity),
                    "use_rf": use_rf,
                }
            },
        )
        return True
    except CavityAbortError as e:
        logger.error(str(e))
        return False
    except Exception as e:
        logger.exception(
            f"Error detuning {cavity}",
            extra={
                "extra_data": {
                    "cavity": str(cavity),
                    "use_rf": use_rf,
                    "error": str(e),
                }
            },
        )
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
        "--no-rf",
        action="store_true",
        help="Detune without using RF (default: use RF)",
    )

    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """
    CLI entry point for detuning a cavity.

    Returns:
        int: Exit code (0 for success, 1 for failure)
    """
    args = parse_args(argv)

    logger.debug(
        "Starting cavity detune operation",
        extra={
            "extra_data": {
                "cryomodule": args.cryomodule,
                "cavity": args.cavity,
                "use_rf": not args.no_rf,
            }
        },
    )

    try:
        cavity_obj: TuneCavity = TUNE_MACHINE.cryomodules[
            args.cryomodule
        ].cavities[args.cavity]
    except KeyError as e:
        logger.error(
            "Could not find cavity in cryomodule",
            extra={
                "extra_data": {
                    "cryomodule": args.cryomodule,
                    "cavity": args.cavity,
                    "error": str(e),
                }
            },
        )
        return 1

    success = detune_cavity(cavity_obj, use_rf=not args.no_rf)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
