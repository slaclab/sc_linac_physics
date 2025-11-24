import signal
import sys

from pydm import PyDMApplication

from sc_linac_physics.applications.microphonics.gui.main_window import (
    MicrophonicsGUI,
)


def main():
    """Main application entry point"""
    try:
        # Creates Qt Application
        app = PyDMApplication(
            ui_file=None, command_line_args=sys.argv, use_main_window=False
        )

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
