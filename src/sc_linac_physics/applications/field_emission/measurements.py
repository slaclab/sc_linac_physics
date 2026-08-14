import h5py
import re
import pandas as pd
from pathlib import Path
from datetime import datetime

_DATA_DIR = Path(__file__).resolve().parent
input_csv = _DATA_DIR / "All FE measurements by CM.csv"
h5_filename = _DATA_DIR / "field_emission_data_no1.hdf5"


def match_measurement_dates(cryomodule):
    """match cryomodule str to available measurement dates in h5 file"""
    measurements = []
    with h5py.File(h5_filename, "r") as h5f:
        h5_cryo = h5f.get(f"CM{cryomodule}")
        for date in h5_cryo:
            h5_date = datetime.strptime(date, "%Y-%m-%d_%H%M")
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
    formatted_date = datetime.strftime(date, "%Y-%m-%d_%H%M")
    with h5py.File(h5_filename, "r") as h5f:
        h5f_date_group = h5f.get(f"CM{cm}/{formatted_date}")
        if h5f_date_group is None:
            return None
        date = h5f_date_group.attrs["date"]
        formatted_date = datetime.strptime(date, "%m/%d/%y")
        date_str = formatted_date.strftime("%A, %B %d, %Y")
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
    stripped_date = datetime.strftime(date, "%Y-%m-%d_%H%M")
    cav_list = [i + 1 for i, c in enumerate(cav) if c]
    if not cav_list:
        return {}, "", 0
    with h5py.File(h5_filename, "r") as h5f:
        dfs = {}
        for c in cav_list:
            filepath = f"CM{cm}/{stripped_date}/CAV{c}/{readout}"
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
    threshold = 4
    df2 = df.mask(df.iloc[:, 0] < threshold)
    # grab columns corresponding to channels
    idx_list = [i + 1 for i, chan in enumerate(r_channels) if chan]
    x_amplitude = df2.iloc[:, 0]
    rad_cols = df2.iloc[:, idx_list]
    return x_amplitude, rad_cols


if __name__ == "__main__":
    cryo_str = "34"
    cryo = 34
    day = datetime(2025, 5, 1, 16, 33)
    cavi = [True, False, True, True, True, True, True, True]
    # cavi =[True, False, False, False, False, False, False, False]
    reads = "Average"
    r_chan = [True, False, False, False, False, False, False, False]

    data, label, n = find_dataframes(cryo, day, cavi, reads)
    for dat in data.values():
        x_axis, cols = get_columns(dat, r_chan)
        print(x_axis)
        print(cols)
