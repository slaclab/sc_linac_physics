import os
import re
import glob
import h5py
import pandas as pd
from pathlib import Path
from sc_linac_physics.applications.field_emission.amp_vs_radiation_from_csv import (file_handling)

"""
07/13/26 - Kvetta Q
Converts .CSVs from amp_vs_radiation_from_csv.py, contained in central location or folder,
to .hdf5 file. Follows CM --> DATE --> CAVITY --> AVERAGE READOUT/INSTANT READOUT hierarchy for
a folder of .CSVs with specific naming convention. ex: cm08_23_10_06_08_42_cavity7_average.csv.
"""


_DATA_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_CSV = _DATA_DIR
DEFAULT_OUTPUT_FOLDER = _DATA_DIR
INPUT_CSVS = glob.glob(os.path.join(DEFAULT_INPUT_CSV, "*.csv"))
H5_FILENAME = "field_emission_data_test.hdf5"


def main():
    with h5py.File(H5_FILENAME, "a") as h5f:
        for csv_path in INPUT_CSVS:
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

                dset = group.require_dataset(
                    f"{readout_type}",
                    shape=values.shape,
                    dtype=values.dtype,
                    compression="gzip"
                )
                dset[...] = values
                no_time_df = df.drop(columns="timestamps")
                dset.attrs["columns"] = no_time_df.columns.astype(str).tolist()
                dset.attrs["readout_type"] = readout_type
                dset.attrs["source_file"] = csv_name
                dset.attrs["created"] = str(pd.Timestamp.now())

            else:
                print(f"CSV: {csv_name} has incorrect naming format")
                continue


if __name__ == "__main__":
    summary = "Convert amplitude vs radiation .csv files to .hdf5"
    file_handling(summary)
    main()
