"""PV type resolution.

Priority:
    1. Live IOC query via caproto (cached), when sc-sim is running.
    2. Name heuristics, when the IOC is unreachable.

CUDSTATUS / CUDSEVR are special-cased by the engine and never resolved here.
"""

from __future__ import annotations

from functools import lru_cache

_LIVE_QUERY_TIMEOUT_S = 0.5


@lru_cache(maxsize=4096)
def _live_kind(pv_name: str) -> tuple[str, tuple] | None:
    """Ask the running IOC for a PV's native type.

    Returns (kind, enum_strings) or None if the IOC is unreachable.
    kind is one of "FLOAT", "INT", "ENUM", "STRING".
    Cached so 480 cavities don't each pay the caproto timeout repeatedly.
    """
    try:
        from caproto.sync.client import read

        resp = read(pv_name, data_type="control", timeout=_LIVE_QUERY_TIMEOUT_S)
    except Exception:
        return None

    ct = getattr(resp, "data_type", None)
    if ct is None:
        return None

    name = getattr(ct, "name", str(ct)).upper()
    enum_strings = tuple(
        getattr(getattr(resp, "metadata", None), "enum_strings", ()) or ()
    )
    if "ENUM" in name:
        return "ENUM", enum_strings
    if "LONG" in name or "INT" in name or "CHAR" in name:
        return "INT", ()
    if "DOUBLE" in name or "FLOAT" in name:
        return "FLOAT", ()
    if "STRING" in name:
        return "STRING", ()
    return "FLOAT", ()  # safe default


def heuristic_kind(pv_name: str) -> tuple[str, tuple]:
    """Fallback type guess from the PV name when the IOC is unreachable."""
    pv = pv_name.upper()
    if any(t in pv for t in ("_LTCH", "STATUS", "STATE", "READY", "ALRM", "BYP")):
        return "ENUM", ()
    if any(t in pv for t in ("COUNT", "CNT", "NUM", "RATE", "NBR", "INDEX")):
        return "INT", ()
    return "FLOAT", ()


def resolve_kind(pv_name: str) -> tuple[str, tuple]:
    """Resolve (kind, enum_strings) for a PV. IOC first, heuristics second."""
    pv = pv_name.upper()
    if "CUDSTATUS" in pv or "CUDSEVR" in pv:
        return "STRING", ()

    live = _live_kind(pv_name)
    if live is not None:
        return live
    return heuristic_kind(pv_name)