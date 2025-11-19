import logging
from dataclasses import dataclass
from time import sleep, time
from typing import List, Dict, Optional

from lcls_tools.common.controls.pyepics.utils import PVInvalidError, PV

from sc_linac_physics.applications.quench_processing.quench_cavity import (
    QuenchCavity,
)
from sc_linac_physics.applications.quench_processing.quench_utils import (
    QUENCH_LOG_DIR,
)
from sc_linac_physics.utils.logger import custom_logger
from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import (
    HW_MODE_ONLINE_VALUE,
    CavityFaultError,
)

QUENCH_MACHINE = Machine(cavity_class=QuenchCavity)

# Module-level logger with explicit descriptive name
logger = custom_logger(
    "quench_resetter.main",
    log_dir=QUENCH_LOG_DIR,
    log_filename="quench_resetter",
    level=logging.INFO,
)

# Constants
RESET_COOLDOWN_SECONDS = 3.0
MONITORING_CYCLE_SLEEP = 1.0


@dataclass
class CavityResetStats:
    """Statistics for a single cavity's reset history."""

    total_resets: int = 0
    last_reset_time: Optional[float] = None
    last_successful_reset: Optional[float] = None
    failed_reset_count: int = 0


class CavityResetTracker:
    """Track reset times and statistics for individual cavities to enforce cooldown periods."""

    def __init__(self, cooldown_seconds: float = RESET_COOLDOWN_SECONDS):
        self.cooldown_seconds = cooldown_seconds
        self.cavity_stats: Dict[str, CavityResetStats] = {}

    def _get_stats(self, quench_cav: QuenchCavity) -> CavityResetStats:
        """Get or create stats object for a cavity."""
        cavity_id = str(quench_cav)
        if cavity_id not in self.cavity_stats:
            self.cavity_stats[cavity_id] = CavityResetStats()
        return self.cavity_stats[cavity_id]

    def can_reset(self, quench_cav: QuenchCavity) -> tuple[bool, str]:
        """
        Check if cavity can be reset.

        Returns:
            tuple: (can_reset: bool, reason: str)
        """
        stats = self._get_stats(quench_cav)

        # Check cooldown period
        if stats.last_reset_time is not None:
            time_since_reset = time() - stats.last_reset_time
            if time_since_reset < self.cooldown_seconds:
                remaining = self.cooldown_seconds - time_since_reset
                return False, f"cooldown active ({remaining:.1f}s remaining)"

        return True, "ready"

    def get_time_until_ready(self, quench_cav: QuenchCavity) -> float:
        """Get seconds until cavity can be reset again."""
        stats = self._get_stats(quench_cav)

        if stats.last_reset_time is None:
            return 0.0

        time_since_reset = time() - stats.last_reset_time
        remaining = self.cooldown_seconds - time_since_reset
        return max(0.0, remaining)

    def record_reset(self, quench_cav: QuenchCavity, success: bool):
        """Record that a reset was attempted on this cavity."""
        stats = self._get_stats(quench_cav)
        cavity_id = str(quench_cav)

        stats.last_reset_time = time()
        stats.total_resets += 1

        if success:
            stats.last_successful_reset = time()
            logger.debug(
                f"Recorded successful reset for {cavity_id} "
                f"(total: {stats.total_resets})"
            )
        else:
            stats.failed_reset_count += 1
            logger.debug(
                f"Recorded failed reset for {cavity_id} "
                f"(total failures: {stats.failed_reset_count})"
            )

    def get_summary(self) -> Dict[str, dict]:
        """Get summary of all cavity statistics."""
        return {
            cavity_id: {
                "total_resets": stats.total_resets,
                "failed_resets": stats.failed_reset_count,
                "last_reset": stats.last_reset_time,
            }
            for cavity_id, stats in self.cavity_stats.items()
            if stats.total_resets > 0
        }


def _should_check_cavity(quench_cav: QuenchCavity) -> bool:
    """Determine if cavity should be checked for quench."""
    return (
        quench_cav.hw_mode == HW_MODE_ONLINE_VALUE and not quench_cav.turned_off
    )


def _handle_quenched_cavity(
    quench_cav: QuenchCavity,
    reset_tracker: CavityResetTracker,
    counts: Dict[str, int],
) -> None:
    """Handle a cavity that is in quenched state."""
    logger.warning(f"Quench detected on {quench_cav}")

    # Check if we can reset this cavity
    can_reset, reason = reset_tracker.can_reset(quench_cav)

    if not can_reset:
        logger.info(f"Skipping {quench_cav} - {reason}")
        counts["skipped"] += 1
        return

    # Attempt reset
    logger.info(f"Attempting reset for {quench_cav}")
    success = quench_cav.reset_quench()

    reset_tracker.record_reset(quench_cav, success)

    if success:
        counts["reset"] += 1
        logger.info(f"Successfully reset {quench_cav}")
    else:
        counts["error"] += 1
        logger.error(f"Failed to reset {quench_cav}")


def _update_heartbeat(watcher_pv: PV) -> None:
    """Update the heartbeat PV."""
    try:
        current_count = watcher_pv.get()
        watcher_pv.put(current_count + 1)
        logger.debug(f"Heartbeat: {current_count + 1}")
    except Exception as e:
        logger.error(f"Failed to update heartbeat: {e}")


def check_cavities(
    cavity_list: List[QuenchCavity],
    watcher_pv: PV,
    reset_tracker: CavityResetTracker,
) -> Dict[str, int]:
    """
    Check all cavities for quench conditions and attempt reset if needed.

    Args:
        cavity_list: List of QuenchCavity objects to monitor
        watcher_pv: PV for heartbeat counter
        reset_tracker: Tracker for per-cavity reset cooldowns

    Returns:
        Dict with counts: reset, skipped, error, checked
    """
    counts = {"reset": 0, "skipped": 0, "error": 0, "checked": 0}

    try:
        for quench_cav in cavity_list:
            try:
                # Skip offline or turned off cavities
                if not _should_check_cavity(quench_cav):
                    continue

                counts["checked"] += 1

                if quench_cav.is_quenched:
                    _handle_quenched_cavity(quench_cav, reset_tracker, counts)

            except (CavityFaultError, PVInvalidError) as e:
                logger.error(f"Error checking {quench_cav}: {e}")
                counts["error"] += 1
                continue
            except Exception as e:
                logger.error(
                    f"Unexpected error checking {quench_cav}: {e}",
                    exc_info=True,
                )
                counts["error"] += 1
                continue

        # Log summary if anything happened
        if counts["reset"] > 0 or counts["skipped"] > 0:
            logger.info(
                f"Cycle summary: {counts['checked']} checked, "
                f"{counts['reset']} reset, {counts['skipped']} skipped, "
                f"{counts['error']} errors"
            )

        # Update heartbeat
        _update_heartbeat(watcher_pv)

    except Exception as e:
        logger.critical(f"Critical error in check_cavities: {e}", exc_info=True)

    return counts


def initialize_watcher_pv() -> PV:
    """
    Initialize and reset the heartbeat PV.

    Returns:
        Initialized PV object
    """
    pv_name = "PHYS:SYS0:1:SC_CAV_QNCH_RESET_HEARTBEAT"
    logger.info(f"Initializing watcher PV: {pv_name}")

    try:
        watcher_pv = PV(pv_name)
        watcher_pv.put(0)
        logger.info("Heartbeat reset to 0")
        return watcher_pv
    except Exception as e:
        logger.critical(f"Failed to initialize watcher PV: {e}", exc_info=True)
        raise


def load_cavities() -> List[QuenchCavity]:
    """
    Load cavity list from QUENCH_MACHINE.

    Returns:
        List of QuenchCavity objects
    """
    logger.info("Loading cavity list from QUENCH_MACHINE...")

    try:
        cavities = list(QUENCH_MACHINE.all_iterator)
        logger.info("Successfully loaded cavities")
        return cavities

    except Exception as e:
        logger.critical(f"Failed to load cavities: {e}", exc_info=True)
        raise


def _log_final_summary(reset_tracker: CavityResetTracker) -> None:
    """Log final summary statistics on script shutdown."""
    summary = reset_tracker.get_summary()
    if summary:
        logger.info("=" * 80)
        logger.info("Final Reset Statistics:")
        for cavity_id, stats in summary.items():
            logger.info(
                f"  {cavity_id}: "
                f"{stats['total_resets']} total resets, "
                f"{stats['failed_resets']} failed"
            )
        logger.info("=" * 80)
    else:
        logger.info("No resets were performed during this session")


def main():
    """Main entry point for quench processing monitor."""
    logger.info("=" * 80)
    logger.info("Starting Quench Processing Monitor")
    logger.info(f"Reset cooldown period: {RESET_COOLDOWN_SECONDS}s per cavity")
    logger.info(f"Monitoring cycle interval: {MONITORING_CYCLE_SLEEP}s")
    logger.info("=" * 80)

    reset_tracker = None

    try:
        # Initialize watcher PV
        watcher_pv = initialize_watcher_pv()

        # Load cavity list
        cavities = load_cavities()

        # Initialize reset tracker
        reset_tracker = CavityResetTracker(
            cooldown_seconds=RESET_COOLDOWN_SECONDS
        )

        # Main monitoring loop
        logger.info("Starting continuous monitoring (Ctrl+C to stop)...")
        cycle_count = 0

        while True:
            cycle_count += 1
            logger.debug(f"Starting monitoring cycle {cycle_count}")

            check_cavities(cavities, watcher_pv, reset_tracker)

            sleep(MONITORING_CYCLE_SLEEP)

    except KeyboardInterrupt:
        logger.info("=" * 80)
        logger.info("Keyboard interrupt received - shutting down gracefully")
        logger.info("=" * 80)
    except Exception as e:
        logger.critical(f"Fatal error in main: {e}", exc_info=True)
        raise
    finally:
        # Final summary only logged on shutdown
        if reset_tracker:
            _log_final_summary(reset_tracker)

        logger.info("Quench processing monitor stopped")


if __name__ == "__main__":
    main()
