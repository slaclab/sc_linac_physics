from typing import Dict

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLabel,
    QProgressBar, QGridLayout
)


class StatusPanel(QWidget):
    """Panel for displaying cavity status information.
    Provides a grid layout showing status, progress, and messages for up to 8 cavities."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # Dictionary to store references to status widgets for each cavity
        self.status_widgets = {}
        self.setup_ui()

    def setup_ui(self):
        """Initialize the user interface with a grid of status indicators.
        Creates a row for each cavity (1-8) with status label, progress bar, and message area."""
        layout = QVBoxLayout(self)

        # Main container for all status information
        group = QGroupBox("Cavity Status")
        grid_layout = QGridLayout()

        # Set up column headers for the status grid
        headers = ["Cavity", "Status", "Progress", "Message"]
        for col, header in enumerate(headers):
            label = QLabel(header)
            label.setStyleSheet("font-weight: bold")
            grid_layout.addWidget(label, 0, col)

        # Create a row of status widgets for each cavity
        for row, cavity_num in enumerate(range(1, 9), 1):
            # Cavity identifier label
            grid_layout.addWidget(QLabel(f"Cavity {cavity_num}"), row, 0)

            # Status display showing current operation state
            status_label = QLabel("Not configured")
            grid_layout.addWidget(status_label, row, 1)

            # Progress indicator for ongoing operations
            progress_bar = QProgressBar()
            progress_bar.setMinimum(0)
            progress_bar.setMaximum(100)
            grid_layout.addWidget(progress_bar, row, 2)

            # Area for detailed status messages or error information
            msg_label = QLabel("")
            grid_layout.addWidget(msg_label, row, 3)

            # Keep references to widgets for dynamic updates
            self.status_widgets[cavity_num] = {
                'status': status_label,
                'progress': progress_bar,
                'message': msg_label
            }

        group.setLayout(grid_layout)
        layout.addWidget(group)

    def update_cavity_status(self, cavity_num: int, status: str, progress: int, message: str):
        """Update the display for a single cavity with new status information.

        Args:
            cavity_num: Cavity number (1-8)
            status: Current operation state (e.g., "Running", "Complete")
            progress: Operation progress percentage (0-100)
            message: Detailed status or error message
        """
        if cavity_num in self.status_widgets:
            widgets = self.status_widgets[cavity_num]
            widgets['status'].setText(status)
            widgets['progress'].setValue(progress)
            widgets['message'].setText(message)

    def update_all_status(self, status_dict: Dict):
        """Bulk update of status information for multiple cavities.

        Args:
            status_dict: Dictionary mapping cavity numbers to their status info
                Format: {
                    cavity_num: {
                        'status': str,  # Operation state
                        'progress': int,  # Progress percentage
                        'message': str   # Status message
                    }
                }
        """
        for cavity_num, info in status_dict.items():
            self.update_cavity_status(
                cavity_num,
                info.get('status', ''),
                info.get('progress', 0),
                info.get('message', '')
            )

    def update_statistics(self, cavity_num: int, stats: dict):
        """Display statistical analysis results for a cavity's measurements.

        Args:
            cavity_num: Cavity number (1-8)
            stats: Dictionary of calculated statistics including:
                   - mean: Average measurement value
                   - std: Standard deviation of measurements
                   - min: Minimum recorded value
                   - max: Maximum recorded value
                   - outliers: Count of outlier measurements
        """
        if cavity_num in self.status_widgets:
            widgets = self.status_widgets[cavity_num]

            # Format statistics into readable message
            message = (f"Mean: {stats['mean']:.2f}, "
                       f"Std: {stats['std']:.2f}, "
                       f"Range: [{stats['min']:.2f}, {stats['max']:.2f}], "
                       f"Outliers: {stats['outliers']}")

            # Update display with statistics
            widgets['status'].setText("Running")
            widgets['message'].setText(message)

    def reset_all(self):
        """Reset all cavity displays to their initial state.
        Clears all progress, messages, and status indicators."""
        for cavity_num in range(1, 9):
            self.update_cavity_status(
                cavity_num,
                "Not configured",
                0,
                ""
            )

    def set_cavity_error(self, cavity_num: int, error_msg: str):
        """Mark a cavity as being in an error state with visual indication.

        Args:
            cavity_num: Cavity number (1-8)
            error_msg: Description of the error condition
        """
        self.update_cavity_status(
            cavity_num,
            "Error",
            0,
            error_msg
        )
        # Highlight error state in red
        if cavity_num in self.status_widgets:
            self.status_widgets[cavity_num]['status'].setStyleSheet("color: red")

    def clear_cavity_error(self, cavity_num: int):
        """Remove error indication from a cavity's display.

        Args:
            cavity_num: Cavity number (1-8)
        """
        if cavity_num in self.status_widgets:
            self.status_widgets[cavity_num]['status'].setStyleSheet("")

    def get_cavity_status(self, cavity_num: int) -> Dict:
        """Retrieve current status information for a cavity.

        Args:
            cavity_num: Cavity number (1-8)

        Returns:
            Dictionary containing current status, progress, and message
            Returns empty dict if cavity number not found
        """
        if cavity_num in self.status_widgets:
            widgets = self.status_widgets[cavity_num]
            return {
                'status': widgets['status'].text(),
                'progress': widgets['progress'].value(),
                'message': widgets['message'].text()
            }
        return {}
