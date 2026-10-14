import pandas as pd
import matplotlib.pyplot as plt

from sc_linac_physics.applications.field_emission.constants import (
    CAV_RANGE,
    CSV_DATE_FORMAT,
    CSV_OUTPUT_DIR,
    RAD_READ_TYPES,
    RAD_CHAN_RANGE,
)
from sc_linac_physics.utils.archiver import get_series
from sc_linac_physics.utils.sc_linac.decarad import Decarad
from sc_linac_physics.utils.sc_linac.linac import MACHINE

"""
08/06/26 - Kvetta Q
Builds process variables and calls fetch method to request archiver data of cryomodule amplitude (MV)
vs radiation. If time is not listed in .csv, time is start date listed in .csv file + 24 hours. Most
helpful if used after start and stop times for cavities are known (or after running amp_vs_time).
"""


def amplitude_pvs(cryomodule):
    """AACTMEAN of each cavity in the cryomodule, cavity 1 first"""
    cavities = MACHINE.cryomodules[cryomodule].cavities
    return [cavities[cav].aact_pv for cav in CAV_RANGE]


def rad_readout_pvs(decarad, readout):
    """dose rate PV of each decarad head, head 1 first

    "average" is GAMMAAVE, "instant" is GAMMA_DOSE_RATE.
    """
    heads = Decarad(int(decarad)).heads
    if readout == "average":
        return [heads[h].avg_dose_rate_pv for h in RAD_CHAN_RANGE]
    if readout == "instant":
        return [heads[h].raw_dose_rate_pv for h in RAD_CHAN_RANGE]
    raise ValueError(f"Unknown readout type: {readout}")


def align_pvs_to_common_time(series):
    """join each PV's valid samples onto one shared timebase

    series: PV name -> Series indexed by timestamp, from get_series. Each PV
    keeps its first sample at a repeated timestamp. Rows are carried forward
    to every other PV's timestamps, and rows before any PV's first sample are
    dropped.
    """
    deduped = {
        pv: s[~s.index.duplicated(keep="first")].sort_index()
        for pv, s in series.items()
    }
    aligned = pd.concat(deduped, axis=1, sort=True)
    aligned = aligned.ffill()
    aligned = aligned.dropna(how="any")
    # update_h5py.convert_to_h5 drops this column by name.
    aligned.index.name = "timestamps"
    return aligned


def plot_amp_vs_rad(aligned_data):
    """plot amplitude on x-axis, radiation on y-axis"""
    x_axis = aligned_data.iloc[
        :, 0
    ]  # all rows, first column (amp data lives here)
    rad_cols = aligned_data.columns[
        1:
    ]  # all columns after first (radmon channels live here)
    fig, ax = plt.subplots()
    for col in rad_cols:
        ax.scatter(x_axis, aligned_data[col], label=col, marker=".")
    ax.set_title(aligned_data.columns[0])
    ax.set_xlabel("Amplitude (MV)")
    ax.set_ylabel("Radiation")
    ax.legend()
    # plt.show()  # uncomment if you'd like to visualize
    plt.close(fig)


def generate_amp_vs_rad_csvs(cm, start, end, decarad):
    """fetch one run and write a CSV per cavity and readout

    Every cavity shares the decarad PVs, so each distinct PV is fetched once:
    8 amplitudes + 10 heads x 2 readouts, 28 PVs, in parallel by get_series.
    """
    print(f"Processing CM{cm} {start} -> {end}")
    csv_date = start.strftime(CSV_DATE_FORMAT)
    amp_pvs = amplitude_pvs(cm)
    rad_pvs = {
        readout: rad_readout_pvs(decarad, readout) for readout in RAD_READ_TYPES
    }
    all_pvs = amp_pvs + [pv for pvs in rad_pvs.values() for pv in pvs]
    fetched = get_series(all_pvs, start, end)

    for readout in RAD_READ_TYPES:
        for cav_num, amp_pv in enumerate(amp_pvs, start=1):
            series = {pv: fetched[pv] for pv in [amp_pv] + rad_pvs[readout]}
            aligned_time_data = align_pvs_to_common_time(series)
            csv_path = (
                CSV_OUTPUT_DIR
                / f"cm{cm}_{csv_date}_cavity{cav_num}_{readout}.csv"
            )
            aligned_time_data.to_csv(csv_path)
