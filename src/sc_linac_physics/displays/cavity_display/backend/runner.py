"""
Cavity fault monitoring service.

Continuously monitors all SC linac cavities for fault conditions and updates
a heartbeat PV to indicate service health.
"""

import signal
import sys
from datetime import datetime
from time import sleep, time
from typing import List, Optional

from sc_linac_physics.displays.cavity_display.backend.backend_cavity import (
    BackendCavity,
)
from sc_linac_physics.displays.cavity_display.backend.backend_machine import (
    BackendMachine,
)
from sc_linac_physics.displays.cavity_display.utils.utils import (
    DEBUG,
    BACKEND_SLEEP_TIME,
    cavity_fault_logger,
)
from sc_linac_physics.utils.epics import (
    PV,
    PVConnectionError,
    PVGetError,
    PVPutError,
)

# Global flag to track initialization progress
_initialization_in_progress = False
_cavity_init_count = 0
_last_progress_time = 0
SLOW_CAVITY_THRESHOLD_SEC = 0.1


def _signal_handler_during_init(signum, frame):
    """Handle Ctrl+C during initialization."""

    if _initialization_in_progress:
        print("\n\n" + "=" * 70)
        print("Initialization interrupted by user")
        print("Cleaning up and exiting...")
        print("=" * 70 + "\n")
        cavity_fault_logger.info("Initialization interrupted by user")
        sys.exit(0)
    else:
        # Re-raise to let normal handler catch it
        raise KeyboardInterrupt()


def track_cavity_init():
    """Callback to track cavity initialization progress."""
    global _cavity_init_count, _last_progress_time

    _cavity_init_count += 1
    current_time = time()

    # Update progress every second or every 10 cavities
    if (_cavity_init_count % 10 == 0) or (
        current_time - _last_progress_time >= 1.0
    ):
        # Simple progress indicator (estimated 296 total cavities)
        estimated_total = 296
        percent = (_cavity_init_count / estimated_total) * 100

        # Create a simple progress bar
        bar_length = 40
        filled = int(bar_length * _cavity_init_count / estimated_total)
        bar = "█" * filled + "░" * (bar_length - filled)

        print(
            f"\r  [{bar}] {percent:5.1f}% | "
            f"Cavities: {_cavity_init_count:>3}/{estimated_total} | "
            f"Avg: {(current_time - _last_progress_time) / 10:.2f}s/cavity",
            end="",
            flush=True,
        )

        _last_progress_time = current_time


class Runner:
    """
    Monitors and checks faults for all backend cavities.

    Continuously polls all cavities for fault conditions and updates a heartbeat PV
    to indicate the service is running. The heartbeat PV can be monitored by external
    systems to verify the fault checker is alive.

    Attributes:
        watcher_pv_name: PV name for heartbeat monitoring
        backend_cavities: List of all cavity objects to monitor
    """

    def __init__(self, lazy_fault_pvs: bool = False):
        """
        Initialize the Runner.

        Args:
            lazy_fault_pvs: If True, delays initialization of fault PVs until first access.
                          This can speed up startup but may cause delays on first fault check.
        """
        global _initialization_in_progress, _cavity_init_count, _last_progress_time

        init_start = time()

        self.watcher_pv_name = "PHYS:SYS0:1:SC_CAV_FAULT_HEARTBEAT"
        self._watcher_pv_obj: Optional[PV] = None
        self._running = False
        self._heartbeat_failures = 0
        self._max_heartbeat_failures = 10
        self._first_check = True

        cavity_fault_logger.info(
            "Initializing cavity fault runner",
            extra={
                "extra_data": {
                    "lazy_fault_pvs": lazy_fault_pvs,
                    "debug_mode": DEBUG,
                    "sleep_time_sec": BACKEND_SLEEP_TIME,
                    "heartbeat_pv": self.watcher_pv_name,
                }
            },
        )

        # Print initialization message
        if not lazy_fault_pvs:
            print(f"\n{'='*70}")
            print("Initializing Cavity Fault Runner")
            print("Connecting to ~17,000 EPICS PVs (sequential initialization)")
            print("Expected duration: ~2-5 minutes")
            print("Press Ctrl+C to cancel initialization")
            print(f"{'='*70}\n")

        # Initialize backend machine and cavities
        machine_start = time()
        _initialization_in_progress = True
        _cavity_init_count = 0
        _last_progress_time = time()

        # Patch the BackendCavity __init__ to call our progress tracker
        original_init = BackendCavity.__init__

        def patched_init(self, *args, **kwargs):
            result = original_init(self, *args, **kwargs)
            if not lazy_fault_pvs:
                track_cavity_init()
            return result

        BackendCavity.__init__ = patched_init

        try:
            backend_machine = BackendMachine(lazy_fault_pvs=lazy_fault_pvs)
            machine_creation_duration = time() - machine_start

            iterator_start = time()
            self.backend_cavities: List[BackendCavity] = list(
                backend_machine.all_iterator
            )
            iterator_duration = time() - iterator_start

            total_machine_duration = time() - machine_start

            # Count total PVs initialized
            total_fault_pvs = sum(
                len(cav.faults) for cav in self.backend_cavities
            )
            total_pvs = total_fault_pvs + (len(self.backend_cavities) * 3)

            # Clear progress line and print completion
            if not lazy_fault_pvs:
                print()  # New line after progress bar

            cavity_fault_logger.info(
                "Backend cavities initialized successfully",
                extra={
                    "extra_data": {
                        "cavity_count": len(self.backend_cavities),
                        "fault_pv_count": total_fault_pvs,
                        "total_pv_count": total_pvs,
                        "lazy_mode": lazy_fault_pvs,
                        "machine_creation_sec": round(
                            machine_creation_duration, 3
                        ),
                        "iterator_sec": round(iterator_duration, 3),
                        "total_duration_sec": round(total_machine_duration, 3),
                    }
                },
            )

            # Print completion message
            if not lazy_fault_pvs:
                print(f"\n{'='*70}")
                print("✓ Initialization complete!")
                print(f"  Cavities: {len(self.backend_cavities)}")
                print(f"  Total PVs: {total_pvs:,}")
                print(
                    f"  Duration: {total_machine_duration / 60:.2f} minutes ({total_machine_duration:.1f} seconds)"
                )
                print(
                    f"  Average: {total_machine_duration / len(self.backend_cavities):.2f} seconds per cavity"
                )
                print(
                    f"  Average: {total_machine_duration / total_pvs * 1000:.1f} ms per PV"
                )
                print(f"{'='*70}\n")

        except KeyboardInterrupt:
            print("\n\n" + "=" * 70)
            print("Initialization cancelled by user")
            print("=" * 70 + "\n")
            cavity_fault_logger.info(
                "Initialization cancelled during BackendMachine creation"
            )
            raise
        except Exception as e:
            cavity_fault_logger.critical(
                "Failed to initialize backend cavities",
                extra={
                    "extra_data": {
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "duration_sec": round(time() - machine_start, 3),
                    }
                },
                exc_info=True,
            )
            raise
        finally:
            _initialization_in_progress = False
            # Restore original __init__
            BackendCavity.__init__ = original_init

        total_init_duration = time() - init_start
        cavity_fault_logger.info(
            "Runner initialization complete",
            extra={
                "extra_data": {
                    "total_duration_sec": round(total_init_duration, 3),
                    "lazy_mode": lazy_fault_pvs,
                    "ready_to_run": True,
                }
            },
        )

    @property
    def watcher_pv_obj(self) -> PV:
        """
        Lazy initialization of watcher PV object.

        Returns:
            PV: Connected watcher PV object

        Raises:
            PVConnectionError: If PV cannot be connected
        """
        if not self._watcher_pv_obj:
            start = time()
            cavity_fault_logger.debug(
                "Connecting to watcher PV",
                extra={"extra_data": {"pv_name": self.watcher_pv_name}},
            )
            try:
                self._watcher_pv_obj = PV(
                    self.watcher_pv_name,
                    connection_timeout=10.0,
                    require_connection=True,
                )
                duration = time() - start
                cavity_fault_logger.info(
                    "Watcher PV connected successfully",
                    extra={
                        "extra_data": {
                            "pv_name": self.watcher_pv_name,
                            "duration_sec": round(duration, 3),
                        }
                    },
                )
            except PVConnectionError as e:
                duration = time() - start
                cavity_fault_logger.error(
                    "Failed to connect to watcher PV",
                    extra={
                        "extra_data": {
                            "pv_name": self.watcher_pv_name,
                            "error": str(e),
                            "duration_sec": round(duration, 3),
                        }
                    },
                    exc_info=True,
                )
                raise
        return self._watcher_pv_obj

    def check_faults(self) -> None:  # noqa: C901
        """Check faults for all cavities and update heartbeat."""
        start = time()
        failed_cavities = []
        exception_summary = {}
        slow_cavities = []

        for i, cavity in enumerate(self.backend_cavities):
            cavity_start = time()
            try:
                cavity.run_through_faults()

                # Track slow cavity checks
                cavity_duration = time() - cavity_start
                if cavity_duration > SLOW_CAVITY_THRESHOLD_SEC:
                    slow_cavities.append(
                        (str(cavity), round(cavity_duration, 3))
                    )

                # Progress bar on first check (updates every 10 cavities)
                if self._first_check and (i + 1) % 10 == 0:
                    elapsed = time() - start
                    percent = (i + 1) / len(self.backend_cavities) * 100

                    # Console progress bar
                    bar_length = 40
                    filled = int(
                        bar_length * (i + 1) / len(self.backend_cavities)
                    )
                    bar = "█" * filled + "░" * (bar_length - filled)
                    print(
                        f"\r  First check: [{bar}] {percent:5.1f}% | "
                        f"Cavities: {i + 1:>3}/{len(self.backend_cavities)} | "
                        f"Avg: {elapsed / (i + 1) * 1000:.1f}ms/cavity",
                        end="",
                        flush=True,
                    )

            except Exception as e:
                error_type = type(e).__name__
                exception_summary[error_type] = (
                    exception_summary.get(error_type, 0) + 1
                )
                cavity_fault_logger.error(
                    "Error checking faults for cavity",
                    extra={
                        "extra_data": {
                            "cavity": str(cavity),
                            "cavity_index": i,
                            "error": str(e),
                            "error_type": error_type,
                        }
                    },
                    exc_info=DEBUG,
                )
                failed_cavities.append(cavity)

        # Clear the progress bar after first check completes
        if self._first_check:
            print()  # New line after progress bar

        # Log summary if there were failures
        if failed_cavities:
            successful_count = len(self.backend_cavities) - len(failed_cavities)
            cavity_fault_logger.warning(
                "Fault check cycle had failures",
                extra={
                    "extra_data": {
                        "failed_count": len(failed_cavities),
                        "successful_count": successful_count,
                        "total_count": len(self.backend_cavities),
                        "success_rate_pct": round(
                            successful_count / len(self.backend_cavities) * 100,
                            1,
                        ),
                        "exception_types": exception_summary,
                    }
                },
            )

        # Calculate cycle duration
        delta = time() - start

        # Build log data
        log_data = {
            "duration_sec": round(delta, 3),
            "cavities_checked": len(self.backend_cavities)
            - len(failed_cavities),
            "cavities_failed": len(failed_cavities),
            "avg_per_cavity_ms": round(
                delta / len(self.backend_cavities) * 1000, 1
            ),
            "first_check": self._first_check,
        }

        # Add debug-specific timing info
        if DEBUG:
            log_data["target_sec"] = BACKEND_SLEEP_TIME

        # Add slow cavity info
        if self._first_check and slow_cavities:
            log_data["slow_cavities_count"] = len(slow_cavities)
            log_data["slowest_10"] = sorted(
                slow_cavities, key=lambda x: x[1], reverse=True
            )[:10]
        elif len(slow_cavities) > 10:
            log_data["slow_cavities_count"] = len(slow_cavities)

        # Log with appropriate level
        if self._first_check:
            cavity_fault_logger.info(
                "First fault check cycle completed",
                extra={"extra_data": log_data},
            )
            self._first_check = False
        elif DEBUG:
            cavity_fault_logger.debug(
                "Fault check cycle completed", extra={"extra_data": log_data}
            )
        elif delta > BACKEND_SLEEP_TIME * 1.5:
            cavity_fault_logger.warning(
                "Fault check significantly exceeded target cycle time",
                extra={"extra_data": log_data},
            )

        # Sleep only in debug mode to throttle checks
        if DEBUG:
            sleep_time = max(0.0, BACKEND_SLEEP_TIME - delta)
            if sleep_time > 0:
                sleep(sleep_time)

        # Update heartbeat
        self._update_heartbeat()

    def _update_heartbeat(self) -> None:
        """
        Update the watcher PV heartbeat counter.

        Tracks consecutive failures and stops the runner if too many failures occur,
        as this likely indicates a systemic problem.
        """
        try:
            current_value = self.watcher_pv_obj.get(timeout=2.0)
            new_value = current_value + 1
            self.watcher_pv_obj.put(new_value, timeout=2.0)

            # Reset failure counter on success
            if self._heartbeat_failures > 0:
                cavity_fault_logger.info(
                    "Heartbeat recovered after failures",
                    extra={
                        "extra_data": {
                            "previous_failures": self._heartbeat_failures,
                            "heartbeat_value": new_value,
                        }
                    },
                )
                self._heartbeat_failures = 0

            # Periodic milestone logging
            if DEBUG and new_value % 100 == 0:
                cavity_fault_logger.debug(
                    "Heartbeat milestone",
                    extra={"extra_data": {"heartbeat_count": new_value}},
                )

        except (PVConnectionError, PVGetError, PVPutError) as e:
            self._heartbeat_failures += 1
            cavity_fault_logger.error(
                "Heartbeat update failed",
                extra={
                    "extra_data": {
                        "pv_name": self.watcher_pv_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "consecutive_failures": self._heartbeat_failures,
                        "max_allowed": self._max_heartbeat_failures,
                    }
                },
                exc_info=DEBUG,
            )

            if self._heartbeat_failures >= self._max_heartbeat_failures:
                cavity_fault_logger.critical(
                    "Too many consecutive heartbeat failures, stopping runner",
                    extra={
                        "extra_data": {
                            "failures": self._heartbeat_failures,
                            "threshold": self._max_heartbeat_failures,
                        }
                    },
                )
                self.stop()

        except Exception as e:
            self._heartbeat_failures += 1
            cavity_fault_logger.error(
                "Unexpected error updating heartbeat",
                extra={
                    "extra_data": {
                        "pv_name": self.watcher_pv_name,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "consecutive_failures": self._heartbeat_failures,
                    }
                },
                exc_info=True,
            )

            if self._heartbeat_failures >= self._max_heartbeat_failures:
                cavity_fault_logger.critical(
                    "Too many heartbeat failures, stopping"
                )
                self.stop()

    def run(self) -> None:
        """
        Run the fault checker continuously.

        Initializes the heartbeat counter and runs the check loop until stopped
        via keyboard interrupt, signal, or critical error. Logs periodic status
        updates for monitoring.
        """
        cavity_fault_logger.info("Starting fault checker service")
        print(
            f"\nFault checker service started. Monitoring {len(self.backend_cavities)} cavities..."
        )
        print("Press Ctrl+C to stop.\n")

        self._running = True
        service_start_time = datetime.now()

        # Initialize heartbeat
        heartbeat_init_start = time()
        try:
            self.watcher_pv_obj.put(0, timeout=10.0)
            heartbeat_init_duration = time() - heartbeat_init_start
            cavity_fault_logger.info(
                "Heartbeat initialized",
                extra={
                    "extra_data": {
                        "pv_name": self.watcher_pv_name,
                        "initial_value": 0,
                        "duration_sec": round(heartbeat_init_duration, 3),
                    }
                },
            )
        except (PVConnectionError, PVPutError) as e:
            heartbeat_init_duration = time() - heartbeat_init_start
            cavity_fault_logger.critical(
                "Failed to initialize heartbeat PV",
                extra={
                    "extra_data": {
                        "pv_name": self.watcher_pv_name,
                        "error": str(e),
                        "duration_sec": round(heartbeat_init_duration, 3),
                    }
                },
                exc_info=True,
            )
            cavity_fault_logger.warning(
                "Continuing without initial heartbeat (will retry)"
            )

        cycle_count = 0
        last_status_log = service_start_time
        status_log_interval = 300.0  # Log status every 5 minutes

        try:
            while self._running:
                self.check_faults()
                cycle_count += 1

                # Periodic status log based on time
                now = datetime.now()
                if (
                    now - last_status_log
                ).total_seconds() >= status_log_interval:
                    cavity_fault_logger.info(
                        "Fault checker running normally",
                        extra={
                            "extra_data": {
                                "cycles_completed": cycle_count,
                                "cavities_monitored": len(
                                    self.backend_cavities
                                ),
                                "uptime_sec": round(
                                    (now - service_start_time).total_seconds(),
                                    1,
                                ),
                                "interval_sec": round(
                                    (now - last_status_log).total_seconds(), 1
                                ),
                            }
                        },
                    )
                    last_status_log = now

        except KeyboardInterrupt:
            print("\n\n" + "=" * 70)
            print("Shutdown requested by user (Ctrl+C)")
            print("=" * 70 + "\n")
            cavity_fault_logger.info(
                "Received keyboard interrupt, initiating shutdown"
            )
            self.stop()

        except Exception as e:
            cavity_fault_logger.critical(
                "Unexpected error in run loop",
                extra={
                    "extra_data": {
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "cycles_completed": cycle_count,
                    }
                },
                exc_info=True,
            )
            raise

        finally:
            cavity_fault_logger.info(
                "Fault checker stopped",
                extra={"extra_data": {"total_cycles": cycle_count}},
            )

    def stop(self) -> None:
        """Gracefully stop the runner."""
        if self._running:
            cavity_fault_logger.info("Stopping fault checker service")
            self._running = False

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully."""
        signal_name = signal.Signals(signum).name
        print(f"\n\n{'='*70}")
        print(f"Received signal: {signal_name}")
        print(f"{'='*70}\n")
        cavity_fault_logger.info(
            "Received shutdown signal",
            extra={
                "extra_data": {
                    "signal": signal_name,
                    "signal_number": signum,
                }
            },
        )
        self.stop()

    def __enter__(self):
        """Context manager entry."""

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is not None:
            cavity_fault_logger.error(
                "Exception occurred in context manager",
                extra={
                    "extra_data": {
                        "exception_type": (
                            exc_type.__name__ if exc_type else None
                        ),
                        "exception_value": (str(exc_val) if exc_val else None),
                    }
                },
                exc_info=(exc_type, exc_val, exc_tb),
            )

        self.stop()
        # Return False to re-raise the exception if it's not KeyboardInterrupt
        return exc_type is KeyboardInterrupt


def main():
    """Entry point for the fault checker service."""
    cavity_fault_logger.info(
        "Cavity fault checker starting up",
        extra={
            "extra_data": {
                "debug_mode": DEBUG,
                "cycle_time_sec": BACKEND_SLEEP_TIME,
            }
        },
    )

    # Install custom signal handler during initialization
    signal.signal(signal.SIGINT, _signal_handler_during_init)

    runner = None

    try:
        # Use lazy_fault_pvs=False for better runtime performance
        # With parallel initialization, startup is much faster (~30-60 seconds vs 5 minutes)
        try:
            runner = Runner(lazy_fault_pvs=False)
        except KeyboardInterrupt:
            # Already handled by _signal_handler_during_init
            sys.exit(0)

        # Restore original handler and use runner's handler
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        with runner:
            # Register signal handlers for runtime
            signal.signal(signal.SIGINT, runner._signal_handler)
            signal.signal(signal.SIGTERM, runner._signal_handler)
            runner.run()

    except KeyboardInterrupt:
        # This should rarely be reached due to handlers above
        print("\n\n" + "=" * 70)
        print("Shutdown complete")
        print("=" * 70 + "\n")
        cavity_fault_logger.info("Shutdown via KeyboardInterrupt")
        sys.exit(0)

    except Exception as e:
        cavity_fault_logger.critical(
            "Fatal error in main",
            extra={
                "extra_data": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            },
            exc_info=True,
        )
        print(f"\n\nFatal error: {e}\n")
        sys.exit(1)

    cavity_fault_logger.info("Cavity fault checker shutdown complete")
    print("\nShutdown complete.\n")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Final catch-all for any missed interrupts
        print("\n\nShutdown complete.\n")
        sys.exit(0)
