"""Builds the MP Processing display UI.

Same grid as PiezoWithRFUI: toolbar and status against Stored Data, then
Settings against Live PVs. Below them, one row per quench, then Phase
History.
"""

from typing import NamedTuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QVBoxLayout,
)
from pydm.widgets import PyDMLabel

from sc_linac_physics.applications.rf_commissioning.phases.mp_processing import (  # noqa: E501
    MPProcessingLimits,
)

from .base import PhaseUIBase
from .styles import PV_LABEL_STYLE
from .theme import (
    BG_INSET,
    BG_PANEL,
    BORDER,
    MONO_FONT_STACK,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)

QUENCH_COLUMNS = ("#", "Time", "ADES (MV)", "Since previous (s)")

# No app-wide rule styles tables, so without this Qt falls back to the
# system palette: white cells in the dark theme.
QUENCH_TABLE_STYLE = f"""
    QTableWidget {{
        background-color: {BG_INSET};
        alternate-background-color: {BG_PANEL};
        color: {TEXT_PRIMARY};
        gridline-color: {BORDER};
        border: 1px solid {BORDER};
        font-family: {MONO_FONT_STACK};
    }}
    QHeaderView::section {{
        background-color: {BG_PANEL};
        color: {TEXT_SECONDARY};
        border: none;
        border-bottom: 1px solid {BORDER};
        padding: 3px;
    }}
"""


class Setting(NamedTuple):
    """One spin box for an MPProcessingLimits field.

    The box shows field / scale: stable time is set in minutes, and
    MPProcessingLimits keeps seconds.
    """

    widget: str
    caption: str
    field: str
    unit: str
    low: float
    high: float
    step: float
    decimals: int
    scale: float = 1.0


SETTINGS = (
    Setting("start_mv_spin", "Start ADES:", "start_amplitude_mv", "MV",
            0.5, 30.0, 0.1, 2),
    Setting("step_mv_spin", "Step:", "step_mv", "MV", 0.01, 2.0, 0.05, 2),
    Setting("step_seconds_spin", "Step every:", "step_seconds", "s",
            1.0, 600.0, 5.0, 0),
    Setting("stable_minutes_spin", "Stable after:", "stable_seconds", "min",
            0.5, 120.0, 0.5, 1, scale=60.0),
)  # fmt: skip


class MPProcessingUI(PhaseUIBase):
    """Builds the MP Processing display UI."""

    def build(self) -> QVBoxLayout:
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.addLayout(self._build_main_toolbar(), 0, 0)
        grid.addWidget(self._build_status(), 1, 0)
        grid.addWidget(
            self._build_stored_data_section(
                self._get_parent_stored_data_fields()
            ),
            0,
            1,
            2,
            1,
        )
        grid.addWidget(self._build_settings(), 2, 0)
        grid.addWidget(self._build_live_pvs(), 2, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        main_layout.addLayout(grid)
        main_layout.addWidget(self._build_quench_table(), stretch=1)
        main_layout.addWidget(self._build_history(), stretch=1)
        return main_layout

    def _build_status(self) -> QGroupBox:
        """This run, read from record.mp_processing once a second."""
        group = QGroupBox("MP Processing")
        layout = QGridLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        rows = (
            ("Step:", "step_label"),
            ("Phase:", "local_phase_status"),
            ("Quenches:", "quench_count_label"),
            ("Highest ADES written:", "max_ades_label"),
            ("Since last quench:", "since_quench_label"),
        )
        for row, (caption, name) in enumerate(rows):
            layout.addWidget(QLabel(caption), row, 0)
            layout.addWidget(
                self._register(name, self._make_local_label("-")), row, 1
            )
        group.setLayout(layout)
        return group

    def _build_settings(self) -> QGroupBox:
        """MPProcessingLimits for the next run. Locked while one runs."""
        group = QGroupBox("Settings")
        layout = QGridLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        defaults = MPProcessingLimits()
        for row, setting in enumerate(SETTINGS):
            spin = self._register(
                setting.widget, QDoubleSpinBox(parent=self.parent)
            )
            spin.setRange(setting.low, setting.high)
            spin.setSingleStep(setting.step)
            spin.setDecimals(setting.decimals)
            spin.setSuffix(f" {setting.unit}")
            spin.setValue(getattr(defaults, setting.field) / setting.scale)
            layout.addWidget(QLabel(setting.caption), row, 0)
            layout.addWidget(spin, row, 1)
        group.setLayout(layout)
        return group

    def _build_live_pvs(self) -> QGroupBox:
        """Read-only PyDMLabels. MPProcessingController sets each channel."""
        group = QGroupBox("Live PVs")
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setContentsMargins(8, 8, 8, 8)
        # decimals: None keeps the PV's own PREC. Amplitudes show 2: the sim
        # serves ADES_MAX with PREC 0, which showed 15.8 as "16".
        # CHECK: what PREC do ADES, AACTMEAN and ADES_MAX have on production?
        rows = (
            ("ADES:", "pydm_ades", 2),
            ("AACTMEAN:", "pydm_aact", 2),
            ("ADES_MAX:", "pydm_ades_max", 2),
            ("Quench latch (QUENCH_LTCH):", "pydm_quench_latch", None),
            ("RF mode (RFMODE):", "pydm_rf_mode", None),
            ("RF state (RFSTATE):", "pydm_rf_state", None),
        )
        for row, (caption, name, decimals) in enumerate(rows):
            label = self._register(name, PyDMLabel(parent=self.parent))
            label.setStyleSheet(PV_LABEL_STYLE)
            label.setAlignment(Qt.AlignCenter)
            label.showUnits = True
            if decimals is not None:
                label.precisionFromPV = False
                label.precision = decimals
            grid.addWidget(QLabel(caption), row, 0)
            grid.addWidget(label, row, 1)
        group.setLayout(grid)
        return group

    def _build_quench_table(self) -> QGroupBox:
        """One row per quench this run recorded."""
        group = QGroupBox("Quenches")
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        table = self._register(
            "quench_table", QTableWidget(0, len(QUENCH_COLUMNS))
        )
        table.setHorizontalHeaderLabels(QUENCH_COLUMNS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setStyleSheet(QUENCH_TABLE_STYLE)
        table.setMinimumHeight(80)
        layout.addWidget(table)
        group.setLayout(layout)
        return group
