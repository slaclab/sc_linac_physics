import argparse

from applications.tuning.tune_cavity import TuneCavity
from applications.tuning.tune_rack import TuneRack
from applications.tuning.tune_stepper import TuneStepper
from utils.sc_linac.linac import Machine
from utils.sc_linac.linac_utils import (
    ALL_CRYOMODULES,
    PARK_DETUNE,
    StepperAbortError,
    StepperError,
    CavityAbortError,
    DetuneError,
    CavityHWModeError,
)

TUNE_MACHINE = Machine(
    cavity_class=TuneCavity, stepper_class=TuneStepper, rack_class=TuneRack
)


def detune_cavity(cavity: TuneCavity, args: argparse.Namespace):
    if cavity.script_is_running:
        cavity.status_message = f"{cavity} script already running"
        return
    try:
        if args.cold_landing:
            cavity.move_to_cold_landing()
        elif args.park:
            cavity.park()
    except (
        StepperAbortError,
        StepperError,
        CavityAbortError,
        DetuneError,
        CavityHWModeError,
    ) as e:
        cavity.stepper_tuner.abort_flag = False
        cavity.abort_flag = False
        # cavity.status = error
        cavity.status_message = e


if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
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
        help="Cavity number as an int",
    )

    parser.add_argument(
        "--cold_landing",
        "-cold",
        action="store_true",
        help="Tune cavity to cold landing",
    )

    parser.add_argument(
        "--park",
        "-p",
        action="store_true",
        help=f"Park cavity at {PARK_DETUNE} kHz",
    )

    parsed_args: argparse.Namespace = parser.parse_args()
    cm_name = parsed_args.cryomodule
    cav_num = parsed_args.cavity

    cav_obj: TuneCavity = TUNE_MACHINE.cryomodules[cm_name].cavities[cav_num]
    detune_cavity(cav_obj, parsed_args)
