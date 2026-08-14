import csv
import os
import re
import glob
import h5py
import pandas as pd

"""
07/13/26 - Kvetta Q
Converts .CSVs from amp_vs_radiation_from_csv.py to .hdf5 file. Follows CM --> DATE --> CAVITY --> AVERAGE
READOUT/INSTANT READOUT hierarchy for a folder of .CSVs with specific naming convention
ex: cm08_23_10_06_08_42_cavity7_average.csv.
"""


input_path = "/Users/kvetta/Desktop/combined_data/"
input_csvs = glob.glob(os.path.join(input_path, "*.csv"))
h5_filename = "field_emission_data.hdf5"
all_cm_csv = "All FE measurements by CM.csv"


metadata_lookup = {}  # key: (cm, month, day, year, hour, minute) -> row
with open(all_cm_csv) as csvfile:
    reader = csv.reader(csvfile)
    next(reader)  # skip header
    for row in reader:
        if len(row) < 12 or row[1] == "#":  # skip malformed rows
            continue
        cm_str = row[1].replace("CM", "").strip()
        try:
            month, day, year = row[2].split("/")
            hour, minute = row[3].split(":")
            # attempt to unify dates with zero padding
            key = (
                cm_str.zfill(2),
                month.zfill(2),
                day.zfill(2),
                year.zfill(2),
                hour.zfill(2),
                minute.zfill(2),
            )
            metadata_lookup[key] = row
        except (ValueError, IndexError):
            print(f"Malformed CSV row: {row}")

with h5py.File(h5_filename, "a") as h5f:
    for csv_path in input_csvs:
        csv_name = os.path.basename(csv_path)

        match = re.fullmatch(
            r"cm(\d+|\w+)_(\d+_\d+_\d+_\d+_\d+)_cavity(\d+)_(\w+)\.csv",
            csv_name,
        )
        if match:
            cm = match.group(1)
            raw_date = match.group(2)
            yy, mo, dd, hh, mn = raw_date.split("_")
            date = f"20{yy}-{mo}-{dd}_{hh}{mn}"
            cav = match.group(3)
            readout_type = match.group(4)

            # read matching .csv and grab values
            df = pd.read_csv(csv_path)
            values = df.drop(columns="timestamps").to_numpy(dtype="float64")

            # define attributes at the date level
            date_group = h5f.require_group(f"CM{cm}/{date}")
            date_group.attrs["cryomodule"] = cm
            date_group.attrs["cavity"] = cav

            key = (cm, mo, dd, yy, hh, mn)
            if key in metadata_lookup:
                row = metadata_lookup[key]
                date_group.attrs["date"] = row[2]
                date_group.attrs["time_start"] = row[3]
                if row[4]:
                    date_group["date_end"] = row[4]
                date_group.attrs["time_end"] = row[5]
                date_group.attrs["decarad"] = row[6]
                date_group.attrs["elog"] = row[7]
                date_group.attrs["notes"] = row[8]
                date_group.attrs["filter_rechar"] = row[9]
                date_group.attrs["filter_multipacting"] = row[10]
                date_group.attrs["filter_commissioning"] = row[11]
            else:
                print(f"No CSV metadata match for {csv_name}: key={key}")

            # store dataset at the cavity/readout level
            cav_group = h5f.require_group(f"CM{cm}/{date}/CAV{cav}")
            dset = cav_group.require_dataset(
                f"{readout_type}",
                shape=values.shape,
                dtype=values.dtype,
                compression="gzip",
            )
            dset[...] = values
            no_time_df = df.drop(columns="timestamps")

            # define attributes at the readout level
            dset.attrs["columns"] = no_time_df.columns.astype(str).tolist()
            dset.attrs["readout_type"] = readout_type
            dset.attrs["source_file"] = csv_name
            dset.attrs["created"] = str(pd.Timestamp.now())
        else:
            print(f"CSV: {csv_name} has incorrect naming format")
            continue
