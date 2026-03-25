"""Compatibility wrapper for Piezo Pre-RF display.

Use PiezoPreRFDisplay from phase_displays as the single implementation source.
"""

from sc_linac_physics.applications.rf_commissioning.ui.phase_displays import (
    PiezoPreRFDisplay,
)

__all__ = ["PiezoPreRFDisplay"]


def main():
    """Main entry point for running the display standalone."""
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = PiezoPreRFDisplay()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
