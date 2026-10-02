from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Union


@dataclass(frozen=True)
class ArchiverValue:
    """Single archived data point."""
    value: Union[float, int, str]
    timestamp: datetime
    severity: int = 0
    status: int = 0


@dataclass
class ArchiveDataHandler:
    """Container for time-series archiver data."""
    pv_name: str
    values: List[Union[float, int, str]]
    timestamps: List[datetime]
    severities: List[int]
    statuses: List[int]

    @classmethod
    def from_archiver_values(cls, pv_name: str, archiver_values: List[ArchiverValue]):
        return cls(
            pv_name=pv_name,
            values=[av.value for av in archiver_values],
            timestamps=[av.timestamp for av in archiver_values],
            severities=[av.severity for av in archiver_values],
            statuses=[av.status for av in archiver_values],
        )