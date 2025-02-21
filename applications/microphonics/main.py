"""Application entry point for the Microphonics measurement system"""

import signal
import sys

from PyQt5.QtWidgets import QApplication

from applications.microphonics.gui.main_window import MicrophonicsGUI


def main():
    """Main application entry point"""
    try:
        # Create Qt Application
        app = QApplication(sys.argv)

        # Handle signals in main thread
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        # Create and show main window
        window = MicrophonicsGUI()
        window.show()

        # Start Qt event loop
        return app.exec_()

    except Exception as e:
        print(f"Error starting application: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
