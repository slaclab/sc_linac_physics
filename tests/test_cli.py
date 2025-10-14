# tests/test_cli.py
import sys
from unittest.mock import Mock, patch, MagicMock

import pytest

from sc_linac_physics import cli


class TestDisplaysConfiguration:
    """Test the DISPLAYS configuration dictionary."""

    def test_displays_structure(self):
        """Test that DISPLAYS has the expected structure."""
        assert isinstance(cli.DISPLAYS, dict)
        assert len(cli.DISPLAYS) > 0

        for name, info in cli.DISPLAYS.items():
            assert "launcher" in info
            assert "description" in info
            assert isinstance(info["launcher"], str)
            assert isinstance(info["description"], str)

    def test_main_displays_present(self):
        """Test that main displays are configured."""
        main_displays = ["srf-home", "cavity", "fault-decoder", "fault-count"]
        for display in main_displays:
            assert display in cli.DISPLAYS

    def test_applications_present(self):
        """Test that applications are configured."""
        applications = ["quench", "setup", "q0", "tuning"]
        for app in applications:
            assert app in cli.DISPLAYS

    def test_launcher_names_format(self):
        """Test that launcher names follow expected format."""
        for name, info in cli.DISPLAYS.items():
            launcher = info["launcher"]
            assert launcher.startswith("launch_")
            assert "_" in launcher


class TestListDisplays:
    """Test the list_displays function."""

    def test_list_displays_output(self, capsys):
        """Test that list_displays produces expected output."""
        cli.list_displays()

        captured = capsys.readouterr()
        output = captured.out

        # Check header
        assert "SC Linac Physics" in output
        assert "Available Applications" in output

        # Check sections
        assert "DISPLAYS:" in output
        assert "APPLICATIONS:" in output

        # Check usage instructions
        assert "Usage:" in output
        assert "sc-linac" in output

    def test_list_displays_contains_all_displays(self, capsys):
        """Test that list_displays shows all configured displays."""
        cli.list_displays()

        captured = capsys.readouterr()
        output = captured.out

        for name in cli.DISPLAYS.keys():
            assert name in output

    def test_list_displays_contains_descriptions(self, capsys):
        """Test that list_displays shows descriptions."""
        cli.list_displays()

        captured = capsys.readouterr()
        output = captured.out

        for info in cli.DISPLAYS.values():
            assert info["description"] in output

    def test_list_displays_formatting(self, capsys):
        """Test that list_displays has proper formatting."""
        cli.list_displays()

        captured = capsys.readouterr()
        output = captured.out

        # Check for separator lines
        assert "=" * 70 in output

        # Check for proper spacing
        lines = output.split("\n")
        assert any(line.strip() == "" for line in lines)  # Has blank lines


class TestLaunchDisplay:
    """Test the launch_display function."""

    def test_launch_display_basic(self):
        """Test basic display launch."""
        # Mock the launchers module before it's imported
        mock_launchers = MagicMock()
        mock_func = Mock()
        mock_launchers.launch_srf_home = mock_func

        with patch.dict("sys.modules", {"sc_linac_physics.launchers": mock_launchers}):
            cli.launch_display("srf-home")

        mock_func.assert_called_once()

    def test_launch_display_with_extra_args(self):
        """Test display launch with extra arguments."""
        mock_launchers = MagicMock()
        mock_func = Mock()
        mock_launchers.launch_cavity_display = mock_func

        original_argv = sys.argv.copy()

        with patch.dict("sys.modules", {"sc_linac_physics.launchers": mock_launchers}):
            cli.launch_display("cavity", ["--arg1", "value1"])

        # Verify launcher was called
        mock_func.assert_called_once()

        # Verify sys.argv was restored
        assert sys.argv == original_argv

    def test_launch_display_argv_modification(self):
        """Test that sys.argv is properly modified during launch."""

        def check_argv():
            # Should have script name + extra args
            assert len(sys.argv) == 3
            assert sys.argv[1] == "--test"
            assert sys.argv[2] == "value"

        mock_launchers = MagicMock()
        mock_func = Mock(side_effect=check_argv)
        mock_launchers.launch_fault_decoder = mock_func

        original_argv = sys.argv.copy()

        with patch.dict("sys.modules", {"sc_linac_physics.launchers": mock_launchers}):
            cli.launch_display("fault-decoder", ["--test", "value"])

        # Verify argv was restored
        assert sys.argv == original_argv

    def test_launch_display_argv_restored_on_exception(self):
        """Test that sys.argv is restored even if launcher raises exception."""
        mock_launchers = MagicMock()
        mock_func = Mock(side_effect=Exception("Launch failed"))
        mock_launchers.launch_quench_processing = mock_func

        original_argv = sys.argv.copy()

        with patch.dict("sys.modules", {"sc_linac_physics.launchers": mock_launchers}):
            with pytest.raises(Exception, match="Launch failed"):
                cli.launch_display("quench")

        # Verify argv was restored despite exception
        assert sys.argv == original_argv

    def test_launch_all_displays(self):
        """Test launching each configured display."""
        for display_name, info in cli.DISPLAYS.items():
            mock_launchers = MagicMock()
            mock_func = Mock()
            setattr(mock_launchers, info["launcher"], mock_func)

            with patch.dict("sys.modules", {"sc_linac_physics.launchers": mock_launchers}):
                cli.launch_display(display_name)

            mock_func.assert_called_once()

    def test_launch_display_with_none_args(self):
        """Test launch_display with None as extra_args."""
        mock_launchers = MagicMock()
        mock_func = Mock()
        mock_launchers.launch_tuning = mock_func

        with patch.dict("sys.modules", {"sc_linac_physics.launchers": mock_launchers}):
            cli.launch_display("tuning", None)

        mock_func.assert_called_once()


class TestMain:
    """Test the main CLI entry point."""

    @patch("sc_linac_physics.cli.list_displays")
    def test_main_list_command(self, mock_list):
        """Test main with 'list' command."""
        with patch("sys.argv", ["sc-linac", "list"]):
            cli.main()

        mock_list.assert_called_once()

    @patch("sc_linac_physics.cli.launch_display")
    def test_main_launch_display(self, mock_launch):
        """Test main launching a display."""
        with patch("sys.argv", ["sc-linac", "srf-home"]):
            cli.main()

        mock_launch.assert_called_once_with("srf-home", [])

    @patch("sc_linac_physics.cli.launch_display")
    def test_main_with_extra_args(self, mock_launch):
        """Test main with extra arguments."""
        # Note: argparse collects these as args, not --arg1 --arg2
        with patch("sys.argv", ["sc-linac", "cavity", "arg1", "value1", "arg2"]):
            cli.main()

        mock_launch.assert_called_once_with("cavity", ["arg1", "value1", "arg2"])

    def test_main_invalid_display(self):
        """Test main with invalid display name."""
        with patch("sys.argv", ["sc-linac", "invalid-display"]):
            with pytest.raises(SystemExit):
                cli.main()

    def test_main_no_arguments(self):
        """Test main with no arguments."""
        with patch("sys.argv", ["sc-linac"]):
            with pytest.raises(SystemExit):
                cli.main()

    @patch("sc_linac_physics.cli.launch_display")
    def test_main_all_displays(self, mock_launch):
        """Test main can launch all configured displays."""
        for display_name in cli.DISPLAYS.keys():
            mock_launch.reset_mock()

            with patch("sys.argv", ["sc-linac", display_name]):
                cli.main()

            mock_launch.assert_called_once_with(display_name, [])

    def test_main_help(self, capsys):
        """Test main --help output."""
        with patch("sys.argv", ["sc-linac", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                cli.main()

            assert exc_info.value.code == 0

        captured = capsys.readouterr()
        output = captured.out

        assert "SC Linac Physics" in output
        assert "Examples:" in output
        assert "sc-linac list" in output


class TestArgumentParsing:
    """Test argument parsing behavior."""

    def test_parser_accepts_valid_displays(self):
        """Test that parser accepts all valid display names."""
        for display_name in cli.DISPLAYS.keys():
            with patch("sys.argv", ["sc-linac", display_name]):
                with patch("sc_linac_physics.cli.launch_display"):
                    # Should not raise
                    cli.main()

    def test_parser_accepts_list(self):
        """Test that parser accepts 'list' command."""
        with patch("sys.argv", ["sc-linac", "list"]):
            with patch("sc_linac_physics.cli.list_displays"):
                # Should not raise
                cli.main()

    def test_parser_help_examples(self, capsys):
        """Test that help includes usage examples."""
        with patch("sys.argv", ["sc-linac", "--help"]):
            with pytest.raises(SystemExit):
                cli.main()

        captured = capsys.readouterr()
        output = captured.out

        # Check for example commands
        assert "sc-linac srf-home" in output
        assert "sc-linac cavity" in output
        assert "sc-linac fault-decoder" in output
        assert "sc-linac quench" in output


class TestIntegration:
    """Integration tests."""

    def test_full_workflow_list(self, capsys):
        """Test complete workflow: list displays."""
        with patch("sys.argv", ["sc-linac", "list"]):
            cli.main()

        captured = capsys.readouterr()
        output = captured.out

        # Verify output contains expected information
        assert "DISPLAYS:" in output
        assert "APPLICATIONS:" in output

        for name in cli.DISPLAYS.keys():
            assert name in output

    def test_full_workflow_launch(self):
        """Test complete workflow: launch display."""
        mock_launchers = MagicMock()
        mock_func = Mock()
        mock_launchers.launch_srf_home = mock_func

        with patch.dict("sys.modules", {"sc_linac_physics.launchers": mock_launchers}):
            with patch("sys.argv", ["sc-linac", "srf-home", "test-arg"]):
                cli.main()

        # Verify launcher was called
        mock_func.assert_called_once()

    def test_full_workflow_with_multiple_args(self):
        """Test complete workflow with multiple arguments."""
        mock_launchers = MagicMock()
        mock_func = Mock()
        mock_launchers.launch_cavity_display = mock_func

        original_argv = sys.argv.copy()

        with patch.dict("sys.modules", {"sc_linac_physics.launchers": mock_launchers}):
            with patch("sys.argv", ["sc-linac", "cavity", "CM01", "verbose"]):
                cli.main()

        mock_func.assert_called_once()
        assert sys.argv == original_argv


class TestErrorHandling:
    """Test error handling scenarios."""

    def test_invalid_display_name_error(self):
        """Test error handling for invalid display name."""
        with patch("sys.argv", ["sc-linac", "nonexistent"]):
            with pytest.raises(SystemExit) as exc_info:
                cli.main()

            # Should exit with error code
            assert exc_info.value.code != 0

    def test_launcher_exception_propagates(self):
        """Test that exceptions from launchers propagate."""
        mock_launchers = MagicMock()
        mock_func = Mock(side_effect=RuntimeError("Display error"))
        mock_launchers.launch_fault_count = mock_func

        with patch.dict("sys.modules", {"sc_linac_physics.launchers": mock_launchers}):
            with patch("sys.argv", ["sc-linac", "fault-count"]):
                with pytest.raises(RuntimeError, match="Display error"):
                    cli.main()

    def test_missing_launcher_attribute(self):
        """Test error when launcher attribute doesn't exist."""
        mock_launchers = MagicMock()
        # Make getattr raise AttributeError
        mock_launchers.launch_q0_measurement = MagicMock(side_effect=AttributeError("No such launcher"))

        with patch.dict("sys.modules", {"sc_linac_physics.launchers": mock_launchers}):
            with patch("sys.argv", ["sc-linac", "q0"]):
                with pytest.raises(AttributeError):
                    cli.main()


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @patch("sc_linac_physics.cli.launch_display")
    def test_empty_extra_args(self, mock_launch):
        """Test with empty extra arguments list."""
        with patch("sys.argv", ["sc-linac", "setup"]):
            cli.main()

        mock_launch.assert_called_once_with("setup", [])

    @patch("sc_linac_physics.cli.launch_display")
    def test_many_extra_args(self, mock_launch):
        """Test with many extra arguments."""
        many_args = [f"arg{i}" for i in range(20)]

        with patch("sys.argv", ["sc-linac", "tuning"] + many_args):
            cli.main()

        mock_launch.assert_called_once_with("tuning", many_args)

    def test_displays_dict_immutability(self):
        """Test that DISPLAYS dict retains its structure."""
        original_len = len(cli.DISPLAYS)
        original_keys = set(cli.DISPLAYS.keys())

        # Verify structure is consistent
        assert len(cli.DISPLAYS) == original_len
        assert set(cli.DISPLAYS.keys()) == original_keys


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
