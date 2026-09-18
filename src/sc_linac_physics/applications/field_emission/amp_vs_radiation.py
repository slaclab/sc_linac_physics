import pandas as pd
import matplotlib.pyplot as plt

from sc_linac_physics.applications.field_emission.constants import (
    CAV_RANGE,
    CSV_DATE_FORMAT,
    CSV_OUTPUT_DIR,
    RAD_READ_TYPES,
    RAD_CHAN_RANGE,
)
from sc_linac_physics.utils.sc_linac.linac_utils import (
    build_cavity_pv_prefix,
    LINAC_TUPLES,
)
from lcls_tools.common.data.archiver import get_values_over_time_range

"""
08/06/26 - Kvetta Q
Builds process variables and calls fetch method to request archiver data of cryomodule amplitude (MV)
vs radiation. If time is not listed in .csv, time is start date listed in .csv file + 24 hours. Most
helpful if used after start and stop times for cavities are known (or after running amp_vs_time).
"""


def build_amplitude_pvs(cryomodule):
    """AACTMEAN amplitudes for each cavity to be plotted against"""
    amplitude_pv = []
    sel_linac = next(
        (linac for linac, cms in LINAC_TUPLES if cryomodule in cms), "L1B"
    )

    for cavity in CAV_RANGE:
        amplitude_pv.append(
            build_cavity_pv_prefix(sel_linac, cryomodule, cavity) + "AACTMEAN"
        )
    return amplitude_pv


def build_decarad_pvs(decarad):
    """for each selected radmon channel generate pv for radiation channel(s)"""
    rad_pv_prefix = f"RADM:SYS0:{decarad}00:"
    decarad_position = rad_pv_prefix + "POSN"
    decarad_hvmon = rad_pv_prefix + "HVMON"
    return rad_pv_prefix, decarad_position, decarad_hvmon


def build_rad_readout_pvs(decarad, rad_channels, rad_readout_type):
    """choose radmon readout suffix depending on selection (instant vs average)"""
    rad_readout_type = rad_readout_type.lower()
    rad_readout_pvs = []
    rad_prefix, _, _ = build_decarad_pvs(decarad)
    if rad_readout_type == "instant":
        for sel_rad_channel in rad_channels:
            rad_readout_pv = (
                rad_prefix + f"{sel_rad_channel:02d}:GAMMA_DOSE_RATE"
            )
            rad_readout_pvs.append(rad_readout_pv)
    elif rad_readout_type == "average":
        for sel_rad_channel in rad_channels:
            rad_readout_pv = rad_prefix + f"{sel_rad_channel:02d}:GAMMAAVE"
            rad_readout_pvs.append(rad_readout_pv)
    else:
        raise ValueError(f"Unknown readout type: {rad_readout_type}")
    return rad_readout_pvs


def fetch_pv_data(pv_list, start_date, end_date):
    """fetch amplitudes and radiation within date range and store"""
    dfs = {}
    data_handler = get_values_over_time_range(
        pv_list, start_date, end_date, time_delta=None, timeout=90
    )
    for pv_name, raw_data in data_handler.items():
        handler = data_handler[pv_name]
        df = pd.DataFrame(
            {
                "timestamps": handler.timestamps,
                "values": handler.values,
                "is_valid": handler.validities,
            }
        )
        dfs[pv_name] = df
    return dfs


def align_pvs_to_common_time(dfs):
    """join dataframes (dict of dicts) to common master timebase"""
    series_per_pv = {}
    for pv_name, df in dfs.items():
        valid = df["is_valid"].astype(bool)
        s = pd.Series(
            df.loc[valid, "values"].to_numpy(),
            index=df.loc[valid, "timestamps"],
        )
        s = s[~s.index.duplicated(keep="first")]
        s = s.sort_index()
        series_per_pv[pv_name] = s
    aligned = pd.concat(series_per_pv, axis=1, sort=True)
    aligned = aligned.ffill()
    aligned = aligned.dropna(how="any")
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
    """combine methods for portable amplitude and radiation generation"""
    print(f"Processing CM{cm} {start} -> {end}")
    csv_date = start.strftime(CSV_DATE_FORMAT)
    amp_pvs = build_amplitude_pvs(cm)
    for readout in RAD_READ_TYPES:
        rad_pvs = build_rad_readout_pvs(decarad, RAD_CHAN_RANGE, readout)

        pv_lists = []
        for amp_pv in amp_pvs:
            pv_lists.append([amp_pv] + rad_pvs)

        for i, p_list in enumerate(pv_lists):
            cav_num = i + 1
            dataframes = fetch_pv_data(p_list, start, end)
            aligned_time_data = align_pvs_to_common_time(dataframes)
            csv_path = (
                CSV_OUTPUT_DIR
                / f"cm{cm}_{csv_date}_cavity{cav_num}_{readout}.csv"
            )
            aligned_time_data.to_csv(csv_path)
