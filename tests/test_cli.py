"""Tests for the command-line interface."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from sc_linac_physics import cli


class TestDisplayInfo:
    """Tests for DisplayInfo dataclass."""

    def test_display_info_creation(self):
        """Test creating a DisplayInfo instance."""

        def dummy_launcher():
            pass

        info = cli.DisplayInfo(
            name="test-display",
            launcher=dummy_launcher,
            description="Test description",
            category="display",
        )

        assert info.name == "test-display"
        assert info.launcher == dummy_launcher
        assert info.description == "Test description"
        assert info.category == "display"


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_extract_description_from_docstring_with_docstring(self):
        """Test extracting description from function with docstring."""

        def func_with_docstring():
            """This is a test function.

            With multiple lines.
            """
            pass

        result = cli._extract_description_from_docstring(func_with_docstring)
        assert result == "This is a test function."

    def test_extract_description_from_docstring_no_docstring(self):
        """Test extracting description from function without docstring."""

        def func_without_docstring():
            pass

        result = cli._extract_description_from_docstring(func_without_docstring)
        assert result == "No description available"

    def test_extract_description_from_docstring_empty_docstring(self):
        """Test extracting description from function with empty docstring."""

        def func_empty_docstring():
            """"""
            pass

        result = cli._extract_description_from_docstring(func_empty_docstring)
        assert result == "No description available"

    def test_extract_description_multiline_formatting(self):
        """Test extracting description with whitespace handling."""

        def func_whitespace():
            """
            Description with leading whitespace.
            """
            pass

        result = cli._extract_description_from_docstring(func_whitespace)
        assert result == "Description with leading whitespace."

    def test_get_display_name_with_launch_prefix(self):
        """Test converting function name to display name."""
        result = cli._get_display_name("launch_srf_home")
        assert result == "srf-home"

    def test_get_display_name_without_launch_prefix(self):
        """Test converting function name without launch prefix."""
        result = cli._get_display_name("some_function")
        assert result == "some_function"

    def test_get_display_name_multiple_underscores(self):
        """Test converting function name with multiple underscores."""
        result = cli._get_display_name("launch_fault_count_display")
        assert result == "fault-count-display"

    def test_get_category_with_decorator(self):
        """Test getting category from decorated function."""

        def decorated_func():
            pass

        decorated_func._launcher_category = "display"

        result = cli._get_category(decorated_func)
        assert result == "display"

    def test_get_category_without_decorator(self):
        """Test getting category from undecorated function."""

        def undecorated_func():
            pass

        result = cli._get_category(undecorated_func)
        assert result == "application"


class TestDiscoverLaunchers:
    """Tests for launcher discovery."""

    @patch("sc_linac_physics.cli.inspect.getmembers")
    def test_discover_launchers(self, mock_getmembers):
        """Test automatic launcher discovery."""

        def launch_test_display():
            """Test display."""
            pass

        launch_test_display._launcher_category = "display"

        def launch_test_app():
            """Test application."""
            pass

        launch_test_app._launcher_category = "application"

        def launch_python_display():
            """Base function to exclude."""
            pass

        def not_a_launcher():
            """Should be excluded."""
            pass

        mock_getmembers.return_value = [
            ("launch_test_display", launch_test_display),
            ("launch_test_app", launch_test_app),
            ("launch_python_display", launch_python_display),
            ("not_a_launcher", not_a_launcher),
        ]

        result = cli._discover_launchers()

        assert len(result) == 2
        assert any(
            d.name == "test-display" and d.category == "display" for d in result
        )
        assert any(
            d.name == "test-app" and d.category == "application" for d in result
        )
        assert not any(d.name == "python-display" for d in result)
        assert not any(d.name == "not_a_launcher" for d in result)


class TestListDisplays:
    """Tests for list_displays function."""

    def test_list_displays_output(self, capsys):
        """Test that list_displays produces expected output."""
        with patch.object(
            cli,
            "DISPLAY_LIST",
            [
                cli.DisplayInfo(
                    name="test-display",
                    launcher=lambda: None,
                    description="A test display",
                    category="display",
                ),
                cli.DisplayInfo(
                    name="test-app",
                    launcher=lambda: None,
                    description="A test application",
                    category="application",
                ),
            ],
        ):
            cli.list_displays()

        captured = capsys.readouterr()
        output = captured.out

        assert "SC Linac Physics - Available Applications" in output
        assert "DISPLAYS:" in output
        assert "APPLICATIONS:" in output
        assert "test-display" in output
        assert "A test display" in output
        assert "test-app" in output
        assert "A test application" in output
        assert "Usage: sc-linac <name>" in output

    def test_list_displays_empty(self, capsys):
        """Test list_displays with no displays."""
        with patch.object(cli, "DISPLAY_LIST", []):
            cli.list_displays()

        captured = capsys.readouterr()
        output = captured.out

        assert "SC Linac Physics - Available Applications" in output
        assert "DISPLAYS:" in output
        assert "APPLICATIONS:" in output

    def test_list_displays_sorting(self, capsys):
        """Test that displays are sorted alphabetically."""
        with patch.object(
            cli,
            "DISPLAY_LIST",
            [
                cli.DisplayInfo("zebra", lambda: None, "Z", "display"),
                cli.DisplayInfo("alpha", lambda: None, "A", "display"),
                cli.DisplayInfo("beta", lambda: None, "B", "display"),
            ],
        ):
            cli.list_displays()

        captured = capsys.readouterr()
        output = captured.out

        # Check that alpha appears before beta and zebra in the output
        alpha_pos = output.find("alpha")
        beta_pos = output.find("beta")
        zebra_pos = output.find("zebra")

        assert alpha_pos < beta_pos < zebra_pos


class TestLaunchDisplay:
    """Tests for launch_display function."""

    def test_launch_display_without_extra_args(self):
        """Test launching a display without extra arguments."""
        mock_launcher = MagicMock()
        display_info = cli.DisplayInfo(
            name="test",
            launcher=mock_launcher,
            description="Test",
            category="display",
        )

        with patch.object(cli, "DISPLAYS", {"test": display_info}):
            cli.launch_display("test")

        mock_launcher.assert_called_once()

    def test_launch_display_with_extra_args(self):
        """Test launching a display with extra arguments."""
        mock_launcher = MagicMock()
        display_info = cli.DisplayInfo(
            name="test",
            launcher=mock_launcher,
            description="Test",
            category="display",
        )

        original_argv = sys.argv.copy()
        with patch.object(cli, "DISPLAYS", {"test": display_info}):
            cli.launch_display("test", ["--arg1", "--arg2"])

        mock_launcher.assert_called_once()
        # sys.argv should be restored
        assert sys.argv == original_argv

    def test_launch_display_restores_argv_on_exception(self):
        """Test that sys.argv is restored even if launcher raises exception."""

        def failing_launcher():
            raise RuntimeError("Test error")

        display_info = cli.DisplayInfo(
            name="test",
            launcher=failing_launcher,
            description="Test",
            category="display",
        )

        original_argv = sys.argv.copy()
        with patch.object(cli, "DISPLAYS", {"test": display_info}):
            with pytest.raises(RuntimeError, match="Test error"):
                cli.launch_display("test", ["--arg"])

        assert sys.argv == original_argv

    def test_launch_display_default_extra_args(self):
        """Test launch_display with default None extra_args."""
        mock_launcher = MagicMock()
        display_info = cli.DisplayInfo(
            name="test",
            launcher=mock_launcher,
            description="Test",
            category="display",
        )

        with patch.object(cli, "DISPLAYS", {"test": display_info}):
            cli.launch_display("test")

        mock_launcher.assert_called_once()


class TestMain:
    """Tests for main CLI entry point."""

    def test_main_list_command(self, capsys):
        """Test main with list command."""
        with patch.object(sys, "argv", ["sc-linac", "list"]):
            with patch.object(cli, "DISPLAYS", {}):
                with patch.object(cli, "DISPLAY_LIST", []):
                    cli.main()

        captured = capsys.readouterr()
        assert "SC Linac Physics - Available Applications" in captured.out

    def test_main_launch_display(self):
        """Test main with display launch command."""
        mock_launcher = MagicMock()
        display_info = cli.DisplayInfo(
            name="test",
            launcher=mock_launcher,
            description="Test",
            category="display",
        )

        with patch.object(sys, "argv", ["sc-linac", "test"]):
            with patch.object(cli, "DISPLAYS", {"test": display_info}):
                with patch.object(cli, "DISPLAY_LIST", [display_info]):
                    cli.main()

        mock_launcher.assert_called_once()

    @patch("sc_linac_physics.cli.launch_display")
    def test_main_launch_display_with_args(self, mock_launch):
        """Test main with display launch and extra arguments."""
        mock_launcher = MagicMock()
        display_info = cli.DisplayInfo(
            name="test",
            launcher=mock_launcher,
            description="Test",
            category="display",
        )

        with patch.object(sys, "argv", ["sc-linac", "test", "arg1", "arg2"]):
            with patch.object(cli, "DISPLAYS", {"test": display_info}):
                with patch.object(cli, "DISPLAY_LIST", [display_info]):
                    cli.main()

        # Verify launch_display was called with the correct arguments
        mock_launch.assert_called_once_with("test", ["arg1", "arg2"])

    def test_main_invalid_display(self):
        """Test main with invalid display name."""
        with patch.object(sys, "argv", ["sc-linac", "nonexistent"]):
            with patch.object(cli, "DISPLAYS", {}):
                with patch.object(cli, "DISPLAY_LIST", []):
                    with pytest.raises(SystemExit):
                        cli.main()

    def test_main_no_arguments(self):
        """Test main without any arguments."""
        with patch.object(sys, "argv", ["sc-linac"]):
            with pytest.raises(SystemExit):
                cli.main()

    def test_main_help_flag(self):
        """Test main with help flag."""
        with patch.object(sys, "argv", ["sc-linac", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                cli.main()

        # --help should exit with code 0
        assert exc_info.value.code == 0


class TestModuleLevelVariables:
    """Tests for module-level variables."""

    def test_display_list_exists(self):
        """Test that DISPLAY_LIST is populated."""
        assert isinstance(cli.DISPLAY_LIST, list)

    def test_displays_dict_exists(self):
        """Test that DISPLAYS dictionary is populated."""
        assert isinstance(cli.DISPLAYS, dict)

    def test_displays_dict_matches_list(self):
        """Test that DISPLAYS dict matches DISPLAY_LIST."""
        for display in cli.DISPLAY_LIST:
            assert display.name in cli.DISPLAYS
            assert cli.DISPLAYS[display.name] == display


class TestIntegration:
    """Integration tests."""

    def test_end_to_end_list(self, capsys):
        """Test end-to-end listing of displays."""
        with patch.object(sys, "argv", ["sc-linac", "list"]):
            cli.main()

        captured = capsys.readouterr()
        # Should have standard output structure
        assert "SC Linac Physics" in captured.out
        assert "DISPLAYS:" in captured.out
        assert "APPLICATIONS:" in captured.out

    def test_end_to_end_launch(self):
        """Test end-to-end launching."""
        mock_launcher = MagicMock()
        display_info = cli.DisplayInfo(
            name="test-display",
            launcher=mock_launcher,
            description="Test",
            category="display",
        )

        with patch.object(cli, "DISPLAYS", {"test-display": display_info}):
            with patch.object(cli, "DISPLAY_LIST", [display_info]):
                with patch.object(sys, "argv", ["sc-linac", "test-display"]):
                    cli.main()

        # Verify the mock launcher was actually called
        mock_launcher.assert_called_once()
