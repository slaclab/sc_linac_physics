# sc_linac_physics

Operator displays, analysis tools, and command-line interface for the LCLS-II superconducting (SC) linac at SLAC.

[![CI](https://github.com/slaclab/sc_linac_physics/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/slaclab/sc_linac_physics/actions/workflows/python-app.yml)
[![Release](https://github.com/slaclab/sc_linac_physics/actions/workflows/release.yml/badge.svg?branch=main)](https://github.com/slaclab/sc_linac_physics/actions/workflows/release.yml)

The SC linac accelerates the LCLS-II electron beam through five sections (L0B–L4B) containing 60 cryomodules and 296 superconducting RF cavities. This package provides the software used by operators and physicists to control, monitor, and commission those cavities: PyDM-based GUIs, hierarchical setup automation, fault monitoring, and analysis tools for Q0 measurement, microphonics, and tuning.

For architecture documentation and per-application guides, see [`docs/`](docs/index.md).

## Installation

Requires Python 3.12+. Install from source (not published to PyPI):

```bash
git clone git@github.com:slaclab/sc_linac_physics.git
cd sc_linac_physics
pip install -e ".[dev,test]"   # development + testing
# pip install -e .             # package only
```

> Two dependencies (`edmbutton`, `lcls-tools`) install from `github.com/slaclab` and require network access.

## Displays and Applications

All GUIs require PyQt5. Use `sc-linac list` to see everything available.

| Command | Description |
|---------|-------------|
| `sc-srf-home` | Main operator dashboard — launches other tools, manages background watchers |
| `sc-cavity` | Real-time fault monitoring across all 296 cavities with heatmap visualization |
| `sc-faults` | Cavity fault decoder |
| `sc-fcount` | Fault count statistics |
| `sc-setup` | Automated cavity setup GUI (SSA cal → auto-tune → characterization → RF ramp) |
| `sc-q0` | Q0 (cavity quality factor) measurement |
| `sc-tune` | Cavity frequency tuning interface |
| `sc-quench` | Quench processing — auto-resets false trips, logs real quenches |

The unified launcher `sc-linac <command>` is an alternative entry point for all of the above.

## Setup Commands

Setup commands automate cavity turn-on across four hierarchy levels. Append `--shutdown` (or `-off`) to any command to reverse it.

```bash
# Entire machine
sc-setup-all
sc-setup-all --no_hl        # exclude harmonic linearizer cryomodules
sc-setup-all --shutdown

# One linac section (0–4)
sc-setup-linac -l 2
sc-setup-linac -l 2 --shutdown

# One cryomodule
sc-setup-cm -cm 01
sc-setup-cm -cm H1 --shutdown

# One cavity
sc-setup-cav -cm 01 -cav 3
sc-setup-cav -cm 01 -cav 3 -off
```

**Valid identifiers:**
- Linacs: `0`–`4` (L0B, L1B, L2B, L3B, L4B)
- Cryomodules: `01` (L0B) · `02`–`03` (L1B) · `H1`–`H2` (HL) · `04`–`15` (L2B) · `16`–`35` (L3B) · `37`–`59` (L4B)
- Cavities: `1`–`8` — use the bare number (`01`, not `CM01`)

## Operations Polling

```bash
sc-tune-status-poll     # persist TUNE_CONFIG + DF_COLD snapshots to SQLite + JSON
sc-tune-status-query    # interactive or one-shot SQL query against the SQLite DB
sc-sim                  # start simulated EPICS IOC for development without hardware
```

## Development

### Setup

```bash
git clone git@github.com:slaclab/sc_linac_physics.git
cd sc_linac_physics
pip install -e ".[dev,test]"
```

### Testing

80% coverage is required and enforced in CI.

```bash
QT_QPA_PLATFORM=offscreen pytest
QT_QPA_PLATFORM=offscreen pytest tests/test_cli.py -v   # single file
```

### Linting and formatting

```bash
flake8 . --count --max-complexity=10 --max-line-length=120 --show-source --statistics
black --check .
black .                 # auto-format
```

### Running without live hardware

```bash
export PYDM_DEFAULT_PROTOCOL=fake   # UI testing without EPICS
export QT_QPA_PLATFORM=offscreen    # headless Qt (CI, servers)
# or: xvfb-run -a sc-srf-home
```

### Architecture

```
src/sc_linac_physics/
├── utils/          Shared infrastructure: hardware model, EPICS wrappers, Qt utilities
├── applications/   Standalone applications (auto_setup, q0, tuning, …)
├── displays/       PyDM operator displays (cavity_display, srfhome, …)
└── cli/            Unified entry-point launcher and watcher management
```

The hardware model (`utils/sc_linac/`) defines a `Machine → Linac → Cryomodule → Rack → Cavity` hierarchy reused by every application. See [`docs/`](docs/index.md) for detailed per-module documentation.

### Adding a display

1. Create a `pydm.Display` subclass under `src/sc_linac_physics/displays/`
2. Register it with the `@display` decorator in `cli/launchers.py`
3. Add a `[project.scripts]` entry in `pyproject.toml`
4. Add tests in `tests/`

### Release process

Releases are automated via `python-semantic-release` on pushes to `main`. Commits must follow the Angular convention — the version bump and changelog entry are derived automatically.

```
feat(q0): add automated calibration routine   → minor bump
fix(display): prevent crash on PV disconnect   → patch bump
BREAKING CHANGE: ...                           → major bump
```

Artifacts (sdist + wheel) are attached to GitHub Releases. PyPI publishing is disabled.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Qt errors in headless environments | `export QT_QPA_PLATFORM=offscreen` or `xvfb-run -a ...` |
| PV connections during development | `export PYDM_DEFAULT_PROTOCOL=fake` |
| `ImportError` after cloning | Use editable install: `pip install -e .` |
| CLI command not found | Reinstall with `pip install -e .` and check your venv is active |
| `Invalid cryomodule` error | Use bare number (`01`, `H1`), not `CM01` |

## Contributing

PRs and issues are welcome. Before submitting: run `black` and `flake8`, add tests for new behavior, and use conventional commit messages to keep the automated changelog accurate.

## Authors

- Lisa Zacarias (zacarias@slac.stanford.edu)
- Sebastian Aderhold (aderhold@slac.stanford.edu)
- Derikka Bisi (dabisi@slac.stanford.edu)
- Haley Marts (hmarts@slac.stanford.edu)

See [CHANGELOG.md](CHANGELOG.md) for release notes.

## License

See [LICENSE](LICENSE).

COPYRIGHT © SLAC National Accelerator Laboratory. This work is supported in part by the U.S. Department of Energy, Office of Basic Energy Sciences under contract DE-AC02-76SF00515.

Neither the name of the Leland Stanford Junior University, SLAC National Accelerator Laboratory, U.S. Department of Energy nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
