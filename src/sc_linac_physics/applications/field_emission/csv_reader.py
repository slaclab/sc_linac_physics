import csv
from datetime import datetime, timedelta

"""
07/01/26 - Kvetta Q
Reads .csv (structured: COMMENT, CRYOMODULE, DATE MM/DD/YY, START_TIME, STOP_TIME, DECARAD)
and calls fetch method to request archiver data of cryomodule amplitude (MV) vs time where
time is start date listed in .csv file + 24 hours. YIELDS (not returns) cryomodule, date,
start, and stop times. Also includes raw data fetch. Be sure to use both as loop.
"""


def read_from_csv(filepath):
    """yield formatted data for columns of each valid csv row"""
    with open(filepath) as file:
        reader = csv.reader(file)

        # skip header row
        next(reader)

        for row in reader:
            if row[0] == "#":  # skip columns where data was misread
                continue
            cm = row[1][2:]
            try:
                date = datetime.strptime(row[2], "%m/%d/%y")
            except (ValueError, IndexError):
                # print(f"Row malformed, skipping row:\n{row}")
                continue

            if row[3] == "":
                start_date = date
                end_date = start_date + timedelta(days=1)
            else:
                start_date = datetime.strptime(
                    f"{row[2]} {row[3]}", "%m/%d/%y %H:%M"
                )
                if row[4] == "":
                    end_date = datetime.strptime(
                        f"{row[2]} {row[5]}", "%m/%d/%y %H:%M"
                    )
                else:
                    end_date = datetime.strptime(
                        f"{row[4]} {row[5]}", "%m/%d/%y %H:%M"
                    )

            timestamp = start_date.strftime("%y_%m_%d_%H_%M")
            decarad = row[6] if row[6] is not None else ""
            yield cm, decarad, start_date, end_date, timestamp


def read_raw_data(filepath):
    """yield unmodified data from columns of each valid csv row"""
    with open(filepath) as file:
        reader = csv.reader(file)

        # skip header row
        next(reader)

        for row in reader:
            if row[0] == "#":  # skip columns where data was misread
                continue
            cm = row[1][2:]
            try:
                date = datetime.strptime(row[2], "%m/%d/%y")
            except ValueError, IndexError:
                # print(f"Row malformed, skipping row:\n{row}")
                continue

            date = row[2]
            start = row[3]
            stop = row[5]
            decarad = row[6] if row[6] is not None else ""
            log = row[7] if row[7] is not None else ""
            notes = row[8] if row[8] is not None else ""
            yield cm, date, start, stop, decarad, log, notes
