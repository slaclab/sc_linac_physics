#!/usr/bin/env python

"""
Script to optimize SEL phase offsets
Originally by J. Nelson, refactored by L. Zacarias
"""

import argparse
import time
from typing import List, Optional

from sc_linac_physics.applications.sel_phase_optimizer.sel_phase_linac import (
    SEL_MACHINE,
    SELCavity,
    MAX_STEP,
)
from sc_linac_physics.utils.epics import PV, PVInvalidError, PVConnectionError

_HEARTBEAT_PV: Optional[PV] = None


def get_heartbeat_pv() -> PV:
    """Lazy initialization of heartbeat PV"""
    global _HEARTBEAT_PV
    if _HEARTBEAT_PV is None:
        _HEARTBEAT_PV = PV("PHYS:SYS0:1:SC_SEL_PHAS_OPT_HEARTBEAT")
    return _HEARTBEAT_PV


def update_heartbeat(time_to_wait: int):
    """
    Update heartbeat PV while waiting

    Args:
        time_to_wait: Number of seconds to wait
    """
    print(f"Sleeping for {time_to_wait} seconds")
    heartbeat_pv = get_heartbeat_pv()

    for _ in range(time_to_wait):
        try:
            current_value = heartbeat_pv.get()
            heartbeat_pv.put(current_value + 1)
        except (PVConnectionError, PVInvalidError, TypeError) as e:
            print(f"Heartbeat update failed: {e}")
        time.sleep(1)


def run():
    """Main optimization loop"""
    cavities: List[SELCavity] = list(SEL_MACHINE.all_iterator)
    heartbeat_pv = get_heartbeat_pv()

    while True:
        num_large_steps = 0

        for cavity in cavities:
            try:
                step_size = cavity.straighten_iq_plot()
                num_large_steps += 1 if step_size >= MAX_STEP else 0

                # Update heartbeat
                try:
                    current_value = heartbeat_pv.get()
                    heartbeat_pv.put(current_value + 1)
                except (PVConnectionError, PVInvalidError) as e:
                    cavity.logger.warning(f"Heartbeat update failed: {e}")

            except (PVInvalidError, TypeError) as e:
                cavity.logger.error(f"Failed to straighten IQ plot: {e}")

        if num_large_steps > 5:
            print(
                f"\033[91mPhase change limited to 5 deg {num_large_steps} times. "
                f"Re-running program.\033[0m"
            )
            update_heartbeat(5)
        else:
            current_time = time.strftime("%m/%d/%y %H:%M:%S", time.localtime())
            print(
                f"\033[94mThanks for your help! The current date/time is {current_time}\033[0m"
            )
            update_heartbeat(600)


def main():
    """Entry point for SEL phase optimizer"""
    parser = argparse.ArgumentParser(description="Optimize SEL phase offsets")
    parser.parse_args()

    try:
        heartbeat_pv = get_heartbeat_pv()
        heartbeat_pv.put(0)
        run()
    except PVConnectionError as e:
        print(f"\033[91mFailed to connect to heartbeat PV: {e}\033[0m")
        raise
    except KeyboardInterrupt:
        print("\n\033[93mOptimization stopped by user\033[0m")
    except Exception as e:
        print(f"\033[91mUnexpected error: {e}\033[0m")
        raise


if __name__ == "__main__":
    main()
