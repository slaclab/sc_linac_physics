import argparse

from applications.auto_setup.setup_cavity import SetupCavity
from setup_linac import SETUP_MACHINE
from utils.sc_linac.linac_utils import ALL_CRYOMODULES


def main():
    global cavity_object

    if cavity_object.script_is_running:
        cavity_object.status_message = f"{cavity_object} script already running"
        return

    if args.shutdown:
        cavity_object.shut_down()

    else:
        cavity_object.setup()


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
        "--cavity",
        "-cav",
        required=True,
        choices=range(1, 9),
        type=int,
        help="Cavity number as an int",
    )
    parser.add_argument(
        "--shutdown", "-off", action="store_true", help="Turn off cavity and SSA"
    )

    args = parser.parse_args()
    print(args)
    cm_name = args.cryomodule
    cav_num = args.cavity

    cavity_object: SetupCavity = SETUP_MACHINE.cryomodules[cm_name].cavities[cav_num]

    main()
