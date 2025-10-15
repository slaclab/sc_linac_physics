from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QGridLayout

from sc_linac_physics.applications.microphonics.utils.ui_utils import create_status_widgets


class StatusPanel(QWidget):
    """Panel for displaying cavity status info"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.status_widgets = {}
        self.setup_ui()

    def setup_ui(self):
        """Initialize user interface"""
        layout = QVBoxLayout(self)

        # Create status group
        group = QGroupBox("Cavity Status")
        grid_layout = QGridLayout()

        # Create status widgets for all cavities
        self.status_widgets = create_status_widgets(
            self,
            items=list(range(1, 9)),
            grid_layout=grid_layout,
            headers=["Cavity", "Status", "Progress", "Message"],
            initial_status="Not configured",
            initial_message="",
        )
        group.setLayout(grid_layout)
        layout.addWidget(group)

    def update_cavity_status(self, cavity_num: int, status: str, progress: int, message: str):
        """Update status for a single cavity"""
        if cavity_num in self.status_widgets:
            widgets = self.status_widgets[cavity_num]
            widgets["status"].setText(status)
            widgets["progress"].setValue(progress)
            widgets["message"].setText(message)

    def update_statistics(self, cavity_num: int, stats: dict):
        """Update stats information for a cavity

        Args:
            cavity_num: Cavity number (1-8)
            stats: Dictionary containing statistical values:
        """
        if cavity_num in self.status_widgets:
            widgets = self.status_widgets[cavity_num]

            # Format stat values
            message = (
                f"Mean: {stats['mean']:.2f}, "
                f"Std: {stats['std']:.2f}, "
                f"Range: [{stats['min']:.2f}, {stats['max']:.2f}], "
                f"Outliers: {stats['outliers']}"
            )

            # Update status widgets
            widgets["status"].setText("Complete")
            widgets["progress"].setValue(100)
            widgets["message"].setText(message)

    def reset_all(self):
        """Reset all cavities to initial state"""
        for cavity_num in range(1, 9):
            self.update_cavity_status(cavity_num, "Not configured", 0, "")
