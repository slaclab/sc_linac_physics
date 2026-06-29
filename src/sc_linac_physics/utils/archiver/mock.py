"""Mock archiver data generator."""

from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta
<<<<<<< HEAD

from .models import ArchiverValue, ArchiveDataHandler

_LIVE_QUERY_TIMEOUT_S = 0.5

=======
from typing import Dict, List, Union

from .models import ArchiverValue, ArchiveDataHandler

>>>>>>> d4170b1 (Add archiver source and test files)

def _stable_seed(pv_name: str, start_time: datetime, end_time: datetime) -> int:
    key = f"{pv_name}|{start_time.isoformat()}|{end_time.isoformat()}".encode("utf-8")
    return int(hashlib.sha256(key).hexdigest()[:8], 16)

<<<<<<< HEAD
def _live_kind(pv_name: str) -> tuple[str, tuple] | None:
    """
    Ask the running IOC for a PV's native type.
    Returns (kind, enum_strings) or None if the IOC is unreachable.
    kind is one of "FLOAT", "INT", "ENUM", "STRING".
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
=======
>>>>>>> d4170b1 (Add archiver source and test files)

class MockArchiveDataHandler:
    """Generates mock time-series for one PV."""

    def __init__(
        self,
        pv_name: str,
        start_time: datetime,
        end_time: datetime,
        sample_rate_hz: float = 1.0,
    ):
        self.pv_name = pv_name
        self.start_time = start_time
        self.end_time = end_time
        self.sample_rate_hz = sample_rate_hz

        self.rng = random.Random(_stable_seed(pv_name, start_time, end_time))
<<<<<<< HEAD
        self.kind, self.enum_strings = self._resolve_kind()
=======
>>>>>>> d4170b1 (Add archiver source and test files)

        self.timestamps = self._generate_timestamps()
        self.values = self._generate_values()
        self.severities = self._generate_severities()
        self.statuses = self._generate_statuses()

<<<<<<< HEAD
    def _resolve_kind(self) -> tuple[str, tuple]:
        """Tier 1: live IOC query. Tier 2: name heuristic. Tier 3: FLOAT default."""
        live = _live_kind(self.pv_name)
        if live is not None:
            return live

        # Fallback when IOC is unreachable (names are unreliable — last resort)
        pv = self.pv_name.upper()
        if "CUDSTATUS" in pv:
            return "STRING", ()
        if any(t in pv for t in ("_LTCH", "STATUS", "STATE", "READY", "ALRM", "BYP")):
            return "ENUM", ()
        if any(t in pv for t in ("COUNT", "CNT", "NUM", "RATE", "NBR", "INDEX")):
            return "INT", ()
        return "FLOAT", ()

    def _generate_timestamps(self) -> list[datetime]:
        timestamps: list[datetime] = []
=======
    def _generate_timestamps(self) -> List[datetime]:
        timestamps: List[datetime] = []
>>>>>>> d4170b1 (Add archiver source and test files)
        current = self.start_time
        interval = timedelta(seconds=1.0 / self.sample_rate_hz)

        while current <= self.end_time:
            timestamps.append(current)
            current += interval

        return timestamps

<<<<<<< HEAD
    def _generate_values(self) -> list[union[float, int, str]]:
        # CUDSTATUS keeps its historical string behavior.
        if "CUDSTATUS" in self.pv_name:
            return self._generate_fault_codes()

        if self.kind == "ENUM":
            return self._generate_enum_values()
        if self.kind == "INT":
            return self._generate_int_values()
        if self.kind == "STRING":
            return self._generate_fault_codes()

        # FLOAT: pick a realistic range from the known analog PVs, else generic.
        base, noise = self._analog_range()
        return self._generate_numeric_values(base_value=base, noise_range=noise)
    
    def _analog_range(self) -> tuple[float, float]:
        pv = self.pv_name
        if any(k in pv for k in ("ADES", "AACT", "GDES", "GACT", "AACTMEAN")):
            return 16.5, 0.1
        if any(k in pv for k in ("PDES", "PACT")):
            return 0.0, 0.5
        if any(k in pv for k in ("DF", "DETUNE")):
            return 0.0, 10.0
        if "SEL_ASET" in pv:
            return 0.0, 0.5
        return 0.0, 0.1  # generic float default

    def _generate_int_values(self) -> list[int]:
        return [self.rng.randint(0, 5) for _ in self.timestamps]

    def _generate_enum_values(self) -> list[int]:
        # MODE showed enum_strings can be empty -> fall back to small cardinality.
        n_states = len(self.enum_strings) if self.enum_strings else 3
        values: list[int] = []
        for _ in self.timestamps:
            if self.rng.random() < 0.9:
                values.append(0)   # nominal state
            else:
                values.append(self.rng.randint(1, max(1, n_states - 1)))
        return values
    
    def _generate_numeric_values(self, base_value: float, noise_range: float) -> list[float]:
        values: list[float] = []
=======
    def _generate_values(self) -> List[Union[float, int, str]]:
        pv = self.pv_name

        # Gradients
        if any(k in pv for k in ("ADES", "AACT", "GDES", "GACT", "AACTMEAN")):
            return self._generate_numeric_values(base_value=16.5, noise_range=0.1)

        # Phases
        if any(k in pv for k in ("PDES", "PACT")):
            return self._generate_numeric_values(base_value=0.0, noise_range=0.5)

        # Detune/df
        if any(k in pv for k in ("DF", "DETUNE")):
            return self._generate_numeric_values(base_value=0.0, noise_range=10.0)

        # Drive level-ish
        if "SEL_ASET" in pv:
            return self._generate_numeric_values(base_value=0.0, noise_range=0.5)

        # Status/fault PVs
        if "CUDSTATUS" in pv:
            # Keep as strings for now; adjust to ints if downstream expects numeric
            return self._generate_fault_codes()

        # Default
        return self._generate_numeric_values(base_value=0.0, noise_range=0.1)

    def _generate_numeric_values(self, base_value: float, noise_range: float) -> List[float]:
        values: List[float] = []
>>>>>>> d4170b1 (Add archiver source and test files)
        for i in range(len(self.timestamps)):
            noise = self.rng.uniform(-noise_range, noise_range)
            drift = i * 0.00001

            if self.rng.random() < 0.02:
                fault_spike = self.rng.uniform(-5 * noise_range, 5 * noise_range)
                v = base_value + noise + drift + fault_spike
            else:
                v = base_value + noise + drift

            values.append(v)
        return values

<<<<<<< HEAD
    def _generate_fault_codes(self) -> list[str]:
        fault_codes = ["TLC", "Quench", "FPGA Fault", "No Fault"]
        values: list[str] = []
=======
    def _generate_fault_codes(self) -> List[str]:
        fault_codes = ["TLC", "Quench", "FPGA Fault", "No Fault"]
        values: List[str] = []
>>>>>>> d4170b1 (Add archiver source and test files)
        for _ in self.timestamps:
            if self.rng.random() < 0.9:
                values.append("TLC")
            else:
                values.append(self.rng.choice(fault_codes))
        return values

<<<<<<< HEAD
    def _generate_severities(self) -> list[int]:
        severities: list[int] = []
=======
    def _generate_severities(self) -> List[int]:
        severities: List[int] = []
>>>>>>> d4170b1 (Add archiver source and test files)
        for _ in self.timestamps:
            if self.rng.random() < 0.9:
                severities.append(0)
            else:
                severities.append(self.rng.choice([1, 2]))
        return severities

<<<<<<< HEAD
    def _generate_statuses(self) -> list[int]:
        statuses: list[int] = []
=======
    def _generate_statuses(self) -> List[int]:
        statuses: List[int] = []
>>>>>>> d4170b1 (Add archiver source and test files)
        for _ in self.timestamps:
            if self.rng.random() < 0.95:
                statuses.append(0)
            else:
                statuses.append(1)
        return statuses


def mock_get_values_over_time_range(
<<<<<<< HEAD
    pv_list: list[str],
    start_time: datetime,
    end_time: datetime,
) -> dict[str, ArchiveDataHandler]:
=======
    pv_list: List[str],
    start_time: datetime,
    end_time: datetime,
) -> Dict[str, ArchiveDataHandler]:
>>>>>>> d4170b1 (Add archiver source and test files)
    """Generate mock data for multiple PVs."""
    if not pv_list:
        return {}

<<<<<<< HEAD
    result: dict[str, ArchiveDataHandler] = {}
=======
    result: Dict[str, ArchiveDataHandler] = {}
>>>>>>> d4170b1 (Add archiver source and test files)
    for pv_name in pv_list:
        mock = MockArchiveDataHandler(pv_name, start_time, end_time)

        archiver_values = [
            ArchiverValue(value=val, timestamp=ts, severity=sev, status=stat)
            for val, ts, sev, stat in zip(
                mock.values,
                mock.timestamps,
                mock.severities,
                mock.statuses,
            )
        ]
        result[pv_name] = ArchiveDataHandler.from_archiver_values(pv_name, archiver_values)

    return result