from dataclasses import dataclass

EPICS_NO_ALARM_VAL = 0
EPICS_MINOR_VAL = 1
EPICS_MAJOR_VAL = 2
EPICS_INVALID_VAL = 3


@dataclass
class PVConfig:
    """Configuration for PV operations"""

    connection_timeout: float = 5.0
    get_timeout: float = 2.0
    put_timeout: float = 30.0
    max_retries: int = 3
    retry_delay: float = 0.5
