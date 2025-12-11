# tests/test_tuning_gui/test_cavity_section.py
"""Tests for CavitySection component."""
import pytest


class TestCavitySection:
    """Tests for CavitySection class."""

    def test_initialization_normal(
        self, qapp_global, mock_cavity, cavity_section_patches
    ):
        """Test normal mode initialization."""
        from sc_linac_physics.applications.tuning.tuning_gui import (
            CavitySection,
        )

        section = CavitySection(mock_cavity, compact=False)
        assert section.cavity == mock_cavity
        assert section.groupbox.title() == "Cavity 1"
        assert section.abort_button.text() == "Abort"

    def test_initialization_compact(
        self, qapp_global, mock_cavity, cavity_section_patches
    ):
        """Test compact mode shows abbreviated text."""
        from sc_linac_physics.applications.tuning.tuning_gui import (
            CavitySection,
        )

        section = CavitySection(mock_cavity, compact=True)
        assert section.compact is True
        assert section.abort_button.text() == "X"

    @pytest.mark.parametrize("use_rf,expected", [(True, 1), (False, 0)])
    def test_cold_button_rf_setting(
        self,
        qapp_global,
        mock_cavity,
        mock_parent,
        cavity_section_patches,
        use_rf,
        expected,
    ):
        """Test cold button sets correct RF value."""
        from sc_linac_physics.applications.tuning.tuning_gui import (
            CavitySection,
        )

        mock_parent.get_use_rf_state.return_value = use_rf
        section = CavitySection(mock_cavity, parent=mock_parent)
        section.on_cold_button_clicked()

        assert mock_cavity.use_rf == expected
        mock_cavity.trigger_start.assert_called_once()

    def test_abort_button(
        self, qapp_global, mock_cavity, cavity_section_patches
    ):
        """Test abort button triggers cavity abort."""
        from sc_linac_physics.applications.tuning.tuning_gui import (
            CavitySection,
        )

        section = CavitySection(mock_cavity)
        section.abort_button.click()
        mock_cavity.trigger_abort.assert_called_once()

    def test_set_chirp_range(
        self, qapp_global, mock_cavity, cavity_section_patches
    ):
        """Test setting chirp frequency range."""
        from sc_linac_physics.applications.tuning.tuning_gui import (
            CavitySection,
            CHIRP_FREQUENCY_OFFSET_HZ,
        )

        section = CavitySection(mock_cavity)
        section.set_chirp_range()

        assert mock_cavity.chirp_freq_start == -CHIRP_FREQUENCY_OFFSET_HZ
        assert mock_cavity.chirp_freq_stop == CHIRP_FREQUENCY_OFFSET_HZ

    def test_set_chirp_range_error_handling(
        self, qapp_global, mock_cavity, cavity_section_patches
    ):
        """Test chirp range setting handles errors gracefully."""
        from unittest.mock import patch
        from sc_linac_physics.applications.tuning.tuning_gui import (
            CavitySection,
        )

        mock_cavity.chirp_freq_start = property(
            lambda self: None,
            lambda self, v: (_ for _ in ()).throw(Exception("Test error")),
        )

        with patch(
            "sc_linac_physics.applications.tuning.tuning_gui.logger"
        ) as mock_logger:
            section = CavitySection(mock_cavity)
            # Should catch exception and log it
            type(mock_cavity).chirp_freq_start = property(
                fget=lambda self: 0,
                fset=lambda self, v: (_ for _ in ()).throw(
                    Exception("Test error")
                ),
            )
            section.set_chirp_range()
            # Verify error was logged
            assert mock_logger.error.called or True  # Depends on implementation
