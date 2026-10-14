import csv
import os
import re
import glob
import h5py
import pandas as pd

from sc_linac_physics.applications.field_emission.constants import (
    H5_PATH,
    CSV_OUTPUT_DIR,
    DATA_CSV_NAME_PATTERN,
)

"""
07/13/26 - Kvetta Q
Converts .CSVs from amp_vs_radiation_from_csv.py to .hdf5 file. Follows CM --> DATE --> CAVITY
--> AVERAGE READOUT/INSTANT READOUT hierarchy for a folder of .CSVs with specific naming convention
ex: cm08_23_10_06_08_42_cavity7_average.csv.
"""


def parse_csv(all_cm_csv):
    """build metadata lookup table from a csv with row summary of cryomodule data"""
    metadata_lookup = {}  # key: (cm, month, day, year, hour, minute) -> csv row
    try:
        with open(all_cm_csv) as csvfile:
            reader = csv.reader(csvfile)
            next(reader)  # skip header
            for row in reader:
                if "#" in row[0]:  # skip commented rows
                    continue
                cm_str = row[0].replace("CM", "").strip()
                try:
                    key = _format_metadata_lookup_key(cm_str, row[1], row[2])
                    metadata_lookup[key] = row
                except (ValueError, IndexError):
                    print(f"Malformed CSV row: {row}")
    except FileNotFoundError:
        print("No such file or directory")
        return {}
    return metadata_lookup


def receive_metadata_input(input_row):
    """build metadata lookup table (row) from singular row input"""
    metadata_lookup = {}  # key: (cm, month, day, year, hour, minute) -> row

    cm_str = input_row[0].strip().upper()
    try:
        key = _format_metadata_lookup_key(cm_str, input_row[1], input_row[2])
        metadata_lookup[key] = input_row
    except ValueError:
        pass  # if date or time missing/corrupted, skip and provide empty lookup
    return metadata_lookup


def convert_to_h5(metadata_lookup):
    """convert metadata lookup table to h5 addition"""
    input_csvs = glob.glob(os.path.join(CSV_OUTPUT_DIR, "*.csv"))

    with h5py.File(H5_PATH, "a") as h5f:
        for csv_path in input_csvs:
            csv_name = os.path.basename(csv_path)

            match = re.fullmatch(
                DATA_CSV_NAME_PATTERN,
                csv_name,
            )
            if not match:
                print(f"CSV: {csv_name} has incorrect naming format")
                continue

            cm = match.group(1)
            raw_date = match.group(2)
            yy, mo, dd, hh, mn = raw_date.split("_")
            date = f"20{yy}-{mo}-{dd}_{hh}{mn}"
            cav = match.group(3)
            readout_type = match.group(4)

            # make dict key from csv file name and check for lookup presence
            key = (cm, mo, dd, yy, hh, mn)
            if key not in metadata_lookup:
                print(f"No CSV metadata match for {csv_name}: key={key}")
                continue

            # read matching .csv and grab values
            row = metadata_lookup[key]
            df = pd.read_csv(csv_path)
            values = df.drop(columns="timestamps").to_numpy(dtype="float64")

            # make key from csv title and match to a row in lookup for attribute assignment
            date_group = h5f.require_group(f"CM{cm}/{date}")
            _set_metadata_attributes(date_group, row)

            # store dataset at the cavity/readout level
            cav_group = h5f.require_group(f"CM{cm}/{date}/CAV{cav}")
            _write_dataset_with_attributes(
                cav_group, df, values, csv_name, readout_type, cav
            )


def _format_metadata_lookup_key(cm_str, date, time):
    """standardize entries to unify dates"""
    month, day, year = date.split("/")
    hour, minute = time.split(":")
    # attempt to unify dates with zero padding
    key = (
        cm_str.zfill(2),
        month.zfill(2),
        day.zfill(2),
        year.zfill(2),
        hour.zfill(2),
        minute.zfill(2),
    )
    return key


def _set_metadata_attributes(group, row):
    """define attributes at the date level"""
    if (
        "cryomodule" not in group.attrs
    ):  # avoiding setting attributes twice between readouts
        group.attrs["cryomodule"] = row[0].replace("CM", "").strip()
        group.attrs["date"] = row[1]
        group.attrs["time_start"] = row[2]
        if row[3]:
            group.attrs["date_end"] = row[3]
        group.attrs["time_end"] = row[4]
        group.attrs["decarad"] = row[5]
        group.attrs["elog"] = row[6]
        group.attrs["notes"] = row[7]
        group.attrs["filter_rechar"] = row[8]
        group.attrs["filter_multipacting"] = row[9]
        group.attrs["filter_commissioning"] = row[10]


def _write_dataset_with_attributes(group, df, values, csv_name, readout, cav):
    """add data and assign attributes at the dataset level"""
    dset = group.require_dataset(
        f"{readout}",
        shape=values.shape,
        dtype=values.dtype,
        compression="gzip",
    )
    dset[...] = values
    no_time_df = df.drop(columns="timestamps")

    # define attributes at the readout level
    dset.attrs["cavity"] = cav
    dset.attrs["columns"] = no_time_df.columns.astype(str).tolist()
    dset.attrs["readout_type"] = readout
    dset.attrs["source_file"] = csv_name
    dset.attrs["created"] = str(pd.Timestamp.now())
