"""Multi-phase commissioning container display."""

from dataclasses import dataclass
from typing import Optional, Type

import signal
import sys

from PyQt5.QtWidgets import QTabWidget, QVBoxLayout
from pydm import Display, PyDMApplication

from sc_linac_physics.applications.rf_commissioning import CommissioningPhase
from sc_linac_physics.applications.rf_commissioning.session_manager import (
    CommissioningSession,
)
from sc_linac_physics.applications.rf_commissioning.ui.phase_display_base import (
    PhaseDisplayBase,
)
from sc_linac_physics.applications.rf_commissioning.ui.piezo_pre_rf_display import (
    PiezoPreRFDisplay,
)


@dataclass(frozen=True)
class PhaseTabSpec:
    """Metadata for a phase tab."""

    title: str
    display_class: Type[PhaseDisplayBase]
    phase: Optional[CommissioningPhase] = None


class MultiPhaseCommissioningDisplay(Display):
    """Container window that hosts multiple phase displays."""

    def __init__(
        self,
        parent=None,
        session: Optional[CommissioningSession] = None,
        phase_specs: Optional[list[PhaseTabSpec]] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("RF Commissioning")

        self.session = session or CommissioningSession("commissioning.db")
        self.phase_specs = phase_specs or self._default_phase_specs()

        self.tabs = QTabWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        self.setLayout(layout)

        self._phase_displays: list[PhaseDisplayBase] = []
        self._init_tabs()
        self._update_tab_states()

    def _default_phase_specs(self) -> list[PhaseTabSpec]:
        return [
            PhaseTabSpec(
                title="1. Piezo Pre-RF",
                display_class=PiezoPreRFDisplay,
                phase=CommissioningPhase.PIEZO_PRE_RF,
            )
        ]

    def _init_tabs(self) -> None:
        for spec in self.phase_specs:
            display = spec.display_class(session=self.session)
            self._phase_displays.append(display)
            self.tabs.addTab(display, spec.title)

    def _update_tab_states(self) -> None:
        if not self.session.has_active_record():
            for i in range(1, self.tabs.count()):
                self.tabs.setTabEnabled(i, False)
            return

        record = self.session.get_active_record()
        phase_order = CommissioningPhase.get_phase_order()
        current_index = phase_order.index(record.current_phase)

        for i, spec in enumerate(self.phase_specs):
            if spec.phase is None:
                self.tabs.setTabEnabled(i, True)
                continue

            phase_index = phase_order.index(spec.phase)
            self.tabs.setTabEnabled(i, phase_index <= current_index)

    def start_new_record(self, cavity_name: str, cryomodule: str) -> None:
        record, _ = self.session.start_new_record(cavity_name, cryomodule)
        for display in self._phase_displays:
            display.refresh_from_record(record)
        self._update_tab_states()
        self.tabs.setCurrentIndex(0)

    def load_record(self, record_id: int) -> bool:
        record = self.session.load_record(record_id)
        if not record:
            return False

        for display in self._phase_displays:
            display.on_record_loaded(record, record_id)

        self._update_tab_states()

        for i, spec in enumerate(self.phase_specs):
            if spec.phase == record.current_phase:
                self.tabs.setCurrentIndex(i)
                break

        return True

    def save_active_record(self) -> bool:
        return self.session.save_active_record()


def main() -> int:
    """Run the multi-phase commissioning display standalone via PyDM."""
    app = PyDMApplication(
        ui_file=None, command_line_args=sys.argv, use_main_window=False
    )
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    window = MultiPhaseCommissioningDisplay()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
