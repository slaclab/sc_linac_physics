from unittest.mock import patch, MagicMock

import pytest

from sc_linac_physics.cli import watcher_commands


@pytest.fixture
def with_tmux_launcher(monkeypatch):
    monkeypatch.setattr(watcher_commands, "_has_tmux_launcher", lambda: True)


@pytest.fixture
def without_tmux_launcher(monkeypatch, tmp_path):
    monkeypatch.setattr(watcher_commands, "_has_tmux_launcher", lambda: False)
    monkeypatch.setattr(watcher_commands, "_local_dir", lambda: tmp_path)
    # conftest replaces any *.log file with a mock, so use another suffix.
    monkeypatch.setattr(
        watcher_commands, "_log_path", lambda name: tmp_path / f"{name}.out"
    )
    return tmp_path


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


@pytest.mark.usefixtures("with_tmux_launcher")
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


@pytest.mark.usefixtures("with_tmux_launcher")
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


class TestLocalFallback:
    """Without tmux_launcher, watchers run as local background processes"""

    @patch("sc_linac_physics.cli.watcher_commands.os.system")
    @patch("sc_linac_physics.cli.watcher_commands.subprocess.Popen")
    @patch("sys.argv", ["watcher_commands", "restart", "SC_CAV_QNCH_RESET"])
    def test_restart_starts_module_and_writes_pid(
        self, mock_popen, mock_system, without_tmux_launcher
    ):
        mock_popen.return_value.pid = 4321
        watcher_commands.main()

        mock_system.assert_not_called()
        argv = mock_popen.call_args[0][0]
        module = watcher_commands.WATCHER_CONFIGS[
            "SC_CAV_QNCH_RESET"
        ].__module__
        assert argv[1:] == ["-m", module]
        assert mock_popen.call_args.kwargs["start_new_session"] is True
        pid_file = without_tmux_launcher / "SC_CAV_QNCH_RESET.pid"
        assert pid_file.read_text() == "4321"
        assert (without_tmux_launcher / "SC_CAV_QNCH_RESET.out").exists()

    @patch("sc_linac_physics.cli.watcher_commands.os.killpg")
    @patch("sc_linac_physics.cli.watcher_commands.os.kill")
    @patch("sys.argv", ["watcher_commands", "stop", "SC_CAV_QNCH_RESET"])
    def test_stop_kills_running_watcher(
        self, mock_kill, mock_killpg, without_tmux_launcher
    ):
        pid_file = without_tmux_launcher / "SC_CAV_QNCH_RESET.pid"
        pid_file.write_text("4321")
        watcher_commands.main()

        mock_killpg.assert_called_once_with(
            4321, watcher_commands.signal.SIGTERM
        )
        assert not pid_file.exists()

    @patch("sc_linac_physics.cli.watcher_commands.os.killpg")
    @patch("sys.argv", ["watcher_commands", "stop", "SC_CAV_QNCH_RESET"])
    def test_stop_without_pid_file_is_a_no_op(
        self, mock_killpg, without_tmux_launcher, capsys
    ):
        watcher_commands.main()
        mock_killpg.assert_not_called()
        assert "not running" in capsys.readouterr().out

    @patch(
        "sc_linac_physics.cli.watcher_commands.os.kill",
        side_effect=ProcessLookupError,
    )
    @patch("sc_linac_physics.cli.watcher_commands.os.killpg")
    @patch("sys.argv", ["watcher_commands", "stop", "SC_CAV_QNCH_RESET"])
    def test_stop_with_stale_pid_file(
        self, mock_killpg, mock_kill, without_tmux_launcher
    ):
        pid_file = without_tmux_launcher / "SC_CAV_QNCH_RESET.pid"
        pid_file.write_text("4321")
        watcher_commands.main()

        mock_killpg.assert_not_called()
        assert not pid_file.exists()

    @patch("sc_linac_physics.cli.watcher_commands.os.execvp")
    @patch("sc_linac_physics.cli.watcher_commands.sys.stdout")
    @patch("sys.argv", ["watcher_commands", "show", "SC_CAV_QNCH_RESET"])
    def test_show_tails_log_in_a_terminal(
        self, mock_stdout, mock_execvp, without_tmux_launcher
    ):
        mock_stdout.isatty.return_value = True
        log = without_tmux_launcher / "SC_CAV_QNCH_RESET.out"
        log.write_text("hello\n")
        watcher_commands.main()

        mock_execvp.assert_called_once()
        assert mock_execvp.call_args[0][1][-1] == str(log)

    @patch("sc_linac_physics.cli.watcher_commands.subprocess.Popen")
    @patch("sc_linac_physics.cli.watcher_commands.is_macos", return_value=True)
    @patch("sc_linac_physics.cli.watcher_commands.sys.stdout")
    @patch("sys.argv", ["watcher_commands", "show", "SC_CAV_QNCH_RESET"])
    def test_show_opens_console_without_a_terminal(
        self, mock_stdout, mock_is_macos, mock_popen, without_tmux_launcher
    ):
        mock_stdout.isatty.return_value = False
        log = without_tmux_launcher / "SC_CAV_QNCH_RESET.out"
        log.write_text("hello\n")
        watcher_commands.main()

        mock_popen.assert_called_once_with(["open", "-a", "Console", str(log)])

    @patch("sc_linac_physics.cli.watcher_commands.os.execvp")
    @patch("sys.argv", ["watcher_commands", "show", "SC_CAV_QNCH_RESET"])
    def test_show_without_log(self, mock_execvp, without_tmux_launcher, capsys):
        watcher_commands.main()
        mock_execvp.assert_not_called()
        assert "No log" in capsys.readouterr().out
