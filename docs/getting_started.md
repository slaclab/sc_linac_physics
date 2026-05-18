# Getting Started

This guide is for new contributors — including those new to Python, PyQt, and EPICS.
By the end you will have written three working displays from scratch, each building on the last.

## Prerequisites

Follow the installation steps in [README.md](../README.md):

```bash
conda create -n sclp python=3.12
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
    app = PyDMApplication()
    window = CavityStatusDisplay()
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
    app = PyDMApplication()
    window = CryomoduleOverview()
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
- Try `CM = "H1"` (a high-loaded-Q cryomodule). Does it still run?

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

### Hints

**Getting the list of cryomodule names for L1B:**

```python
from sc_linac_physics.utils.sc_linac.linac_utils import L1B, L1BHL

# L1B = ["02", "03"]
# L1BHL = ["H1", "H2"]
all_cms = L1B + L1BHL
```

**An alarm-sensitive `PyDMLabel` changes color automatically based on EPICS alarm severity:**

```python
from pydm.widgets import PyDMLabel

# alarmSensitiveContent changes the text color; alarmSensitiveBorder adds a colored border.
# EPICS severity 0 = no alarm (green), 1 = minor (yellow), 2 = major (red), 3 = invalid (magenta).
# This correctly handles all severity levels — no manual bit manipulation needed.
fault_label = PyDMLabel(init_channel=prefix + "CUDSTATUS")
fault_label.alarmSensitiveBorder = True
fault_label.alarmSensitiveContent = True
fault_label.setFixedWidth(50)
```

**Using a `QGridLayout` for the table:**

```python
from PyQt5.QtWidgets import QGridLayout

grid = QGridLayout()
grid.addWidget(QLabel("CM"), 0, 0)           # row 0, col 0
grid.addWidget(QLabel("CAV1"), 0, 1)         # row 0, col 1
# ... add LED widgets at (row, col) positions ...
```

**Structure to aim for:**

```python
for row_idx, cm_name in enumerate(all_cms, start=1):
    grid.addWidget(QLabel(cm_name), row_idx, 0)
    for col_idx, cav_num in enumerate(range(1, 9), start=1):
        prefix = build_cavity_pv_prefix("L1B", cm_name, cav_num)
        led = ...  # create the LED for this cavity
        grid.addWidget(led, row_idx, col_idx)
```

---

## Next Steps

Once you're comfortable with these exercises:

- **`docs/utils/linac_model.md`** — complete PV naming reference and hardware constants.
- **`docs/utils/shared_utilities.md`** — the `PV` wrapper, `PVBatch`, logging.
- **`docs/applications/auto_setup.md`** — the first real application to read. Its
  `applications/auto_setup/frontend/` directory uses the same patterns you just practiced.
- **`utils/qt.py`** — the `Worker(QThread)` pattern for running blocking operations
  without freezing the UI.
- **`AGENTS.md`** — project-wide conventions you should follow when contributing.
