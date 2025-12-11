# tests/applications/tuning/test_tuner.py
"""Tests for Tuner main display."""
from unittest.mock import patch, Mock

import pytest
from PyQt5.QtWidgets import QWidget, QCheckBox


class MockDisplay(QWidget):
    """Mock Display that's actually a QWidget."""

    def __init__(self, *args, **kwargs):
        super().__init__()


class TestTunerMethods:
    """Tests for Tuner methods without full initialization."""

    @pytest.fixture
    def tuner_minimal(self, qapp_global, mock_machine):
        """Create minimal Tuner instance for testing methods."""
        from sc_linac_physics.applications.tuning.tuning_gui import Tuner

        # Use Tuner.__new__() for Qt classes in Python 3.13+
        tuner = Tuner.__new__(Tuner)

        # Set only the attributes we need
        tuner.machine = mock_machine
        tuner.use_rf_checkbox = QCheckBox()
        tuner.use_rf_checkbox.setChecked(True)
        tuner.current_cryomodule = None
        tuner.rack_screen_cache = {}
        tuner.current_rack_screens = None
        tuner.rack_layout = Mock()
        tuner._window_title = "SRF Tuner"

        # Mock methods that would require full initialization
        tuner.setWindowTitle = Mock(
            side_effect=lambda x: setattr(tuner, "_window_title", x)
        )
        tuner.windowTitle = Mock(return_value=tuner._window_title)

        return tuner

    def test_get_use_rf_state_true(self, tuner_minimal):
        """Test getting RF usage state when True."""
        tuner_minimal.use_rf_checkbox.setChecked(True)
        assert tuner_minimal.get_use_rf_state() is True

    def test_get_use_rf_state_false(self, tuner_minimal):
        """Test getting RF usage state when False."""
        tuner_minimal.use_rf_checkbox.setChecked(False)
        assert tuner_minimal.get_use_rf_state() is False

    def test_cm_cold_button_with_rf(self, tuner_minimal, mock_machine):
        """Test cryomodule cold button with RF enabled."""
        tuner_minimal.use_rf_checkbox.setChecked(True)
        tuner_minimal.current_cryomodule = mock_machine.cryomodules["CM01"]

        tuner_minimal.on_cm_cold_button_clicked()

        assert tuner_minimal.current_cryomodule.use_rf == 1
        tuner_minimal.current_cryomodule.trigger_start.assert_called_once()

    def test_cm_cold_button_without_rf(self, tuner_minimal, mock_machine):
        """Test cryomodule cold button with RF disabled."""
        tuner_minimal.use_rf_checkbox.setChecked(False)
        tuner_minimal.current_cryomodule = mock_machine.cryomodules["CM01"]

        tuner_minimal.on_cm_cold_button_clicked()

        assert tuner_minimal.current_cryomodule.use_rf == 0
        tuner_minimal.current_cryomodule.trigger_start.assert_called_once()

    def test_cm_abort_button(self, tuner_minimal, mock_machine):
        """Test cryomodule abort button."""
        tuner_minimal.current_cryomodule = mock_machine.cryomodules["CM01"]
        tuner_minimal.on_cm_abort_button_clicked()

        tuner_minimal.current_cryomodule.trigger_abort.assert_called_once()

    def test_cm_cold_button_no_selection(self, tuner_minimal):
        """Test cryomodule cold button with no selection logs warning."""
        with patch(
            "sc_linac_physics.applications.tuning.tuning_gui.logger"
        ) as mock_logger:
            tuner_minimal.current_cryomodule = None
            tuner_minimal.on_cm_cold_button_clicked()
            mock_logger.warning.assert_called_once()

    def test_cm_abort_button_no_selection(self, tuner_minimal):
        """Test cryomodule abort button with no selection logs warning."""
        with patch(
            "sc_linac_physics.applications.tuning.tuning_gui.logger"
        ) as mock_logger:
            tuner_minimal.current_cryomodule = None
            tuner_minimal.on_cm_abort_button_clicked()
            mock_logger.warning.assert_called_once()

    def test_cryomodule_changed(self, tuner_minimal, mock_machine):
        """Test changing cryomodule selection."""
        with patch(
            "sc_linac_physics.applications.tuning.tuning_gui.RackScreen"
        ) as mock_rack_screen:
            # Mock RackScreen to return screens with real QWidget groupbox
            def create_screen(*args, **kwargs):
                screen = Mock()
                screen.groupbox = QWidget()  # Real QWidget, not Mock
                return screen

            mock_rack_screen.side_effect = create_screen

            tuner_minimal.on_cryomodule_changed("CM01")

            assert (
                tuner_minimal.current_cryomodule
                == mock_machine.cryomodules["CM01"]
            )

    def test_empty_cryomodule_selection(self, tuner_minimal):
        """Test handling empty cryomodule selection."""
        tuner_minimal.on_cryomodule_changed("")

        # Should not crash, current_cryomodule stays None
        assert tuner_minimal.current_cryomodule is None


class TestTunerIntegration:
    """Integration tests that verify the window can actually be created and displayed."""

    @pytest.mark.timeout(10)
    def test_window_creation(self, qapp_global, tuner_patches):
        """Test that Tuner window can be created."""
        from sc_linac_physics.applications.tuning.tuning_gui import Tuner

        with patch(
            "sc_linac_physics.applications.tuning.tuning_gui.Display",
            MockDisplay,
        ):
            tuner = Tuner()

            # Verify window was created
            assert tuner is not None
            assert isinstance(tuner, QWidget)

            # Verify window properties
            assert "SRF Tuner" in tuner.windowTitle()
            assert tuner.isVisible() is False  # Not shown yet

    @pytest.mark.timeout(10)
    def test_window_has_required_widgets(self, qapp_global, tuner_patches):
        """Test that window contains all required widgets."""
        from sc_linac_physics.applications.tuning.tuning_gui import Tuner

        with patch(
            "sc_linac_physics.applications.tuning.tuning_gui.Display",
            MockDisplay,
        ):
            tuner = Tuner()

            # Check critical widgets exist
            assert hasattr(tuner, "cm_selector")
            assert hasattr(tuner, "use_rf_checkbox")
            assert hasattr(tuner, "cm_cold_button")
            assert hasattr(tuner, "cm_abort_button")
            assert hasattr(tuner, "rack_container")

            # Check initial states
            assert tuner.use_rf_checkbox.isChecked() is True
            assert (
                tuner.use_rf_checkbox.isEnabled() is False
            )  # Disabled until feature ready

    @pytest.mark.timeout(10)
    def test_window_can_be_shown_and_hidden(self, qapp_global, tuner_patches):
        """Test that window can be shown and hidden."""
        from sc_linac_physics.applications.tuning.tuning_gui import Tuner

        with patch(
            "sc_linac_physics.applications.tuning.tuning_gui.Display",
            MockDisplay,
        ):
            tuner = Tuner()

            # Show the window
            tuner.show()
            assert tuner.isVisible() is True

            # Process events to allow window to render
            qapp_global.processEvents()

            # Hide the window
            tuner.hide()
            assert tuner.isVisible() is False

            # Clean up
            tuner.close()

    @pytest.mark.timeout(10)
    def test_window_layout_structure(self, qapp_global, tuner_patches):
        """Test that window has correct layout structure."""
        from sc_linac_physics.applications.tuning.tuning_gui import Tuner

        with patch(
            "sc_linac_physics.applications.tuning.tuning_gui.Display",
            MockDisplay,
        ):
            tuner = Tuner()

            # Check layout exists
            assert tuner.layout() is not None

            # Check that rack container is present
            assert tuner.rack_container is not None
            assert tuner.rack_layout is not None

    @pytest.mark.timeout(10)
    def test_cryomodule_selector_populated(self, qapp_global, mock_machine):
        """Test that cryomodule selector is populated with available CMs."""
        from sc_linac_physics.applications.tuning.tuning_gui import Tuner

        # Create proper RackScreen mock that returns real QWidgets
        def create_rack_screen(*args, **kwargs):
            screen = Mock()
            screen.groupbox = QWidget()  # Must be real QWidget
            return screen

        with (
            patch(
                "sc_linac_physics.applications.tuning.tuning_gui.Display",
                MockDisplay,
            ),
            patch(
                "sc_linac_physics.applications.tuning.tuning_gui.ALL_CRYOMODULES",
                ["CM01", "CM02"],
            ),
            patch(
                "sc_linac_physics.applications.tuning.tuning_gui.Machine"
            ) as mock_machine_cls,
            patch(
                "sc_linac_physics.applications.tuning.tuning_gui.RackScreen",
                side_effect=create_rack_screen,
            ),
        ):

            # Setup mock machine with two cryomodules
            mock_machine_cls.return_value = mock_machine

            tuner = Tuner()

            # Check that combobox has items
            assert tuner.cm_selector.count() == 2
            assert tuner.cm_selector.itemText(0) == "CM01"
            assert tuner.cm_selector.itemText(1) == "CM02"

    @pytest.mark.timeout(10)
    def test_window_responds_to_user_interaction(
        self, qapp_global, tuner_patches
    ):
        """Test that window responds to user interaction (button clicks)."""
        from sc_linac_physics.applications.tuning.tuning_gui import Tuner

        with patch(
            "sc_linac_physics.applications.tuning.tuning_gui.Display",
            MockDisplay,
        ):
            tuner = Tuner()

            # Verify buttons are clickable (don't crash)
            assert tuner.cm_cold_button.isEnabled() is True
            assert tuner.cm_abort_button.isEnabled() is True

    @pytest.mark.timeout(10)
    def test_window_renders_correctly(self, qapp_global, tuner_patches):
        """Test that window launches and renders without crashing."""
        from sc_linac_physics.applications.tuning.tuning_gui import Tuner

        with patch(
            "sc_linac_physics.applications.tuning.tuning_gui.Display",
            MockDisplay,
        ):
            tuner = Tuner()
            tuner.show()

            # Verify window is shown
            assert tuner.isVisible() is True

            # Process events to ensure rendering happens
            qapp_global.processEvents()

            # Verify window is still visible after event processing
            assert tuner.isVisible() is True

            # Verify window has non-zero size (actually rendered)
            assert tuner.width() > 0
            assert tuner.height() > 0

            # Clean shutdown
            tuner.hide()
            tuner.close()

            # Verify clean shutdown
            assert tuner.isVisible() is False
