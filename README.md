
# sc_linac_physics

Controls, analysis, and displays for SC Linac operations.

- Python: 3.12+ (tested on 3.12 and 3.13)
- GUI stack: PyDM + PyQt5/Qt
- Includes packaged displays, configuration YAML/JSON, and example data

### Badges:

CI: [![CI](https://github.com/slaclab/sc_linac_physics/actions/workflows/python-app.yml/badge.svg?branch=main)](https://github.com/slaclab/sc_linac_physics/actions/workflows/python-app.yml)

Release: [![Release](https://github.com/slaclab/sc_linac_physics/actions/workflows/release.yml/badge.svg?branch=main)](https://github.com/slaclab/sc_linac_physics/actions/workflows/release.yml)

## Features

- PyDM-based operator displays for SC Linac
- Unified command-line interface for all displays and applications
- Hierarchical setup control (global → linac → cryomodule → cavity)
- Analysis utilities using NumPy/SciPy/scikit-learn
- Plotting with matplotlib and pyqtgraph
- EPICS/Channel Access via caproto and pyepics
- Configuration with YAML/JSON
- Packaged calibration and example data
- Simulated EPICS IOC service for testing and development

## Requirements

- Python >= 3.12
- Qt runtime (PyQt5)
- On Linux headless environments (CI/containers), Xvfb or offscreen Qt

Core dependencies (installed automatically):

- pydm, PyQt5, qtpy, pyqtgraph
- numpy, scipy, scikit-learn, matplotlib
- pydantic, pyyaml, h5py
- requests, urllib3, caproto
- lcls-tools and edmbutton from GitHub

System packages (Linux, recommended for headless testing):

- xvfb, libxkbcommon-x11-0, libglu1-mesa, libxcb-xinerama0

## Installation

From PyPI (if published):

```bash
pip install sc_linac_physics
```

From source:

```bash
git clone git@github.com:slaclab/sc_linac_physics.git
cd sc_linac_physics
pip install -U pip setuptools wheel
# Development + testing tools:
pip install -e ".[dev,test]"
# Or just the package:
# pip install -e .
```

Notes:

- If behind a firewall, ensure access to GitHub for dependency sources:
    - https://github.com/slaclab/edmbutton.git
    - https://github.com/slaclab/lcls-tools.git

## Quick Start

### Command Line Tools

After installation, the following commands are available:

#### General Launcher Utility

```bash
# List all available applications
sc-linac list

# Launch displays and applications
sc-linac cavity-display      # Launch the cavity control display.
sc-linac fault-count         # Launch the fault count display.
sc-linac fault-decoder       # Launch the fault decoder display.
sc-linac srf-home            # Launch the SRF home display.

sc-linac auto-setup          # Launch the auto setup GUI.
sc-linac microphonics        # Launch the microphonics GUI.
sc-linac q0-measurement      # Launch the Q0 measurement GUI.
sc-linac quench-processing   # Launch the quench processing GUI.
sc-linac tuning              # Launch the tuning GUI.
```

#### Display Launcher Shortcuts

```bash
sc-srf-home          # SRF home overview display - main control interface
sc-cavity            # Cavity control and monitoring display
sc-faults            # Cavity fault decoder with detailed diagnostics
sc-fcount            # Cavity fault count display and statistics
```

#### Application Launcher Shortcuts

```bash
sc-quench            # Quench processing application
sc-setup             # Automated cavity setup (GUI)
sc-q0                # Q0 measurement application
sc-tune              # Cavity tuning interface
```

#### Setup Commands (Hierarchical Control)

The setup commands provide hierarchical control from global (entire machine) down to individual cavities:

**Global Level - Entire Machine**
```bash
sc-setup-all                    # Setup all cryomodules
sc-setup-all --no_hl            # Setup all except HL cryomodules
sc-setup-all --shutdown         # Shutdown all cryomodules
```

**Linac Level**
```bash
sc-setup-linac -l 0             # Setup Linac 0 (all cryomodules in linac)
sc-setup-linac -l 1             # Setup Linac 1
sc-setup-linac -l 2 --shutdown  # Shutdown Linac 2
```

**Cryomodule Level**
```bash
sc-setup-cm -cm 01              # Setup Cryomodule 01 (all cavities)
sc-setup-cm -cm 02              # Setup Cryomodule 02
sc-setup-cm -cm H1 --shutdown   # Shutdown Cryomodule H1
sc-setup-cm -cm 03 -off         # Shutdown Cryomodule 03 (short form)
```

**Cavity Level**
```bash
sc-setup-cav -cm 01 -cav 1      # Setup specific cavity
sc-setup-cav -cm 02 -cav 3      # Setup CM02, cavity 3
sc-setup-cav -cm 01 -cav 2 -off # Shutdown specific cavity
```

#### Simulation Service

For testing and development without live hardware:

```bash
sc-sim                 # Start simulated IOC service
sc-sim --list-pvs      # List all available PVs
sc-sim --interfaces=127.0.0.1  # Run on localhost only
```

### Python API

Python import check:

```python
import sc_linac_physics

print("Package version:", getattr(sc_linac_physics, "__version__", "unknown"))
```

Programmatic display launching:

```python
from sc_linac_physics import launchers

# Launch displays programmatically
launchers.launch_srf_home()
launchers.launch_cavity_display()
launchers.launch_fault_decoder()
launchers.launch_fault_count()

# Launch applications
launchers.launch_quench_processing()
launchers.launch_auto_setup()
launchers.launch_q0_measurement()
launchers.launch_tuning()
```

### Using PyDM directly

You can also launch displays using PyDM directly:

```bash
pydm path/to/your_display.ui
```

Tip: Set PYDM_DEFAULT_PROTOCOL=fake to try displays without live PVs:

```bash
export PYDM_DEFAULT_PROTOCOL=fake
sc-cavity
```

Headless usage (e.g., servers/CI):

```bash
export QT_QPA_PLATFORM=offscreen
# or use Xvfb:
xvfb-run -a sc-srf-home
```

## Command Reference

### Complete Command List

**Displays:**
- `sc-srf-home` - SRF home overview display
- `sc-cavity` - Cavity control and monitoring
- `sc-faults` - Fault decoder
- `sc-fcount` - Fault count display

**Applications:**
- `sc-quench` - Quench processing
- `sc-setup` - Auto setup GUI
- `sc-q0` - Q0 measurement
- `sc-tune` - Tuning application

**Setup Commands:**
- `sc-setup-all` - Global setup (all cryomodules)
- `sc-setup-linac` - Linac level setup
- `sc-setup-cm` - Cryomodule level setup
- `sc-setup-cav` - Cavity level setup

**Simulation:**
- `sc-sim` - Simulated IOC service

### Setup Command Examples

```bash
# Setup entire machine
sc-setup-all

# Setup all except high-level cryomodules
sc-setup-all --no_hl

# Setup specific linac
sc-setup-linac -l 0

# Setup specific cryomodule
sc-setup-cm -cm 01

# Setup specific cavity
sc-setup-cav -cm 01 -cav 1

# Shutdown examples (add --shutdown or -off to any command)
sc-setup-all --shutdown
sc-setup-linac -l 0 -off
sc-setup-cm -cm 01 --shutdown
sc-setup-cav -cm 01 -cav 1 -off
```

### Cryomodule and Cavity Numbers

- Cryomodules: `01`, `02`, `03`, `H1`, `H2`, `04`-`35`
- Cavities: `1` through `8`
- Linacs: `0` through `3`

Examples:
```bash
sc-setup-cav -cm 01 -cav 1    # Cryomodule 01, cavity 1
sc-setup-cav -cm H1 -cav 5    # High-level cryomodule H1, cavity 5
sc-setup-cm -cm 15            # Cryomodule 15
```

## Development

Set up environment:

```bash
git clone git@github.com:slaclab/sc_linac_physics.git
cd sc_linac_physics
pip install -U pip setuptools wheel
pip install -e ".[dev,test]"
```

Code style and lint:

```bash
flake8 . --count --max-complexity=10 --max-line-length=120 --show-source --statistics
black --check .
# To auto-format:
# black .
```

Run tests with coverage (Linux headless):

```bash
export QT_QPA_PLATFORM=offscreen
pytest

# Run specific test files
pytest tests/test_cli.py -v
pytest tests/test_launchers.py -v
```

Combine multi-version coverage (if you test with multiple Python versions):

```bash
python -m pip install --upgrade coverage
coverage combine
coverage report -m
coverage html -d htmlcov
```

### Adding New Displays

1. Create your display file in `src/sc_linac_physics/displays/`
2. Add a launcher function in `launchers.py`:

```python
def launch_my_display():
    """Launch my custom display."""
    from pydm import PyDMApplication
    from pathlib import Path

    app = PyDMApplication()
    display_path = Path(__file__).parent / "displays" / "my_display.ui"
    app.make_main_window(str(display_path))
    app.exec_()
```

3. Add a script entry in `pyproject.toml`:

```toml
[project.scripts]
sc-my-display = "sc_linac_physics.launchers:launch_my_display"
```

4. Add tests in `tests/test_launchers.py`

### Adding New CLI Tools

1. Create your script with a `main()` function
2. Add an entry in `pyproject.toml`:

```toml
[project.scripts]
sc-my-tool = "sc_linac_physics.path.to.module:main"
```

3. Reinstall: `pip install -e .`
4. Test: `sc-my-tool --help`

## Release Process

Releases are automated with semantic-release on pushes to the main branch.

- Commit messages follow the Angular convention (examples below)
- Version is derived from commit history and written to pyproject.toml
- GitHub Releases are created with changelog and build artifacts (sdist/wheel)
- Tags are formatted as v{version} (e.g., v0.2.3)

Commit message examples:

- `feat(q0): add automated calibration routine`
- `feat(cli): add hierarchical setup commands`
- `fix(display): prevent crash when PV is disconnected`
- `docs: update operator instructions`
- `refactor: simplify analysis pipeline`
- `chore: update CI Python versions`
- `perf: speed up data loading`
- `test(cli): add comprehensive CLI test coverage`
- `BREAKING CHANGE: rename module sc_linac_physics.foo to sc_linac_physics.bar`

Note: Upload to PyPI is disabled by default; artifacts are attached to GitHub Releases.

## Project Structure and Data

Packaged data included under the distribution:

- displays/*
- applications/q0/calibrations/*
- applications/q0/data/*
- Any *.ui, *.yaml, *.yml, *.json files

Access packaged files robustly via importlib.resources (Python 3.12+), not relative paths.

Example:

```python
from importlib.resources import files

base = files("sc_linac_physics")
display_dir = base / "displays"
for p in display_dir.iterdir():
    if p.suffix == ".ui":
        print("Found display:", p)
```

## Troubleshooting

- **Qt errors in headless environments:**
    - Set `QT_QPA_PLATFORM=offscreen` or use Xvfb (`xvfb-run -a ...`)
- **PV connections during development:**
    - Use `PYDM_DEFAULT_PROTOCOL=fake` to test UI flow without EPICS
- **Import issues when developing:**
    - Ensure editable install (`-e`) or add src/ to PYTHONPATH
- **CLI command not found after installation:**
    - Reinstall with `pip install -e .` or check that your virtual environment is activated
    - Verify console_scripts entry points in pyproject.toml
- **Invalid cryomodule name:**
    - Use just the number (e.g., `01`, `H1`) not `CM01`
    - Valid choices shown in error message or help text

## Contributing

- Open issues and pull requests are welcome
- Please run black and flake8 locally before submitting
- Add tests for new features/bugfixes where possible
- Use conventional commit messages (Angular style) to drive automated releases

## License

This project is licensed under the terms described in the LICENSE file included with the repository.

## Authors

- Lisa Zacarias (zacarias@slac.stanford.edu)
- Sebastian Aderhold (aderhold@slac.stanford.edu)
- Derikka Bisi (dabisi@slac.stanford.edu)
- Haley Marts (hmarts@slac.stanford.edu)

## Changelog

See CHANGELOG.md for release notes (auto-generated by semantic-release).
