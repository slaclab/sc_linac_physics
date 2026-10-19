"""``sc-edm``: open an EDM screen from the command line.

Examples::

    sc-edm cavity 02 3 --tab 4
    sc-edm ssa H1 2
    sc-edm freqscan 02 A
    sc-edm cryo 02
    sc-edm cavity 02 3 --print

Each screen is a subcommand, built from ``utils/edm_screens.SCREENS``, so
``sc-edm --help`` lists every screen.
"""

import argparse
import shlex
import sys
from typing import List, Optional

from sc_linac_physics.utils.edm_screens import (
    SCREENS,
    ScreenLevel,
    edm_command,
    open_screen,
    resolve_tab,
    screen_path_and_macros,
)
from sc_linac_physics.utils.sc_linac.linac_utils import ALL_CRYOMODULES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sc-edm",
        description="Open an SRF EDM screen.",
        epilog="Example: sc-edm cavity 02 3 --tab 4",
    )
    subparsers = parser.add_subparsers(
        dest="screen", required=True, metavar="SCREEN"
    )

    for screen in SCREENS.values():
        sub = subparsers.add_parser(
            screen.name, help=screen.description, description=screen.path
        )
        if screen.level is not ScreenLevel.GLOBAL:
            sub.add_argument(
                "cryomodule",
                choices=ALL_CRYOMODULES,
                metavar="CM",
                help="Cryomodule, e.g. 02 or H1",
            )
        if screen.level is ScreenLevel.RACK:
            sub.add_argument("rack", choices=["A", "B"], type=str.upper)
        if screen.level is ScreenLevel.CAVITY:
            sub.add_argument(
                "cavity", type=int, choices=range(1, 9), metavar="CAV"
            )
        if screen.has_tabs:
            sub.add_argument(
                "--tab", help="SELTAB number to open on (default 0)"
            )
        sub.add_argument(
            "--print",
            action="store_true",
            dest="print_only",
            help="Print the edm command instead of running it",
        )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    screen = SCREENS[args.screen]

    tab = None
    if getattr(args, "tab", None) is not None:
        try:
            tab = resolve_tab(args.tab)
        except ValueError as e:
            parser.error(str(e))

    path, macros = screen_path_and_macros(
        screen,
        cryomodule=getattr(args, "cryomodule", None),
        rack=getattr(args, "rack", None),
        cavity=getattr(args, "cavity", None),
        tab=tab,
    )
    command = edm_command(path, macros)

    if args.print_only:
        print(shlex.join(command))
        return 0

    if "$EDM" in command[-1]:
        print(
            "sc-edm: $EDM is not set. Run this on a production machine, "
            "or use --print to see the command.",
            file=sys.stderr,
        )
        return 1

    try:
        open_screen(command)
    except FileNotFoundError:
        print("sc-edm: 'edm' is not on PATH.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
