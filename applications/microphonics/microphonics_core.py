from typing import List

from PyQt5.QtCore import QThread


class AcquisitionWorker(QThread):
    """Worker thread for data acquisition using res_data_acq"""

    def __init__(self, linac: str, cm_num: str, rack: str, cavities: List[int],
                 channels: List[str], decimation: int):
        super().__init__()
        self.linac = linac
        self.cm_num = cm_num
        self.rack = rack
        self.cavities = cavities
        self.channels = channels
        self.decimation = decimation
        self.running = False
        pass
