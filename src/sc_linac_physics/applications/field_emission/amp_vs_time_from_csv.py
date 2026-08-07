import argparse
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from sc_linac_physics.applications.field_emission.csv_reader import read_from_csv
from sc_linac_physics.applications.field_emission.amp_vs_radiation_from_csv import (
    build_amplitude_pvs,
    fetch_pv_data,
    align_pvs_to_common_time,
    file_handling,
)

"""
07/15/26 - Kvetta Q
Reads .csv (structured: COMMENT, CRYOMODULE, DATE MM/DD/YY, START_TIME, STOP_TIME, DECARAD)
and calls fetch method to request archiver data of cryomodule amplitude (MV) vs time. If time
is not listed in .csv, time is start date listed in .csv file + 24 hours. Attempts to trim
data to closest cavity activity window. Not yet perfect trimming.
"""


_DATA_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_CSV = _DATA_DIR / "All FE measurements by CM.csv"
DEFAULT_OUTPUT_FOLDER = _DATA_DIR


def trim_ends(df, tolerance):
    """works to clean data of zero or high constant tails"""
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


def plot_cavity_data(cavity_data, cryomodule, timestamp, output_path):
    """plot amplitude vs time for cavities of listed cryomodules"""
    if cavity_data.empty:
        print("Cavity data is empty, skipping plot")
    else:
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
            f"/{output_path}/amp_plot_cm{cryomodule}_{timestamp}.png"
        )
        plt.close(fig)
    return


def main():
    summary = "Plot amplitude vs time from .csv file"
    arg = file_handling(summary)

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
    # csv_path = args.output / f"amplitudes_{cryo}_{stamp}.csv"
    # aligned_data.to_csv(csv_path)
    # plot_cavity_data(aligned_data, cryo, stamp, args.output)

    # Process
    for cryo, _, start, end, stamp in read_from_csv(arg.input):
        print(f"Processing CM{cryo} {start} -> {end}")
        amplitude_pvs = build_amplitude_pvs(cryo)
        dataframes = fetch_pv_data(amplitude_pvs, start, end)
        aligned_data = align_pvs_to_common_time(dataframes)
        # aligned_data = trim_ends(aligned_data, 0.8)
        csv_path = arg.output / f"amplitudes_{cryo}_{stamp}.csv"
        aligned_data.to_csv(csv_path)
        plot_cavity_data(aligned_data, cryo, stamp, arg.output)


if __name__ == "__main__":
    main()









