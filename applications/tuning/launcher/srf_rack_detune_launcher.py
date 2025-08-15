import argparse

from applications.tuning.launcher.srf_cavity_detune_launcher import TUNE_MACHINE
from applications.tuning.tune_rack import TuneRack
from utils.sc_linac.linac_utils import ALL_CRYOMODULES, PARK_DETUNE
from utils.sc_linac.rack import Rack


def detune_rack(rack: TuneRack, args: argparse.Namespace):
    if args.cold_landing:
        rack.move_to_cold_landing()
    elif args.park:
        rack.park()


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
        "--rack",
        "-r",
        required=True,
        choices=["A", "B"],
        type=str.upper,
        help="Cavity number as an int",
    )

    parser.add_argument(
        "--cold_landing",
        "-cold",
        action="store_true",
        help="Tune cavities to cold landing",
    )

    parser.add_argument(
        "--park",
        "-p",
        action="store_true",
        help=f"Park cavities at {PARK_DETUNE} kHz",
    )

    parsed_args: argparse.Namespace = parser.parse_args()
    cm_name = parsed_args.cryomodule
    rack_name = parsed_args.rack

    cryomodule = TUNE_MACHINE.cryomodules[cm_name]
    rack_obj: Rack = cryomodule.rack_a if rack_name == "A" else cryomodule.rack_b
    detune_rack(rack_obj, parsed_args)
