import signal
import sys
from datetime import datetime
from time import sleep
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
    CAV_LOG_DIR,
)
from sc_linac_physics.utils.epics import (
    PV,
    PVConnectionError,
    PVGetError,
    PVPutError,
)
from sc_linac_physics.utils.logger import custom_logger

# Initialize logger
logger = custom_logger(
    name="cavity.fault.runner",
    log_filename="cavity_fault_runner",
    log_dir=CAV_LOG_DIR,
)


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
        self.watcher_pv_name = "PHYS:SYS0:1:SC_CAV_FAULT_HEARTBEAT"
        self._watcher_pv_obj: Optional[PV] = None
        self._running = False
        self._shutdown_requested = False
        self._heartbeat_failures = 0
        self._max_heartbeat_failures = 10

        logger.info(
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

        try:
            backend_machine = BackendMachine(lazy_fault_pvs=lazy_fault_pvs)
            self.backend_cavities: List[BackendCavity] = list(
                backend_machine.all_iterator
            )
            logger.info(
                "Backend cavities initialized successfully",
                extra={
                    "extra_data": {
                        "cavity_count": len(self.backend_cavities),
                        "lazy_mode": lazy_fault_pvs,
                    }
                },
            )
        except Exception as e:
            logger.critical(
                "Failed to initialize backend cavities",
                extra={
                    "extra_data": {
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }
                },
                exc_info=True,
            )
            raise

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
            logger.debug(
                "Connecting to watcher PV",
                extra={"extra_data": {"pv_name": self.watcher_pv_name}},
            )
            try:
                # PV class will handle connection retries and logging
                self._watcher_pv_obj = PV(
                    self.watcher_pv_name,
                    connection_timeout=10.0,
                    require_connection=True,
                )
                logger.info(
                    "Watcher PV connected successfully",
                    extra={"extra_data": {"pv_name": self.watcher_pv_name}},
                )
            except PVConnectionError as e:
                logger.error(
                    "Failed to connect to watcher PV",
                    extra={
                        "extra_data": {
                            "pv_name": self.watcher_pv_name,
                            "error": str(e),
                        }
                    },
                    exc_info=True,
                )
                raise
        return self._watcher_pv_obj

    def check_faults(self) -> None:
        """
        Check faults for all cavities and update heartbeat.

        Measures execution time and sleeps to maintain consistent cycle time.
        Logs performance metrics and tracks failures. If individual cavities fail,
        continues checking others to maximize coverage.
        """
        start = datetime.now()

        failed_cavities = []
        exception_summary = {}

        for cavity in self.backend_cavities:
            try:
                cavity.run_through_faults()
            except Exception as e:
                error_type = type(e).__name__

                # Track exception types for summary
                exception_summary[error_type] = (
                    exception_summary.get(error_type, 0) + 1
                )

                logger.error(
                    "Error checking faults for cavity",
                    extra={
                        "extra_data": {
                            "cavity": str(cavity),
                            "error": str(e),
                            "error_type": error_type,
                        }
                    },
                    exc_info=DEBUG,  # Full traceback only in debug mode
                )
                failed_cavities.append(cavity)

        # Log summary if there were failures
        if failed_cavities:
            logger.warning(
                "Fault check cycle had failures",
                extra={
                    "extra_data": {
                        "failed_count": len(failed_cavities),
                        "total_count": len(self.backend_cavities),
                        "success_rate_pct": round(
                            (len(self.backend_cavities) - len(failed_cavities))
                            / len(self.backend_cavities)
                            * 100,
                            1,
                        ),
                        "exception_types": exception_summary,
                    }
                },
            )

        # Calculate sleep time to maintain consistent cycle
        delta = (datetime.now() - start).total_seconds()

        if DEBUG:
            logger.debug(
                "Fault check cycle completed",
                extra={
                    "extra_data": {
                        "duration_sec": round(delta, 3),
                        "target_sec": BACKEND_SLEEP_TIME,
                        "cavities_checked": len(self.backend_cavities),
                        "cavities_failed": len(failed_cavities),
                    }
                },
            )

        sleep_time = max(0.0, BACKEND_SLEEP_TIME - delta)
        if sleep_time > 0:
            sleep(sleep_time)
        elif (
            delta > BACKEND_SLEEP_TIME * 1.5
        ):  # Only warn if significantly over
            logger.warning(
                "Fault check significantly exceeded target cycle time",
                extra={
                    "extra_data": {
                        "actual_sec": round(delta, 3),
                        "target_sec": BACKEND_SLEEP_TIME,
                        "overrun_sec": round(delta - BACKEND_SLEEP_TIME, 3),
                        "overrun_pct": round(
                            (delta / BACKEND_SLEEP_TIME - 1) * 100, 1
                        ),
                    }
                },
            )

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

            # PV.get() raises exception if it fails, so we know this is valid
            new_value = current_value + 1
            self.watcher_pv_obj.put(new_value, timeout=2.0)

            # Reset failure counter on success
            if self._heartbeat_failures > 0:
                logger.info(
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
                logger.debug(
                    "Heartbeat milestone",
                    extra={"extra_data": {"heartbeat_count": new_value}},
                )

        except (PVConnectionError, PVGetError, PVPutError) as e:
            self._heartbeat_failures += 1

            logger.error(
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

            # Stop if too many consecutive failures
            if self._heartbeat_failures >= self._max_heartbeat_failures:
                logger.critical(
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
            # Catch any unexpected exceptions
            self._heartbeat_failures += 1

            logger.error(
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
                logger.critical("Too many heartbeat failures, stopping")
                self.stop()

    def run(self) -> None:
        """
        Run the fault checker continuously.

        Initializes the heartbeat counter and runs the check loop until stopped
        via keyboard interrupt, signal, or critical error. Logs periodic status
        updates for monitoring.
        """
        logger.info("Starting fault checker service")
        self._running = True

        # Initialize heartbeat
        try:
            self.watcher_pv_obj.put(0, timeout=10.0)
            logger.info(
                "Heartbeat initialized",
                extra={
                    "extra_data": {
                        "pv_name": self.watcher_pv_name,
                        "initial_value": 0,
                    }
                },
            )
        except (PVConnectionError, PVPutError) as e:
            logger.critical(
                "Failed to initialize heartbeat PV",
                extra={
                    "extra_data": {
                        "pv_name": self.watcher_pv_name,
                        "error": str(e),
                    }
                },
                exc_info=True,
            )
            # Don't return - try to run anyway, heartbeat updates will retry
            logger.warning("Continuing without initial heartbeat (will retry)")

        cycle_count = 0
        last_status_log = datetime.now()
        status_log_interval = 300.0  # Log status every 5 minutes

        try:
            while self._running and not self._shutdown_requested:
                self.check_faults()
                cycle_count += 1

                # Periodic status log based on time
                now = datetime.now()
                if (
                    now - last_status_log
                ).total_seconds() >= status_log_interval:
                    logger.info(
                        "Fault checker running normally",
                        extra={
                            "extra_data": {
                                "cycles_completed": cycle_count,
                                "cavities_monitored": len(
                                    self.backend_cavities
                                ),
                                "uptime_sec": round(
                                    (now - last_status_log).total_seconds(), 1
                                ),
                            }
                        },
                    )
                    last_status_log = now

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, initiating shutdown")
            self.stop()
        except Exception as e:
            logger.critical(
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
            logger.info(
                "Fault checker stopped",
                extra={"extra_data": {"total_cycles": cycle_count}},
            )

    def stop(self) -> None:
        """Gracefully stop the runner."""
        if self._running:
            logger.info("Stopping fault checker service")
            self._running = False
            self._shutdown_requested = True

    def _signal_handler(self, signum: int, frame) -> None:
        """Handle shutdown signals gracefully."""
        signal_name = signal.Signals(signum).name
        logger.info(
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
            logger.error(
                "Exception occurred in context manager",
                extra={
                    "extra_data": {
                        "exception_type": (
                            exc_type.__name__ if exc_type else None
                        ),
                        "exception_value": str(exc_val) if exc_val else None,
                    }
                },
                exc_info=(exc_type, exc_val, exc_tb),
            )
        self.stop()


def main():
    """Entry point for the fault checker service."""
    logger.info(
        "Cavity fault checker starting up",
        extra={
            "extra_data": {
                "debug_mode": DEBUG,
                "cycle_time_sec": BACKEND_SLEEP_TIME,
            }
        },
    )

    try:
        with Runner(lazy_fault_pvs=False) as runner:
            # Register signal handlers
            signal.signal(signal.SIGINT, runner._signal_handler)
            signal.signal(signal.SIGTERM, runner._signal_handler)

            runner.run()

    except Exception as e:
        logger.critical(
            "Fatal error in main",
            extra={
                "extra_data": {
                    "error": str(e),
                    "error_type": type(e).__name__,
                }
            },
            exc_info=True,
        )
        sys.exit(1)

    logger.info("Cavity fault checker shutdown complete")
    sys.exit(0)


if __name__ == "__main__":
    main()
