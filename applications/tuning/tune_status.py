from csv import DictWriter

from lcls_tools.superconducting.sc_linac_utils import ALL_CRYOMODULES

from applications.tuning.tune_cavity import TuneCavity
from applications.tuning.tune_stepper import TuneStepper
from utils.sc_linac.linac import Machine

CM_KEY = "Cryomodule"
CAV_KEY = "Cavity"
CONFIG_KEY = "Tune Config"
STEPS_KEY = "Steps to Cold Landing"
DF_COLD_KEY = "DF Cold"
HW_MODE_KEY = "HW Mode"

PARK_MACHINE = Machine(cavity_class=TuneCavity, stepper_class=TuneStepper)

with open("cavity_status.csv", "w", newline="") as csvfile:
    fieldnames = [CM_KEY, CAV_KEY, CONFIG_KEY, STEPS_KEY, DF_COLD_KEY, HW_MODE_KEY]
    writer = DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()

    for cm_name in ALL_CRYOMODULES:
        cm_object = PARK_MACHINE.cryomodules[cm_name]
        for cavity_number, cavity in cm_object.cavities.items():
            writer.writerow(
                {
                    CM_KEY: cm_object.name,
                    CAV_KEY: cavity_number,
                    CONFIG_KEY: cavity.tune_config_pv_obj.get(as_string=True),
                    DF_COLD_KEY: int(cavity.df_cold_pv_obj.get()),
                    STEPS_KEY: cavity.stepper_tuner.steps_cold_landing_pv_obj.get(),
                    HW_MODE_KEY: cavity.hw_mode_str,
                }
            )
