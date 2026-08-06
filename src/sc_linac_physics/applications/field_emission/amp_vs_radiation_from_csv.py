import argparse
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from sc_linac_physics.applications.field_emission.csv_reader import read_from_csv
from sc_linac_physics.utils.sc_linac.linac_utils import (
    build_cavity_pv_prefix,
    LINAC_TUPLES,
)
from lcls_tools.common.data.archiver import get_values_over_time_range

"""
08/06/26 - Kvetta Q
Reads .csv (structured: COMMENT, CRYOMODULE, DATE MM/DD/YY, START_TIME, STOP_TIME, DECARAD)
and calls fetch method to request archiver data of cryomodule amplitude (MV) vs radiation. If time
is not listed in .csv, time is start date listed in .csv file + 24 hours. Most helpful if used
after start and stop times for cavities are known (or after running amp_vs_time).
"""


_DATA_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_CSV = _DATA_DIR / "All FE measurements by CM.csv"
DEFAULT_OUTPUT_FOLDER = _DATA_DIR


def is_date_valid(start_date, end_date):
    """end date before start date ->  send error"""
    if start_date > end_date:
        raise ValueError("Start date is greater than end date")
    return start_date, end_date


def build_amplitude_pvs(cryomodule):
    """AACTMEAN amplitudes for each cavity to be plotted against"""
    amplitude_pv = []
    sel_linac = next(
        (linac for linac, cms in LINAC_TUPLES if cryomodule in cms), "L1B"
    )

    for cavity in range(1, 9):
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
        s = pd.Series(df["values"].values, index=df["timestamps"])
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


def file_handling(summary_str):
    """establish input and output folders"""
    parser = argparse.ArgumentParser(summary_str)
    parser.add_argument("-i", "--input",
                        type=Path,
                        default=DEFAULT_INPUT_CSV,
                        help="Path to the input file(s)")
    parser.add_argument("-o", "--output",
                        type=Path,
                        default=DEFAULT_OUTPUT_FOLDER,
                        help="Path to the output folder")
    args = parser.parse_args()
    if not args.input.exists():
        raise FileNotFoundError(f"Input file not found at {args.input}")
    args.output.mkdir(parents=True, exist_ok=True)
    return args


def main():
    summary = "Plot amplitude vs radiation from .csv file"
    arg = file_handling(summary)

    rad_chans = list(range(1, 11))
    rad_readout = "average"
    # cryomod: str = "18"
    # dec = 2
    # start = datetime(2025,2,6,14,17)
    # end = datetime(2025,2,6,15,4)
    # delta = timedelta(seconds=1)

    for cryomod, dec, start, end, stamp in read_from_csv(arg.input):
        print(f"Processing CM{cryomod} {start} -> {end}")
        amp_pvs = build_amplitude_pvs(cryomod)
        rad_pvs = build_rad_readout_pvs(dec, rad_chans, rad_readout)

        pv_lists = []
        for amp_pv in amp_pvs:
            pv_lists.append([amp_pv] + rad_pvs)

        for i, p_list in enumerate(pv_lists):
            cav_num = i + 1
            dataframes = fetch_pv_data(p_list, start, end)
            aligned_time_data = align_pvs_to_common_time(dataframes)
            csv_path = arg.output / f"cm{cryomod}_{stamp}_cavity{cav_num}_{rad_readout}.csv"
            aligned_time_data.to_csv(csv_path)
    #        plot_amp_vs_rad(aligned_time_data)


if __name__ == "__main__":
    main()