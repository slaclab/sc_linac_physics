# Cavity Characterization Phase UI — Design

Date: 2026-09-10
Status: approved, awaiting implementation plan
Backend: PR #285 (`feat/cavity-char-phase`), not yet merged

## Purpose

Give the operator a real display for the CAVITY_CHAR commissioning phase,
replacing the `GenericPhaseUI` placeholder currently registered for it. The
phase measures loaded Q and cavity scale factor, and the operator decides
whether those numbers reach the cavity.

The backend (`phases/cavity_char.py`) already separates reading from pushing
for exactly this reason. Its `_push_results()` docstring says the step is
"reached only once the operator has confirmed" — but nothing in the backend
enforces that. **Enforcing it is this UI's central job.**

## Scope

Single cavity only. A batch view over a cryomodule is explicitly out of scope;
if operators want one it becomes its own design.

## Decisions

Each of these was a real fork. Recording the reasoning, not just the outcome.

### Drive level: operator-entered, no inference

Ryan's outline calls for 10% drive on 7 kW SSAs and 15% on 3.8 kW ones. The
hardware model has no SSA power rating: `SSA.max_fwd_pwr` reads `CALPWR`, which
is the *measured* max forward power from the last calibration, and
`fwd_power_lower_limit` (500 for harmonic linearizers, 3000 otherwise) is a
calibration floor rather than a rating.

We considered thresholding `CALPWR` as a proxy for the rating, since SSA_CHAR
runs immediately before this phase and a 7 kW SSA calibrates near 7 kW.
**Rejected.** Inferring a nameplate rating from a measured calibration result
would put a hardware assumption in the UI that nobody has validated, and the
failure mode is silent: a poorly-calibrated SSA would be silently reclassified
into the wrong drive bucket.

So the UI keeps #285's behavior exactly — a spinbox defaulting to
`SAFE_PULSED_DRIVE_LEVEL` (10) and capped at `CavityCharLimits.max_drive_level`
(15). The 7 kW / 3.8 kW rule stays operator knowledge until someone supplies a
real rating PV or an owned cryomodule-to-power-class mapping.

### Push gate: inline review panel with an explicit button

Results render in the phase panel next to the cavity's Q window. The push
button stays disabled until `read_results` has succeeded, and its confirm text
names the two PVs being written (`PUSH_QLOADED.PROC`, `PUSH_CAV_SCALE.PROC` —
both processed with a 1, `wait=False`) and what each physically sets.

We considered a modal dialog, following the `cold_landing_dialog.py` precedent
from #270. **Rejected for this phase**: the cold landing commits a single
number the operator has to judge against a remembered value, so a focused modal
helps. Here the operator is comparing three measured values against a window
that is already on screen, and moving that comparison into a modal would hide
the context that makes it judgeable.

### Out-of-range loaded Q: allowed, but requires a typed reason

The backend deliberately returns SUCCESS with a warning when loaded Q falls
outside the window, leaving the push decision to the operator, and
`CavityCharacterization.passed` reports False for that record either way.

The UI honors that — the push is not blocked — but an out-of-range push
requires the operator to type a reason first, persisted to the existing
`CavityCharacterization.notes` field. Blocking the push outright would diverge
from the backend's stated intent; allowing it silently would lose the only
explanation of why an out-of-window value was accepted onto the machine.

### Probe Q: omitted entirely

Ryan's outline asks for probe Q to be displayed and pushed. It cannot be:
`calculate_probe_q()` processes `QPROBE_CALC1.PROC`, which only *triggers* the
calculation, and there is no value record to read the result from and no
`PUSH_QPROBE` to push it with. `_read_probe_q()` returns None on purpose.

Rather than render a permanently-empty row, the panel omits probe Q. When the
PV names are supplied, the row and its push arrive together.

### Progress display: status text and elapsed-vs-timeout, no progress bar

`wait_for_completion` polls `PROBECALSTS` every 1 s against a 300 s timeout. The
panel shows the characterization status message plus a running
elapsed / 300 s readout.

No determinate progress bar. Elapsed time is not fraction complete, and the
hardware reports nothing about how far along the measurement is — a bar would
imply knowledge we do not have.

## Hardware assumptions

Stated here because they are invisible in the code that relies on them.

1. **There is no characterization abort PV.** `Cavity` exposes
   `PROBECALSTRT`, `PROBECALSTS` and `PROBECALTS` for this measurement and
   nothing else. `request_abort()` sets `abort_flag`, which `check_abort()`
   reads inside Python loops. So Abort ends the `_wait_for_completion` poll
   and writes nothing to the machine, and the button has to say that.

   CHECK: once `PROBECALSTRT` is written, does the IOC always reach either a
   settled status or `CHARACTERIZATION_CRASHED_VALUE`? The UI assumes so,
   because it has nothing to send that would stop it.

2. **`PROBECALSTS` is the only progress signal.** `characterization_running`
   and `characterization_crashed` compare it against
   `CHARACTERIZATION_RUNNING_VALUE` and `CHARACTERIZATION_CRASHED_VALUE`.
   Nothing reports partial progress, which is why the panel shows elapsed time
   rather than a fraction.

3. **Probe Q derivation is triggered, then read.** `_read_results()` processes
   `QPROBE_CALC1.PROC`, sleeps `status_settle_delay` (2 s), then reads. The
   ordering is relied on, so the read step is not a pure read.

   CHECK: is 2 s enough for the calc record to settle on hardware?

4. **The Q window is per cavity class.** `Cavity.__init__` sets
   `loaded_q_lower_limit` / `loaded_q_upper_limit` from harmonic-linearizer,
   HE (#284) or standard constants. The panel reads those attributes off the
   loaded cavity rather than hard-coding a pair.

## Architecture

Follows the existing four-layer phase pattern, mirroring SSA_CHAR:

| Layer | File | Role |
|---|---|---|
| Builder | `ui/builders/phase_builders.py` — new `CavityCharUI(PhaseUIBase)` | Layout and widget registration via `_register()` |
| Controller | `ui/controllers/cavity_char_controller.py` | Phase driving, PV connections, threading, signals |
| Display | `ui/displays/cavity_char.py` — real `CavityCharDisplay` | `BasePlaceholderDisplay` subclass; slots delegate to controller |
| Registry | `ui/displays/registry.py` | Repoint `CAVITY_CHAR` off the `standard.py` placeholder |

Alternatives rejected:

- **Extending `GenericPhaseUI` with a results panel.** The gated push needs
  real controller state for button enablement and reason capture; bolting that
  onto the generic placeholder produces a placeholder that is no longer one.
- **A reusable measure → review → commit component.** The four remaining
  phases (PIEZO_WITH_RF, HIGH_POWER_RAMP, MP_PROCESSING, ONE_HOUR_RUN) share
  this shape, so factoring it out is tempting. Deferred: that is speculative
  generality from one implemented example, and CLAUDE.md asks this
  single-maintainer area to favor explicit over compact. Extract it when the
  second phase genuinely rhymes.

### Registry hazard

`displays/__init__.py` re-exports the *placeholder* `FrequencyTuningDisplay`
from `standard.py` while `registry.py` maps the phase to the real one in
`frequency_tuning.py` — two classes, one name, left behind by #270. #297 fixes
that one and adds a test parametrized over `PHASE_DISPLAY_MAP` asserting each
phase's registry class is the object the package exports.

Replacing the `CavityCharDisplay` placeholder is the same manoeuvre. When the
real display lands, the placeholder goes and every re-export is repointed in
the same change — and #297's test then covers CAVITY_CHAR for free, so the
assertion listed under Testing below is already there if #297 merges first.

## Data flow

```
operator sets drive level (spinbox, default 10, max 15)
    -> controller runs phase steps on a Worker(QThread)
       verify_initial_state -> set_drive_level -> start_characterization
    -> wait_for_completion: poll PROBECALSTS @1s, emit elapsed
       panel shows status text + elapsed/300s; Abort stops waiting only
    -> read_results: loaded Q, scale factor, in-tolerance flag
       panel renders them beside the cavity's actual Q window
    -> operator reviews
       in window     -> push button enabled
       out of window -> push button enabled only after a reason is typed
    -> push_results: PUSH_QLOADED, PUSH_CAV_SCALE
    -> record_results / finalize_phase
```

No blocking EPICS call runs on the Qt main thread; the phase is driven from
`Worker(QThread)` per `utils/qt.py`, consistent with the other phase
controllers.

## Error handling

- `read_results` returning RETRY (3 s delay) surfaces as a retrying status, not
  a failure — the measurement may still be settling.
- `characterization_crashed` is a distinct terminal state from timeout and must
  read differently in the panel; conflating them hides an IOC fault.
- Timeout at 300 s leaves the record unpushed and says so.
- Stale prerequisites (SSA cal or frequency tuning older than
  `prerequisite_staleness_hours`, 24 h) are a warning banner, matching the
  backend's choice to warn rather than block.
- The push failing mid-way (RETRY) must not leave the panel claiming success;
  loaded Q and scale factor are two separate PV writes and the second can fail
  after the first succeeds.

## Testing

Headless Qt via `QT_QPA_PLATFORM=offscreen` (set by `conftest.py`), EPICS PVs
mocked. Coverage must clear the 80% CI threshold.

Cases that matter most:

- Push button is disabled before a successful read.
- Out-of-range loaded Q leaves the push disabled until a reason is entered, and
  the reason reaches `CavityCharacterization.notes`.
- Out-of-range loaded Q still records `passed == False`.
- Drive level is clamped to `max_drive_level` and defaults to
  `SAFE_PULSED_DRIVE_LEVEL`.
- Abort during the wait stops polling and does not claim the characterization
  was stopped.
- `characterization_crashed` and timeout produce distinguishable states.
- The Q window shown is the loaded cavity's own bounds — asserted for standard,
  harmonic-linearizer and HE cavities.
- A record with no `cavity_char` data renders empty without raising.
- The class exported from the displays package is identical to
  `PHASE_DISPLAY_MAP[CommissioningPhase.CAVITY_CHAR]`.

## PR split

Split along the machine-write axis rather than by file, so the two PRs that
command hardware stay small enough to read every write.

| PR | Content | ~Lines | Machine writes |
|---|---|---|---|
| 1 | `CavityCharController` + `CavityCharUI` skeleton: drive-level spinbox, run/abort, status text with elapsed-vs-timeout | ~350 | Drive level, `PROBECALSTRT` |
| 2 | Results review panel, read-only: loaded Q, scale factor, Q window, in/out-of-tolerance, `refresh_from_record` | ~250 | None |
| 3 | The gated push: button enablement, out-of-range typed reason to `notes`, PV names in the confirm text | ~200 | `PUSH_QLOADED.PROC`, `PUSH_CAV_SCALE.PROC` |

PR 2 touches no hardware and can be reviewed purely as presentation. Each is
independently mergeable in order.

Branched from `feat/cavity-char-phase` (#285) rather than `main`, so the
controller can import `CavityCharPhase` directly. Diffs read as UI-only once
#285 merges.

## Operator-visible

The CAVITY_CHAR phase changes from a generic placeholder to a working display.
Operators gain a drive-level entry, a live characterization status, and a
review-then-push step for loaded Q and cavity scale factor — the measured
values no longer reach the cavity without an explicit click. Pushing an
out-of-window loaded Q now requires typing a reason, which is saved with the
record. The Abort button stops the software from waiting; it does not stop the
cavity characterization, and the UI says so.
