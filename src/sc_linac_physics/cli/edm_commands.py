"""``sc-edm``: open an EDM screen from the command line.

Usage examples are in ``docs/displays/edm_screens.md``.

Each screen is a subcommand, built from ``utils/edm_screens.SCREENS``, so
``sc-edm --help`` lists every screen.
"""

import argparse
import shlex
import sys
from typing import List, Optional

from sc_linac_physics.utils.edm_screens import (
    CAVITY_TABS,
    CHARACTERIZATION_TABS,
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
                "--tab",
                help="Tab to open on, by name or SELTAB number (default 0): "
                + ", ".join(CAVITY_TABS),
            )
            sub.add_argument(
                "--char",
                help="Characterization sub-tab, by name or SELCHAR number "
                "(default 3): " + ", ".join(CHARACTERIZATION_TABS),
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

    tab = char = None
    try:
        if getattr(args, "tab", None) is not None:
            tab = resolve_tab(args.tab, CAVITY_TABS)
        if getattr(args, "char", None) is not None:
            char = resolve_tab(args.char, CHARACTERIZATION_TABS)
    except ValueError as e:
        parser.error(str(e))

    path, macros = screen_path_and_macros(
        screen,
        cryomodule=getattr(args, "cryomodule", None),
        rack=getattr(args, "rack", None),
        cavity=getattr(args, "cavity", None),
        tab=tab,
        char=char,
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
