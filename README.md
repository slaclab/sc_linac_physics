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
- Analysis utilities using NumPy/SciPy/scikit-learn
- Plotting with matplotlib and pyqtgraph
- EPICS/Channel Access via caproto and pyepics
- Configuration with YAML/JSON
- Packaged calibration and example data

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
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
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

## Quick start

Python import check:

```python
import sc_linac_physics

print("Package version:", getattr(sc_linac_physics, "__version__", "unknown"))
```

Running displays:

- The package includes PyDM UI files under the “displays” directory.
- You can launch a display using PyDM, for example:

```bash
pydm path/to/your_display.ui
```

Tip: Set PYDM_DEFAULT_PROTOCOL=fake to try displays without live PVs:

```bash
export PYDM_DEFAULT_PROTOCOL=fake
```

Headless usage (e.g., servers/CI):

```bash
export QT_QPA_PLATFORM=offscreen
# or use Xvfb:
xvfb-run -a pydm path/to/your_display.ui
```

## Development

Set up environment:

```bash
git clone git@github.com:slaclab/sc_linac_physics.git
cd sc_linac_physics
python -m venv .venv
source .venv/bin/activate
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
```

Combine multi-version coverage (if you test with multiple Python versions):

```bash
python -m pip install --upgrade coverage
coverage combine
coverage report -m
coverage html -d htmlcov
```

## Release process

Releases are automated with semantic-release on pushes to the main branch.

- Commit messages follow the Angular convention (examples below)
- Version is derived from commit history and written to pyproject.toml
- GitHub Releases are created with changelog and build artifacts (sdist/wheel)
- Tags are formatted as v{version} (e.g., v0.2.3)

Commit message examples:

- feat(q0): add automated calibration routine
- fix(display): prevent crash when PV is disconnected
- docs: update operator instructions
- refactor: simplify analysis pipeline
- chore: update CI Python versions
- perf: speed up data loading
- BREAKING CHANGE: rename module sc_linac_physics.foo to sc_linac_physics.bar

Note: Upload to PyPI is disabled by default; artifacts are attached to GitHub Releases.

## Project structure and data

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

- Qt errors in headless environments:
    - Set QT_QPA_PLATFORM=offscreen or use Xvfb (xvfb-run -a ...)
- PV connections during development:
    - Use PYDM_DEFAULT_PROTOCOL=fake to test UI flow without EPICS
- Import issues when developing:
    - Ensure editable install (-e) or add src/ to PYTHONPATH

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