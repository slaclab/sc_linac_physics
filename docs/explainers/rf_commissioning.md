# How RF commissioning is built

An onboarding map of `applications/rf_commissioning/`: the layers, what one
button click passes through on its way to the machine and to SQLite, how a
phase is written, what each implemented phase writes to EPICS, and the places
where the code surprises people. Everything here is read from upstream main.
The few facts the code cannot establish were checked against the IOC records
and say so. For the phase list, session API and database tables, see the
[RF Commissioning](../applications/rf_commissioning.md) page.

## 1. The shape of the app

Commissioning is nine phases run in a fixed order per cavity. Each phase has a
stored value, a record attribute and a data model, all declared in one registry
<span class="cite">`models/registry.py::create_phase_registry`</span>. Today
three phases are real. The rest have a tab with a placeholder display whose Run
button only logs
<span class="cite">`ui/displays/base_placeholder.py::BasePlaceholderDisplay.on_run_automated_test “This is a placeholder implementation”`</span>.

| # | Phase | Phase class | Controller | Status on main |
|---|---|---|---|---|
| 1 | `PIEZO_PRE_RF` | `PiezoPreRFPhase` | `PiezoPreRFController`, plus a batch window | Implemented |
| 2 | `SSA_CHAR` | `SSACharPhase` | `SSACharController` | Implemented |
| 3 | `FREQUENCY_TUNING` | `FrequencyTuningPhase` | `FrequencyTuningController` (4 stages) | Implemented |
| 4 | `CAVITY_CHAR` | — | — | Placeholder. Backend in open PR #285, UI in progress |
| 5 | `PIEZO_WITH_RF` | — | — | Placeholder |
| 6 | `HIGH_POWER_RAMP` | — | — | Placeholder |
| 7 | `MP_PROCESSING` | — | — | Placeholder |
| 8 | `ONE_HOUR_RUN` | — | — | Placeholder |
| 9 | `COMPLETE` | — | — | No tab. Its registry entry has `record_attr=None` <span class="cite">`models/registry.py::create_phase_registry “record_attr=None,”`</span> |

Five layers, top to bottom:

| Layer | Where | Job |
|---|---|---|
| Container | `ui/multi_phase_screen.py`, `ui/container/` | The window. Header, cavity picker, progress bar, notes, one tab per phase. Built from mixins. |
| Display | `ui/displays/` | One tab's widgets. Forwards button clicks to its controller. |
| Controller | `ui/controllers/` | Runs the phase on a background thread, pushes results back to the GUI with Qt signals, calls the session to open and close attempts. |
| Phase | `phases/` | The steps. The automated test's PV writes happen here, through `Cavity`, `SSA`, `Piezo` and `StepperTuner` from `utils/sc_linac/`. Controllers and PyDM widgets also write some PVs directly when the operator acts. Section 5 lists both. |
| Session and storage | `session_manager.py`, `services/workflow_service.py`, `models/persistence/` | `CommissioningSession` is the facade the UI calls. `WorkflowService` owns phase attempts. Repositories own SQL. |

!!! note "Not the layout CLAUDE.md describes"

    The repo-wide CLAUDE.md describes a `backend/ frontend/ launcher/` layout
    and `Worker(QThread)` threading. This app uses neither. There is no
    `launcher/` directory: the entry point is
    <span class="cite">`cli/launchers.py::launch_rf_commissioning`</span>.
    Threads are plain `threading.Thread`
    <span class="cite">`ui/controllers/piezo_pre_rf_controller.py::PiezoPreRFController._run_phase_in_background “Thread(target=worker, daemon=True).start()”`</span>.

## 2. Follow one click

An operator presses *Run automated test* on the Piezo Pre-RF tab. Step through
what happens. The other two implemented phases follow the same path with their
own controller.

[Follow one click: step through it](widgets/click_trace.html)

The hops, in order: display → session
opens attempt → controller builds phase → background thread runs steps →
hardware → signal back to GUI → session completes attempt → record saved with a
version check.

## 3. Writing a phase

A phase subclasses `PhaseBase` and implements five members: `phase_type`,
`validate_prerequisites`, `get_phase_steps`, `execute_step` and
`finalize_phase`
<span class="cite">`phases/phase_base.py::PhaseBase “Subclasses must implement:”`</span>.

- `get_phase_steps` returns an ordered list of step names. `SSACharPhase` is
  the cleanest short example
  <span class="cite">`phases/ssa_char.py::SSACharPhase.get_phase_steps`</span>.
- `execute_step` dispatches on the name and returns a `PhaseStepResult`
  carrying `SUCCESS`, `RETRY`, `FAILED` or `SKIP`
  <span class="cite">`phases/phase_base.py::PhaseResult`</span>.
- `RETRY` re-runs the step after `retry_delay_seconds`, default 5 s
  <span class="cite">`phases/phase_base.py::PhaseStepResult “retry_delay_seconds: float = 5.0”`</span>. A step runs at most 3 times, so it gets 2 retries
  <span class="cite">`phases/phase_base.py::PhaseBase.__init__ “self._max_retries_per_step: int = 3”`</span>. An exception also uses up an attempt. Piezo goes through `PhaseBase`,
  which waits before retrying an exception. SSA and frequency tuning each have
  their own copy of this loop, with the same limit, that retries an exception
  at once
  <span class="cite">`ui/controllers/ssa_char_controller.py::SSACharController._execute_step_with_retries “retry_count = 0”, ui/controllers/frequency_tuning_controller.py::FrequencyTuningController._execute_step_with_retries “retry_count = 0”`</span>.
- Abort is a flag, not an interrupt
  <span class="cite">`phases/phase_base.py::PhaseContext.request_abort “self.abort_requested = True”`</span>. A long step has to check it itself.

!!! note "Five step loops"

    `PhaseBase.run()` exists but no controller calls it. Each of the three
    controllers has its own step loop and calls private phase methods directly,
    for example
    <span class="cite">`ui/controllers/ssa_char_controller.py::SSACharController._run_phase_in_background “self.phase._mark_phase_started()”`</span>. The batch Piezo window has one more. So there are five step loops, and
    they do not all do the same bookkeeping. One example: `PhaseBase.run()` and
    the batch window reset the attempt counter before each step
    <span class="cite">`phases/phase_base.py::PhaseBase.run “self._retry_count = 0”, ui/controllers/batch_piezo_pre_rf_controller.py::BatchPiezoPreRFController._run_step “state.phase._retry_count = 0”`</span>. The single-cavity Piezo controller does not, so exceptions add up across
    the whole phase there. Read the controller for the phase you are touching,
    not just `PhaseBase`.

    Decided 2026-10-02: one shared step runner will replace these loops, before
    any placeholder phase is implemented.

## 4. What gets stored

SQLite. The schema is in one function
<span class="cite">`models/persistence/database_schema.py::initialize_database_schema`</span>.

| Table | One row per | Holds |
|---|---|---|
| `commissioning_records` | cavity | One JSON column per phase payload, general notes, and a `version` counter |
| `commissioning_runs` | record | Run status |
| `commissioning_phase_instances` | attempt of a phase | Status, operator, timestamps. Unique on `(run_id, phase, attempt_number)` <span class="cite">`models/persistence/database_schema.py::initialize_database_schema “UNIQUE(run_id, phase, attempt_number)”`</span> |
| `commissioning_phase_artifacts` | artifact | JSON payload tied to an attempt |
| `commissioning_workflow_events` | event | Append-only log |
| `measurement_history` | measurement | A row per measurement. Notes can be edited later (below) |
| `operators`, `cryomodule_records` |  | Operator list, cryomodule-level records |

### Two things that are not where you would look

- **Phase status is not stored on the record.** On load it is rebuilt from the
  latest attempt of each phase
  <span class="cite">`models/persistence/database_helpers.py::build_workflow_state “if previous is None or attempt >= previous[0]:”`</span>. The in-memory `record.phase_status` that `PhaseBase` updates is not what
  persists.
- **`phase_history` is not persisted.** It is reset on every load
  <span class="cite">`repositories/records.py::RecordRepository.row_to_record “phase_history=[],”`</span>.

### Two people, one cavity

Saves use optimistic locking. The update only matches if the version is
unchanged since load
<span class="cite">`repositories/records.py::RecordRepository.save_record “WHERE id = ? AND version = ?”`</span>. The window also polls every 5 s and reloads if someone else saved
<span class="cite">`ui/container/sync.py::_SyncMixin._check_for_external_changes “if local_version is not None and db_version > local_version:”`</span>. Measurement notes skip the version check
<span class="cite">`repositories/measurements.py::MeasurementRepository.append_measurement_note “"UPDATE measurement_history SET notes = ? WHERE id = ?",”`</span>.

## 5. What each phase writes to the machine

Only what the code shows, in step order. Reads are left out. Where a phase
hands off to a shared `Cavity` method, the table names the method rather than
repeating what it writes.

### PIEZO_PRE_RF

| Step | PV | Value | Source |
|---|---|---|---|
| `setup_piezo` | `BIAS` | 25 | <span class="cite">`piezo.py::Piezo.enable “self.bias_voltage = 25”`</span> |
|  | `ENABLE` | only if not already enabled: disable, wait 2 s, enable. Repeats until the piezo reports enabled, up to 10 tries, then raises | <span class="cite">`piezo.py::Piezo.enable “self.enable_pv_obj.put(linac_utils.PIEZO_DISABLE_VALUE)”, piezo.py::Piezo “ENABLE_MAX_ATTEMPTS = 10”`</span> |
|  | `MODECTRL` | `PIEZO_MANUAL_VALUE` | <span class="cite">`piezo.py::Piezo.set_to_manual “self.feedback_control_pv_obj.put(linac_utils.PIEZO_MANUAL_VALUE)”`</span> |
|  | `DAC_SP` | 0 | <span class="cite">`phases/piezo_pre_rf.py::PiezoPreRFPhase._setup_piezo “piezo.dc_setpoint = 0”`</span> |
| `trigger_prerf_test` | `TESTSTRT` | 1 | <span class="cite">`phases/piezo_pre_rf.py::PiezoPreRFPhase._trigger_prerf_test “piezo.prerf_test_start_pv_obj.put(1)”`</span> |

### SSA_CHAR

| Step | PV | Value | Source |
|---|---|---|---|
| `set_drive_max` | `DRV_MAX_REQ` | operator's drive max, a 0–1 fraction | <span class="cite">`phases/ssa_char.py::SSACharPhase._set_drive_max “self.cavity.ssa.drive_max = drive_max”`</span> |
| `reset_and_power_on` | `FaultReset` | 1, while faulted | <span class="cite">`ssa.py::SSA.reset “self.reset_pv_obj.put(1)”`</span> |
|  | `PowerOn` | 1, if off | <span class="cite">`ssa.py::SSA.turn_on “self.turn_on_pv_obj.put(1)”`</span> |
|  | `INTLK_RESET_ALL` | 1 | <span class="cite">`cavity.py::Cavity.reset_interlocks “self._interlock_reset_pv_obj.put(1, wait=False)”`</span> |
| `start_calibration` | `CALSTRT` | 1 | <span class="cite">`ssa.py::SSA.start_calibration “self._calibration_start_pv_obj.put(1, wait=False)”`</span> |
| `validate_and_push` | `PUSH_SSA_SLOPE.PROC` | 1, after the slope passes validation | <span class="cite">`phases/ssa_char.py::SSACharPhase._validate_and_push “self.cavity.push_ssa_slope()”`</span> |

The drive-max spinbox on the tab is a PyDM widget bound straight to the
setpoint PV, so editing it writes the PV before any test runs
<span class="cite">`ui/controllers/ssa_char_controller.py::SSACharController._apply_ssa_pv_mapping “("drive_max_spinbox", ssa.drive_max_setpoint_pv),”`</span>.

### FREQUENCY_TUNING

Four operator-driven stages. Stage 3 runs `Cavity._auto_tune`, which has its
own explainer: [How auto-tune works](auto_tune.md), section 5 of which walks
the four stages in detail.

| Stage | Writes | Source |
|---|---|---|
| 1 | Delegates to `Cavity.setup_tuning` and friends. Records the cold-landing detune for the operator. It does not write `DF_COLD`: the operator pushes that from the UI (next table) | <span class="cite">`phases/frequency_tuning.py::FrequencyTuningPhase._prepare_cavity_for_tuning “self.cavity.setup_tuning()”, phases/frequency_tuning.py “the operator pushes it to”`</span> |
| 2 | Refuses to move until `DF_COLD` matches the recorded value within 1 Hz. Then `TOTSGN_RESET` = 0, then a +50,000 / −50,000 microstep probe move | <span class="cite">`phases/frequency_tuning.py::FrequencyTuningPhase._check_df_cold_recorded “DF_COLD does not match the recorded cold-landing”, phases/frequency_tuning.py::FrequencyTuningPhase._do_probe_move “self.cavity.stepper_tuner.move(probe, speed=speed, check_detune=False)”`</span> |
| 3 | `SCALE_CALC.B` from the measured Hz/microstep, auto-tune, `NSTEPS_COLD`, `TUNE_CONFIG` | <span class="cite">`phases/frequency_tuning.py::FrequencyTuningPhase._write_cold_landing_steps “self.cavity.stepper_tuner.steps_cold_landing_pv_obj.put(”`</span> |
| 4 | Rack frequency scan: `FSCAN:SEL` = 1 for this cavity and 0 for the rest of the rack, then `FSCAN:FREQ_START` = −3,500,000 Hz, `FSCAN:FREQ_STOP` = 50,000 Hz, `FSCAN:RMS_THRESH` = 10.0, `FSCAN:MODE_OVERLAP` = 1,000, then `FSCAN:START` = 1, then, once the scan is done, `FSCAN:PUSH_8PI9.PROC` = 1 and `FSCAN:PUSH_7PI9.PROC` = 1 for this cavity. The four settings are `FrequencyTuningLimits` defaults. | <span class="cite">`rack.py::Rack.run_fscan “self.fscan_rms_thresh_pv_obj.put(rms_thresh)”, rack.py::Rack.run_fscan “cav.fscan_push_8pi9_pv_obj.put(1)”, cavity.py::Cavity.__init__ “self.pv_addr("FSCAN:PUSH_8PI9.PROC")”, phases/frequency_tuning.py::FrequencyTuningLimits “pi_scan_rms_thresh: float = 10.0”`</span> |

### Writes outside the phase

These happen when the operator clicks or edits something, not as a step of the
automated test.

| Trigger | Writes | Source |
|---|---|---|
| Frequency tuning: push cold landing | `DF_COLD` = the chosen value | <span class="cite">`ui/controllers/frequency_tuning_controller.py::FrequencyTuningController._commit_cold_landing “PV(cavity.pv_addr("DF_COLD")).put(value)”`</span> |
| Frequency tuning: push SCALE | `SCALE_CALC.B` via `set_hz_per_microstep` | <span class="cite">`ui/controllers/frequency_tuning_controller.py::FrequencyTuningController.push_hz_per_step_to_scale “self._cavity.stepper_tuner.set_hz_per_microstep(signed_hz)”`</span> |
| Frequency tuning: manual move buttons | `MOV_REQ_POS` / `MOV_REQ_NEG` = 1 | <span class="cite">`ui/controllers/frequency_tuning_controller.py::FrequencyTuningController._do_stepper_move “stepper.move_positive()”`</span> |
| SSA char: push slope button | `PUSH_SSA_SLOPE.PROC` = 1 | <span class="cite">`ui/controllers/ssa_char_controller.py::SSACharController.on_push_slope “cavity.push_ssa_slope()”`</span> |
| PyDM widgets, on edit | Piezo enable and mode combos, SSA drive max, stepper step-count spinboxes write their bound PVs directly | <span class="cite">`ui/builders/phase_builders.py “PyDMEnumComboBox(parent=self.parent)”`</span> |

### Checked against the IOC

Three things that look wrong in the code and are not. Confirmed against the IOC
records on 2026-10-02. Those records are not in this repo.

- `FSCAN:FREQ_START` and `FREQ_STOP` are in Hz (record EGU), so stage 4 scans
  −3.5 MHz to +50 kHz.
- `TESTSTS` is an enum: 0 Crash, 1 Complete, 2 Running. The code's `== 0` crash
  test matches
  <span class="cite">`phases/piezo_pre_rf.py::PiezoPreRFPhase._trigger_prerf_test “is_crash = test_status == 0  # Crash”`</span>.
- `CommissioningPiezo` reads `CHA_TESTMSG2` for channel B's message. That is
  the real PV name, not a typo
  <span class="cite">`models/commissioning_piezo.py::CommissioningPiezo.__init__ “self.pv_addr("CHA_TESTMSG2")”`</span>.

## 6. Where newcomers trip

1. **Three prerequisite checks that disagree.**
   `CommissioningRecord.can_start_phase` and
   `WorkflowService._validate_phase_prerequisites` accept a previous phase that
   is complete or skipped. `CommissioningSession.can_run_phase` accepts
   complete only
   <span class="cite">`rf_commissioning/session_manager.py::CommissioningSession.can_run_phase “if previous_status != PhaseStatus.COMPLETE:”`</span>. Decided 2026-10-02: complete or skipped is the rule, and `can_run_phase`
   will defer to the workflow service. Nothing records a skip yet.
2. **Frequency tuning's stage checks are not in its step list.** They exist
   only in `execute_step`'s dispatch, and only Stage 1 opens an attempt
   <span class="cite">`ui/controllers/frequency_tuning_controller.py::FrequencyTuningController._find_open_phase_instance_id “Only Stage 1 opens a phase instance”`</span>.
3. **The batch Piezo window skips the session facade.** It calls the workflow
   service directly and writes no measurement history
   <span class="cite">`ui/controllers/batch_piezo_pre_rf_controller.py::BatchPiezoPreRFController._init_record_and_context “phase_start = self.session.workflow.start_phase_for_record(”`</span>.
4. **Docs drift.** `docs/applications/rf_commissioning.md` says only the Piezo
   tab shows by default. All phases with a record attribute show
   <span class="cite">`ui/container/phase_specs.py::DEFAULT_BETA_VISIBLE_PHASES`</span>. It also calls `phase_history` an append-only checkpoint history, but
   `phase_history` is not persisted (section 4).
5. **Small naming bumps.** `self._controller` in `FrequencyTuningDisplay` vs
   `self.controller` elsewhere. `ssa_char` in the registry but
   `"ssa_characterization"` in `CommissioningRecord.to_dict`.

## 7. Running and testing it

### Launch the app

Install once with `pip install -e ".[dev,test]"` from the repo root. Then pick
how much of the machine you want:

| You want | Run | What you get |
|---|---|---|
| Layout only | `PYDM_DEFAULT_PROTOCOL=fake sc-rf-comm` | The window opens with no EPICS. PV values are zero or empty. Good for UI work. |
| Live fake data | `sc-sim` in one terminal, then `sc-rf-comm` in another | A caproto IOC serving simulated cavity PVs. Phases can run end to end against it. See [Getting started](../getting_started.md). |
| The real machine | `sc-rf-comm` on a control-room host | Phases write to the PVs in section 5. |

`sc-linac rf-commissioning` launches the same window through the unified CLI
<span class="cite">`cli/launchers.py::launch_rf_commissioning “MultiPhaseCommissioningDisplay, *sys.argv[1:], standalone=standalone”`</span>.

### Which database it opens

There is no command-line flag for the database path. The window always builds a
default `CommissioningSession()`
<span class="cite">`ui/multi_phase_screen.py::MultiPhaseCommissioningDisplay.__init__ “self.session = session or CommissioningSession()”`</span>, which picks the path by OS
<span class="cite">`rf_commissioning/session_manager.py::get_default_db_path “db_dir = get_srf_base_dir() if is_linux() else get_database_dir()”`</span>:

- Linux: `/home/physics/srf/commissioning.db`
  <span class="cite">`utils/platform_paths.py::get_srf_base_dir “return Path("/home/physics/srf")”`</span>
- macOS: `~/.sc_linac_physics/databases/commissioning.db`. The docstring on
  `get_default_db_path` still says `~/databases/`, which is out of date.

!!! warning "The Linux default is the production database"

    On Linux this is the production database. `/home/physics` is the shared
    physics login and `srf` is the group's directory in it, so a dev session on
    any of those hosts saves into the real commissioning records. For safe
    local work, run on a Mac, or construct the window yourself with
    `MultiPhaseCommissioningDisplay(session=CommissioningSession(db_path=...))`.

### Open this page

The docs site publishes it at
[slaclab.github.io/sc_linac_physics/explainers/rf_commissioning/](https://slaclab.github.io/sc_linac_physics/explainers/rf_commissioning/),
rebuilt on every merge to main. The step-through also opens on its own,
offline too: `docs/explainers/widgets/click_trace.html` from a checkout. It
makes no network loads.

### Test it

- Tests: `pytest tests/applications/rf_commissioning -n auto`. About 900
  tests, about 12 s.
- EPICS is faked for the whole test run by `tests/conftest.py`, which installs
  a fake PV class at configure time.
- Three patterns worth copying:
    - Real SQLite in `tmp_path`:
      <span class="cite">`tests/applications/rf_commissioning/test_session_workflow.py`</span>
    - Controller against a stub view:
      <span class="cite">`tests/applications/rf_commissioning/test_piezo_pre_rf_controller.py`</span>
    - Container methods on a `SimpleNamespace` stub:
      <span class="cite">`tests/applications/rf_commissioning/ui/test_multi_phase_screen.py`</span>
