# Field Emission

Plots cavity amplitude against decarad radiation for past measurement runs, one plot per cavity.

For how it works — what it plots, where each run's data comes from, how the cache fills and fails — see the explainer: [How the field emission display works](../explainers/field_emission.md).

## Run it

```bash
sc-linac field-emission
```

## Where the data lives

| What | Where |
|---|---|
| Runs known to git | `src/sc_linac_physics/applications/field_emission/field_emission_runs.csv` |
| Runs added from the display | `field_emission/added_runs.csv` |
| Cached run data | `archiver_cache/<pv>/windows/<start>_<end>.parquet`, one file per PV per run, times in UTC |

Both are under `/home/physics/srf/` on Linux and `~/.sc_linac_physics/` on macOS. `archiver_cache/` is shared with other apps that read archived data. A run that ended less than a day ago isn't cached yet, so it is fetched each time.

## Add a run

Click **Add New Data** next to the plot toolbar. Use **Single CM** for one run, or **Multi CMs from CSV** for a file of runs. CSV columns, in order, with a header row:

```
Cryomodule, Start Date, Start Time, End Date, End Time, Decarad #, Link to Measurement, Notes, Recharacterization, Multipacting, Commissioning
```

- Dates are `mm/dd/yy`, times `hh:mm` (24 h). Leave End Date empty when the run ends on its start date.
- Times are Pacific. A time that daylight saving repeats or skips, such as 1:15 on the fall-back Sunday, is refused.
- Decarad is `1` or `2`. Filters are `Y` or `N`.
- A `#` in the first column skips the row.
- The eLog link may be empty. If given, it must be an `mccelog` link.
- Every row is checked before any is added. The first bad row is reported with its line number.

Added runs are shared by everyone using the same `field_emission/` directory. To make a run permanent for every installation, add its row to `field_emission_runs.csv` in a PR.

## Files

| File | Role |
|---|---|
| `field_emission_gui.py` | The display |
| `run_cache.py` | Run list; reads each run through the archiver cache |
| `amp_vs_radiation.py` | Fetches and aligns one run's PVs |
| `measurements.py` | Lists runs and loads their data for the display |
| `plot_me.py` | Plotting and the fit line |
| `gui_updater.py` | Validates Add New Data input; adds and fetches runs |
| `add_run_dialogs.py` | The Add New Data dialogs |
