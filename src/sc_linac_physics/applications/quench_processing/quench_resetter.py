import logging
from dataclasses import dataclass
from time import sleep, time
from typing import List, Dict, Optional

from sc_linac_physics.applications.quench_processing.quench_cavity import (
    QuenchCavity,
)
from sc_linac_physics.applications.quench_processing.quench_utils import (
    QUENCH_LOG_DIR,
)
from sc_linac_physics.utils.epics import PV, PVInvalidError
from sc_linac_physics.utils.logger import custom_logger
from sc_linac_physics.utils.sc_linac.linac import Machine
from sc_linac_physics.utils.sc_linac.linac_utils import (
    HW_MODE_ONLINE_VALUE,
    CavityFaultError,
)

QUENCH_MACHINE = Machine(cavity_class=QuenchCavity)

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
    total_real_quenches: int = 0  # Times we detected a real quench
    last_reset_time: Optional[float] = None
    last_check_was_quenched: bool = False  # Track state from last check


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
        Check if cavity can be reset based on cooldown.

        Returns:
            tuple: (can_reset: bool, reason: str)
        """
        stats = self._get_stats(quench_cav)

        if stats.last_reset_time is not None:
            time_since_reset = time() - stats.last_reset_time
            if time_since_reset < self.cooldown_seconds:
                remaining = self.cooldown_seconds - time_since_reset
                return False, f"cooldown active ({remaining:.1f}s remaining)"

        return True, "ready"

    def record_fake_quench_reset(self, quench_cav: QuenchCavity):
        """Record that a fake quench reset was sent."""
        stats = self._get_stats(quench_cav)
        stats.last_reset_time = time()
        stats.total_resets += 1

    def record_real_quench(self, quench_cav: QuenchCavity):
        """Record that a real quench was detected."""
        stats = self._get_stats(quench_cav)
        stats.last_reset_time = time()  # Apply cooldown
        stats.total_real_quenches += 1
        stats.last_check_was_quenched = True

    def record_not_quenched(self, quench_cav: QuenchCavity):
        """Record that cavity is not quenched."""
        stats = self._get_stats(quench_cav)
        stats.last_check_was_quenched = False

    def get_summary(self) -> Dict[str, dict]:
        """Get summary of all cavity statistics."""
        return {
            cavity_id: {
                "total_resets": stats.total_resets,
                "total_real_quenches": stats.total_real_quenches,
                "currently_quenched": stats.last_check_was_quenched,
            }
            for cavity_id, stats in self.cavity_stats.items()
            if stats.total_resets > 0 or stats.total_real_quenches > 0
        }


def _handle_quenched_cavity(
    quench_cav: QuenchCavity,
    reset_tracker: CavityResetTracker,
    counts: Dict[str, int],
) -> None:
    """Handle a cavity that is in quenched state."""
    # Check cooldown
    can_reset, reason = reset_tracker.can_reset(quench_cav)
    if not can_reset:
        logger.debug(f"{quench_cav} quenched but {reason}")
        counts["skipped"] += 1
        return

    # Validate if it's a fake quench
    logger.info(f"Quench detected on {quench_cav}, validating...")
    is_real = quench_cav.validate_quench(wait_for_update=True)

    if is_real:
        logger.warning(f"REAL quench on {quench_cav}, NOT resetting")
        counts["real_quench"] += 1
        reset_tracker.record_real_quench(quench_cav)
        return

    # Fake quench - send reset command (non-blocking)
    logger.info(f"FAKE quench on {quench_cav}, sending reset command")

    if not quench_cav._interlock_reset_pv_obj:
        quench_cav._interlock_reset_pv_obj = PV(quench_cav.interlock_reset_pv)

    quench_cav._interlock_reset_pv_obj.put(1, wait=False)
    reset_tracker.record_fake_quench_reset(quench_cav)
    counts["reset"] += 1


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
    Check all cavities for quench conditions and send reset commands if needed.

    Args:
        cavity_list: List of QuenchCavity objects to monitor
        watcher_pv: PV for heartbeat counter
        reset_tracker: Tracker for per-cavity reset cooldowns

    Returns:
        Dict with counts: reset, skipped, error, checked, real_quench
    """
    counts = {
        "reset": 0,
        "skipped": 0,
        "error": 0,
        "checked": 0,
        "real_quench": 0,
    }

    try:
        for quench_cav in cavity_list:
            try:
                # Skip offline or turned off cavities
                if (
                    quench_cav.hw_mode != HW_MODE_ONLINE_VALUE
                    or quench_cav.turned_off
                ):
                    continue

                counts["checked"] += 1

                # If not quenched, record and move on
                if not quench_cav.is_quenched:
                    reset_tracker.record_not_quenched(quench_cav)
                    continue

                # Handle quenched cavity
                _handle_quenched_cavity(quench_cav, reset_tracker, counts)

            except (CavityFaultError, PVInvalidError) as e:
                logger.error(f"Error checking {quench_cav}: {e}")
                counts["error"] += 1
            except Exception as e:
                logger.error(
                    f"Unexpected error checking {quench_cav}: {e}",
                    exc_info=True,
                )
                counts["error"] += 1

        # Log summary if anything interesting happened
        if any(counts[k] > 0 for k in ["reset", "real_quench", "error"]):
            logger.info(
                f"Cycle: {counts['checked']} checked, {counts['reset']} reset, "
                f"{counts['real_quench']} real quenches, {counts['skipped']} skipped, "
                f"{counts['error']} errors"
            )

        # Update heartbeat
        _update_heartbeat(watcher_pv)

    except Exception as e:
        logger.critical(f"Critical error in check_cavities: {e}", exc_info=True)

    return counts


def initialize_watcher_pv() -> PV:
    """Initialize and reset the heartbeat PV."""
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
    """Load cavity list from QUENCH_MACHINE."""
    logger.info("Loading cavity list from QUENCH_MACHINE...")

    try:
        cavities = list(QUENCH_MACHINE.all_iterator)
        logger.info(f"Successfully loaded {len(cavities)} cavities")
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

        # Separate by current state
        currently_quenched = {
            k: v for k, v in summary.items() if v["currently_quenched"]
        }
        successfully_cleared = {
            k: v for k, v in summary.items() if not v["currently_quenched"]
        }

        if successfully_cleared:
            logger.info(
                f"\nSuccessfully cleared ({len(successfully_cleared)} cavities):"
            )
            for cavity_id, stats in successfully_cleared.items():
                logger.info(
                    f"  {cavity_id}: {stats['total_resets']} fake quench resets"
                )

        if currently_quenched:
            logger.info(
                f"\nStill quenched ({len(currently_quenched)} cavities):"
            )
            for cavity_id, stats in currently_quenched.items():
                msg_parts = []
                if stats["total_resets"] > 0:
                    msg_parts.append(
                        f"{stats['total_resets']} fake quench resets"
                    )
                if stats["total_real_quenches"] > 0:
                    msg_parts.append(
                        f"{stats['total_real_quenches']} real quenches detected"
                    )
                logger.info(f"  {cavity_id}: {', '.join(msg_parts)}")

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
        if reset_tracker:
            _log_final_summary(reset_tracker)

        logger.info("Quench processing monitor stopped")


if __name__ == "__main__":
    main()
