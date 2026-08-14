from datetime import datetime, timedelta
from sc_linac_physics.utils.archiver.mock import mock_get_values_over_time_range
s = datetime(2024, 1, 1); e = s + timedelta(minutes=1)
for shape in ["flat", "linear", "parabolic", "sine"]:
    v = mock_get_values_over_time_range(["X:ADES"], s, e, trend=shape, trend_amplitude=5, noise_scale=0)["X:ADES"].values
    print(f"{shape:10} first={v[0]:.2f} mid={v[len(v)//2]:.2f} last={v[-1]:.2f}")