#!/usr/bin/env python

"""
Script to optimize SEL phase offsets
Originally by J. Nelson, refactored by L. Zacarias
"""
import argparse
import time
from typing import List

from lcls_tools.common.controls.pyepics.utils import PV, PVInvalidError

from sc_linac_physics.applications.sel_phase_optimizer.sel_phase_linac import (
    SEL_MACHINE,
    SELCavity,
    MAX_STEP,
)

HEARTBEAT_PV = PV("PHYS:SYS0:1:SC_SEL_PHAS_OPT_HEARTBEAT")


def update_heartbeat(time_to_wait: int):
    print(f"Sleeping for {time_to_wait} seconds")
    for _ in range(time_to_wait):
        try:
            HEARTBEAT_PV.put(HEARTBEAT_PV.get() + 1)
        except TypeError as e:
            print(e)
        time.sleep(1)


def run():
    cavities: List[SELCavity] = list(SEL_MACHINE.all_iterator)

    while True:
        num_large_steps = 0

        for cavity in cavities:
            try:
                num_large_steps += (
                    1 if cavity.straighten_iq_plot() >= MAX_STEP else 0
                )
                HEARTBEAT_PV.put(HEARTBEAT_PV.get() + 1)
            except (PVInvalidError, TypeError) as e:
                cavity.logger.error(e)

        if num_large_steps > 5:
            print(
                f"\033[91mPhase change limited to 5 deg {num_large_steps} times."
                f" Re-running program.\033[0m"
            )
            update_heartbeat(5)
        else:
            timi = time.localtime()
            current_time = time.strftime("%m/%d/%y %H:%M:%S", timi)
            print(
                f"\033[94mThanks for your help! The current date/time is {current_time}\033[0m"
            )
            update_heartbeat(600)


def main():
    parser = argparse.ArgumentParser(description="Optimize SEL phase offsets")
    parser.parse_args()

    HEARTBEAT_PV.put(0)
    run()


if __name__ == "__main__":
    main()
