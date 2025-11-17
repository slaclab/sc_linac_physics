import argparse
import logging
import sys
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
from sc_linac_physics.applications.auto_setup.backend.setup_utils import (
    SETUP_LOG_DIR,
)
from sc_linac_physics.utils.logger import custom_logger
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES


def setup_cavity(
    cavity_object: SetupCavity, args: argparse.Namespace, logger: logging.Logger
):
    """
    Setup or shutdown a single cavity within a cryomodule.

    Args:
        cavity_object: SetupCavity object to operate on
        args: Parsed command-line arguments
        logger: Logger instance
    """
    if cavity_object.script_is_running:
        cavity_object.set_status_message(
            f"{cavity_object} script already running", logging.WARNING
        )
        logger.warning("%s script already running", cavity_object)
        return

    if args.shutdown:
        logger.info("Triggering shutdown for %s", cavity_object)
        cavity_object.trigger_shutdown()
    else:
        cm: SetupCryomodule = cavity_object.cryomodule

        logger.debug(
            "Setting request flags for %s from cryomodule",
            cavity_object,
            extra={
                "extra_data": {
                    "ssa_cal_requested": cm.ssa_cal_requested,
                    "auto_tune_requested": cm.auto_tune_requested,
                    "cav_char_requested": cm.cav_char_requested,
                    "rf_ramp_requested": cm.rf_ramp_requested,
                    "cavity": str(cavity_object),
                }
            },
        )

        cavity_object.ssa_cal_requested = cm.ssa_cal_requested
        cavity_object.auto_tune_requested = cm.auto_tune_requested
        cavity_object.cav_char_requested = cm.cav_char_requested
        cavity_object.rf_ramp_requested = cm.rf_ramp_requested

        logger.info("Triggering setup for %s", cavity_object)
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

    logger = custom_logger(
        __name__, log_dir=str(SETUP_LOG_DIR), log_filename="cryomodule_launcher"
    )

    try:
        logger.info(
            "Starting cryomodule setup script",
            extra={
                "extra_data": {
                    "cryomodule": cm_name,
                    "shutdown": parsed_args.shutdown,
                }
            },
        )

        cm: SetupCryomodule = SETUP_MACHINE.cryomodules[cm_name]

        logger.info(
            "Cryomodule setup request flags",
            extra={
                "extra_data": {
                    "ssa_cal_requested": cm.ssa_cal_requested,
                    "auto_tune_requested": cm.auto_tune_requested,
                    "cav_char_requested": cm.cav_char_requested,
                    "rf_ramp_requested": cm.rf_ramp_requested,
                    "cryomodule": cm_name,
                }
            },
        )

        cavity_count = len(cm.cavities)
        logger.info("Processing %d cavities in %s", cavity_count, cm_name)

        for idx, cavity in enumerate(cm.cavities.values(), 1):
            logger.info(
                "Processing cavity %d/%d: %s", idx, cavity_count, cavity
            )
            setup_cavity(cavity, parsed_args, logger)
            sleep(0.1)

        logger.info(
            "Cryomodule setup script completed successfully",
            extra={
                "extra_data": {
                    "cryomodule": cm_name,
                    "cavities_processed": cavity_count,
                    "shutdown": parsed_args.shutdown,
                }
            },
        )

    except KeyError as e:
        error_msg = f"Invalid cryomodule name: {e}"
        logger.error(
            error_msg,
            extra={"extra_data": {"cryomodule": cm_name, "error": str(e)}},
        )
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        error_msg = f"Error during cryomodule setup: {e}"
        logger.exception(
            error_msg,
            extra={
                "extra_data": {
                    "cryomodule": cm_name,
                    "shutdown": parsed_args.shutdown,
                }
            },
        )
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
