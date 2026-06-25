# sc_linac_physics

Operator displays, analysis tools, and command-line interface for the LCLS-II superconducting (SC) linac at SLAC.

[![CI](https://github.com/slaclab/sc_linac_physics/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/slaclab/sc_linac_physics/actions/workflows/python-app.yml)
[![Release](https://github.com/slaclab/sc_linac_physics/actions/workflows/release.yml/badge.svg?branch=main)](https://github.com/slaclab/sc_linac_physics/actions/workflows/release.yml)

The LCLS superconducting linac accelerates an electron beam through five sections (L0B–L4B) containing 60 cryomodules and 480 superconducting RF cavities. This package provides the software used by operators and physicists to control, monitor, and commission those cavities: PyDM-based GUIs, hierarchical setup automation, fault monitoring, and analysis tools for Q0 measurement, microphonics, and tuning.

For architecture documentation and per-application guides, see [`docs/`](docs/index.md).

## Installation

This project requires Python 3.12+. The easiest way to get started:

1. **Install conda** (if you don't have it): Follow the [conda installation guide](https://docs.conda.io/projects/conda/en/latest/user-guide/install/)

2. **Create a Python environment:**

```bash
conda create -n sclp "python>=3.12"
conda activate sclp
```

3. **Install this package** from source (not published to PyPI):

Optional: set up GitHub SSH first (recommended for contributors):

```bash
ssh-keygen -t ed25519 -C "your_email@example.com"
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub
```

Add the printed key to GitHub:

- https://github.com/settings/keys

Then verify SSH access:

```bash
ssh -T git@github.com
```

Clone with SSH:

```bash
git clone git@github.com:slaclab/sc_linac_physics.git
```

Or clone with HTTPS (no SSH key setup required):

```bash
git clone https://github.com/slaclab/sc_linac_physics.git
```

Then install:

```bash
cd sc_linac_physics
pip install -e ".[dev,test]"
```

For package-only installation (without development/testing dependencies), use:

```bash
pip install -e .
```

> Two dependencies (`edmbutton`, `lcls-tools`) install from `github.com/slaclab` and require network access.

## Quick Start

### Running displays locally

To run displays without live accelerator hardware, start the simulator in one terminal:

```bash
conda activate sclp
sc-sim
```

Then launch any display in another terminal:

```bash
sc-srf-home
```

### Learning to develop

New to this codebase? Start with the [Getting Started Guide](docs/getting_started.md), which walks you through three hands-on exercises building displays from scratch. You'll learn EPICS, PyQt, and PyDM basics along the way. The guide uses `sc-sim` for live data and also includes a layout-only mode with `PYDM_DEFAULT_PROTOCOL=fake`.

## Usage

Run `sc-linac list` to see all available commands. Key entry points:

| Command | Description |
|---------|-------------|
| `sc-srf-home` | Main operator dashboard |
| `sc-cavity` | Real-time fault monitoring across all 296 cavities |
| `sc-setup` | Automated cavity setup GUI |

Setup commands (`sc-setup-all`, `sc-setup-linac`, `sc-setup-cm`, `sc-setup-cav`) automate cavity turn-on across hierarchy levels. Run any with `--help` for usage.

## Development

### Testing

80% coverage is required and enforced in CI. Tests mock EPICS and do not require the simulator.

```bash
pytest
pytest tests/test_cli.py -v   # single file
```

### Linting and formatting

Pre-commit hooks run `black` and `flake8` automatically on each commit (set up via `pre-commit install`). To run manually:

```bash
black .
flake8 . --count --max-complexity=10 --max-line-length=120 --show-source --statistics
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

### Releases

Releases are automated via `python-semantic-release` on pushes to `main`. Commits must follow the Angular convention — the version bump and changelog entry are derived automatically.

```
feat(q0): add automated calibration routine   → minor bump
fix(display): prevent crash on PV disconnect   → patch bump
BREAKING CHANGE: ...                           → major bump
```

The latest tagged release is automatically deployed to production every Tuesday afternoon.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Displays show no data | Start the simulator with `sc-sim` |
| Qt errors in headless environments | `export QT_QPA_PLATFORM=offscreen` or `xvfb-run -a ...` |
| `ImportError` after cloning | Use editable install: `pip install -e .` |
| CLI command not found | Run `conda activate sclp` and try again; if still missing, reinstall with `pip install -e .` |
| `Invalid cryomodule` error | Use bare number (`01`, `H1`), not `CM01` |

## Contributing

PRs and issues are welcome. After cloning, install the pre-commit hooks:

```bash
pre-commit install
```

This runs `black` and `flake8` automatically on each commit. Add tests for new behavior and use conventional commit messages to keep the automated changelog accurate.

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
