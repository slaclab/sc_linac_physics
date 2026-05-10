"""Sync/update-banner helpers for the multi-phase commissioning container."""

import logging

from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QWidget,
)

logger = logging.getLogger(__name__)


def update_sync_status(host, is_synced: bool, message: str = "") -> None:
    """Update the global sync status indicator."""
    if is_synced:
        host.sync_status.setText("● Synced")
        host.sync_status.setStyleSheet("""
                        QLabel {
                            color: #4CAF50;
                            font-weight: bold;
                            padding: 5px 10px;
                            background-color: rgba(76, 175, 80, 0.15);
                            border-radius: 3px;
                        }
                    """)
    else:
        host.sync_status.setText(f"⚠ {message or 'Out of Sync'}")
        host.sync_status.setStyleSheet("""
                        QLabel {
                            color: #FF9800;
                            font-weight: bold;
                            padding: 5px 10px;
                            background-color: rgba(255, 152, 0, 0.15);
                            border-radius: 3px;
                            border: 1px solid #FF9800;
                        }
                    """)


def check_for_external_changes(host) -> None:
    """Enhanced change detection with visible notification."""
    if not host.session.has_active_record():
        return

    record_id = host.session.get_active_record_id()
    if not record_id:
        return

    try:
        result = host.session.db.get_record_with_version(record_id)
        if not result:
            return

        _, db_version = result
        local_version = host.session._active_record_version

        if local_version is not None and db_version > local_version:
            show_update_banner(host, db_version, local_version)

    except Exception as e:
        logger.exception("Error checking for external changes: %s", e)


def show_update_banner(host, db_version: int, local_version: int) -> None:
    """Show a prominent banner when external updates are detected."""
    if hasattr(host, "_update_banner") and host._update_banner:
        return

    host._update_banner = QWidget()
    host._update_banner.setStyleSheet("""
                    QWidget {
                        background-color: #FF9800;
                        border: 2px solid #F57C00;
                        border-left: 5px solid #F57C00;
                    }
                    QLabel {
                        color: white;
                        font-weight: bold;
                        padding: 5px;
                    }
                    QPushButton {
                        background-color: white;
                        color: #F57C00;
                        font-weight: bold;
                        padding: 8px 16px;
                        border-radius: 4px;
                        border: none;
                    }
                    QPushButton:hover {
                        background-color: #f5f5f5;
                    }
                """)

    layout = QHBoxLayout()
    layout.setContentsMargins(15, 10, 15, 10)

    icon = QLabel("⚠️")
    icon.setStyleSheet("font-size: 24px;")
    layout.addWidget(icon)

    message = QLabel(
        f"<b>This record was updated by another user</b><br>"
        f"<small>Your version: {local_version} → Database version: {db_version}</small>"
    )
    layout.addWidget(message)
    layout.addStretch()

    reload_btn = QPushButton("🔄 Reload Now")
    reload_btn.clicked.connect(host._reload_from_banner)
    layout.addWidget(reload_btn)

    dismiss_btn = QPushButton("✕ Dismiss")
    dismiss_btn.clicked.connect(host._dismiss_banner)
    layout.addWidget(dismiss_btn)

    host._update_banner.setLayout(layout)

    # Insert banner at position 1 (after header, before progress)
    host.layout().insertWidget(1, host._update_banner)

    # Update sync status
    update_sync_status(host, False, "Out of Sync")


def reload_from_banner(host) -> None:
    """Reload record from update banner."""
    record_id = host.session.get_active_record_id()
    if record_id:
        reply = QMessageBox.question(
            host,
            "Reload Record",
            "Reloading will discard any unsaved changes. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply == QMessageBox.Yes:
            host.load_record(record_id)
            dismiss_banner(host)
            update_sync_status(host, True, "Reloaded")


def dismiss_banner(host) -> None:
    """Remove the update notification banner."""
    if hasattr(host, "_update_banner") and host._update_banner:
        host._update_banner.deleteLater()
        host._update_banner = None


def handle_note_conflict(host, conflict) -> None:
    """Handle note update conflicts from optimistic locking."""
    QMessageBox.warning(
        host,
        "Record Updated",
        "This record was updated by another user. "
        "Please reload before editing notes.",
    )
    show_update_banner(host, conflict.actual_version, conflict.expected_version)
