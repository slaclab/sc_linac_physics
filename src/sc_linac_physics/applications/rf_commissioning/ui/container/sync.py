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


class _SyncMixin:
    def _update_sync_status(self, is_synced: bool, message: str = "") -> None:
        """Update the global sync status indicator."""
        if is_synced:
            self.sync_status.setText("● Synced")
            self.sync_status.setStyleSheet("""
                            QLabel {
                                color: #4CAF50;
                                font-weight: bold;
                                padding: 5px 10px;
                                background-color: rgba(76, 175, 80, 0.15);
                                border-radius: 3px;
                            }
                        """)
        else:
            self.sync_status.setText(f"⚠ {message or 'Out of Sync'}")
            self.sync_status.setStyleSheet("""
                            QLabel {
                                color: #FF9800;
                                font-weight: bold;
                                padding: 5px 10px;
                                background-color: rgba(255, 152, 0, 0.15);
                                border-radius: 3px;
                                border: 1px solid #FF9800;
                            }
                        """)

    def _check_for_external_changes(self) -> None:
        """Enhanced change detection with visible notification."""
        if not self.session.has_active_record():
            return

        record_id = self.session.get_active_record_id()
        if not record_id:
            return

        try:
            result = self.session.get_record_with_version(record_id)
            if not result:
                return

            _, db_version = result
            local_version = self.session.get_active_record_version()

            if local_version is not None and db_version > local_version:
                self._show_update_banner(db_version, local_version)

        except Exception as e:
            logger.exception("Error checking for external changes: %s", e)

    def _show_update_banner(self, db_version: int, local_version: int) -> None:
        """Show a prominent banner when external updates are detected."""
        if hasattr(self, "_update_banner") and self._update_banner:
            return

        self._update_banner = QWidget()
        self._update_banner.setStyleSheet("""
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
        reload_btn.clicked.connect(self._reload_from_banner)
        layout.addWidget(reload_btn)

        dismiss_btn = QPushButton("✕ Dismiss")
        dismiss_btn.clicked.connect(self._dismiss_banner)
        layout.addWidget(dismiss_btn)

        self._update_banner.setLayout(layout)

        # Insert banner at position 1 (after header, before progress)
        self.layout().insertWidget(1, self._update_banner)

        self._update_sync_status(False, "Out of Sync")

    def _reload_from_banner(self) -> None:
        """Reload record from update banner."""
        record_id = self.session.get_active_record_id()
        if record_id:
            reply = QMessageBox.question(
                self,
                "Reload Record",
                "Reloading will discard any unsaved changes. Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )

            if reply == QMessageBox.Yes:
                self.load_record(record_id)
                self._dismiss_banner()
                self._update_sync_status(True, "Reloaded")

    def _dismiss_banner(self) -> None:
        """Remove the update notification banner."""
        if hasattr(self, "_update_banner") and self._update_banner:
            self._update_banner.deleteLater()
            self._update_banner = None

    def _handle_note_conflict(self, conflict) -> None:
        """Handle note update conflicts from optimistic locking."""
        QMessageBox.warning(
            self,
            "Record Updated",
            "This record was updated by another user. "
            "Please reload before editing notes.",
        )
        self._show_update_banner(
            conflict.actual_version, conflict.expected_version
        )


# Backward-compat aliases so existing tests continue to work.
update_sync_status = _SyncMixin._update_sync_status
check_for_external_changes = _SyncMixin._check_for_external_changes
show_update_banner = _SyncMixin._show_update_banner
reload_from_banner = _SyncMixin._reload_from_banner
dismiss_banner = _SyncMixin._dismiss_banner
handle_note_conflict = _SyncMixin._handle_note_conflict
