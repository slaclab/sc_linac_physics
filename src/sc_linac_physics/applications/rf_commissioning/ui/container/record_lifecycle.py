"""Record lifecycle helpers for multi-phase commissioning container."""


class _RecordLifecycleMixin:
    def start_new_record(self, cryomodule: str, cavity_number: int) -> bool:
        """Start a new commissioning record."""
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

        self.update_progress_indicator(record)
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
        record = self.session.load_record(record_id)
        if not record:
            return False

        self._sync_cavity_selection_from_record(record)
        self.update_progress_indicator(record)

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
        cm_index = self.cryomodule_combo.findText(record.cryomodule)
        if cm_index >= 0:
            self.cryomodule_combo.setCurrentIndex(cm_index)

        cav_index = self.cavity_combo.findText(str(record.cavity_number))
        if cav_index >= 0:
            self.cavity_combo.setCurrentIndex(cav_index)

    def on_phase_advanced(self, record) -> None:
        """Handle notification that a phase has advanced."""
        self.update_progress_indicator(record)
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
