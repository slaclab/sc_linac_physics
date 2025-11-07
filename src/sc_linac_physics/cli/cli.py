"""Command-line interface for SC Linac Physics."""

import argparse
import inspect
import sys
from dataclasses import dataclass
from typing import Callable, List

from sc_linac_physics.cli import launchers


@dataclass
class DisplayInfo:
    """Information about a display or application."""

    name: str
    launcher: Callable
    description: str
    category: str  # "display" or "application"


def _extract_description_from_docstring(func: Callable) -> str:
    """Extract the first line of a function's docstring."""
    if func.__doc__:
        # Get first non-empty line
        lines = [line.strip() for line in func.__doc__.strip().split("\n")]
        return lines[0] if lines else "No description available"
    return "No description available"


def _get_display_name(func_name: str) -> str:
    """Convert function name to display name.

    Example: launch_srf_home -> srf-home
    """
    if func_name.startswith("launch_"):
        name = func_name[7:]  # Remove 'launch_' prefix
        return name.replace("_", "-")
    return func_name


def _get_category(func: Callable) -> str:
    """Get the category from the function's decorator attribute."""
    # Check if function has the _launcher_category attribute set by decorator
    if hasattr(func, "_launcher_category"):
        return func._launcher_category

    # Default to application if not decorated
    return "application"


def _discover_launchers():
    """Automatically discover all launcher functions from launchers module."""
    display_list = []

    # Get all functions from launchers module
    for name, obj in inspect.getmembers(launchers, inspect.isfunction):
        # Only include functions that start with 'launch_'
        # Exclude the base launch_python_display function
        if name.startswith("launch_") and name != "launch_python_display":
            display_name = _get_display_name(name)
            description = _extract_description_from_docstring(obj)
            category = _get_category(obj)

            display_list.append(
                DisplayInfo(
                    name=display_name,
                    launcher=obj,
                    description=description,
                    category=category,
                )
            )

    return display_list


# Automatically discover all launchers
DISPLAY_LIST: List[DisplayInfo] = _discover_launchers()

# Create lookup dictionary for easy access
DISPLAYS = {display.name: display for display in DISPLAY_LIST}


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
  sc-linac microphonics      Launch microphonics GUI
        """,
    )

    display_choices = list(DISPLAYS.keys()) + ["list"]
    parser.add_argument(
        "display",
        choices=display_choices,
        help="Display or application to launch",
    )
    parser.add_argument(
        "args", nargs="*", help="Additional arguments to pass to PyDM"
    )

    args = parser.parse_args()

    if args.display == "list":
        list_displays()
    else:
        launch_display(args.display, args.args)


def list_displays():
    """List available displays and applications."""
    print("\n SC Linac Physics - Available Applications\n")
    print("=" * 70)

    # Calculate the maximum name length for better formatting
    max_name_length = (
        max(len(display.name) for display in DISPLAY_LIST)
        if DISPLAY_LIST
        else 15
    )
    # Add some padding
    column_width = max_name_length + 2

    print("\n DISPLAYS:")
    for display in sorted(DISPLAY_LIST, key=lambda x: x.name):
        if display.category == "display":
            print(f"  {display.name:<{column_width}} - {display.description}")

    print("\n APPLICATIONS:")
    for display in sorted(DISPLAY_LIST, key=lambda x: x.name):
        if display.category == "application":
            print(f"  {display.name:<{column_width}} - {display.description}")

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
    if extra_args is None:
        extra_args = []

    display_info = DISPLAYS[display_name]
    launcher_func = display_info.launcher

    # Override sys.argv with extra args
    original_argv = sys.argv
    sys.argv = [sys.argv[0]] + extra_args

    try:
        launcher_func()
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    main()
