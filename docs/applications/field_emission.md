# README

The purpose of the GUI is to aid in the visualization and characterization of field emission from linac cavities. This collection of scripts is to generate the appropriate data files, update, and run the field emission GUI.

Radiation data is collected by one of two decarads with 10 channels each and is recorded in the archiver. The display fetches each run from the archiver once and keeps it in a local cache, so runs stay viewable when the archiver is down.

The collection consists of:

## GUI Suite

- **`field_emission_runs.csv`**: the runs known to git, one row per run, in the "To Add Data" column order below.

- **The run cache**, in `get_field_emission_dir()`: `/home/physics/srf/field_emission/` on Linux, `~/.sc_linac_physics/field_emission/` on macOS.
  - `runs/cm<CM>_<YYYY-MM-DD_HHMM>.h5`: one file per run, fetched from the archiver the first time the run is needed. Datasets `CAV<n>/average` and `CAV<n>/instant`: first column cavity amplitude, then decarad channels 1–10. Safe to delete; a deleted run is fetched again.
  - `added_runs.csv`: runs added from the display, same columns as `field_emission_runs.csv`.

- **`field_emission_gui.py`**: the display, launched by `sc-linac field-emission`. On open it fetches every listed run not cached yet, one at a time, with progress in the window title; it stops at the first failure. Plotting a run that isn't cached fetches it first (PLOT shows LOADING...).

- **`run_cache.py`**: reads the run list (committed plus added) and loads each run from the cache, fetching it if needed.

- **`field_emission_gui_update.py`**: holds the "Add New Data" dialogs used by the display.

- **`measurements.py`**: called by `field_emission_gui.py` to list runs and load their data.


- **`plot_me.py`**: called by `field_emission_gui.py` for plotting. Contains the `fit_equation` method, to be further adjusted for improved fit line.


## Additional Scripts

- **`amp_vs_radiation_from_csv.py`**: takes start and end time data to find radiation during active cavity session. Necessary for gui_updater use. Contains the `align_pvs_to_common_time` method, used to give common timebase between process variables which may have inconsistencies in time data.


- **`gui_updater.py`**: validates "Add New Data" input; its worker adds the runs to `added_runs.csv` and fetches them into the cache.


- **`update_h5py.py`**: builds the old bundled `field_emission_data.hdf5` from CSVs. No longer used by the display; to be removed.


## To Add Data

Use the "Add New Data" button next to the plot toolbar in `sc-linac field-emission`. Added runs go into `added_runs.csv` in the cache directory, so everyone using that directory sees them, and are fetched right away. Data can be added individually, by cryomodule, or by CSV for multiple entries.  If using CSV, though actual header names can be anything, columns should be written in the following order:

"Cryomodule, Start Date, Start Time, End Date, End Time, Decarad #, Link to Measurement, Notes, Recharacterization, Multipacting, Commissioning"

The run list refreshes when the dialog closes. To make a run permanent for every installation, add its row to `field_emission_runs.csv` in a PR.

> **NOTE:** CSV reader is written with the expectation of a header row in multi-entry CSV.

> **NOTE:** Including "#" in the first column of a row skips it.

> **NOTE:** A column should be included for end date in the case of overnight operation where the start date and end date will not be the same (albeit only one day apart), regardless of if that column has data.


## Possible Additional Work to Be Done


- **Extra filter for measurement characteristics:** columns have been included in csv reader and gui handler for additional filtering of cryomodule data (recharacterization/multipacting/commissioning). They are kept in the run list. Reflection in display (possibly) necessary.


- **Overlapping Plots:** due to time constraints, the ability to overlap data for further comparison has been excluded. If added, this ability can become a radio button setting in addition to the Amplitude vs Radiation and Fit Line toggles above the Plot button.


## Entry point

```bash
sc-linac field-emission
```
