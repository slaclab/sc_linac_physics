"""Builds the Piezo with RF display UI.

Same grid as CavityCharUI: toolbar and status against Stored Data, then
Review and Push against Live PVs, with Phase History below.
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QLabel, QPushButton
from PyQt5.QtWidgets import QVBoxLayout
from pydm.widgets import PyDMLabel

from .base import PhaseUIBase
from .styles import PV_LABEL_STYLE

PUSH_BUTTON_TEXT = "Push to IOC…"
DECLINE_BUTTON_TEXT = "Don't Push…"


class PiezoWithRFUI(PhaseUIBase):
    """Builds the Piezo with RF display UI."""

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
        grid.addWidget(self._build_review(), 2, 0)
        grid.addWidget(self._build_live_pvs(), 2, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        main_layout.addLayout(grid)
        main_layout.addWidget(self._build_history(), stretch=1)
        return main_layout

    def _build_status(self) -> QGroupBox:
        group = QGroupBox("Piezo with RF")
        layout = QGridLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        for row, (caption, name) in enumerate(
            (("Step:", "step_label"), ("Phase:", "local_phase_status"))
        ):
            layout.addWidget(QLabel(caption), row, 0)
            layout.addWidget(
                self._register(name, self._make_local_label("-")), row, 1
            )
        group.setLayout(layout)
        return group

    def _build_review(self) -> QGroupBox:
        """This run's read_results values, and the two ways to finish.

        Both buttons are built disabled. PiezoWithRFDisplay enables them when
        read_results succeeds: the push gate lives on the phase that read the
        values (PiezoWithRFPhase._push_detune_gain).
        """
        group = QGroupBox("Review and Push")
        layout = QGridLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)
        for row, (caption, name) in enumerate(
            (
                ("Amplifier gain A:", "gain_a_label"),
                ("Amplifier gain B:", "gain_b_label"),
                ("New detune gain (DFGAIN_NEW):", "detune_gain_label"),
                ("Test result:", "test_result_label"),
            )
        ):
            layout.addWidget(QLabel(caption), row, 0)
            layout.addWidget(
                self._register(name, self._make_local_label("-")), row, 1
            )

        for column, (name, text, callback) in enumerate(
            (
                ("push_button", PUSH_BUTTON_TEXT, "on_push"),
                ("decline_button", DECLINE_BUTTON_TEXT, "on_decline_push"),
            )
        ):
            button = self._register(name, QPushButton(text, parent=self.parent))
            button.setEnabled(False)
            self._connect(button, callback)
            layout.addWidget(button, 4, column)

        group.setLayout(layout)
        return group

    def _build_live_pvs(self) -> QGroupBox:
        """Read-only PyDMLabels. PiezoWithRFController sets each channel."""
        group = QGroupBox("Live PVs")
        grid = QGridLayout()
        grid.setSpacing(6)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.addWidget(QLabel("New"), 0, 1, alignment=Qt.AlignCenter)
        grid.addWidget(QLabel("Current"), 0, 2, alignment=Qt.AlignCenter)

        def pv_label(name: str, decimals: int | None = None) -> PyDMLabel:
            """decimals: None for enums; gains show 6, like Review."""
            label = self._register(name, PyDMLabel(parent=self.parent))
            label.setStyleSheet(PV_LABEL_STYLE)
            label.setAlignment(Qt.AlignCenter)
            if decimals is not None:
                label.precisionFromPV = False
                label.precision = decimals
            return label

        rows = (
            # caption, New widget, Current widget (None: nothing), decimals
            ("Test run (RFTESTSTS):", "pydm_test_run", None, None),
            ("Test status (RFTESTSTAT):", "pydm_test_status", None, None),
            ("Amp gain A (CHA_AMPGAIN):", "pydm_gain_a", None, 6),
            ("Amp gain B (CHB_AMPGAIN):", "pydm_gain_b", None, 6),
            (
                "Detune gain (DFGAIN_NEW / DFGAIN):",
                "pydm_dfgain_new",
                "pydm_dfgain_current",
                6,
            ),
            ("RF state:", "pydm_rf_state", None, None),
        )
        for row, (caption, new, current, decimals) in enumerate(rows, 1):
            grid.addWidget(QLabel(caption), row, 0)
            grid.addWidget(pv_label(new, decimals), row, 1)
            if current is not None:
                grid.addWidget(pv_label(current, decimals), row, 2)

        group.setLayout(grid)
        return group
