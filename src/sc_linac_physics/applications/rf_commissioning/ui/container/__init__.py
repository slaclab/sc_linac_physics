"""Container-level helpers for the multi-phase commissioning UI."""

from .phase_specs import PhaseTabSpec, build_default_phase_specs
from .progress import build_progress_phases
from .header import build_header_panel
from .notes import build_enhanced_notes_panel, load_notes
from .note_actions import (
    build_note_dialog,
    get_selected_note_ref,
    on_edit_note,
    quick_add_note,
    show_notes_context_menu,
)
from .records import (
    confirm_and_start_new,
    load_selected_record,
    on_load_or_start,
    show_record_selector,
    start_new_from_dialog,
)
from .sync import (
    check_for_external_changes,
    dismiss_banner,
    handle_note_conflict,
    reload_from_banner,
    show_update_banner,
    update_sync_status,
)
from .persistence import (
    handle_save_conflict,
    save_active_record,
    show_database_browser,
    show_measurement_history,
)
from .record_lifecycle import (
    load_record,
    on_phase_advanced,
    start_new_record,
    sync_cavity_selection_from_record,
)
from .tab_state import (
    get_phase_icon,
    init_tabs,
    on_tab_changed,
    update_tab_states,
)

__all__ = [
    "PhaseTabSpec",
    "build_default_phase_specs",
    "build_progress_phases",
    "build_header_panel",
    "build_enhanced_notes_panel",
    "load_notes",
    "quick_add_note",
    "show_notes_context_menu",
    "on_edit_note",
    "get_selected_note_ref",
    "build_note_dialog",
    "on_load_or_start",
    "show_record_selector",
    "load_selected_record",
    "start_new_from_dialog",
    "confirm_and_start_new",
    "update_sync_status",
    "check_for_external_changes",
    "show_update_banner",
    "reload_from_banner",
    "dismiss_banner",
    "handle_note_conflict",
    "save_active_record",
    "handle_save_conflict",
    "show_measurement_history",
    "show_database_browser",
    "start_new_record",
    "load_record",
    "sync_cavity_selection_from_record",
    "on_phase_advanced",
    "init_tabs",
    "get_phase_icon",
    "update_tab_states",
    "on_tab_changed",
]
