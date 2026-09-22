import h5py
import re
import pandas as pd

from datetime import datetime
from sc_linac_physics.applications.field_emission.constants import (
    H5_PATH,
    H5_DATE_FORMAT,
    H5_MEASUREMENT_PATH,
    H5_READOUT_PATH,
    DISPLAY_DATE_FORMAT,
    AMPLITUDE_THRESHOLD,
)


def match_measurement_dates(cryomodule):
    """match cryomodule str to available measurement dates in h5 file"""
    measurements = []
    with h5py.File(H5_PATH, "r") as h5f:
        h5_cryo = h5f.get(f"CM{cryomodule}")
        if h5_cryo is None:
            return []
        for date in h5_cryo:
            h5_date = datetime.strptime(date, H5_DATE_FORMAT)
            display_str = f"CM{cryomodule}    {h5_date}"
            measurements.append(
                {
                    "display": display_str,
                    "cm": cryomodule,
                    "date": h5_date,
                }
            )
    return measurements


def fetch_measurement_metadata(cm, date):
    """use measurement to find metadata about selected measurement date from h5 file"""
    h5_date = datetime.strftime(date, H5_DATE_FORMAT)
    with h5py.File(H5_PATH, "r") as h5f:
        h5f_date_group = h5f.get(
            H5_MEASUREMENT_PATH.format(cm=cm, date=h5_date)
        )
        if h5f_date_group is None:
            return None
        date = h5f_date_group.attrs["date"]
        formatted_date = datetime.strptime(date, "%m/%d/%y")
        date_str = formatted_date.strftime(DISPLAY_DATE_FORMAT)
        return (
            date_str,
            h5f_date_group.attrs["time_start"],
            h5f_date_group.attrs["time_end"],
            h5f_date_group.attrs["decarad"],
            h5f_date_group.attrs["elog"],
            h5f_date_group.attrs["notes"],
        )


def find_dataframes(cm, date, cav, read):
    """search h5 file for matching datasets to create dataframes for plotting"""
    readout = read.lower()
    h5_date = datetime.strftime(date, H5_DATE_FORMAT)
    cav_list = [i + 1 for i, c in enumerate(cav) if c]
    if not cav_list:
        return {}, "", 0
    with h5py.File(H5_PATH, "r") as h5f:
        dfs = {}
        for c in cav_list:
            filepath = H5_READOUT_PATH.format(
                cm=cm, date=h5_date, cav=c, readout=readout
            )
            dataset = h5f[filepath]
            df = pd.DataFrame(dataset)
            dfs[c] = df

        columns = dataset.attrs["columns"]
        amp_label = columns[0]
        amp_label_parts = amp_label.split(":")
        title = ":".join(amp_label_parts[:3])
        if len(cav_list) > 1:
            # ex: "ACCL:L1B:0310" → "ACCL:L1B:03x0" for multiple cavities
            title = re.sub(r"(:\d+)(\d)0", r"\1x0", title)
        num = len(dfs)

    return dfs, title, num


def get_columns(df, r_channels):
    # eliminate rows under active amplitude threshold voltage
    threshold = AMPLITUDE_THRESHOLD
    df2 = df.mask(df.iloc[:, 0] < threshold)
    # grab columns corresponding to channels
    idx_list = [i + 1 for i, chan in enumerate(r_channels) if chan]
    x_amplitude = df2.iloc[:, 0]
    rad_cols = df2.iloc[:, idx_list]
    return x_amplitude, rad_cols


def fetch_plot_data(cavity, measurement, readout_type):
    if not measurement or not any(cavity):
        return {}

    # Fetch data for every measurement
    all_results = []
    for m in measurement:
        selected, label, n = find_dataframes(
            m["cm"], m["date"], cavity, readout_type
        )
        all_results.append(
            {
                "measurement": m,
                "dataframes": selected,
                "label": label,
            }
        )
    return all_results
