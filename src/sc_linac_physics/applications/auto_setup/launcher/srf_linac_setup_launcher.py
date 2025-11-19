import argparse
import logging
import sys
from time import sleep

from sc_linac_physics.applications.auto_setup.backend.setup_cryomodule import (
    SetupCryomodule,
)
from sc_linac_physics.applications.auto_setup.backend.setup_linac import (
    SetupLinac,
)
from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SETUP_MACHINE,
)
from sc_linac_physics.applications.auto_setup.backend.setup_utils import (
    SETUP_LOG_DIR,
)
from sc_linac_physics.utils.logger import custom_logger
from sc_linac_physics.utils.sc_linac.linac_utils import LINAC_CM_DICT


def setup_cryomodule(
    cryomodule_object: SetupCryomodule,
    args: argparse.Namespace,
    logger: logging.Logger,
):
    """
    Setup or shutdown a single cryomodule within a linac.

    Args:
        cryomodule_object: SetupCryomodule object to operate on
        args: Parsed command-line arguments
        logger: Logger instance
    """
    if args.shutdown:
        logger.info("Triggering shutdown for %s", cryomodule_object)
        cryomodule_object.trigger_shutdown()
    else:
        linac = cryomodule_object.linac

        logger.debug(
            "Setting request flags for %s from linac",
            cryomodule_object,
            extra={
                "extra_data": {
                    "ssa_cal_requested": linac.ssa_cal_requested,
                    "auto_tune_requested": linac.auto_tune_requested,
                    "cav_char_requested": linac.cav_char_requested,
                    "rf_ramp_requested": linac.rf_ramp_requested,
                    "cryomodule": str(cryomodule_object),
                }
            },
        )

        cryomodule_object.ssa_cal_requested = linac.ssa_cal_requested
        cryomodule_object.auto_tune_requested = linac.auto_tune_requested
        cryomodule_object.cav_char_requested = linac.cav_char_requested
        cryomodule_object.rf_ramp_requested = linac.rf_ramp_requested

        logger.info("Triggering setup for %s", cryomodule_object)
        cryomodule_object.trigger_start()


def main():
    """Main entry point for the linac setup CLI."""
    parser = argparse.ArgumentParser(
        description="Setup or shutdown all cryomodules in a specific linac",
        epilog="Example: sc-setup-linac -l 0",
    )
    parser.add_argument(
        "--linac",
        "-l",
        required=True,
        choices=range(4),
        type=int,
        help="Linac number as an int (0-3)",
    )

    parser.add_argument(
        "--shutdown",
        "-off",
        action="store_true",
        help="Turn off all cavities and SSAs in the linac",
    )

    args = parser.parse_args()
    linac_number: int = args.linac

    logger = custom_logger(
        __name__, log_dir=str(SETUP_LOG_DIR), log_filename="linac_launcher"
    )

    try:
        logger.info(
            "Starting linac setup script",
            extra={
                "extra_data": {
                    "linac_number": linac_number,
                    "shutdown": args.shutdown,
                    "args": str(args),
                }
            },
        )

        linac: SetupLinac = SETUP_MACHINE.linacs[linac_number]

        logger.info(
            "Linac setup request flags",
            extra={
                "extra_data": {
                    "ssa_cal_requested": linac.ssa_cal_requested,
                    "auto_tune_requested": linac.auto_tune_requested,
                    "cav_char_requested": linac.cav_char_requested,
                    "rf_ramp_requested": linac.rf_ramp_requested,
                    "linac_number": linac_number,
                }
            },
        )

        cryomodule_list = LINAC_CM_DICT[linac_number]
        logger.info(
            "Setting up %d cryomodule(s) in Linac %d",
            len(cryomodule_list),
            linac_number,
        )

        for idx, cm_name in enumerate(cryomodule_list, 1):
            cm_object: SetupCryomodule = SETUP_MACHINE.cryomodules[cm_name]
            logger.info(
                "Processing cryomodule %d/%d: %s",
                idx,
                len(cryomodule_list),
                cm_name,
            )
            setup_cryomodule(cm_object, args, logger)
            sleep(0.5)

        logger.info(
            "Linac setup script completed successfully",
            extra={
                "extra_data": {
                    "linac_number": linac_number,
                    "cryomodules_processed": len(cryomodule_list),
                    "shutdown": args.shutdown,
                }
            },
        )

    except KeyError as e:
        error_msg = f"Invalid linac number or cryomodule: {e}"
        logger.error(
            error_msg,
            extra={
                "extra_data": {"linac_number": linac_number, "error": str(e)}
            },
        )
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        error_msg = f"Error during linac setup: {e}"
        logger.exception(
            error_msg,
            extra={
                "extra_data": {
                    "linac_number": linac_number,
                    "shutdown": args.shutdown,
                }
            },
        )
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
