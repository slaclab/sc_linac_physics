from datetime import datetime, timedelta, timezone
<<<<<<< HEAD
import matplotlib.pyplot as plt

from sc_linac_physics.utils.archiver import (
    get_values_over_time_range,
    start_mock_archiver,
)

start_mock_archiver()
=======
import requests
import matplotlib.pyplot as plt

from sc_linac_physics.utils.archiver import get_values_over_time_range

>>>>>>> d4170b1 (Add archiver source and test files)

def fmt(dt):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


pv_candidates = [
    "ACCL:L0B:0110:ADES",
    "ACCL:L0B:0110:CUDSTATUS",
    "ACCL:L0B:0110:CUDSEVR",
    "ACCL:L0B:0110:PDES",
]

end = datetime.now(timezone.utc)
<<<<<<< HEAD
start = end - timedelta(days=1)

for pv_name in pv_candidates:
    print(f"Trying {pv_name}")
=======
start = end - timedelta(days=30)

for pv_name in pv_candidates:
    r = requests.get(
        "http://lcls-archapp.slac.stanford.edu/retrieval/data/getData.json",
        params={
            "from": fmt(start),
            "to": fmt(end),
            "pv": [pv_name],
        },
        timeout=10,
    )

    print(f"Trying {pv_name} -> status {r.status_code}")

    if r.status_code != 200:
        print("  no real data for this PV")
        continue
>>>>>>> d4170b1 (Add archiver source and test files)

    data = get_values_over_time_range(
        pv_list=[pv_name],
        start_time=start,
        end_time=end,
    )

    handler = data[pv_name]

    print(f"  points returned: {len(handler.values)}")
    for ts, value in zip(handler.timestamps, handler.values):
        print(f"    {ts} -> {value}")

    if len(handler.values) >= 1:
        plt.figure(figsize=(8, 3))
        plt.scatter(handler.timestamps, handler.values, s=40)
        plt.title(f"Archiver sample for {handler.pv_name}")
        plt.xlabel("Time")
        plt.ylabel("Value")
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()
        break
    else:
        print("  no points returned")