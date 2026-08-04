import h5py
import re
import pandas as pd
from datetime import datetime
from csv_reader import read_from_csv, read_raw_data

input_csv = "All FE measurements by CM.csv"
h5_filename = "field_emission_data.hdf5"


def match_measurement_dates(cryomodule):
    """match cryomodule to available measurement dates"""
    measurements = []
    for csv_cryo, csv_dec, csv_start, csv_end, csv_stamp in read_from_csv(
        input_csv
    ):
        if cryomodule == csv_cryo:
            display_str = f"CM{csv_cryo}    {csv_start}"
            measurements.append(
                {
                    "display": display_str,
                    "cm": csv_cryo,
                    "date": csv_start,
                }
            )
    return measurements


def fetch_measurement_metadata(cm, date):
    """use measurement to find metadata about selected measurement date"""
    for (
        csv_cryo,
        csv_date,
        csv_start,
        csv_stop,
        csv_dec,
        csv_notes,
        csv_log,
    ) in read_raw_data(input_csv):
        if cm == csv_cryo:
            csv_date_fmt = datetime.strptime(
                f"{csv_date} {csv_start}", "%m/%d/%y %H:%M"
            )
            if csv_date_fmt == date:
                date_str = csv_date_fmt.strftime("%A, %B %d, %Y")
                return (
                    date_str,
                    csv_start,
                    csv_stop,
                    csv_dec,
                    csv_notes,
                    csv_log,
                )
            else:
                continue
    return None


def find_dataframes(cm, date, cav, read):
    """search h5 file for matching datasets to create dataframes for plotting"""
    readout = read.lower()
    stripped_date = datetime.strftime(date, "%Y-%m-%d_%H%M")
    cav_list = [i + 1 for i, c in enumerate(cav) if c]
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
    cryo = 34
    day = datetime(2025, 5, 1, 16, 33)
    cavi = [True, False, True, True, True, True, True, True]
    # cav =[True, False, False, False, False, False, False, False]
    reads = "Average"
    r_chan = [True, False, False, False, False, False, False, False]

    data, label, n = find_dataframes(cryo, day, cavi, reads)
    for dat in data.values():
        x_axis, cols = get_columns(dat, r_chan)
        print(x_axis)
        print(cols)
