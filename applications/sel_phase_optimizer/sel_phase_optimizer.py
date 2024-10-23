#!/usr/bin/env python

"""
Script to optimize SEL phase offsets
Originally by J. Nelson, refactored by L. Zacarias
"""

import time

from lcls_tools.common.controls.pyepics.utils import PV, PVInvalidError

from sel_phase_linac import SEL_MACHINE
from utils.sc_linac.cryomodule import Cryomodule
from utils.sc_linac.linac_utils import ALL_CRYOMODULES

HEARTBEAT_PV = PV("PHYS:SYS0:1:SC_SEL_PHAS_OPT_HEARTBEAT")


def update_heartbeat(time_to_wait: int):
    for _ in range(time_to_wait):
        try:
            HEARTBEAT_PV.put(HEARTBEAT_PV.get() + 1)
        except TypeError as e:
            print(e)
        time.sleep(1)


def run():
    num_large_steps = 0
    for cm_name in ALL_CRYOMODULES:
        cm_obj: Cryomodule = SEL_MACHINE.cryomodules[cm_name]
        for cav_obj in cm_obj.cavities.values():
            try:
                num_large_steps += 1 if cav_obj.straighten_cheeto() else 0
            except PVInvalidError as e:
                cav_obj.logger.error(e)
        update_heartbeat(1)
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
        print(f"Sleeping for 600 seconds")
        print("")
        update_heartbeat(600)


if __name__ == "__main__":
    HEARTBEAT_PV.put(0)
    while True:
        run()
