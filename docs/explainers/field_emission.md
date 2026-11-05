# How the field emission display works

`applications/field_emission/` plots cavity amplitude against decarad
radiation readings, one plot per cavity, for past measurement runs. This page
covers what the display reads, where each run's data comes from, how runs get
into the shared archiver cache, and how that fails. For the command, paths and how to add
a run, see the [Field Emission](../applications/field_emission.md) page.

## 1. What the display shows

Pick a cryomodule, one or more measurement runs, cavities, decarad channels,
and a readout type. Each plot puts cavity amplitude on the x-axis and one point
series per decarad channel on the y-axis.

[Mockup of the field emission display](widgets/field_emission_display.html)

<span class="cite">`field_emission_gui.py::FieldEmission.build_linac_configuration, field_emission_gui.py::FieldEmission.build_meas_selection, field_emission_gui.py::FieldEmission.build_decarad_configuration, field_emission_gui.py::FieldEmission.build_toolbar “Add New Data”, field_emission_gui.py::FieldEmission._plot_one_date “n_rows = min(2, n)”, field_emission_gui.py::FieldEmission._configure_plot_canvas “Radiation (mR/hr)”`</span>

PLOT stays disabled until at least one cavity, one channel and one measurement
are picked, and while a plot is loading. Selecting several measurements
switches to a grid of cavities × dates.
<span class="cite">`field_emission_gui.py::FieldEmission._refresh_plot_button_state “can_plot and not self._loading”, field_emission_gui.py::FieldEmission._plot_multiple_dates`</span>

| | PV | Notes |
|---|---|---|
| x: amplitude | `ACCL:{linac}:{cm}{cav}0:AACTMEAN` | MV, each cavity's own `AACTMEAN`, taken from the linac model <span class="cite">`field_emission/amp_vs_radiation.py::amplitude_pvs “.aact_pv”, sc_linac/cavity.py::Cavity.aact_pv “self.pv_addr("AACTMEAN")”, field_emission/constants.py::CAVITIES “CAVITIES = 8”`</span> |
| y: radiation, "average" | `RADM:SYS0:{n}00:{ch:02d}:GAMMAAVE` | decarad `n` is 1 or 2, heads 01–10 (see below) <span class="cite">`field_emission/amp_vs_radiation.py::rad_readout_pvs “avg_dose_rate_pv”, sc_linac/decarad.py::Decarad “RADM:SYS0:{num}00:”, sc_linac/decarad.py::DecaradHead.avg_dose_rate_pv “GAMMAAVE”`</span> |
| y: radiation, "instant" | `RADM:SYS0:{n}00:{ch:02d}:GAMMA_DOSE_RATE` | <span class="cite">`field_emission/amp_vs_radiation.py::rad_readout_pvs “raw_dose_rate_pv”, sc_linac/decarad.py::DecaradHead.raw_dose_rate_pv “GAMMA_DOSE_RATE”`</span> |

Every PV is read from the archiver, never live. The display writes no PVs.
<span class="cite">`field_emission/amp_vs_radiation.py::fetch_run “(fetch or get_series)(run_pvs(cm, decarad), start, end)”`</span>

### What it does to the data before you see it

**Rows under 4 MV are dropped.** Any sample where `AACTMEAN` is below
`AMPLITUDE_THRESHOLD = 4` is masked out of both the plot and the fit.
<span class="cite">`field_emission/constants.py::AMPLITUDE_THRESHOLD “AMPLITUDE_THRESHOLD = 4”, field_emission/measurements.py::get_columns “df.mask(df.iloc[:, 0]”`</span>

**The optional fit line** is `rad = C1 · E^2.5 · exp(−C2 / E)`, with `E` the
amplitude in MV, fitted per channel with `scipy.optimize.curve_fit` (5500
evaluations max). Channels with fewer than 2 nonzero points, or that don't
converge, get no line. The legend shows C1 and C2.
<span class="cite">`plot_me.py::fit_equation “c1 * (amp**2.5) * np.exp((-c2) / amp)”, plot_me.py::add_poly_fit “skip fitting when less than two samples”, field_emission/constants.py::NUM_FIT_ITERATIONS “NUM_FIT_ITERATIONS = 5500”`</span>

**No background is subtracted.** The dose is plotted and fitted as archived.
The linac model subtracts a fixed background before using a reading (0.8 for
`GAMMAAVE`, 8 for `GAMMA_DOSE_RATE`). Quench processing uses the subtracted
`GAMMA_DOSE_RATE`. Field emission does not subtract either.
<span class="cite">`linac_utils.py::DECARAD_BACKGROUND_READING_AVG “DECARAD_BACKGROUND_READING_AVG = 0.8”, linac_utils.py::DECARAD_BACKGROUND_READING_RAW “DECARAD_BACKGROUND_READING_RAW = 8”, quench_processing/quench_cavity.py “if self.decarad.max_raw_dose”`</span>

!!! warning "Open questions"

    CHECK: where does this fit form come from, and is 2.5 the intended
    exponent? Nothing in the repo cites a source.

    CHECK: should the fit use background-subtracted dose? That would change C1
    and C2.

    CHECK: is 4 MV the right "cavity is on" cutoff for every cryomodule,
    including LCLS-II-HE?

### Which channel is which

There are two decarads, each with 10 heads
<span class="cite">`sc_linac/decarad.py::Decarad “for head in range(1, 11)”`</span>.
CHECK, from the SRF group, no document: one head sits at each end of the
cryomodule and one at each cavity's tuner access port, and the decarads are
wheeled between cryomodules and set up per run. The archived `POSN` history
below does show them moving. So channel *n* is not tied to any cavity. The run
list records which decarad was used, not how it was set up, and the display
plots every selected channel against every selected cavity. Read the run's elog
to know which head a channel was.

Each head has a text PV naming its position, for example
`RADM:SYS0:100:01:POSN` = "US of Cavity 1, CM01", but those are not archived,
so past runs can't be read back from them. Each decarad's own
`RADM:SYS0:{n}00:POSN` is archived and holds a cryomodule number. It matched
the run list's cryomodule for 76 of 80 runs.

Cavities in one run can overlap in time. In CM06's 2024-02-02 run, CAV3, CAV4
and CAV7 were all above 4 MV at once, so a channel plotted against one of them
can include radiation from the others.

## 2. Where one run's data comes from

A *run* is one row of the run list: a cryomodule, a start and end time, which
decarad was used, and an elog link. The list is `field_emission_runs.csv` in
git plus `added_runs.csv`, which operators add to from the display. A run in
both counts once, as the git row.
<span class="cite">`field_emission/run_cache.py::read_run_list “runs.setdefault((run.cm, run.start), run)”`</span>

1. **Run list row**: `CM01, 10/2/23, 9:13, , 10:00, 1, elog…`. Times are
   naive Pacific, as written.
   <span class="cite">`field_emission/run_cache.py::parse_row, field_emission/run_cache.py::Run “Times are naive Pacific”`</span>
2. **28 PVs read through the archiver store**: 8 `AACTMEAN` + 10 heads × 2
   readouts, each PV once, up to 8 at a time. Each PV's samples for the run's
   exact window come from disk if the store has them, from the archiver if
   not.
   <span class="cite">`field_emission/amp_vs_radiation.py::run_pvs “8 amplitudes, then 10 heads x 2 readouts”, field_emission/run_cache.py::load_run “store.read_windows(pvs, start, end)”, utils/archiver_store.py::ArchiverStore.read_windows “up to max_workers at once”, utils/archiver.py::MAX_WORKERS “MAX_WORKERS = 8”`</span>
3. **Keep valid samples**: samples with INVALID severity are dropped.
   <span class="cite">`utils/archiver.py::series_from_frames “frame.loc[frame["valid"], "value"]”, utils/archiver_store.py::_with_valid “frame["severity"] != EPICS_INVALID_VAL”`</span>
4. **Align, 16 ways**: per cavity × readout, outer-join on timestamp,
   forward-fill, drop any row still missing a value.
   <span class="cite">`field_emission/amp_vs_radiation.py::fetch_run “frames[cav_num, readout] = align_pvs_to_common_time(series)”, field_emission/amp_vs_radiation.py::align_pvs_to_common_time “aligned.ffill()”`</span>

The store keeps the archiver's samples, not the aligned frames. Step 4 runs on
every load, cached or not, so a change to the alignment applies to runs
already cached.
<span class="cite">`field_emission/run_cache.py “so the alignment in amp_vs_radiation.fetch_run runs on every load”`</span>

Measured on CM06's 2024-02-02 run (#513's Testing section, 2026-10-13): 23.4 s
with the archiver cold, 0.09 s once cached. Across runs, a cold archiver took
17–21 s per run through the store and about 1.5 s once warm. No script for
these is in the repo.

### The cache layout

The run cache is the shared archiver cache, the same directory other
analyses read through `ArchiverStore`. Each PV has its own directory. A run's
window is one Parquet file per PV, named by the window's start and end in UTC.

```text
get_archiver_cache_dir()          /home/physics/srf/archiver_cache on Linux
│                                 ~/.sc_linac_physics/archiver_cache on macOS
├── ACCL:L0B:0110:AACTMEAN/       one directory per PV
│   ├── windows/
│   │   └── 20231002T161300.000000Z_20231002T170000.000000Z.parquet
│   │                             CM01's 10/2/23 09:13–10:00 run, in UTC
│   └── 2023-10.parquet           a whole month, if something cached it
├── RADM:SYS0:100:01:GAMMAAVE/
│   └── windows/…
└── … 28 PVs per run

get_field_emission_dir()          /home/physics/srf/field_emission on Linux
└── added_runs.csv                runs added from the display
```

<span class="cite">`utils/archiver_store.py::get_archiver_cache_dir “get_srf_base_dir() / "archiver_cache"”, platform_paths.py::get_srf_base_dir “Path("/home/physics/srf")”, utils/archiver_store.py::ArchiverStore.window_path “<root>/<pv>/windows/<start>_<end>.parquet, times in UTC”, utils/archiver_store.py::ArchiverStore.path “f"{month_start:%Y-%m}.parquet"”, utils/archiver_store.py::ArchiverStore.iter_months “Naive datetimes are read as America/Los_Angeles”, platform_paths.py::get_field_emission_dir, field_emission/constants.py::ADDED_RUNS_PATH`</span>

Each file holds `timestamp`, `value`, `severity` and `status`. `valid` is
worked out from severity on read.
<span class="cite">`utils/archiver_store.py::STORED_COLUMNS “c != "valid"”`</span>
If every month a window touches is already cached as a whole month, the store
reads those instead and writes no window file.
<span class="cite">`utils/archiver_store.py::ArchiverStore.read_window “If those months are all cached already, they are used.”`</span>

The aligned frame puts the amplitude in column 0 and heads 1–10 after it. The
display numbers channels by column position, not by PV name.
<span class="cite">`field_emission/run_cache.py::RunData, field_emission/measurements.py::find_dataframes “pd.DataFrame(values)”, plot_me.py::plot_amp_vs_rad “label = f"Ch {col}"”`</span>
Date, times, elog and notes come from the run list each time, not from the
cache.
<span class="cite">`field_emission/measurements.py::fetch_measurement_metadata “find_run(cm, date, read_run_list())”`</span>

### Checked against the old bundled file

The display used to read a 73.8 MB `field_emission_data.hdf5` shipped inside
the package, built by hand from the same 80 runs (Oct 2023 onward, 37
cryomodules). On 2026-10-07, fetching CM06's 2024-02-02 run directly gave all
16 datasets with the same shapes and columns as the bundled file. #513 then
showed the store gives the same 16 frames as a direct fetch for that run.
Values differ in the last bit for 5–9% of samples (at most 1.8e-15): the
bundled file went through CSVs read back with pandas' default float parser, and
the store keeps what the archiver returns. Three runs in it looked wrong:

- **CM27, dated 2026-10-16**: 1 row in all 16 datasets, and no cavity ever
  above 4 MV. The date was a typo for 2024 (same elog ID as CM27's other
  10/16/24 run), so the archiver was asked about a window in the future. The
  run list in git has the corrected date.
- **CM04 2023-10-25, CAV5 `instant`**: 1 row. The align step drops a timestamp
  until all 11 PVs have had at least one value, so one sparse PV can shrink a
  whole dataset. Here it was CAV5's own `AACTMEAN`. The one value is 0.004 MV,
  so CAV5 was off and nothing above 4 MV was lost.
- **CM01 2023-10-02**: channel 1 read up to about 88 between 09:39 and 09:41
  while every cavity in CM01–CM05, H1, H2 and CM35 was below 4 MV. Decarad 1's
  `POSN` read 35 for the whole run and only changed to 1 at 10:55. CHECK: was
  decarad 1 at CM01 during this run, and what caused the spike?

## 3. How runs get into the cache

A run counts as cached when all 28 of its PVs can be read from disk alone. A
run is fetched the first time any of these needs it.
<span class="cite">`field_emission/run_cache.py::is_cached “store.has_window(pv, run.start, run.end)”, utils/archiver_store.py::ArchiverStore.has_window`</span>

**A run that ended less than a day ago is never written.** The store caches a
window only once it ended more than `SETTLE = 1 day` ago. Until then every load
fetches it from the archiver again, and every open counts it as missing.
<span class="cite">`utils/archiver_store.py::SETTLE “SETTLE = timedelta(days=1)”, utils/archiver_store.py::ArchiverStore.read_window “if _settled(end):”`</span>

### Plotting it

PLOT reads `LOADING...` while the selected runs load on a background thread.
Each PV of a run is read from disk if the store has it and fetched and written
if not. A failed fetch shows its error on the plot.
<span class="cite">`field_emission_gui.py::FieldEmission.on_plot_btn_clicked “self._run_in_background(fetch)”, field_emission_gui.py::FieldEmission._set_loading “LOADING...”, field_emission_gui.py::FieldEmission._on_plot_data_failed “Could not load data”, field_emission/measurements.py::find_dataframes “data = load_run(run)”`</span>

### Opening the display

The first time the window is shown, a background thread loads every listed run
that isn't cached, one run at a time. The window title counts them. The panel
stays usable; plotting a run the fill hasn't reached fetches it directly.
<span class="cite">`field_emission_gui.py::FieldEmission.showEvent “self._start_cache_fill()”, field_emission_gui.py::FieldEmission._start_cache_fill “caching runs from the archiver”`</span>

```text
missing = [run for run in run list if not all 28 PVs on disk]

for run in missing:
    title: "caching runs from the archiver {n}/{len(missing)}"
    read 28 PVs through the store, 8 at a time
        each PV on disk: read it
        each PV not on disk: fetch → write temp file → rename
    align
    # any exception stops here; PVs already written stay
title: "LCLS-II Field Emission", or "background caching stopped (...)"
```

<span class="cite">`field_emission/run_cache.py::fill_cache “missing = [run for run in runs if not is_cached(run, store)]”, field_emission/run_cache.py::fill_cache “load_run(run, store)”, utils/archiver_store.py::_write_atomically “os.replace(tmp, path)”`</span>

### Add New Data

Next to the plot toolbar. *Single CM* takes one run in a form; *Multi CMs from
CSV* takes a file with the run list's columns. Each run is checked (a known
cryomodule, dates in `mm/dd/yy hh:mm`, end after start, decarad 1 or 2, an
`mccelog` link, Y/N filters), appended to `added_runs.csv`, and fetched. A CSV
row may leave the elog link empty, as 7 runs in git do. The first bad CSV row
is reported with its line number, and no row from that file is added. The run
list refreshes when the dialog closes. To make a run permanent for every
installation, add its row to `field_emission_runs.csv` in a PR.
<span class="cite">`gui_updater.py::validate_emission_data, gui_updater.py::UpdateWorker.multi_update “validate_emission_data(row, require_elog=False)”, gui_updater.py::UpdateWorker._add_and_fetch “added = add_runs(rows)”, gui_updater.py::UpdateWorker._add_and_fetch “fetched = fill_cache(runs, self._report)”, field_emission/run_cache.py::add_runs “with open(added_path, "a", newline="")”, field_emission_gui.py::FieldEmission.open_update_dialog “self.on_cryomodule_updated()”`</span>

## 4. How it fails

**"Cached" is per PV.** Each PV's window is written under a temporary name and
renamed when complete, so one PV's file is either all there or not there. A run
can be partly cached: some of its 28 PVs on disk, the rest not. It counts as
not cached, and the next load fetches only the PVs still missing.
<span class="cite">`utils/archiver_store.py::_write_atomically “all or nothing”, utils/archiver_store.py::ArchiverStore._cache “if path.exists():”`</span>

**The archiver is down.** Cached runs plot as usual. Plotting an uncached run
shows the connection error. The 28 reads of one run all finish before the
first error is raised, so PVs that came back before the outage are kept. The
fill on open stops at the first failed run, so an outage costs one failed run,
not one timeout per remaining run. The next open picks up where it stopped.
<span class="cite">`utils/archiver.py::_map_in_daemon_threads “Waits for every call, then raises the first error in item order”, field_emission/run_cache.py::fill_cache “Stops at the first failed fetch and raises it”`</span>

**The archiver doesn't know a PV.** The other PVs of that run are still read
and written, then the load raises `PVNotArchivedError` naming every unknown PV.
<span class="cite">`utils/archiver_store.py::ArchiverStore.read_windows “Raises archiver.PVNotArchivedError naming every unknown PV once all finish.”`</span>

**The cache can't be written** (no permission, disk full). The store logs a
warning and fetches without it. The plot still works, but nothing is kept, so
every open fetches every run again.
<span class="cite">`utils/archiver_store.py::ArchiverStore._cache “archiver cache: cannot write”, utils/archiver_store.py::ArchiverStore._cached “fetching %s without it”`</span>

**Two people fetch the same PV.** Both write a temp file and the second rename
wins. Both files hold the same archiver data. `/home` is NFS v4 on the
control-room machines, and the store takes no locks.
<span class="cite">`utils/archiver_store.py “so a shared cache needs no locks”, utils/archiver_store.py “is NFS v4”`</span>

!!! warning "Open question"

    CHECK: appends to `added_runs.csv` from two operators at the same moment
    could interleave on NFS. Adding runs is rare, so there's no lock. Is that
    acceptable?
    <span class="cite">`field_emission/run_cache.py::add_runs “CHECK: appends from two operators at once on NFS can interleave”`</span>

**Editing a run-list row.** Notes and elog are read from the list, so a change
shows up at once. A window file is named by PV, start and end, so a new end time
asks for a new window, and a new decarad asks for different PVs. Either is
fetched on the next load. The old files stay on disk, unused. To fetch the same
window again, delete its file in each PV's `windows/` directory. That doesn't
help if whole months cover the run, since those are read first.
<span class="cite">`utils/archiver_store.py::ArchiverStore.window_path, field_emission/run_cache.py::is_cached “run_pvs(run.cm, run.decarad)”`</span>

!!! note "One empty PV empties a dataset"

    A PV with no samples in the window is written as an empty file, so it
    isn't asked again. The align step drops every row with a missing value, so
    that PV leaves 0 rows. All 8 cavities share the same 10 decarad PVs, so one
    empty head blanks all 8 datasets for that readout, and the run still counts
    as cached.
    <span class="cite">`utils/archiver_store.py::_write_atomically “Nothing archived that month: record it, so it isn't asked again.”, field_emission/amp_vs_radiation.py::align_pvs_to_common_time “dropna(how="any")”`</span>

### Try it

Each square is a run in the list. Pick how many are already cached, whether
the newest run ended less than a day ago, and what goes wrong during the fill
on open. The right side is the next open with the archiver working.

[Run cache: what a fill on open does](widgets/run_cache.html)

!!! note "Stray temp files"

    A process killed hard during a write can leave a `.<name>.<hex>.tmp` file
    next to the window files. It's ignored, since only the final name counts,
    but nothing deletes it. A normal exception deletes its temp file.
    <span class="cite">`utils/archiver_store.py::_write_atomically “tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")”, utils/archiver_store.py::_write_atomically “tmp.unlink(missing_ok=True)”`</span>
