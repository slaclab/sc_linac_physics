import re
import pandas as pd

from sc_linac_physics.applications.field_emission.constants import (
    DISPLAY_DATE_FORMAT,
    AMPLITUDE_THRESHOLD,
)
from sc_linac_physics.applications.field_emission.run_cache import (
    find_run,
    load_run,
    read_run_list,
)


def match_measurement_dates(cryomodule):
    """runs in the run list for a cryomodule, oldest first"""
    return [
        {
            "display": f"CM{run.cm}    {run.start}",
            "cm": run.cm,
            "date": run.start,
        }
        for run in read_run_list()
        if run.cm == cryomodule
    ]


def fetch_measurement_metadata(cm, date):
    """date, start, end, decarad, elog and notes of a run, for display"""
    run = find_run(cm, date, read_run_list())
    if run is None:
        return None
    return (
        run.start.strftime(DISPLAY_DATE_FORMAT),
        run.start_text,
        run.end_text,
        run.decarad,
        run.elog,
        run.notes,
    )


def find_dataframes(cm, date, cav, read):
    """dataframes of the selected cavities of one run, for plotting

    Fetches the run from the archiver if it is not cached yet, so this can
    block for seconds to minutes. Keep it off the Qt main thread.
    """
    readout = read.lower()
    cav_list = [i + 1 for i, c in enumerate(cav) if c]
    if not cav_list:
        return {}, "", 0
    run = find_run(cm, date, read_run_list())
    if run is None:
        return {}, "", 0

    data = load_run(run)
    dfs = {}
    for c in cav_list:
        values, columns = data[c, readout]
        # Integer column labels: plot_amp_vs_rad numbers channels by them
        dfs[c] = pd.DataFrame(values)
    amp_label = columns[0]
    amp_label_parts = amp_label.split(":")
    title = ":".join(amp_label_parts[:3])
    if len(cav_list) > 1:
        # ex: "ACCL:L1B:0310" → "ACCL:L1B:03x0" for multiple cavities
        title = re.sub(r"(:\d+)(\d)0", r"\1x0", title)
    return dfs, title, len(dfs)


def get_columns(df, r_channels):
    """get selected columns from dataframe, masking setup amplitude"""
    # eliminate rows under active amplitude threshold voltage
    threshold = AMPLITUDE_THRESHOLD
    df2 = df.mask(df.iloc[:, 0] < threshold)
    # grab columns corresponding to channels
    idx_list = [i + 1 for i, chan in enumerate(r_channels) if chan]
    x_amplitude = df2.iloc[:, 0]
    rad_cols = df2.iloc[:, idx_list]
    return x_amplitude, rad_cols


def fetch_plot_data(cavity, measurement, readout_type):
    """grab amplitude and radiation data from all selected measurements"""
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
