import pytest

from sc_linac_physics.applications.auto_setup.frontend import gui_cavity as _gc


class _SyncExecutor:
    """Executes submitted callables synchronously so tests can assert results."""

    def submit(self, fn, *args, **kwargs):
        fn(*args, **kwargs)


@pytest.fixture(autouse=True)
def sync_cavity_executor(monkeypatch):
    monkeypatch.setattr(_gc, "_executor", _SyncExecutor())
