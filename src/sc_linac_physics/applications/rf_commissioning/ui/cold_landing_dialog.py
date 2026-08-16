"""Dialog for committing a cold-landing frequency to DF_COLD.

Every route to DF_COLD goes through here, on purpose. DF_COLD and the value
stored on the record have to agree — the tuning gates compare them within 1 Hz —
and the previous button wrote whatever the *live* detune happened to be at the
moment it was clicked, which could differ from the value Stage 1 recorded and so
produce the very mismatch the gates exist to catch.

Committing is never automatic. Which frequency belongs in DF_COLD is an operator
judgment: usually the value measured here, sometimes the current live reading,
and sometimes a number from a partner lab. The last case requires a written
justification, because a cold landing that was not measured on this cavity is
something the next person reading the record needs explained.
"""

from dataclasses import dataclass

from PyQt5.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
)

from sc_linac_physics.applications.rf_commissioning.ui.builders.theme import (
    BG_INSET,
    BORDER_EMPHASIS,
    COLOR_WARNING,
    RADIUS_SM,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

SOURCE_MEASURED = "measured"
SOURCE_LIVE = "live"
SOURCE_ENTERED = "entered"


@dataclass(frozen=True)
class ColdLandingChoice:
    """What the operator chose to commit, and why."""

    value_hz: float
    source: str
    justification: str = ""

    def provenance(self) -> str:
        """One-line description for the activity feed and measurement history."""
        if self.source == SOURCE_MEASURED:
            return f"{self.value_hz:.0f} Hz (measured by Stage 1)"
        if self.source == SOURCE_LIVE:
            return f"{self.value_hz:.0f} Hz (current live detune)"
        return f"{self.value_hz:.0f} Hz (entered: {self.justification})"


class ColdLandingDialog(QDialog):
    """Ask which cold-landing frequency to commit to DF_COLD."""

    def __init__(
        self,
        measured_hz: float | None,
        live_hz: float | None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Save Cold Landing Frequency")
        self.setMinimumWidth(500)
        self._measured_hz = measured_hz
        self._live_hz = live_hz
        self._build_ui()
        self._refresh_enabled()

    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout()
        layout.setSpacing(8)

        blurb = QLabel(
            "DF_COLD is the cavity's reference resting frequency. Tuning will "
            "not start until it is set — moving the stepper makes the cold "
            "landing impossible to measure afterwards."
        )
        blurb.setWordWrap(True)
        # A word-wrapped QLabel reports the height of a single line, so in a
        # QVBoxLayout it gets squeezed and the text is clipped. Let it grow.
        blurb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        blurb.setStyleSheet(f"QLabel {{ color: {TEXT_MUTED}; }}")
        layout.addWidget(blurb)

        self._group = QButtonGroup(self)

        self._measured_radio = QRadioButton(
            f"Use the measured value — {measured_text(self._measured_hz)}"
        )
        self._measured_radio.setEnabled(self._measured_hz is not None)
        self._group.addButton(self._measured_radio)
        layout.addWidget(self._measured_radio)

        self._live_radio = QRadioButton(
            f"Use the current live detune — {measured_text(self._live_hz)}"
        )
        self._live_radio.setEnabled(self._live_hz is not None)
        self._group.addButton(self._live_radio)
        layout.addWidget(self._live_radio)

        self._entered_radio = QRadioButton(
            "Enter a value (e.g. from a partner lab)"
        )
        self._group.addButton(self._entered_radio)
        layout.addWidget(self._entered_radio)

        entry_row = QHBoxLayout()
        entry_row.addSpacing(22)
        self._value_box = QDoubleSpinBox()
        # Cold-landing detune runs to a few MHz either side of resonance.
        self._value_box.setRange(-5_000_000.0, 5_000_000.0)
        self._value_box.setDecimals(0)
        self._value_box.setSuffix(" Hz")
        self._value_box.setFixedWidth(160)
        entry_row.addWidget(self._value_box)
        entry_row.addStretch()
        layout.addLayout(entry_row)

        just_label = QLabel("Justification (required for an entered value):")
        just_label.setStyleSheet(f"QLabel {{ color: {TEXT_MUTED}; }}")
        layout.addWidget(just_label)
        self._justification = QPlainTextEdit()
        self._justification.setFixedHeight(56)
        self._justification.setPlaceholderText(
            "e.g. cold landing measured at JLab during VTS; cavity not "
            "re-measured after shipping"
        )
        self._justification.setStyleSheet(
            f"QPlainTextEdit {{ background: {BG_INSET}; color: {TEXT_PRIMARY}; "
            f"border: 1px solid {BORDER_EMPHASIS}; "
            f"border-radius: {RADIUS_SM}; }}"
        )
        layout.addWidget(self._justification)

        self._warning = QLabel("")
        self._warning.setWordWrap(True)
        self._warning.setStyleSheet(f"QLabel {{ color: {COLOR_WARNING}; }}")
        layout.addWidget(self._warning)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        self.setLayout(layout)

        # Default to the measured value when there is one — the common case.
        if self._measured_hz is not None:
            self._measured_radio.setChecked(True)
        elif self._live_hz is not None:
            self._live_radio.setChecked(True)
        else:
            self._entered_radio.setChecked(True)

        self._group.buttonClicked.connect(self._refresh_enabled)
        self._justification.textChanged.connect(self._refresh_enabled)

    def _refresh_enabled(self, *_args) -> None:
        """Gate Save on having a usable value, and a reason if it was typed."""
        entered = self._entered_radio.isChecked()
        self._value_box.setEnabled(entered)
        self._justification.setEnabled(entered)

        if entered and not self._justification.toPlainText().strip():
            self._warning.setText(
                "An entered value needs a justification — it will be stored "
                "with the record so the next reader knows where it came from."
            )
            ok = False
        else:
            self._warning.setText("")
            ok = True

        self._buttons.button(QDialogButtonBox.Save).setEnabled(ok)

    # ------------------------------------------------------------------

    def choice(self) -> ColdLandingChoice | None:
        """Return what the operator selected, or None if nothing is usable."""
        if self._entered_radio.isChecked():
            return ColdLandingChoice(
                value_hz=float(self._value_box.value()),
                source=SOURCE_ENTERED,
                justification=self._justification.toPlainText().strip(),
            )
        if self._live_radio.isChecked() and self._live_hz is not None:
            return ColdLandingChoice(
                value_hz=float(self._live_hz), source=SOURCE_LIVE
            )
        if self._measured_radio.isChecked() and self._measured_hz is not None:
            return ColdLandingChoice(
                value_hz=float(self._measured_hz), source=SOURCE_MEASURED
            )
        return None


def measured_text(value: float | None) -> str:
    """Render a value for a radio label, or say it is unavailable."""
    return "not available" if value is None else f"{value:.0f} Hz"


def ask_for_cold_landing(
    parent,
    measured_hz: float | None,
    live_hz: float | None,
) -> ColdLandingChoice | None:
    """Show the dialog; return the operator's choice, or None if cancelled."""
    dialog = ColdLandingDialog(measured_hz, live_hz, parent=parent)
    if dialog.exec_() != QDialog.Accepted:
        return None
    return dialog.choice()
