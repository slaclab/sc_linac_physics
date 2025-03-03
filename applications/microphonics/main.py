import signal
import sys

from PyQt5.QtWidgets import QApplication

from applications.microphonics.gui.main_window import MicrophonicsGUI


def main():
    """Main application entry point"""
    try:
        # Creates Qt Application
        app = QApplication(sys.argv)

        # Handles signals in main thread
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        # Creates and show main window
        window = MicrophonicsGUI()
        window.show()

        # Will start Qt event loop
        return app.exec_()

    except Exception as e:
        print(f"Error starting application: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
