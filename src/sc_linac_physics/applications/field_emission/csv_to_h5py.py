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


if __name__ == "__main__":
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
                yy, mm, dd, hh, ss = raw_date.split("_")
                date = f"20{yy}-{mm}-{dd}_{hh}{ss}"
                cav = match.group(3)
                readout_type = match.group(4)

                df = pd.read_csv(csv_path)
                values = df.drop(columns="timestamps").to_numpy(dtype="float64")

                group = h5f.require_group(f"CM{cm}/{date}/CAV{cav}")
                group.attrs["cryomodule"] = cm
                group.attrs["cavity"] = cav
                group.attrs["date"] = date

                dset = group.create_dataset(
                    f"{readout_type}", data=values, compression="gzip"
                )
                no_time_df = df.drop(columns="timestamps")
                dset.attrs["columns"] = no_time_df.columns.astype(str).tolist()
                dset.attrs["readout_type"] = readout_type
                dset.attrs["source_file"] = csv_name
                dset.attrs["created"] = str(pd.Timestamp.now())

            else:
                print(f"CSV: {csv_name} has incorrect naming format")
