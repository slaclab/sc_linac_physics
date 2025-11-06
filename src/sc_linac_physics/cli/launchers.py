"""PyDM display launchers for SC Linac Physics."""

import sys

from pydm import PyDMApplication
from pydm.main_window import PyDMMainWindow


def display(func):
    """Decorator to mark a launcher as a display."""
    func._launcher_category = "display"
    return func


def application(func):
    """Decorator to mark a launcher as an application."""
    func._launcher_category = "application"
    return func


def launch_python_display(display_class, *args, standalone=True):
    """Launch a Python-based PyDM display.

    Parameters
    ----------
    display_class : class
        The display class to instantiate
    *args
        Additional command line arguments
    standalone : bool, optional
        If True, creates new application and blocks (for standalone launch).
        If False, uses existing application (for child windows). Default is True.

    Returns
    -------
    QWidget or None
        The display window instance if standalone=False, None otherwise
    """

    if standalone:
        # Standalone mode: create app and block
        app = PyDMApplication(command_line_args=list(args))
        new_display = display_class()
        app.main_window.set_display_widget(new_display)
        app.main_window.show()
        sys.exit(app.exec())
    else:
        # Child window mode: use existing app
        app = PyDMApplication.instance()

        if app is None:
            raise RuntimeError(
                "No PyDMApplication instance found. "
                "standalone=False requires an existing application."
            )

        new_display = display_class()

        # Create a new main window for this display
        window = PyDMMainWindow()
        window.set_display_widget(new_display)
        window.show()

        return window


# Display launchers
@display
def launch_srf_home(standalone=True):
    """Launch the SRF home display."""
    from sc_linac_physics.displays.srfhome.srf_home import SRFHome

    return launch_python_display(SRFHome, *sys.argv[1:], standalone=standalone)


@display
def launch_cavity_display(standalone=True):
    """Launch the cavity control display."""
    from sc_linac_physics.displays.cavity_display.cavity_display import (
        CavityDisplayGUI,
    )

    return launch_python_display(
        CavityDisplayGUI, *sys.argv[1:], standalone=standalone
    )


@display
def launch_fault_decoder(standalone=True):
    """Launch the fault decoder display."""
    from sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display import (
        DecoderDisplay,
    )

    return launch_python_display(
        DecoderDisplay, *sys.argv[1:], standalone=standalone
    )


@display
def launch_fault_count(standalone=True):
    """Launch the fault count display."""
    from sc_linac_physics.displays.cavity_display.frontend.fault_count_display import (
        FaultCountDisplay,
    )

    return launch_python_display(
        FaultCountDisplay, *sys.argv[1:], standalone=standalone
    )


# Application launchers
@application
def launch_quench_processing(standalone=True):
    """Launch the quench processing GUI."""
    from sc_linac_physics.applications.quench_processing.quench_gui import (
        QuenchGUI,
    )

    return launch_python_display(
        QuenchGUI, *sys.argv[1:], standalone=standalone
    )


@application
def launch_auto_setup(standalone=True):
    """Launch the auto setup GUI."""
    from sc_linac_physics.applications.auto_setup.setup_gui import SetupGUI

    return launch_python_display(SetupGUI, *sys.argv[1:], standalone=standalone)


@application
def launch_q0_measurement(standalone=True):
    """Launch the Q0 measurement GUI."""
    from sc_linac_physics.applications.q0.q0_gui import Q0GUI

    return launch_python_display(Q0GUI, *sys.argv[1:], standalone=standalone)


@application
def launch_tuning(standalone=True):
    """Launch the tuning GUI."""
    from sc_linac_physics.applications.tuning.tuning_gui import Tuner

    return launch_python_display(Tuner, *sys.argv[1:], standalone=standalone)


@application
def launch_microphonics(standalone=True):
    """Launch the microphonics GUI."""
    from sc_linac_physics.applications.microphonics.gui.main_window import (
        MicrophonicsGUI,
    )

    return launch_python_display(
        MicrophonicsGUI, *sys.argv[1:], standalone=standalone
    )


@display
def launch_plotter(standalone=True):
    from sc_linac_physics.displays.plot.plot import PVGroupArchiverDisplay

    return launch_python_display(
        PVGroupArchiverDisplay, *sys.argv[1:], standalone=standalone
    )


@display
def launch_cryo_signals(standalone=True):
    from sc_linac_physics.displays.plot.cryo_signals import (
        LinacGroupedCryomodulePlotDisplay,
    )

    return launch_python_display(
        LinacGroupedCryomodulePlotDisplay, *sys.argv[1:], standalone=standalone
    )


if __name__ == "__main__":
    launch_srf_home()
