"""PV types from a running sc-sim IOC, for the mock archiver.

Asks Channel Access for each PV's native type. If the first lookup gets no
answer (no IOC running), later lookups are skipped for the rest of the
process: field emission alone reads 28 PVs, which would otherwise cost
LOOKUP_TIMEOUT_S each. Ported from #280 (Sandy Paez Olivarez).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

LOOKUP_TIMEOUT_S = 0.5

_ioc_unreachable = False


@lru_cache(maxsize=4096)
def ioc_kind(pv: str) -> Optional[str]:
    """FLOAT, INT or ENUM from the IOC, or None if it can't be asked."""
    global _ioc_unreachable
    if _ioc_unreachable:
        return None
    try:
        from caproto.sync.client import read

        response = read(pv, data_type="control", timeout=LOOKUP_TIMEOUT_S)
    except Exception:
        _ioc_unreachable = True
        return None

    name = getattr(response.data_type, "name", str(response.data_type))
    name = name.upper()
    if "ENUM" in name:
        return "ENUM"
    if any(t in name for t in ("LONG", "INT", "SHORT", "CHAR")):
        return "INT"
    if "STRING" in name:
        return None  # no string generator; fall back to the name guess
    return "FLOAT"


def reset() -> None:
    """Forget cached kinds and try the IOC again, e.g. after starting sc-sim."""
    global _ioc_unreachable
    _ioc_unreachable = False
    ioc_kind.cache_clear()
