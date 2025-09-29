import signal
import sys

import pyqtgraph as pg
from pydm import PyDMApplication

from applications.microphonics.gui.main_window import MicrophonicsGUI

# Monkey patch for compatibility w/ PyQtGraph versions
if not hasattr(pg.PlotWidget, 'autoRangeEnabled'):
    def autoRangeEnabled(self):
        try:
            vb = self.plotItem.vb
            return (vb.state['autoRange'][0], vb.state['autoRange'][1])
        except (AttributeError, KeyError):
            return (False, False)

    pg.PlotWidget.autoRangeEnabled = autoRangeEnabled

def main():
    """Main application entry point"""
    try:
        # Creates Qt Application
        app = PyDMApplication(ui_file=None, command_line_args=sys.argv, use_main_window=False)

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
