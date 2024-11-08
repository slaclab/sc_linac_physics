import argparse

from applications.auto_setup.setup_cryomodule import SetupCryomodule
from applications.auto_setup.setup_machine import SetupMachine, SETUP_MACHINE
from utils.sc_linac.linac_utils import ALL_CRYOMODULES_NO_HL, ALL_CRYOMODULES


def setup_cryomodule(cryomodule_object: SetupCryomodule):
    if args.shutdown:
        cryomodule_object.trigger_shutdown()

    else:
        cryomodule_object.ssa_cal_requested = machine.ssa_cal_requested
        cryomodule_object.auto_tune_requested = machine.auto_tune_requested
        cryomodule_object.cav_char_requested = machine.cav_char_requested
        cryomodule_object.rf_ramp_requested = machine.rf_ramp_requested

        cryomodule_object.trigger_setup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--no_hl", "-no_hl", action="store_true", help="Exclude HLs from setup script"
    )

    parser.add_argument(
        "--shutdown", "-off", action="store_true", help="Turn off cavity and SSA"
    )

    args = parser.parse_args()
    machine: SetupMachine = SetupMachine()
    print(args)

    if args.no_hl:
        for cm_name in ALL_CRYOMODULES_NO_HL:
            cm_object: SetupCryomodule = SETUP_MACHINE.cryomodules[cm_name]
            setup_cryomodule(cm_object)

    else:
        for cm_name in ALL_CRYOMODULES:
            cm_object: SetupCryomodule = SETUP_MACHINE.cryomodules[cm_name]
            setup_cryomodule(cm_object)
