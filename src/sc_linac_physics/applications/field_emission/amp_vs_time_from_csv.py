import numpy as np
import matplotlib.pyplot as plt
from csv_reader import read_from_csv
from amp_vs_radiation import fetch_pv_data, align_pvs_to_common_time
from sc_linac_physics.utils.sc_linac.linac_utils import (
    build_cavity_pv_prefix,
    LINAC_TUPLES,
)

"""
07/15/26 - Kvetta Q
Reads .csv (structured: COMMENT, CRYOMODULE, DATE MM/DD/YY, START_TIME, STOP_TIME, DECARAD)
and calls fetch method to request archiver data of cryomodule amplitude (MV) vs time. If time
is not listed in .csv, time is start date listed in .csv file + 24 hours. Attempts to trim
data to closest cavity activity window. Not yet perfect trimming.
"""

input_csv = "All Comm measurements by CM.csv"


def build_amplitude_pvs(cryomodule):
    # TODO """fill"""
    amplitude_pv = []
    sel_linac = next(
        (linac for linac, cms in LINAC_TUPLES if cryomodule in cms), "L1B"
    )

    for cavity in range(1, 9):
        amplitude_pv.append(
            build_cavity_pv_prefix(sel_linac, cryomodule, cavity) + "AACTMEAN"
        )
    return amplitude_pv


def trim_ends(df, tolerance):
    # TODO """fill"""
    df = df.copy()
    vals = df.values

    is_head = np.isclose(vals, 0.0, atol=tolerance) | np.isclose(
        vals, df.iloc[0].values, atol=tolerance
    )
    is_tail = np.isclose(vals, 0.0, atol=tolerance) | np.isclose(
        vals, df.iloc[-1].values, atol=tolerance
    )

    head_null = is_head.cumprod(axis=0).astype(bool)
    tail_null = np.flip(
        np.flip(is_tail, axis=0).cumprod(axis=0), axis=0
    ).astype(bool)

    null_mask = head_null | tail_null
    is_null = ~null_mask.all(axis=1)
    try:
        first_real_data = np.where(is_null)[0].min()
    except (ValueError, IndexError):
        first_real_data = 0
    try:
        last_real_data = np.where(is_null)[-1].max()
    except (ValueError, IndexError):
        last_real_data = -2
    df = df.iloc[first_real_data : last_real_data + 1]
    return df


def plot_cavity_data(cavity_data, cryomodule, timestamp):
    # TODO """fill"""
    if not cavity_data.empty:
        fig, ax = plt.subplots()
        for i, col in enumerate(cavity_data.columns):
            ax.plot(
                cavity_data.index, cavity_data[col], label=f"Cavity {i + 1}"
            )
        ax.set_title(cavity_data.columns[0])
        ax.set_ylabel("Amplitude (MV)")
        fig.autofmt_xdate()
        ax.legend(loc="lower right")
        #   plt.show()
        fig.savefig(
            f"/Users/kvetta/sc-rad/cropped_comm/amp_plot_cm{cryomodule}_{timestamp}.png"
        )
        plt.close(fig)
    else:
        print("Cavity data is empty, skipping plot")
        pass
    return


if __name__ == "__main__":
    # INDIVIDUAL CASE
    # cr = 8
    # cryo = f"{cr:02d}"
    # start = datetime(2023, 10, 6, 8, 0)
    # end = datetime(2023, 10, 6, 9, 30)
    # stamp = start.strftime("%y_%m_%d")
    #
    # read_from_csv(input_csv)
    # print(f"Processing CM{cryo} {start} -> {end}")
    # amplitude_pvs = build_amplitude_pvs(cryo)
    # dataframes = fetch_pv_data(amplitude_pvs, start, end)
    # aligned_data = align_pvs_to_common_time(dataframes)
    # aligned_data = trim_ends(aligned_data, 0.8)
    # aligned_data.to_csv(f"/Users/kvetta/sc-rad/extra_run/amplitudes_cm{cryo}_{stamp}.csv")
    # plot_cavity_data(aligned_data, cryo, stamp)

    for cryo, _, start, end, stamp in read_from_csv(input_csv):
        print(f"Processing CM{cryo} {start} -> {end}")
        amplitude_pvs = build_amplitude_pvs(cryo)
        dataframes = fetch_pv_data(amplitude_pvs, start, end)
        aligned_data = align_pvs_to_common_time(dataframes)
        # aligned_data = trim_ends(aligned_data, 0.8)
        aligned_data.to_csv(
            f"/Users/kvetta/sc-rad/cropped_comm/amplitudes_cm{cryo}_{stamp}.csv"
        )
        plot_cavity_data(aligned_data, cryo, stamp)
