# tests/test_integration.py
"""Integration tests using actual console scripts."""
import pytest


@pytest.mark.parametrize(
    "command",
    [
        "sc-linac",
        "sc-setup-all",
        "sc-setup-linac",
        "sc-setup-cm",
        "sc-setup-cav",
        "sc-watcher",
        "sc-sim",
    ],
)
def test_command_help(script_runner, command):
    """Test that commands respond to --help."""
    result = script_runner.run(command, "--help")
    assert result.success or result.returncode in [0, 2]
    assert len(result.stdout) > 0 or len(result.stderr) > 0
