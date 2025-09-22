import argparse

# noqa: E402
from sc_linac_physics.applications.auto_setup.backend.setup_cavity import (
    SetupCavity,
)
# noqa: E402
from sc_linac_physics.applications.auto_setup.backend.setup_machine import (
    SETUP_MACHINE,
)
# noqa: E402
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES


def setup_cavity(cavity: SetupCavity, args: argparse.Namespace):
    if cavity.script_is_running:
        cavity.status_message = f"{cavity} script already running"
        return

    if args.shutdown:
        cavity.shut_down()

    else:
        cavity.setup()


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
        "--shutdown", "-off", action="store_true", help="Turn off cavity and SSA"
    )

    parsed_args: argparse.Namespace = parser.parse_args()
    cm_name = parsed_args.cryomodule
    cav_num = parsed_args.cavity

    cavity_obj: SetupCavity = SETUP_MACHINE.cryomodules[cm_name].cavities[cav_num]

    setup_cavity(cavity_obj, parsed_args)
