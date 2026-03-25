"""Record lifecycle helpers for multi-phase commissioning container."""


def _select_tab_for_record_phase(host, record) -> None:
    """Select the tab that matches the record's current phase."""
    for i, spec in enumerate(host.phase_specs):
        if spec.phase == record.current_phase:
            host.tabs.setCurrentIndex(i)
            break


def start_new_record(host, cryomodule: str, cavity_number: str) -> bool:
    """Start a new commissioning record."""
    record, _record_id, created = host.session.start_new_record(
        cryomodule, cavity_number
    )

    for display in host._phase_displays:
        if hasattr(display, "controller") and hasattr(
            display.controller, "update_pv_addresses"
        ):
            display.controller.update_pv_addresses(cryomodule, cavity_number)

    host.update_progress_indicator(record)
    host._update_tab_states()

    # Keep CM-level tracker in sync for cavity-selection driven workflows
    if hasattr(host, "_update_cm_status_panel"):
        host._update_cm_status_panel(record)

    host._load_notes()

    for display in host._phase_displays:
        display.refresh_from_record(record)

    if created:
        host.tabs.setCurrentIndex(0)
    else:
        _select_tab_for_record_phase(host, record)

    return created


def load_record(host, record_id: int) -> bool:
    """Load an existing commissioning record."""
    record = host.session.load_record(record_id)
    if not record:
        return False

    sync_cavity_selection_from_record(host, record)

    host.update_progress_indicator(record)

    for display in host._phase_displays:
        display.on_record_loaded(record, record_id)

    host._update_tab_states()
    _select_tab_for_record_phase(host, record)

    # Update CM status panel with current record
    if hasattr(host, "_update_cm_status_panel"):
        host._update_cm_status_panel(record)

    host._load_notes()
    host._update_sync_status(True, "Record loaded")

    return True


def sync_cavity_selection_from_record(host, record) -> None:
    """Sync header cavity selection to a loaded record."""
    cm_index = host.cryomodule_combo.findText(record.cryomodule)
    if cm_index >= 0:
        host.cryomodule_combo.setCurrentIndex(cm_index)

    cav_index = host.cavity_combo.findText(str(record.cavity_number))
    if cav_index >= 0:
        host.cavity_combo.setCurrentIndex(cav_index)


def on_phase_advanced(host, record) -> None:
    """Handle notification that a phase has advanced."""
    host.update_progress_indicator(record)
    host._update_tab_states()
    host._update_sync_status(True, "Phase completed")

    # Update CM status panel to reflect changed cavity completion count
    if hasattr(host, "_update_cm_status_panel"):
        host._update_cm_status_panel(record)
    _select_tab_for_record_phase(host, record)
