# How the field emission display works

`applications/field_emission/` plots cavity amplitude against decarad
radiation readings, one plot per cavity, for past measurement runs. This page
covers what the display reads, where each run's data comes from, how runs get
into the local cache, and how that fails. For the command, paths and how to add
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
<span class="cite">`field_emission/amp_vs_radiation.py::fetch_run “get_series(all_pvs, start, end)”`</span>

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

1. **Run list row**: `CM01, 10/2/23, 9:13, , 10:00, 1, elog…`
   <span class="cite">`field_emission/run_cache.py::parse_row`</span>
2. **28 archiver fetches**: 8 `AACTMEAN` + 10 heads × 2 readouts, each PV once,
   up to 8 at a time.
   <span class="cite">`field_emission/amp_vs_radiation.py::fetch_run “8 amplitudes + 10 heads x 2 readouts”, utils/archiver.py::MAX_WORKERS “MAX_WORKERS = 8”`</span>
3. **Align, 16 ways**: per cavity × readout, drop invalid samples, outer-join
   on timestamp, forward-fill, drop any row still missing a value.
   <span class="cite">`field_emission/amp_vs_radiation.py::align_pvs_to_common_time “aligned.ffill()”`</span>
4. **One file per run**: written to a temp file, then renamed into place.
   <span class="cite">`field_emission/run_cache.py::_write_run “os.replace(tmp_name, path)”`</span>

A run took 1.8–2.3 s through the archiver when it was warm. A run nobody has
asked for in a while can take tens of seconds. Caching all 80 runs from empty
took 253 s (#335's Testing section). These and the other counts on this page
were measured once, on 2026-10-07, while writing #335 and this page. No script
for them is in the repo.

### The cache layout

```text
get_field_emission_dir()          /home/physics/srf/field_emission on Linux
│                                 ~/.sc_linac_physics/field_emission on macOS
├── added_runs.csv                runs added from the display
└── runs/
    ├── cm01_2023-10-02_0913.h5   one file per run: cryomodule, start time
    │   attrs: cm, start, end, decarad, fetched
    │   ├── CAV1/average          (rows × 11) float64, attr columns = PV names
    │   ├── CAV1/instant
    │   └── … CAV8
    └── …
```

<span class="cite">`platform_paths.py::get_srf_base_dir “Path("/home/physics/srf")”, platform_paths.py::get_field_emission_dir, field_emission/constants.py::RUN_CACHE_DIR, field_emission/constants.py::ADDED_RUNS_PATH, field_emission/run_cache.py::run_path, field_emission/run_cache.py::_write_run “dset.attrs["columns"]”`</span>

Column 0 is the amplitude, columns 1–10 are heads 1–10. The display numbers
channels by column position, not by PV name.
<span class="cite">`field_emission/measurements.py::find_dataframes “pd.DataFrame(values)”, plot_me.py::plot_amp_vs_rad “label = f"Ch {col}"”`</span>
Date, times, elog and notes come from the run list each time, not from the
file.
<span class="cite">`field_emission/measurements.py::fetch_measurement_metadata “find_run(cm, date, read_run_list())”`</span>

### Checked against the old bundled file

The display used to read a 73.8 MB `field_emission_data.hdf5` shipped inside
the package, built by hand from the same 80 runs (Oct 2023 onward, 37
cryomodules). The cache reproduces it: all 16 datasets of CM06's 2024-02-02 run
have the same shapes and columns. Values differ in the last bit for 5–9% of
samples (at most 1.8e-15): the bundled file went through CSVs read back with
pandas' default float parser, and the cache stores what the archiver returns.
Three runs in it looked wrong:

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

A run is fetched the first time any of these needs it.

### Plotting it

PLOT reads `LOADING...` while the selected runs load on a background thread. A
cached run loads from its file. One that isn't is fetched and written first. A
failed fetch shows its error on the plot.
<span class="cite">`field_emission_gui.py::FieldEmission.on_plot_btn_clicked “self._run_in_background(fetch)”, field_emission_gui.py::FieldEmission._set_loading “LOADING...”, field_emission_gui.py::FieldEmission._on_plot_data_failed “Could not load data”, field_emission/run_cache.py::load_run “if not path.exists():”`</span>

### Opening the display

The first time the window is shown, a background thread fetches every listed
run that has no file yet, one at a time. The window title counts them. The
panel stays usable; plotting a run the fill hasn't reached fetches it directly.
<span class="cite">`field_emission_gui.py::FieldEmission.showEvent “self._start_cache_fill()”, field_emission_gui.py::FieldEmission._start_cache_fill “caching runs from the archiver”`</span>

```text
missing = [run for run in run list if no file for run]

for run in missing:
    title: "caching runs from the archiver {n}/{len(missing)}"
    fetch 28 PVs → align → write temp file → rename
    # any exception stops here; runs already written stay
title: "LCLS-II Field Emission", or "background caching stopped (...)"
```

<span class="cite">`field_emission/run_cache.py::fill_cache “load_run(run, cache_dir)”`</span>

### Add New Data

Next to the plot toolbar. *Single CM* takes one run in a form; *Multi CMs from
CSV* takes a file with the run list's columns. Each run is checked (a known
cryomodule, dates in `mm/dd/yy hh:mm`, end after start, decarad 1 or 2, an
`mccelog` link, Y/N filters), appended to `added_runs.csv`, and fetched. A CSV
row may leave the elog link empty, as 7 runs in git do. The first bad CSV row
is reported with its line number, and no row from that file is added. The run
list refreshes when the dialog closes. To make a run permanent for every
installation, add its row to `field_emission_runs.csv` in a PR.
<span class="cite">`gui_updater.py::validate_emission_data, gui_updater.py::UpdateWorker.multi_update “validate_emission_data(row, require_elog=False)”, gui_updater.py::UpdateWorker._add_and_fetch “added = add_runs(rows)”, field_emission/run_cache.py::add_runs “with open(added_path, "a", newline="")”, field_emission_gui.py::FieldEmission.open_update_dialog “self.on_cryomodule_updated()”`</span>

## 4. How it fails

**"Cached" means the run's file exists.** Each file is written under a
temporary name and renamed when complete, so a run is either all there or not
there. A crash during the write leaves the old state: no file.
<span class="cite">`field_emission/run_cache.py::_write_run “tempfile.mkstemp(”`</span>

**The archiver is down.** Cached runs plot as usual. Plotting an uncached run
shows the connection error. The fill on open stops at the first failure, so an
outage costs one failed run, not one timeout per remaining run, and the next
open picks up where it stopped.

**Two people fetch the same run.** Both write a temp file; the second rename
wins. Both files hold the same archiver data.

!!! warning "Open question"

    CHECK: is `/home/physics/srf` on NFS on the control-room machines? The
    rename is atomic on one local filesystem. Appends to `added_runs.csv` from
    two operators at the same moment could interleave on NFS; adding runs is
    rare, so there's no lock.

**Editing a run-list row.** A file is named by cryomodule and start time only.
Changing a row's notes or elog shows up immediately, since those are read from
the list. Changing its end time or decarad doesn't re-fetch: delete that run's
file and it is fetched again.

!!! note "One empty PV empties a dataset"

    The align step drops every row with a missing value, so a PV with no
    samples in the window leaves 0 rows. All 8 cavities share the same 10
    decarad PVs, so one empty head blanks all 8 datasets for that readout, and
    the run still counts as cached. A PV the archiver doesn't know at all fails
    the fetch instead.
    <span class="cite">`field_emission/amp_vs_radiation.py::align_pvs_to_common_time “dropna(how="any")”`</span>

### Try it

Each square is a run in the list. Pick how many are already cached, and what
goes wrong during the fill on open; the right side is the next open with the
archiver working.

[Run cache: what a fill on open does](widgets/run_cache.html)

!!! note "Stray temp files"

    A process killed hard during the write can leave a `cm…_….*.tmp` next to
    the run files. It's ignored, since only the final name counts, but nothing
    deletes it. A normal exception deletes its temp file.
    <span class="cite">`field_emission/run_cache.py::_write_run “Path(tmp_name).unlink(missing_ok=True)”`</span>
