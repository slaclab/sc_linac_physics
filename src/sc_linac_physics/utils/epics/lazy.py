"""LazyPV: a PV attribute created on first access, then cached."""

from typing import Any, Optional

from sc_linac_physics.utils.epics.core import PV


class LazyPV:
    """Class attribute that creates a PV the first time it is read.

    Replaces the hand-written pattern::

        @property
        def status_pv_obj(self) -> PV:
            if not self._status_pv_obj:
                self._status_pv_obj = PV(self.status_pv)
            return self._status_pv_obj

    with::

        status_pv_obj = LazyPV("status_pv")

    The PV name is read from the instance attribute named by name_attr
    (here self.status_pv) on first access. The PV is cached in
    self._status_pv_obj, the same attribute the hand-written property used,
    so tests that set ``obj._status_pv_obj = make_mock_pv()`` and code that
    reads it directly keep working. The owner class gets a class-level
    ``_status_pv_obj = None`` default, so the ``self._x_pv_obj = None``
    lines in ``__init__`` aren't needed.

    Like a property with no setter, assigning to ``obj.status_pv_obj``
    raises AttributeError.
    """

    def __init__(self, name_attr: str, **pv_kwargs: Any):
        """
        Args:
            name_attr: Instance attribute that holds the PV name.
            **pv_kwargs: Passed to PV(), e.g. connection_timeout.
        """
        self._name_attr = name_attr
        self._pv_kwargs = pv_kwargs
        self._public_name: Optional[str] = None
        self._cache_attr: Optional[str] = None

    def __set_name__(self, owner: type, name: str):
        self._public_name = name
        self._cache_attr = f"_{name}"
        if self._cache_attr not in vars(owner):
            setattr(owner, self._cache_attr, None)

    def __get__(self, obj: Any, objtype: Optional[type] = None):
        if obj is None:
            return self
        pv = getattr(obj, self._cache_attr)
        # `not pv`, not `pv is None`: same test the hand-written properties
        # used, so behavior is unchanged.
        if not pv:
            pv = PV(getattr(obj, self._name_attr), **self._pv_kwargs)
            setattr(obj, self._cache_attr, pv)
        return pv

    def __set__(self, obj: Any, value: Any):
        raise AttributeError(
            f"{self._public_name} is read-only; set {self._cache_attr} "
            f"to replace the PV"
        )
