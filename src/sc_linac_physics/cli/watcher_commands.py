import argparse
import os
import shutil
import signal
import subprocess
import sys
from pathlib import Path

from sc_linac_physics.applications.quench_processing import quench_resetter
from sc_linac_physics.applications.sel_phase_optimizer import (
    sel_phase_optimizer,
)
from sc_linac_physics.displays.cavity_display.backend import runner
from sc_linac_physics.utils.platform_paths import get_srf_base_dir, is_macos

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


# Without tmux_launcher (a laptop, not the production servers), watchers run
# as local background processes. Each gets a log file and a pid file here.
def _has_tmux_launcher() -> bool:
    return shutil.which("tmux_launcher") is not None


def _local_dir() -> Path:
    return get_srf_base_dir() / "watchers"


def _log_path(session_name: str) -> Path:
    return _local_dir() / f"{session_name}.log"


def _pid_path(session_name: str) -> Path:
    return _local_dir() / f"{session_name}.pid"


def _read_running_pid(session_name: str, main_func) -> int | None:
    """Return the pid from the watcher's pid file if that process is ours.

    The pid must be a live process we may signal, and its command line must
    name the watcher module. A pid file left behind after a reboot can point
    at an unrelated process that reused the pid.
    """
    try:
        pid = int(_pid_path(session_name).read_text().strip())
        if pid <= 1:
            return None
        os.kill(pid, 0)
    except (FileNotFoundError, ValueError, ProcessLookupError):
        return None
    except PermissionError:
        return None
    command = subprocess.run(
        ["ps", "-o", "command=", "-p", str(pid)],
        capture_output=True,
        text=True,
    ).stdout
    if main_func.__module__ not in command:
        return None
    return pid


def local_stop(session_name: str, main_func) -> None:
    pid = _read_running_pid(session_name, main_func)
    if pid is None:
        print(f"{session_name} is not running")
    else:
        # The watcher is its own session leader, so this reaches its children.
        os.killpg(pid, signal.SIGTERM)
        print(f"Stopped {session_name} (pid {pid})")
    _pid_path(session_name).unlink(missing_ok=True)


def local_restart(session_name: str, main_func) -> None:
    local_stop(session_name, main_func)
    _local_dir().mkdir(parents=True, exist_ok=True)
    log_path = _log_path(session_name)
    with open(log_path, "ab") as log:
        proc = subprocess.Popen(
            [sys.executable, "-m", main_func.__module__],
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    _pid_path(session_name).write_text(str(proc.pid))
    print(f"Started {session_name} (pid {proc.pid}), logging to {log_path}")


def local_show(session_name: str) -> None:
    log_path = _log_path(session_name)
    if not log_path.exists():
        print(f"No log for {session_name} yet: {log_path}")
        return
    if sys.stdout.isatty():
        os.execvp("tail", ["tail", "-n", "200", "-f", str(log_path)])
    elif is_macos():
        # Launched from SRF Home there is no terminal to tail into.
        subprocess.Popen(["open", "-a", "Console", str(log_path)])
    else:
        print(f"Log for {session_name}: {log_path}")


def _show(session_name: str) -> None:
    if _has_tmux_launcher():
        _run_tmux_command(build_show_command(session_name))
    else:
        local_show(session_name)


def _restart(session_name: str) -> None:
    func = WATCHER_CONFIGS[session_name]
    if _has_tmux_launcher():
        _run_tmux_command(build_restart_command(session_name, func))
    else:
        local_restart(session_name, func)


def _stop(session_name: str) -> None:
    func = WATCHER_CONFIGS[session_name]
    if _has_tmux_launcher():
        _run_tmux_command(build_stop_command(session_name, func))
    else:
        local_stop(session_name, func)


def show_watcher():
    parser = argparse.ArgumentParser(description="Show watcher output")
    parser.add_argument("watcher", choices=WATCHER_CONFIGS.keys())
    args = parser.parse_args()

    _show(args.watcher)


def restart_watcher():
    parser = argparse.ArgumentParser(description="Restart watcher process")
    parser.add_argument("watcher", choices=WATCHER_CONFIGS.keys())
    args = parser.parse_args()

    _restart(args.watcher)


def stop_watcher():
    parser = argparse.ArgumentParser(description="Stop watcher process")
    parser.add_argument("watcher", choices=WATCHER_CONFIGS.keys())
    args = parser.parse_args()

    _stop(args.watcher)


def main():
    """Main CLI entry point for watcher management"""
    parser = argparse.ArgumentParser(
        description="Manage SC Linac watcher processes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Available watchers:
  {', '.join(WATCHER_CONFIGS.keys())}

Examples:
  %(prog)s show SC_CAV_QNCH_RESET
  %(prog)s restart SC_CAV_QNCH_RESET
  %(prog)s stop SC_CAV_QNCH_RESET
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
        _show(args.watcher)
    elif args.command == "restart":
        _restart(args.watcher)
    elif args.command == "stop":
        _stop(args.watcher)
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
