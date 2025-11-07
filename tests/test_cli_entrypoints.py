"""Test that all entry points are properly registered."""

from importlib.metadata import entry_points


def test_all_entry_points_registered(all_script_names):
    """Verify all console scripts are registered."""
    eps = entry_points()

    # Python 3.10+
    try:
        console_scripts = eps.select(group="console_scripts")
        registered_names = {ep.name for ep in console_scripts}
    except AttributeError:
        # Python 3.9
        console_scripts = eps.get("console_scripts", [])
        registered_names = {ep.name for ep in console_scripts}

    for script_name in all_script_names:
        assert (
            script_name in registered_names
        ), f"Entry point '{script_name}' not registered"


def test_entry_point_targets_exist(all_script_names):
    """Verify all entry point targets can be imported."""
    eps = entry_points()

    try:
        console_scripts = eps.select(group="console_scripts")
    except AttributeError:
        console_scripts = eps.get("console_scripts", [])

    for ep in console_scripts:
        if ep.name in all_script_names:
            # This will raise ImportError if target doesn't exist
            func = ep.load()
            assert callable(func), f"{ep.name} -> {ep.value} is not callable"
