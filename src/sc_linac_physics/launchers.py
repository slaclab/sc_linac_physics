"""PyDM display launchers for SC Linac Physics."""

import sys


def launch_python_display(module_path: str, class_name: str, *args):
    """Launch a Python-based PyDM display.

    Parameters
    ----------
    module_path : str
        Full module path
    class_name : str
        Name of the display class
    *args
        Additional command line arguments
    """
    from pydm import PyDMApplication
    import importlib

    # Import the module and get the class
    module = importlib.import_module(module_path)
    display_class = getattr(module, class_name)

    # Create PyDM application and show the display
    app = PyDMApplication(command_line_args=list(args))
    main_window = display_class()
    main_window.show()
    sys.exit(app.exec())


# Display launchers
def launch_srf_home():
    """Launch the SRF home display."""
    launch_python_display("sc_linac_physics.displays.srfhome.srf_home", "SRFHome", *sys.argv[1:])


def launch_cavity_display():
    """Launch the cavity control display."""
    launch_python_display("sc_linac_physics.displays.cavity_display.cavity_display", "CavityDisplayGUI", *sys.argv[1:])


def launch_fault_decoder():
    """Launch the fault decoder display."""
    launch_python_display(
        "sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display", "DecoderDisplay", *sys.argv[1:]
    )


def launch_fault_count():
    """Launch the fault count display."""
    launch_python_display(
        "sc_linac_physics.displays.cavity_display.frontend.fault_count_display", "FaultCountDisplay", *sys.argv[1:]
    )


# Application launchers
def launch_quench_processing():
    """Launch the quench processing GUI."""
    launch_python_display("sc_linac_physics.applications.quench_processing.quench_gui", "QuenchGUI", *sys.argv[1:])


def launch_auto_setup():
    """Launch the auto setup GUI."""
    launch_python_display("sc_linac_physics.applications.auto_setup.setup_gui", "SetupGUI", *sys.argv[1:])


def launch_q0_measurement():
    """Launch the Q0 measurement GUI."""
    launch_python_display("sc_linac_physics.applications.q0.q0_gui", "Q0GUI", *sys.argv[1:])


def launch_tuning():
    """Launch the tuning GUI."""
    launch_python_display("sc_linac_physics.applications.tuning.tuning_gui", "Tuner", *sys.argv[1:])


def launch_microphonics():
    """launch the microphonics GUI"""
    launch_python_display(
        module_path="sc_linac_physics.applications.microphonics.gui.main_window", class_name="MicrophonicsGUI"
    )


if __name__ == "__main__":
    launch_srf_home()
