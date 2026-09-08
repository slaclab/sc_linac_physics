# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_cli.py -v

# Run with coverage report (80% minimum enforced in CI)
pytest --cov=sc_linac_physics --cov-report=term-missing

# Lint
flake8 . --count --max-complexity=10 --max-line-length=120 --show-source --statistics
black --check .

# Format
black .

# Install for development
pip install -e ".[dev,test]"
```

Set `PYDM_DEFAULT_PROTOCOL=fake` to run UI code without live EPICS hardware.

## Documentation

Full documentation lives in [`docs/`](docs/index.md):
- [`docs/utils/linac_model.md`](docs/utils/linac_model.md) — hardware model, PV naming, all constants
- [`docs/utils/shared_utilities.md`](docs/utils/shared_utilities.md) — EPICS `PV`/`PVBatch`, logger, Qt helpers
- [`docs/applications/auto_setup.md`](docs/applications/auto_setup.md) — automated cavity turn-on
- [`docs/applications/rf_commissioning.md`](docs/applications/rf_commissioning.md) — phase-gated acceptance workflow
- [`docs/applications/q0.md`](docs/applications/q0.md), [`microphonics.md`](docs/applications/microphonics.md), [`quench_processing.md`](docs/applications/quench_processing.md), [`tuning.md`](docs/applications/tuning.md)
- [`docs/displays/cavity_display.md`](docs/displays/cavity_display.md), [`srf_home.md`](docs/displays/srf_home.md)

See also `AGENTS.md` at the repo root for architectural conventions enforced across the codebase.

## Architecture

This package provides controls, displays, and analysis tools for the SLAC SC Linac (superconducting RF linac). It is built on PyDM/PyQt5 and uses EPICS (via caproto/pyepics) for hardware communication.

```
src/sc_linac_physics/
├── applications/       # Major standalone applications
├── displays/           # PyDM-based operator displays
├── cli/                # Unified launcher CLI (sc-linac entry point)
└── utils/              # Shared infrastructure (EPICS, Qt, logging, linac model)
```

### Linac Hardware Model (`utils/sc_linac/`)

The full hierarchy is `Machine → Linac → Cryomodule → Rack → Cavity` (+ `SSA`, `StepperTuner`, `Piezo` per cavity). `linac_utils.py` defines cryomodule groupings (L0B–L4B), all EPICS PV naming conventions, and hardware constants. All applications build a module-level `Machine` subclass singleton (e.g., `SETUP_MACHINE`) at import time.

### EPICS Integration (`utils/epics/`)

Use `PV` (never raw `pyepics.PV`) — it adds retry/backoff, typed exceptions, and never returns `None`. For bulk reads across many cavities, use `PVBatch.get_values()`. PV objects are always lazily instantiated on first property access to avoid connecting to hardware at import time.

Platform-aware paths (log dirs, database dirs) live in `utils/platform_paths.py`.

### Displays (`displays/`)

All displays inherit from `pydm.Display`. They are launched either from `.ui` files or as Python classes. The `@display` decorator in `cli/launchers.py` registers them for the unified CLI and handles standalone vs. embedded modes.

### Applications (`applications/`)

Each major application follows a three-layer pattern:
- `backend/` — business logic and EPICS communication, no Qt dependency
- `frontend/` — PyQt5 widgets
- `launcher/` — CLI entry point(s)

### Hierarchical Setup (`applications/auto_setup/`)

`SetupMachine` → `SetupLinac` → `SetupCryomodule` → `SetupCavity` mirrors the physical hierarchy. CLI commands at each level (`sc-setup-all`, `sc-setup-linac`, `sc-setup-cm`, `sc-setup-cav`) map to corresponding backend classes. Request flags (SSA cal, auto-tune, characterization, RF ramp) are EPICS PVs set by GUI/CLI before triggering start.

### RF Commissioning (`applications/rf_commissioning/`)

Nine-phase gated acceptance workflow (PIEZO_PRE_RF → SSA_CHAR → … → ONE_HOUR_RUN → COMPLETE). `CommissioningSession` is the application facade; `PhaseBase` is the abstract base for all phases; `WorkflowService` orchestrates normalized phase instances; `CommissioningDatabase` (SQLite) stores records with optimistic locking. See the three `.md` files inside `applications/rf_commissioning/` for detailed architecture docs.

### Threading

Long-running operations use `Worker(QThread)` from `utils/qt.py`, which emits `finished`, `progress`, `error`, and `status` signals. Never run blocking EPICS calls on the main Qt thread.

### Logging

`utils/logger.py` provides `custom_logger()` with rotating file handlers. Use `utils/platform_paths.py` to get the correct base log directory (`/home/physics/srf/logfiles` on Linux, `~/` on macOS).

## Testing Notes

- Headless Qt tests require `QT_QPA_PLATFORM=offscreen` (set automatically by `conftest.py` — no need to set it manually).
- `conftest.py` redirects `/home/physics` to a temp directory so tests never write to real paths.
- EPICS PVs are mocked via `unittest.mock`; no hardware connection is required.
- `pytest-asyncio` is configured with `asyncio_mode = auto`.
- The 80% coverage threshold is enforced by CI — check coverage before opening a PR.

## Scope and shipping

These rules exist because AI-assisted development makes it easy to produce more
change per PR than a reviewer can absorb. They are about reviewability, not
about slowing down.

### Split at planning time, not review time

Before starting a piece of work, state how it will be split into PRs. Splitting
is a planning decision — once the code is written, splitting becomes a chore and
gets skipped. If a task can't be described as a sequence of independently
mergeable changes, say so and explain why before starting.

### Target PR size

Aim for **under 400 changed lines** excluding tests and generated files. Past
~800, split it. Large mechanical changes (renames, formatting, generated code)
are exempt but should be their own PR, never mixed with logic changes.

When a change is growing past the target mid-work, stop and propose a split
rather than continuing.

### Flag operator-visible changes

If a change alters what a user sees or how an application behaves by default —
new or reordered UI, changed defaults, renamed commands, altered PV usage,
different launch behavior — say so explicitly in the PR description under the
`## Operator-visible` heading, in one or two sentences of plain language.

These need a short note to `#srf-software` when released. Changes that hide
inside a large commit and surprise people at launch are the specific failure
mode this prevents.

The PR template (`.github/pull_request_template.md`) has sections for this, for
split rationale, for decisions worth recording, and for tagging a learning
reviewer. Fill them in rather than deleting them.

### Record decisions with reasoning

When choosing between real alternatives — reusing production code vs.
reimplementing, staging a rollout, deferring a migration — write down the
reasoning, not just the outcome. A comment at the decision point is enough for
small calls; anything architectural goes in `docs/`.

The reasoning is what nobody can reconstruct later. The code shows what was
chosen; it never shows what was rejected or why.

### Write for the physicist reading it

Two reviewers are auto-requested by `.github/CODEOWNERS`, and they read for
different things. Sebastian reads software design — framework structure, phase
sequencing, threading, persistence. Ryan reads machine behavior, and as area
physicist he needs to know exactly what the code commands the hardware to do and
how it derives the numbers people act on.

#### Say what the code does. Do not explain what the hardware does.

This is the rule that matters most, and it is the one an earlier version of this
section got backwards by asking for "what physically happens."

Every written review comment Sebastian left over July–August — five, across
#284 and #288 — corrected an explanation of the hardware. None corrected the
code.
#284 stated the LCLS-II-HE loaded-Q window correctly, then explained it as the
same cavity "held to a looser standard" when it follows from a different default
Qext. #288 claimed active microphonics compensation the machine does not have
(it is slow drift feedback, cutoff a few Hz), and described cold landing as
recorded after the stepper moves rather than before.

Fluent wrong physics is worse than no physics: it reads authoritative, so it
costs the reviewer a fact-check instead of a read, and it is indistinguishable
from not having looked at the change at all.

Two categories, treated differently:

**Derivable from this repo — assert it.** Which PV is written, in what units,
in what order, what value, what the code branches on, where a constant lives.
Checkable against the source by whoever is reading. This is most of what the
area physicist actually needs.

**A fact about the physical machine — cite it or flag it.** Why the hardware
behaves that way, feedback bandwidths, what happens inside the cavity, the
ordering of physical events the code does not itself control. If a source exists
in-repo, point at it. If not, write the claim as a question instead of a
sentence:

```python
# CHECK: is DF_COLD recorded before the stepper moves, or after?
```

Reviewers can grep `CHECK:` and clear them in one pass. Three flagged questions
make a better PR than three confident sentences that turn out to be wrong —
and flagging them *is* the "pre-digest before sending it for review" that has
now been asked for two years running.

#### The rest

- **Make PV writes obvious.** Any code path that puts a value to the machine
  should be readable without tracing three layers of indirection. Name the PV,
  the units, and the value.
- **State hardware assumptions as assumptions.** The code encodes expectations
  about tuner behavior, limit switches, piezo state, and cavity frequency
  response. Name the expectation and where it is relied on. Do not justify it.
- **Cite the arithmetic in analysis code.** In `q0/`, `quench_processing/`,
  `microphonics/`: name the relationship and where the constants came from, with
  a source. A silent change to a fit is a silent change to a physics conclusion.
  Cite rather than re-derive.
- **Flag anything that changes what the machine does**, even when the code
  change looks cosmetic. Reordered writes, changed defaults, adjusted timeouts.

`applications/rf_commissioning/` remains single-maintainer. Non-trivial changes
there should be readable by someone who did not write them — favor explicit
naming and docstrings on phase logic over compact code.

### How to write it

This governs PR descriptions, docs, and comments. The audience is a physicist
and a manager, both reading between other things. Aim at what you would type in
Slack, not at a technical report.

The failure mode is measurable and it runs backwards: the smallest PRs get the
longest descriptions, because a small diff leaves room to explain. #292 is 66
lines of CI config and 580 words. #284 is 132 lines and 702 words, and is one of
only two PRs to draw written review comments.

**Budgets.** *What this changes*: 60 words. Each recorded decision: 80. If a
section needs more, the PR is probably too big — check the size comment.

**Register.** Lead with the verdict: "CI PR, no code touched." "Simple PR, just
colors and buttons." Say what the reader should do. Short sentences — if one
needs a comma to survive, split it. Hedge honestly ("my best guess is") rather
than elaborately.

**Cut on sight.** Restating what the diff already shows. Explaining at length
why a rejected alternative was rejected. Implementation detail nobody will act
on. Empty template headings — delete the heading rather than writing "None
tagged."

**Vocabulary: if it names something in the code, use it.** Cavity, detune,
cryomodule, piezo, SSA, chirp, `NSTEPS_COLD` — identifiers, PV names and
constants the reader can grep. No gloss needed. Jargon is the opposite: words
that exist only in prose. Orthogonal, idempotent, invariant, semantics,
pre-flight — none of them name anything in `src/`.

The test is grep, not taste, and it separates cleanly: each domain term above
appears in 10–217 files, each prose term in zero. It has to be identifiers
rather than any text match, or the jargon launders itself — write "source of
truth" into one docstring and it has "appeared in the code."

## Conventions

- Black 80-character line length; Flake8 allows up to 120 (the two tools have different limits — this is intentional).
- Releases use conventional commits (`feat`, `fix`, `perf`, `refactor`) and are published to GitHub Releases (not PyPI) via `python-semantic-release`.
- Packaged data (`.ui` files, `faults.csv`, Q0 calibration/example data) must be listed in `pyproject.toml` under `[tool.setuptools.package-data]` — CI verifies the built wheel contains them.
