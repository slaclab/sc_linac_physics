from typing import Dict

import numpy as np

from sc_linac_physics.applications.q0 import q0_utils


class RFRun(q0_utils.DataRun):
    def __init__(self, amplitudes: Dict[int, float]):
        super().__init__()
        self.amplitudes = amplitudes
        self.pressure_buffer = []
        self._avg_pressure = None

    @property
    def avg_pressure(self):
        if not self._avg_pressure:
            self._avg_pressure = np.mean(self.pressure_buffer)
        return self._avg_pressure

    @avg_pressure.setter
    def avg_pressure(self, value: float):
        self._avg_pressure = value
