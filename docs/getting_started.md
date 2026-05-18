# Getting Started

This guide is for new contributors — including those new to Python, PyQt, and EPICS.
By the end you will have written three working displays from scratch, each building on the last.

## Prerequisites

Follow the installation steps in [README.md](../README.md):

```bash
conda create -n sclp python
conda activate sclp
pip install -e ".[dev,test]"
```

Verify your install:

```bash
pytest
```

---

## Background

You only need to understand three things before starting the exercises.

### EPICS and Process Variables

The accelerator hardware (cavities, SSAs, tuners) publishes its state over a protocol called
**EPICS**. Each measured or controlled quantity — gradient, fault status, drive level — is
exposed as a **Process Variable (PV)**. A PV has a name and a value that updates in real time.

PV names in this codebase follow a strict pattern:

```
ACCL:{linac}:{cryomodule}{cavity}0:{suffix}
```

For example, the gradient readback of cavity 1 in cryomodule 02 of linac L1B is:

```
ACCL:L1B:0210:GACT
```

The helper `build_cavity_pv_prefix` in `utils/sc_linac/linac_utils.py` constructs the prefix
for you:

```python
from sc_linac_physics.utils.sc_linac.linac_utils import build_cavity_pv_prefix

prefix = build_cavity_pv_prefix("L1B", "02", 1)
# -> "ACCL:L1B:0210:"
full_pv = prefix + "GACT"
# -> "ACCL:L1B:0210:GACT"
```

### Qt and the Event Loop

Qt is the GUI toolkit. A Qt program is not a script that runs top-to-bottom — it starts an
**event loop** that keeps the window alive and responds to user actions (clicks, PV updates,
timer ticks). The last line of every display script hands control over to the event loop:

```python
sys.exit(app.exec_())
```

Everything visible on screen is a **widget** (`QLabel`, `QPushButton`, …). Widgets are
arranged using **layouts** (`QVBoxLayout` for vertical stacking, `QHBoxLayout` for horizontal).
You attach a layout to a widget, add child widgets to the layout, and Qt handles all sizing and
positioning.

**One critical rule:** never do blocking work (sleep, network calls, EPICS reads) on the main
thread. Doing so freezes the UI. Long-running operations belong in a background thread — see
`utils/qt.py` and `docs/utils/shared_utilities.md` once you're comfortable with the basics.

### PyDM

**PyDM** is a layer on top of Qt built specifically for control-system displays. Its key
contribution is **channel-aware widgets**: a `PyDMLabel` is just a `QLabel` that knows how to
subscribe to a PV and update itself whenever the value changes. You pass the PV name as
`init_channel` and PyDM handles the rest:

```python
from pydm.widgets import PyDMLabel

label = PyDMLabel(init_channel="ACCL:L1B:0210:GACT")
# This label will show the live gradient value and update automatically.
```

All displays in this codebase inherit from `pydm.Display` rather than `QWidget` directly.

---

## Starting the Simulator

The exercises below connect to a simulated EPICS IOC so you can see live (fake) data without
real hardware. Open a **separate terminal** and run:

```bash
conda activate sclp
sc-sim
```

Leave it running for the duration of the exercises. You should see Caproto IOC startup messages.

If you just want to check layout without any data (no second terminal needed), set:

```bash
export PYDM_DEFAULT_PROTOCOL=fake
```

Values will be zero or empty, but the display will still open.

---

## Exercise 1: A Single Cavity Status Display

**Goal:** Build a read-only status panel for one cavity.
**Concepts:** `pydm.Display`, `QVBoxLayout`/`QHBoxLayout`, `PyDMLabel`, event loop boilerplate.

### What you will build

```
┌─ Cavity L1B:CM02:CAV1 ─────────────────┐
│  Gradient actual (MV/m):      16.0      │
│  Drive level (%):              0.0      │
│  SSA status:                  SSA On    │
│  Fault code:                  TLC       │
└─────────────────────────────────────────┘
```

### Step 1 — Create the file

Create `cavity_status.py` anywhere outside the `src/` tree (your home directory is fine).

### Step 2 — Write the display class

```python
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)
from pydm import Display, PyDMApplication
from pydm.widgets import PyDMLabel

LINAC = "L1B"
CM = "02"
CAV = 1

# Build the PV prefix for this cavity.
# Result: "ACCL:L1B:0210:"
PV_PREFIX = f"ACCL:{LINAC}:{CM}{CAV}0:"


class CavityStatusDisplay(Display):
    def __init__(self, parent=None, args=None, macros=None):
        # Always call super().__init__ — Display does important setup here.
        super().__init__(parent=parent, args=args, macros=macros)
        self.setWindowTitle(f"Cavity {LINAC}:CM{CM}:CAV{CAV}")

        # The outermost layout belongs to the Display widget itself.
        outer = QVBoxLayout()
        self.setLayout(outer)

        # A QGroupBox is a labelled border around a group of related widgets.
        group = QGroupBox(f"Cavity {LINAC}:CM{CM}:CAV{CAV}")
        group_layout = QVBoxLayout()
        group.setLayout(group_layout)
        outer.addWidget(group)

        # Each row: a plain QLabel on the left, a live PyDMLabel on the right.
        for description, pv_suffix in [
            ("Gradient actual (MV/m):", "GACT"),
            ("Drive level (%):", "SEL_ASET"),
            ("SSA status:", "SSA:StatusMsg"),
            ("Fault code:", "CUDSTATUS"),
        ]:
            row = QHBoxLayout()
            row.addWidget(QLabel(description))

            # PyDMLabel subscribes to the PV and refreshes whenever the value
            # changes — no polling code needed.
            value = PyDMLabel(init_channel=PV_PREFIX + pv_suffix)
            value.setAlignment(Qt.AlignRight)
            row.addWidget(value)

            group_layout.addLayout(row)


if __name__ == "__main__":
    # PyDMApplication owns the event loop and initializes PyDM data plugins.
    # Using plain QApplication here would leave PyDMLabel unable to connect to PVs.
    # use_main_window=False prevents PyDM from opening an extra empty window.
    app = PyDMApplication(use_main_window=False)
    window = CavityStatusDisplay()
    window.resize(380, 160)
    window.show()
    # exec_() blocks here until the window is closed.
    sys.exit(app.exec_())
```

### Step 3 — Run it

With `sc-sim` already running in another terminal:

```bash
python cavity_status.py
```

### Things to try

- Change `CAV = 1` to another number (1–8) and rerun. What changes?
- Change `CM = "02"` to `"03"` (another cryomodule in L1B). Does it still work?
- What happens if you set `CM = "99"` (a cryomodule that doesn't exist in the simulator)?
- Add a fifth row showing `AACTMEAN` (mean amplitude). What units does it use?

---

## Exercise 2: A Cryomodule Overview

**Goal:** Show all 8 cavities of one cryomodule in a single display.
**Concepts:** loops for dynamic widget creation, `build_cavity_pv_prefix`, `QScrollArea`.

### What you will build

```
┌─ Cryomodule L1B:CM02 ─────────────────────────────────────────┐
│  CAV1   Gradient: 16.0 MV/m   SSA: SSA On   Fault: TLC        │
│  CAV2   Gradient: 16.0 MV/m   SSA: SSA On   Fault: TLC        │
│  ...                                                           │
│  CAV8   Gradient: 16.0 MV/m   SSA: SSA On   Fault: TLC        │
└────────────────────────────────────────────────────────────────┘
```

### Starter code

Create `cryomodule_overview.py` and fill in the `TODO` sections:

```python
import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QScrollArea,
    QWidget,
)
from pydm import Display, PyDMApplication
from pydm.widgets import PyDMLabel

from sc_linac_physics.utils.sc_linac.linac_utils import build_cavity_pv_prefix

LINAC = "L1B"
CM = "02"


class CryomoduleOverview(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.setWindowTitle(f"Cryomodule {LINAC}:CM{CM}")

        outer = QVBoxLayout()
        self.setLayout(outer)

        header = QLabel(f"Cryomodule {LINAC}:CM{CM} — 8 Cavities")
        header.setAlignment(Qt.AlignCenter)
        outer.addWidget(header)

        # QScrollArea lets the window scroll if its contents are taller than
        # the screen.  We create a plain QWidget to hold the cavity rows, then
        # place it inside the scroll area.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout()
        container.setLayout(container_layout)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        for cav_num in range(1, 9):
            prefix = build_cavity_pv_prefix(LINAC, CM, cav_num)
            row_widget = self._make_cavity_row(cav_num, prefix)
            container_layout.addWidget(row_widget)

    def _make_cavity_row(self, cav_num: int, prefix: str) -> QGroupBox:
        group = QGroupBox(f"CAV{cav_num}")
        layout = QHBoxLayout()
        group.setLayout(layout)

        layout.addWidget(QLabel(f"CAV{cav_num}"))

        # TODO: Add a PyDMLabel showing gradient (suffix: "GACT")
        #       Label it "Gradient:"

        # TODO: Add a PyDMLabel showing SSA status (suffix: "SSA:StatusMsg")
        #       Label it "SSA:"

        # TODO: Add a PyDMLabel showing the fault code (suffix: "CUDSTATUS")
        #       Label it "Fault:"

        return group


if __name__ == "__main__":
    app = PyDMApplication(use_main_window=False)
    window = CryomoduleOverview()
    window.resize(600, 400)
    window.show()
    sys.exit(app.exec_())
```

### Run it

```bash
python cryomodule_overview.py
```

### Things to try

- The `alarmSensitiveBorder` and `alarmSensitiveContent` properties on `PyDMLabel` make the
  widget change color when the PV goes into alarm. Try setting both to `True` on the fault label.
- Add a column showing `AACTMEAN` (mean amplitude). How does the layout look with five columns?
- Try `CM = "H1"` (a third-harmonic cryomodule). Does it still run?

---

## Exercise 3: A Linac-Wide Summary

**Goal:** One row per cryomodule, showing a fault indicator for each of its 8 cavities.
**Concepts:** iterating the hardware model, alarm-sensitive widgets, `QGridLayout`.

### What you will build

```
┌─ L1B Status ──────────────────────────────────────────────────────────────────┐
│        CAV1   CAV2   CAV3   CAV4   CAV5   CAV6   CAV7   CAV8                 │
│  CM02   TLC    TLC    TLC    TLC    TLC    TLC    TLC    TLC                  │
│  CM03   TLC    TLC    TLC    TLC    TLC    TLC    TLC    TLC                  │
│  H1     TLC    TLC    TLC    TLC    TLC    TLC    TLC    TLC                  │
│  H2     TLC    TLC    TLC    TLC    TLC    TLC    TLC    TLC                  │
└───────────────────────────────────────────────────────────────────────────────┘
  sc-sim initializes all cavities to MINOR alarm — labels will appear yellow.
```

Before writing any code, skim the **Object hierarchy** and **Instantiation pattern** sections of
[`docs/utils/linac_model.md`](utils/linac_model.md) — it explains how `Machine`, `Linac`,
`Cryomodule`, and `Cavity` relate, and shows the `pv_addr` / `pv_prefix` API you will use below.

### Starter code

Create `linac_summary.py` and fill in the `TODO` section:

```python
import sys

from PyQt5.QtWidgets import (
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)
from pydm import Display, PyDMApplication
from pydm.widgets import PyDMLabel

from sc_linac_physics.utils.sc_linac.linac import Machine

# Build the full hardware object tree.  No EPICS connections are made yet —
# PVs are only opened when a widget first accesses them.
MACHINE = Machine()
LINAC = MACHINE.linacs[1]  # machine.linacs is ordered [L0B, L1B, L2B, L3B, L4B]


class LinacSummary(Display):
    def __init__(self, parent=None, args=None, macros=None):
        super().__init__(parent=parent, args=args, macros=macros)
        self.setWindowTitle(f"{LINAC.name} Fault Summary")

        outer = QVBoxLayout()
        self.setLayout(outer)

        # Wrap the grid in a scroll area so the window stays a manageable size.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        grid = QGridLayout()
        container.setLayout(grid)
        scroll.setWidget(container)
        outer.addWidget(scroll)

        # Header row: one column label per cavity number.
        grid.addWidget(QLabel("CM"), 0, 0)
        for col, cav_num in enumerate(range(1, 9), start=1):
            grid.addWidget(QLabel(f"CAV{cav_num}"), 0, col)

        # Data rows: one row per cryomodule, one cell per cavity.
        # linac.cryomodules is a dict keyed by name string ("02", "H1", …).
        # cm.cavities is a dict keyed by cavity number int (1–8).
        for row, (cm_name, cm) in enumerate(LINAC.cryomodules.items(), start=1):
            grid.addWidget(QLabel(cm_name), row, 0)
            for col, cavity in enumerate(cm.cavities.values(), start=1):
                # TODO: create a PyDMLabel connected to cavity.pv_addr("CUDSTATUS")
                #       set alarmSensitiveBorder and alarmSensitiveContent to True
                #       set a fixed width of 50 and add it to the grid
                pass


if __name__ == "__main__":
    app = PyDMApplication(use_main_window=False)
    window = LinacSummary()
    window.resize(600, 250)
    window.show()
    sys.exit(app.exec_())
```

### Run it

```bash
python linac_summary.py
```

### Things to try

- `cavity.pv_addr(suffix)` is equivalent to `cavity.pv_prefix + suffix`. Print
  `cavity.pv_prefix` for a few cavities to see the full PV naming scheme in action.
- Try iterating over `MACHINE.linacs` instead of a single linac to show all five sections.
  What layout changes are needed to keep it readable?
- `cm.cavities` is a `Dict[int, Cavity]`. What other attributes does `Cavity` expose?
  Browse `utils/sc_linac/cavity.py` and add a second grid showing a different PV.

---

## Next Steps

Once you're comfortable with the exercises above, you can find more detailed documentation and information in the following files:

- **`docs/utils/linac_model.md`** — complete PV naming reference and hardware constants.
- **`docs/utils/shared_utilities.md`** — the `PV` wrapper, `PVBatch`, logging.
- **`docs/applications/auto_setup.md`** — the first real application to read. Its
  `applications/auto_setup/frontend/` directory uses the same patterns you just practiced.
- **`utils/qt.py`** — the `Worker(QThread)` pattern for running blocking operations
  without freezing the UI.
- **`AGENTS.md`** — project-wide conventions you should follow when contributing.
