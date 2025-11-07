from unittest.mock import patch, MagicMock

import pytest

from sc_linac_physics.cli import watcher_commands


class TestCommandBuilders:
    """Test the command builder functions"""

    def test_get_xterm_prefix(self):
        """Test xterm prefix generation"""
        result = watcher_commands._get_xterm_prefix("test_session")
        assert "xterm -T test_session" in result
        assert "TMUX_SSH_USER=laci" in result
        assert "TMUX_SSH_SERVER=lcls-srv03" in result

    def test_build_show_command(self):
        """Test show command generation"""
        command = watcher_commands.build_show_command("SC_CAV_QNCH_RESET")
        assert "xterm" in command
        assert "tmux_launcher open SC_CAV_QNCH_RESET" in command

    def test_build_restart_command(self):
        """Test restart command generation"""
        mock_func = MagicMock()
        mock_func.__module__ = "some.module.path"

        command = watcher_commands.build_restart_command(
            "SC_CAV_QNCH_RESET", mock_func
        )
        assert "xterm" in command
        assert "tmux_launcher restart" in command
        assert "python -m some.module.path" in command
        assert "SC_CAV_QNCH_RESET" in command

    def test_build_stop_command(self):
        """Test stop command generation"""
        mock_func = MagicMock()
        mock_func.__module__ = "some.module.path"

        command = watcher_commands.build_stop_command(
            "SC_CAV_QNCH_RESET", mock_func
        )
        assert "xterm" in command
        assert "tmux_launcher stop" in command
        assert "some.module.path" in command
        assert "SC_CAV_QNCH_RESET" in command


class TestCLICommands:
    """Test the CLI command handlers"""

    @patch("sc_linac_physics.cli.watcher_commands.os.system")
    @patch("sys.argv", ["watcher_commands", "show", "SC_CAV_QNCH_RESET"])
    def test_main_show_command(self, mock_system):
        """Test main function with show command"""
        watcher_commands.main()
        mock_system.assert_called_once()
        call_args = mock_system.call_args[0][0]
        assert "tmux_launcher open SC_CAV_QNCH_RESET" in call_args

    @patch("sc_linac_physics.cli.watcher_commands.os.system")
    @patch("sys.argv", ["watcher_commands", "restart", "SC_CAV_QNCH_RESET"])
    def test_main_restart_command(self, mock_system):
        """Test main function with restart command"""
        watcher_commands.main()
        mock_system.assert_called_once()
        call_args = mock_system.call_args[0][0]
        assert "tmux_launcher restart" in call_args

    @patch("sc_linac_physics.cli.watcher_commands.os.system")
    @patch("sys.argv", ["watcher_commands", "stop", "SC_CAV_QNCH_RESET"])
    def test_main_stop_command(self, mock_system):
        """Test main function with stop command"""
        watcher_commands.main()
        mock_system.assert_called_once()
        call_args = mock_system.call_args[0][0]
        assert "tmux_launcher stop" in call_args

    @patch("sys.argv", ["watcher_commands", "list"])
    @patch("builtins.print")
    def test_main_list_command(self, mock_print):
        """Test main function with list command"""
        watcher_commands.main()
        # Check that print was called with watcher information
        assert mock_print.called
        print_calls = [str(call) for call in mock_print.call_args_list]
        output = " ".join(print_calls)
        assert "SC_CAV_QNCH_RESET" in output

    @patch("sys.argv", ["watcher_commands", "show", "INVALID_WATCHER"])
    def test_main_invalid_watcher(self):
        """Test main function with invalid watcher name"""
        with pytest.raises(SystemExit):
            watcher_commands.main()


class TestWatcherConfigs:
    """Test watcher configurations"""

    def test_watcher_configs_exist(self):
        """Test that WATCHER_CONFIGS is properly defined"""
        assert len(watcher_commands.WATCHER_CONFIGS) > 0

    def test_watcher_configs_have_callable_functions(self):
        """Test that all watcher configs have callable main functions"""
        for name, func in watcher_commands.WATCHER_CONFIGS.items():
            assert callable(func), f"{name} should have a callable function"
            assert hasattr(
                func, "__module__"
            ), f"{name} function should have __module__ attribute"


class TestLegacyFunctions:
    """Test legacy CLI functions"""

    @patch("sc_linac_physics.cli.watcher_commands.os.system")
    @patch("sys.argv", ["show_watcher", "SC_CAV_QNCH_RESET"])
    def test_show_watcher(self, mock_system):
        """Test show_watcher legacy function"""
        watcher_commands.show_watcher()
        mock_system.assert_called_once()

    @patch("sc_linac_physics.cli.watcher_commands.os.system")
    @patch("sys.argv", ["restart_watcher", "SC_CAV_QNCH_RESET"])
    def test_restart_watcher(self, mock_system):
        """Test restart_watcher legacy function"""
        watcher_commands.restart_watcher()
        mock_system.assert_called_once()

    @patch("sc_linac_physics.cli.watcher_commands.os.system")
    @patch("sys.argv", ["stop_watcher", "SC_CAV_QNCH_RESET"])
    def test_stop_watcher(self, mock_system):
        """Test stop_watcher legacy function"""
        watcher_commands.stop_watcher()
        mock_system.assert_called_once()
