"""Application entry point for the Microphonics measurement system"""

import sys

from PyQt5.QtWidgets import QApplication

from gui.main_window import MicrophonicsGUI


def main():
    """Main application entry point"""
    # Create the application
    app = QApplication(sys.argv)

    try:
        # Create and show the main window
        window = MicrophonicsGUI()
        window.show()

        # Start the application event loop
        sys.exit(app.exec_())

    except Exception as e:
        print(f"Error starting application: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
