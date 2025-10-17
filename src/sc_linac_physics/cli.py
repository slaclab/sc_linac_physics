"""Command-line interface for SC Linac Physics."""

import argparse
import sys


DISPLAYS = {
    # Main displays
    "srf-home": {"launcher": "launch_srf_home", "description": "SRF home overview display"},
    "cavity": {"launcher": "launch_cavity_display", "description": "Cavity control and monitoring display"},
    "fault-decoder": {"launcher": "launch_fault_decoder", "description": "Cavity fault decoder display"},
    "fault-count": {"launcher": "launch_fault_count", "description": "Cavity fault count display"},
    # Applications
    "quench": {"launcher": "launch_quench_processing", "description": "Quench processing application"},
    "setup": {"launcher": "launch_auto_setup", "description": "Automated cavity setup"},
    "q0": {"launcher": "launch_q0_measurement", "description": "Q0 measurement application"},
    "tuning": {"launcher": "launch_tuning", "description": "Cavity tuning interface"},
    "microphonics": {"launcher": "launch_microphonics", "description": "Microphonics data acquisition and analysis interface"},
}


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SC Linac Physics Control Applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sc-linac list              List all available applications
  sc-linac srf-home          Launch SRF home display
  sc-linac cavity            Launch cavity display
  sc-linac fault-decoder     Launch fault decoder display
  sc-linac fault-count       Launch fault count display
  sc-linac tuning            Launch tuning GUI
  sc-linac quench            Launch quench processing
  sc-linac setup             Launch auto setup
  sc-linac q0                Launch Q0 measurement
        """,
    )

    display_choices = list(DISPLAYS.keys()) + ["list"]
    parser.add_argument("display", choices=display_choices, help="Display or application to launch")
    parser.add_argument("args", nargs="*", help="Additional arguments to pass to PyDM")

    args = parser.parse_args()

    if args.display == "list":
        list_displays()
    else:
        launch_display(args.display, args.args)


def list_displays():
    """List available displays and applications."""
    print("\n SC Linac Physics - Available Applications\n")
    print("=" * 70)

    print("\n DISPLAYS:")
    for name in ["srf-home", "cavity", "fault-decoder", "fault-count"]:
        if name in DISPLAYS:
            info = DISPLAYS[name]
            print(f"  {name:15} - {info['description']}")

    print("\n APPLICATIONS:")
    for name in ["quench", "setup", "q0", "tuning", "microphonics"]:
        if name in DISPLAYS:
            info = DISPLAYS[name]
            print(f"  {name:15} - {info['description']}")

    print("\n" + "=" * 70)
    print("\nUsage: sc-linac <name>")
    print("       sc-linac-<name>  (direct launcher)\n")


def launch_display(display_name: str, extra_args: list = None):
    """Launch a specific display or application.

    Parameters
    ----------
    display_name : str
        Name of the display to launch
    extra_args : list, optional
        Additional arguments for PyDM
    """
    from . import launchers

    if extra_args is None:
        extra_args = []

    display_info = DISPLAYS[display_name]
    launcher_func = getattr(launchers, display_info["launcher"])

    # Override sys.argv with extra args
    original_argv = sys.argv
    sys.argv = [sys.argv[0]] + extra_args

    try:
        launcher_func()
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    main()
