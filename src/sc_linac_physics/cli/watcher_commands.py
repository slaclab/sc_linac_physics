import argparse
import os
import sys

from sc_linac_physics.applications.quench_processing import quench_resetter
from sc_linac_physics.applications.sel_phase_optimizer import (
    sel_phase_optimizer,
)
from sc_linac_physics.displays.cavity_display.backend import runner

WATCHER_CONFIGS = {
    "SC_CAV_QNCH_RESET": quench_resetter.main,
    "SC_CAV_FAULT": runner.main,
    "SC_SEL_PHAS_OPT": sel_phase_optimizer.main,
    # Add other watchers by importing their main functions
}


def _get_xterm_prefix(session_name: str) -> str:
    """Get the xterm prefix with SSH environment"""
    return (
        f'xterm -T {session_name} -hold -e "'
        f"export TMUX_SSH_USER=laci && "
        f"export TMUX_SSH_SERVER=lcls-srv03 && "
    )


def build_show_command(session_name: str) -> str:
    """Build command to show tmux session output"""
    prefix = _get_xterm_prefix(session_name)
    return f'{prefix}tmux_launcher open {session_name}"'


def build_restart_command(session_name: str, main_func) -> str:
    """Build command to restart tmux session with a watcher"""
    prefix = _get_xterm_prefix(session_name)
    module_path = main_func.__module__
    tmux_cmd = f"tmux_launcher restart 'python -m {module_path}' {session_name}"
    return f'{prefix}{tmux_cmd}"'


def build_stop_command(session_name: str, main_func) -> str:
    """Build command to stop tmux session"""
    prefix = _get_xterm_prefix(session_name)
    module_path = main_func.__module__
    tmux_cmd = f"tmux_launcher stop {module_path} {session_name}"
    return f'{prefix}{tmux_cmd}"'


def _run_tmux_command(command: str):
    """Helper to run tmux commands"""
    os.system(command)


def show_watcher():
    parser = argparse.ArgumentParser(description="Show watcher output")
    parser.add_argument("watcher", choices=WATCHER_CONFIGS.keys())
    args = parser.parse_args()

    command = build_show_command(args.watcher)
    _run_tmux_command(command)


def restart_watcher():
    parser = argparse.ArgumentParser(description="Restart watcher process")
    parser.add_argument("watcher", choices=WATCHER_CONFIGS.keys())
    args = parser.parse_args()

    func = WATCHER_CONFIGS[args.watcher]
    command = build_restart_command(args.watcher, func)
    _run_tmux_command(command)


def stop_watcher():
    parser = argparse.ArgumentParser(description="Stop watcher process")
    parser.add_argument("watcher", choices=WATCHER_CONFIGS.keys())
    args = parser.parse_args()

    func = WATCHER_CONFIGS[args.watcher]
    command = build_stop_command(args.watcher, func)
    _run_tmux_command(command)


def main():
    """Main CLI entry point for watcher management"""
    parser = argparse.ArgumentParser(
        description="Manage SC Linac watcher processes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Available watchers:
  {', '.join(WATCHER_CONFIGS.keys())}

Examples:
  %(prog)s show quench_resetter
  %(prog)s restart quench_resetter
  %(prog)s stop quench_resetter
        """,
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Command to execute"
    )
    subparsers.required = True

    # Show command
    show_parser = subparsers.add_parser("show", help="Show tmux session output")
    show_parser.add_argument(
        "watcher",
        choices=WATCHER_CONFIGS.keys(),
        help="Name of the watcher to show",
    )

    # Restart command
    restart_parser = subparsers.add_parser(
        "restart", help="Restart watcher process"
    )
    restart_parser.add_argument(
        "watcher",
        choices=WATCHER_CONFIGS.keys(),
        help="Name of the watcher to restart",
    )

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop watcher process")
    stop_parser.add_argument(
        "watcher",
        choices=WATCHER_CONFIGS.keys(),
        help="Name of the watcher to stop",
    )

    # List command
    subparsers.add_parser("list", help="List all available watchers")

    args = parser.parse_args()

    if args.command == "show":
        command = build_show_command(args.watcher)
        _run_tmux_command(command)
    elif args.command == "restart":
        func = WATCHER_CONFIGS[args.watcher]
        command = build_restart_command(args.watcher, func)
        _run_tmux_command(command)
    elif args.command == "stop":
        func = WATCHER_CONFIGS[args.watcher]
        command = build_stop_command(args.watcher, func)
        _run_tmux_command(command)
    elif args.command == "list":
        print("Available watchers:")
        for watcher_name, func in WATCHER_CONFIGS.items():
            module_path = func.__module__
            print(f"  - {watcher_name} ({module_path})")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
