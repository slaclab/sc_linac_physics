# How Q0 comes out of the liquid level fits

Every Q0 the app shows comes from straight-line fits to downstream liquid level
(LL) samples. This page covers which fits run and in what order, the two numbers
the app now shows side by side, and what a comparison of the fits on the
packaged data found.

## 1. From LL samples to Q0

Each run (a calibration step, a Q0 heater run, a Q0 RF run) records the raw DS
level monitor values against time
<span class="cite">`q0_cryomodule.py::Q0Cryomodule.monitor_ll “ll_data[datetime.now().timestamp()] = value”`</span>.
The averaging buffer next to it is not what gets stored.

| Step | What the code does | Where |
|---|---|---|
| 1. Run slope | dLL/dt for each run: `siegelslopes` over the samples in the fit window (all of them if none is set). `linregress` is used if `USE_SIEGELSLOPES` is False. | <span class="cite">`q0_utils.py::DataRun.dll_dt`</span>, <span class="cite">`q0_utils.py::USE_SIEGELSLOPES`</span> |
| 2. Calibration line | `linregress` of each calibration run's dLL/dt against its average heater readback. The slope is `dLLdt_dheat` and the intercept is `adjustment`. | <span class="cite">`q0/calibration.py::Calibration.dLLdt_dheat`</span> |
| 3. Heat load | `raw_heat + adjustment`. Here `raw_heat` is the RF run read off the line. The second `adjustment` (the measurement's own) is the heater run's known heat minus where the line puts it. | <span class="cite">`rf_measurement.py::Q0Measurement.heat_load`</span>, <span class="cite">`rf_measurement.py::Q0Measurement.adjustment`</span> |
| 4. Q0 | `calc_q0` with the root-sum-square of the cavity amplitudes. It is called uncorrected, because `use_correction` defaults to False. | <span class="cite">`rf_measurement.py::Q0Measurement._q0_from_heat`</span>, <span class="cite">`q0_utils.py::calc_q0 “return corrected_q0 if use_correction else uncorrected_q0”`</span> |

The calibration intercept cancels in step 3. Algebraically the heat load is

```text
heat_load = heater average_heat + (rf dLL/dt − heater dLL/dt) / dLLdt_dheat
```

So the Q0 depends on the calibration *slope* and on the difference between the
two run slopes. Uncorrected Q0 is proportional to 1 / heat load.

## 2. Two numbers side by side

After a measurement is taken or loaded, the status line and the Q0 fit-plot
title read like this:

```text
Q0 1.76e+10 ± 3.4e+08 (siegel) · linregress 1.77e+10
```

That is CM07's 07/25/22 19:14:24 measurement. The difference is inside the ±, so there is no warning.

<span class="cite">`q0_gui_utils.py::format_q0`</span>

- **The first number is the official Q0.** It is the one saved to the index by
  `save_results`. Nothing about it changed.
- **`linregress`** is the same chain with every run slope fit by least
  squares instead: the calibration runs, the heater run and the RF run. It is
  shown, never saved
  <span class="cite">`rf_measurement.py::Q0Measurement.q0_linregress`</span>,
  <span class="cite">`q0/calibration.py::Calibration.linregress_line`</span>.
- **`±`** is one sigma from the noise in the RF and heater run fits, carried
  through the heat-load formula above
  <span class="cite">`rf_measurement.py::Q0Measurement.q0_sigma`</span>.
  It leaves out calibration-line uncertainty and heater readback error.
- **`⚠ fit-sensitive`** is added when the two Q0s differ by more than
  `FIT_SENSITIVE_SIGMAS` sigma, which is 1 today
  <span class="cite">`rf_measurement.py::Q0Measurement.fit_sensitive`</span>,
  <span class="cite">`q0_utils.py::FIT_SENSITIVE_SIGMAS`</span>.

### Why the ± is widened

`linregress` reports a standard error that assumes every LL sample is
independent of the last. In the packaged data they are not. The residual from
the fitted line at one sample predicts the next one closely: the median lag-1
correlation is 0.97 for RF runs and 0.96 for heater runs.

Taken at face value, the plain standard error gave a median ± of 0.8% of Q0.
With that, the flag fired on 74% of packaged measurements.

The code widens each run's standard error by √((1 + ρ) / (1 − ρ)), where ρ is
that lag-1 correlation
<span class="cite">`q0_utils.py::DataRun.dll_dt_stderr`</span>. This is the
usual correction for residuals that follow a first-order autoregressive pattern.
On the packaged data it gives a median ± of 6.1%, and the flag fires on 9% of
measurements at 1 sigma (2% at 2 sigma).

!!! warning "Open question: where the correlation comes from"

    The code stores raw monitor values, so the correlation is not from the
    averaging buffer.

    CHECK: does the IOC filter or smooth the DS level before Channel Access
    sees it? If so, the correlation is partly that filter, and a fit to
    decimated samples might be cleaner.

## 3. Which fit is better: what the packaged data says

Compared on 2026-10-15 over everything in `q0/data/`. The heater readback was
the reference.

**Calibration linearity.** Within a calibration, dLL/dt should line up with
heater power. Each run's heater power is predicted from a line fit to the
*other* runs. That is leave-one-out, scored in watts. There were 160
calibrations with 4 or more runs.

| Run fit | Median leave-one-out RMS (W) |
|---|---|
| `linregress` | 2.34 |
| `theilslopes` | 2.35 |
| `siegelslopes` (official) | 2.66 |

`siegelslopes` did better in 60 of 160 calibrations (paired Wilcoxon p = 0.001).
By year: 2022 3.13 vs 3.37 W, 2023 1.47 vs 1.72 W, and 2025 a tie at 1.53 vs
1.51 W.

**Q0 heater run.** The heater run inside each Q0 measurement has a known heat.
Its prediction through the calibration was within a median 4.4 W
(`linregress`) vs 3.8 W (`siegelslopes`). Over 279 measurements that is a tie:
siegel was closer in 144 (p = 0.59).

**What drives the gap.** Where the fits disagree, the size of the disagreement
tracks curvature in the LL trace (Spearman 0.81), not outliers (0.30).
Trimming the first 10–50% of each run did not improve either fit.

**LL linearity in band.** Each run was split into six pieces, and each piece's
slope divided by the whole-run slope. From 90.0 to 92.5 every 0.5-wide bin is
within ±2% of 1.0. From 92.5 to 93.0, where runs start right after the fill,
pieces are 8.5% steeper. Level and time are tied together, since LL only falls
during a run. So this cannot tell a sensor effect from settling after the fill.

!!! warning "Open questions for the area physicist"

    The code collects data with DS LL above `MIN_DS_LL`, because the sensor is
    not linear over its full range
    <span class="cite">`q0_utils.py “isn't linear over the full range”`</span>.

    CHECK: is the DS LL sensor linear across 90–93? The data above fits a
    linear sensor up to 92.5, but no reference has been found.

    CHECK: is the steeper 92.5–93 stretch the sensor, or settling after the
    fill?

    CHECK: the comparison treats heater readback as exact. Its accuracy is
    unknown. A constant offset or scale error would not favour either fit.
    Random run-to-run error would add the same scatter to both.

**Reading.** The data mildly favours `linregress`, by about 0.3 W on
calibration scatter. That is not enough on its own to change the official fit.
Changing it would change every Q0 recomputed on load. The side-by-side display
exists so that measurements where the choice matters are visible.

## 4. What is stored, and what is read back

The data files store a "dLL/dt" value for every run. Nothing reads it. On load,
every slope is refit from "Liquid Level Data". Records saved before
`siegelslopes` became the default (Nov 2022) hold `linregress` values.

The index's "Calculated Q0" is whatever the fit in use at the time gave, so a
2022 Q0 in the index can differ from the one the app shows on load. Across the
167 pre-switch measurements the median difference is 2.8%. #415 stops
`load_data` from rewriting the stored value with a refit.
