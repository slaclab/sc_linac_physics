import argparse

from sc_linac_physics.applications.tuning.tune_cavity import TuneCavity
from sc_linac_physics.applications.tuning.tuning_gui import TUNE_MACHINE
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES


def detune_cavity(cavity: TuneCavity, args: argparse.Namespace):
    if cavity.script_is_running:
        cavity.status_message = f"{cavity} script already running"
        return

    cavity.move_to_cold_landing()


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

    parsed_args: argparse.Namespace = parser.parse_args()
    cm_name = parsed_args.cryomodule
    cav_num = parsed_args.cavity

    cavity_obj: TuneCavity = TUNE_MACHINE.cryomodules[cm_name].cavities[cav_num]

    detune_cavity(cavity_obj, parsed_args)
