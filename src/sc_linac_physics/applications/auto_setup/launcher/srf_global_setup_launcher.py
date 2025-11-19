import argparse
import logging
import sys

from sc_linac_physics.applications.auto_setup.backend.setup_cryomodule import (
    SetupCryomodule,
)
from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SetupMachine,
    SETUP_MACHINE,
)
from sc_linac_physics.applications.auto_setup.backend.setup_utils import (
    SETUP_LOG_DIR,
)
from sc_linac_physics.utils.logger import custom_logger
from sc_linac_physics.utils.sc_linac.linac_utils import (
    ALL_CRYOMODULES_NO_HL,
    ALL_CRYOMODULES,
)


def setup_cryomodule(
    cryomodule_object: SetupCryomodule,
    args: argparse.Namespace,
    machine: SetupMachine,
    logger: logging.Logger,
):
    """
    Setup or shutdown a single cryomodule.

    Args:
        cryomodule_object: SetupCryomodule object to operate on
        args: Parsed command-line arguments
        machine: SetupMachine object containing global settings
        logger: Logger instance
    """
    if args.shutdown:
        logger.info("Triggering shutdown for %s", cryomodule_object)
        cryomodule_object.trigger_shutdown()
    else:
        logger.debug(
            "Setting request flags for %s from machine",
            cryomodule_object,
            extra={
                "extra_data": {
                    "ssa_cal_requested": machine.ssa_cal_requested,
                    "auto_tune_requested": machine.auto_tune_requested,
                    "cav_char_requested": machine.cav_char_requested,
                    "rf_ramp_requested": machine.rf_ramp_requested,
                    "cryomodule": str(cryomodule_object),
                }
            },
        )

        cryomodule_object.ssa_cal_requested = machine.ssa_cal_requested
        cryomodule_object.auto_tune_requested = machine.auto_tune_requested
        cryomodule_object.cav_char_requested = machine.cav_char_requested
        cryomodule_object.rf_ramp_requested = machine.rf_ramp_requested

        logger.info("Triggering setup for %s", cryomodule_object)
        cryomodule_object.trigger_start()


def main():
    """Main entry point for the global (machine-wide) setup CLI."""
    parser = argparse.ArgumentParser(
        description="Setup or shutdown all cryomodules in the machine",
        epilog="Example: sc-setup-all --no_hl",
    )
    parser.add_argument(
        "--no_hl",
        "-no_hl",
        action="store_true",
        help="Exclude HLs (Harmonic Linearizer) cryomodules from setup script",
    )

    parser.add_argument(
        "--shutdown",
        "-off",
        action="store_true",
        help="Turn off all cavities and SSAs",
    )

    args = parser.parse_args()

    logger = custom_logger(
        __name__, log_dir=str(SETUP_LOG_DIR), log_filename="global_launcher"
    )

    try:
        logger.info(
            "Starting global setup script",
            extra={
                "extra_data": {
                    "exclude_hl": args.no_hl,
                    "shutdown": args.shutdown,
                    "args": str(args),
                }
            },
        )

        machine: SetupMachine = SetupMachine()

        logger.info(
            "Machine setup request flags",
            extra={
                "extra_data": {
                    "ssa_cal_requested": machine.ssa_cal_requested,
                    "auto_tune_requested": machine.auto_tune_requested,
                    "cav_char_requested": machine.cav_char_requested,
                    "rf_ramp_requested": machine.rf_ramp_requested,
                }
            },
        )

        if args.no_hl:
            cryomodule_list = ALL_CRYOMODULES_NO_HL
            logger.info(
                "Setting up %d cryomodules (excluding HL)", len(cryomodule_list)
            )
        else:
            cryomodule_list = ALL_CRYOMODULES
            logger.info("Setting up %d cryomodules (all)", len(cryomodule_list))

        for idx, cm_name in enumerate(cryomodule_list, 1):
            cm_object: SetupCryomodule = SETUP_MACHINE.cryomodules[cm_name]
            logger.info(
                "Processing cryomodule %d/%d: %s",
                idx,
                len(cryomodule_list),
                cm_name,
            )
            setup_cryomodule(cm_object, args, machine, logger)

        logger.info(
            "Global setup script completed successfully",
            extra={
                "extra_data": {
                    "cryomodules_processed": len(cryomodule_list),
                    "exclude_hl": args.no_hl,
                    "shutdown": args.shutdown,
                }
            },
        )

    except KeyError as e:
        error_msg = f"Invalid cryomodule name: {e}"
        logger.error(
            error_msg,
            extra={"extra_data": {"error": str(e), "exclude_hl": args.no_hl}},
        )
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)

    except Exception as e:
        error_msg = f"Error during global setup: {e}"
        logger.exception(
            error_msg,
            extra={
                "extra_data": {
                    "exclude_hl": args.no_hl,
                    "shutdown": args.shutdown,
                }
            },
        )
        print(f"Error: {error_msg}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
