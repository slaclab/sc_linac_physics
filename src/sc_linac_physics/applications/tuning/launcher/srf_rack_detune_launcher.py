import argparse
from time import sleep

from sc_linac_physics.applications.tuning.tune_cavity import TuneCavity
from sc_linac_physics.applications.tuning.tune_rack import TuneRack
from sc_linac_physics.applications.tuning.tuning_gui import TUNE_MACHINE
from sc_linac_physics.utils.sc_linac.cryomodule import Cryomodule
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES


def detune_cavity(cavity_object: TuneCavity):
    if cavity_object.script_is_running:
        cavity_object.status_message = f"{cavity_object} script already running"
        return

    cavity_object.trigger_start()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
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
        choices=["A", "B"],
        required=True,
        help="Rack name as a string",
    )

    parsed_args = parser.parse_args()

    cm_name = parsed_args.cryomodule
    cm_object: Cryomodule = TUNE_MACHINE.cryomodules[cm_name]
    rack_obj: TuneRack = (
        cm_object.rack_a if parsed_args.rack == "A" else cm_object.rack_b
    )

    for cavity in rack_obj.cavities.values():
        detune_cavity(cavity)
        sleep(0.1)
