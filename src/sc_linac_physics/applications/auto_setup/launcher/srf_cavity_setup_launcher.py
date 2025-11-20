import argparse
import logging
import sys

from sc_linac_physics.applications.auto_setup.backend.setup_cavity import (
    SetupCavity,
)
from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SETUP_MACHINE,
)
from sc_linac_physics.applications.auto_setup.backend.setup_utils import (
    SETUP_LOG_DIR,
)
from sc_linac_physics.utils.logger import custom_logger
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES


def setup_cavity(
    cavity: SetupCavity, args: argparse.Namespace, logger: logging.Logger
):
    if cavity.script_is_running:
        cavity.set_status_message(
            f"{cavity} script already running", logging.WARNING
        )
        logger.warning("%s script already running", cavity)
        return

    if args.shutdown:
        logger.info("Shutting down %s", cavity)
        cavity.shut_down()
    else:
        logger.info("Setting up %s", cavity)
        cavity.setup()


def main():
    """Main entry point for the cavity setup CLI."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Setup or shutdown a specific cavity",
        epilog="Example: sc-setup-cav -cm 01 -cav 1",
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

    # Initialize launcher-specific logger
    cm_name = parsed_args.cryomodule
    cav_num = parsed_args.cavity

    logger = custom_logger(
        __name__, log_dir=str(SETUP_LOG_DIR), log_filename="cavity_launcher"
    )

    try:
        logger.info(
            "Starting cavity setup script",
            extra={
                "extra_data": {
                    "cryomodule": cm_name,
                    "cavity_number": cav_num,
                    "shutdown": parsed_args.shutdown,
                }
            },
        )

        cavity: SetupCavity = SETUP_MACHINE.cryomodules[cm_name].cavities[
            cav_num
        ]

        logger.info(
            "Setup request flags",
            extra={
                "extra_data": {
                    "ssa_cal_requested": cavity.ssa_cal_requested,
                    "auto_tune_requested": cavity.auto_tune_requested,
                    "cav_char_requested": cavity.cav_char_requested,
                    "rf_ramp_requested": cavity.rf_ramp_requested,
                    "cavity": str(cavity),
                }
            },
        )

        setup_cavity(cavity, parsed_args, logger)

        logger.info("Cavity setup script completed successfully")

    except KeyError as e:
        error_msg = f"Invalid cryomodule or cavity number: {e}"
        logger.error(
            error_msg,
            extra={
                "extra_data": {
                    "cryomodule": cm_name,
                    "cavity_number": cav_num,
                    "error": str(e),
                }
            },
        )
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        error_msg = f"Error during cavity setup: {e}"
        logger.exception(
            error_msg,
            extra={
                "extra_data": {
                    "cryomodule": cm_name,
                    "cavity_number": cav_num,
                    "shutdown": parsed_args.shutdown,
                }
            },
        )
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
