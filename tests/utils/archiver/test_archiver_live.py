#!/usr/bin/env python
"""Test archiver integration without GUI. Used for personal debugging"""

import os
from datetime import datetime, timedelta
from sc_linac_physics.utils.archiver import get_values_over_time_range

# Enable mock (simulates what sc-sim does)
os.environ["SC_ARCHIVER_MOCK"] = "1"
print("✓ Mock archiver enabled\n")

# Test 1: Single PV, 1 minute
print("Test 1: Fetch 1 minute of CUDSTATUS data")
print("-" * 50)
end = datetime.now()
start = end - timedelta(minutes=1)

data = get_values_over_time_range(
    pv_list=["ACCL:L1B:0210:CUDSTATUS"],
    start_time=start,
    end_time=end
)

handler = data["ACCL:L1B:0210:CUDSTATUS"]
print(f"PV: {handler.pv_name}")
print(f"Data points: {len(handler.values)}")
print(f"Time range: {handler.timestamps[0]} to {handler.timestamps[-1]}")
print(f"First 10 values: {handler.values[:10]}")
print(f"Fault rate: {sum(1 for v in handler.values if v != 'TLC')}/{len(handler.values)}")
print()

# Test 2: Multiple PVs
print("Test 2: Fetch multiple PVs")
print("-" * 50)
data = get_values_over_time_range(
    pv_list=[
        "ACCL:L1B:0210:CUDSTATUS",
        "ACCL:L1B:0210:CUDSEVR",
        "ACCL:L1B:0210:ADES"
    ],
    start_time=start,
    end_time=end
)

for pv_name in data:
    print(f"{pv_name}: {len(data[pv_name].values)} values")

#!/usr/bin/env python
"""Test real archiver and smart routing logic."""

from sc_linac_physics.utils.archiver import (
    get_values_over_time_range,
    is_archiver_available
)
from datetime import datetime, timedelta

# DON'T set SC_ARCHIVER_MOCK - test real routing!

print("Test: Archiver Smart Routing")
print("=" * 50)

# Check 1: Is archiver reachable?
print("\n1. Checking archiver availability...")
available = is_archiver_available()
print(f"   Archiver available: {available}")

# Check 2: Try to get data (will use real or mock automatically)
print("\n2. Fetching data (auto-routing)...")
end = datetime.now()
start = end - timedelta(minutes=1)

data = get_values_over_time_range(
    pv_list=["ACCL:L1B:0110:ADES"],
    start_time=start,
    end_time=end
)

handler = data["ACCL:L1B:0110:ADES"]
print(f"   Got {len(handler.values)} data points")

# Check 3: Determine if we got real or mock data
if len(handler.values) > 0:
    avg = sum(handler.values) / len(handler.values)
    
    # Mock data characteristics: ~61 points, avg ~16.5
    is_likely_mock = (
        len(handler.values) == 61 and  # 1 minute at 1 Hz
        16.0 <= avg <= 17.0  # Typical mock gradient
    )
    
    if is_likely_mock:
        print(f"   ⚠ Using MOCK data (avg={avg:.2f} MV)")
        if available:
            print("   ⚠ WARNING: Archiver said available but got mock!")
    else:
        print(f"   ✓ Using REAL data (avg={avg:.2f} MV)")

print("\n" + "=" * 50)
if available:
    print("✓ Archiver is UP - should be using real data")
else:
    print("✓ Archiver is DOWN - correctly using mock data")