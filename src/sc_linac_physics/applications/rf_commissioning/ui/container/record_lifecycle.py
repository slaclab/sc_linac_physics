"""Record lifecycle helpers for multi-phase commissioning container."""

from PyQt5.QtWidgets import QMessageBox


class _RecordLifecycleMixin:
    def _refuse_if_phase_running(self) -> bool:
        """Keep the active record fixed while any phase is running.

        Phase controllers save, add history and complete phase instances
        through the session's active record. Replacing it mid-run would
        attach one cavity's measurement to another cavity's record.
        """
        running = any(
            getattr(display, "is_running_phase", lambda: False)()
            for display in self._phase_displays
        )
        if running:
            QMessageBox.warning(
                self,
                "Phase running",
                "A phase is running on the current cavity. Let it finish or "
                "abort it before changing cavity or record.",
            )
        return running

    def start_new_record(self, cryomodule: str, cavity_number: str) -> bool:
        """Start a new commissioning record."""
        if self._refuse_if_phase_running():
            return False
        record, _record_id, created = self.session.start_new_record(
            cryomodule, cavity_number
        )

        for display in self._phase_displays:
            if hasattr(display, "controller") and hasattr(
                display.controller, "update_pv_addresses"
            ):
                display.controller.update_pv_addresses(
                    cryomodule, str(cavity_number)
                )

        self._update_tab_states()
        self._update_cm_status_panel(record)
        self._load_notes()

        for display in self._phase_displays:
            display.refresh_from_record(record)

        if created:
            self.tabs.setCurrentIndex(0)
        else:
            self._select_tab_for_record_phase(record)

        return created

    def load_record(self, record_id: int) -> bool:
        """Load an existing commissioning record."""
        if self._refuse_if_phase_running():
            return False
        record = self.session.load_record(record_id)
        if not record:
            return False

        self._sync_cavity_selection_from_record(record)

        for display in self._phase_displays:
            display.on_record_loaded(record, record_id)

        self._update_tab_states()
        self._select_tab_for_record_phase(record)
        self._update_cm_status_panel(record)
        self._load_notes()
        self._update_sync_status(True, "Record loaded")

        return True

    def _sync_cavity_selection_from_record(self, record) -> None:
        """Sync header cavity selection to a loaded record."""
        linac_str = f"L{record.linac}B"
        linac_index = self.linac_combo.findText(linac_str)
        if linac_index >= 0:
            # Triggers _on_linac_selection_changed, repopulating cryomodule_combo
            self.linac_combo.setCurrentIndex(linac_index)

        cm_index = self.cryomodule_combo.findText(record.cryomodule)
        if cm_index >= 0:
            self.cryomodule_combo.setCurrentIndex(cm_index)

        cav_index = self.cavity_combo.findText(str(record.cavity_number))
        if cav_index >= 0:
            self.cavity_combo.setCurrentIndex(cav_index)

    def on_phase_advanced(self, record) -> None:
        """Handle notification that a phase has advanced."""
        self._update_tab_states()
        self._update_sync_status(True, "Phase completed")
        self._update_cm_status_panel(record)
        self._select_tab_for_record_phase(record)

    def _select_tab_for_record_phase(self, record) -> None:
        """Select the tab that matches the record's current phase."""
        for i, spec in enumerate(self.phase_specs):
            if spec.phase == record.current_phase:
                self.tabs.setCurrentIndex(i)
                break


# Backward-compat aliases so existing tests continue to work.
start_new_record = _RecordLifecycleMixin.start_new_record
load_record = _RecordLifecycleMixin.load_record
sync_cavity_selection_from_record = (
    _RecordLifecycleMixin._sync_cavity_selection_from_record
)
on_phase_advanced = _RecordLifecycleMixin.on_phase_advanced
