import time
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from lcls_tools.common.controls.pyepics.utils import PV

from utils.sc_linac import linac_utils

if TYPE_CHECKING:
    from cavity import Cavity
    

class RFStation(linac_utils.SCLinacObject):