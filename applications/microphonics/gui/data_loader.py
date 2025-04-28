import io
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from applications.microphonics.gui.statistics_calculator import StatisticsCalculator


@dataclass
class LoadedData:
    """Container for loaded data and metadata"""
    channels: Dict[str, np.ndarray]
    cavity_numbers: List[int]
    timestamp: str
    channel_names: List[str]
    file_path: Path


class DataProcessor:
    """Handles data processing and cavity info extraction"""

    @staticmethod
    def extract_cavity_channel_from_pv(pv_string: str) -> Optional[Tuple[int, str]]:
        """
        Extracts cavity number and channel type from PV string.
        """
        try:
            parts = pv_string.split(':')
            # Check structure: ACCL:LXB:CMCAV0:PZT:TYPE:WF
            if len(parts) >= 6 and parts[3] == 'PZT' and parts[5] == 'WF':
                segment3 = parts[2]
                if len(segment3) == 4 and segment3.endswith('0'):
                    # Cavity number is the 3rd character (index 2)
                    cav_num = int(segment3[2])
                    # Channel type is the 5th segment (index 4)
                    channel_type = parts[4]
                    return cav_num, channel_type
                else:
                    # Log warning if format of segment 3 is unexpected
                    print(
                        f"WARN DataProcessor: PV segment '{segment3}' in '{pv_string}' doesn't match <CM><CAV>0 format.")
                    return None
            else:
                # Log warning if overall structure is wrong
                return None
        except (IndexError, ValueError) as e:
            # Log warning if indexing or int conversion fails
            print(f"WARN DataProcessor: Could not parse cavity/channel from PV '{pv_string}': {e}")
            return None


class DataLoader(QObject):
    """Handles loading and processing of Microphonics GUI data files"""

    # Signals for progress and error reporting
    dataLoaded = pyqtSignal(dict)  # Emits processed data for a cavity
    loadError = pyqtSignal(str)  # Emits error messages
    loadProgress = pyqtSignal(int)  # Emits progress percentage

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize DataLoader w/ optional base path for data files.

        Args:
            base_path: Optional path to the data directory. If None, uses the default path.
        """
        super().__init__()
        self.base_path = base_path or Path("/u1/lcls/physics/rf_lcls2/microphonics/")
        self.processor = DataProcessor()
        self.stats_calculator = StatisticsCalculator()

    def load_file(self, file_path: Path):
        if not file_path.exists():
            error_msg = f"Could not find file: {file_path}"
            self.loadError.emit(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            channel_pvs: List[str] = []
            accl_line_index: int = -1

            for i, line in enumerate(lines):
                stripped_line = line.strip()
                if stripped_line.startswith('# ACCL:'):
                    channel_pvs = [pv for pv in stripped_line.strip('# \n').split() if pv]
                    accl_line_index = i
                    break

            if not channel_pvs:
                raise ValueError(f"Essential channel header line ('# ACCL:') not found in {file_path}")
            if accl_line_index == -1:
                raise ValueError(f"Could not locate the '# ACCL:' header line index in {file_path}")

            if accl_line_index + 1 >= len(lines):
                print(f"Warning: No lines found after '# ACCL:' header in {file_path}. Proceeding with empty data.")
                data_array = np.empty((0, len(channel_pvs)), dtype=float)
            else:
                data_io = io.StringIO("".join(lines[accl_line_index + 1:]))
                try:
                    data_array = np.loadtxt(data_io, comments='#', ndmin=2, dtype=float)
                except ValueError as e:
                    raise ValueError(f"Could not parse numerical data following header in {file_path}: {e}")

            if data_array.size == 0 and any(
                    line.strip() and not line.strip().startswith('#') for line in lines[accl_line_index + 1:]):
                print(
                    f"Warning: np.loadtxt resulted in empty array for {file_path} despite non-comment lines existing after header.")
                data_array = np.empty((0, len(channel_pvs)), dtype=float)

            expected_cols = len(channel_pvs)
            actual_cols = data_array.shape[1] if data_array.ndim == 2 else 0

            if data_array.size > 0 and actual_cols != expected_cols:
                error_msg = f"Column mismatch in {file_path}! Header indicates {expected_cols} channels, but data has {actual_cols} columns."
                print(f"ERROR: {error_msg}")
                data_array = np.empty((0, expected_cols), dtype=float)

            all_cavities_data: Dict[int, Dict[str, np.ndarray]] = {}
            found_cavity_numbers = set()

            if not hasattr(self, 'processor') or not hasattr(self.processor, 'extract_cavity_channel_from_pv'):
                raise AttributeError(
                    "DataLoader requires an initialized 'processor' attribute with 'extract_cavity_channel_from_pv' method.")

            for col_idx, pv_name in enumerate(channel_pvs):
                parsed_info = self.processor.extract_cavity_channel_from_pv(pv_name)
                if parsed_info:
                    cav_num, channel_type = parsed_info
                    found_cavity_numbers.add(cav_num)

                    if cav_num not in all_cavities_data:
                        all_cavities_data[cav_num] = {}

                    if data_array.ndim == 2 and col_idx < actual_cols and data_array.shape[0] > 0:
                        column_data = data_array[:, col_idx]
                        all_cavities_data[cav_num][channel_type] = column_data
                    else:
                        all_cavities_data[cav_num][channel_type] = np.array([], dtype=float)
                else:
                    print(
                        f"WARN DataLoader: Could not parse cavity/channel from PV '{pv_name}' in file {file_path}. Skipping column {col_idx}.")

            final_data_dict: Dict[str, Any] = {
                'cavity_list': sorted(list(found_cavity_numbers)),
                'cavities': all_cavities_data,
                'decimation': 1,
                'filepath': str(file_path),
                'source': 'file'
            }

            print(
                f"DEBUG DataLoader: Emitting dataLoaded signal for file {file_path.name} with cavities: {final_data_dict['cavity_list']}")
            self.dataLoaded.emit(final_data_dict)
            self.loadProgress.emit(100)

        except FileNotFoundError:
            pass
        except (ValueError, AttributeError) as ve:
            error_msg = f"Error processing file {file_path.name}: {str(ve)}"
            print(f"ERROR: {error_msg}")
            traceback.print_exc()
            self.loadError.emit(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error loading file {file_path.name}: {str(e)}"
            print(f"CRITICAL ERROR: {error_msg}")
            traceback.print_exc()
            self.loadError.emit(error_msg)

    def validate_file_format(self, file_path: Path) -> bool:
        """
        Check if file is in the correct format.

        Args:
            file_path: Path to the file to validate

        Returns:
            bool: True if the file appears to be in the correct format
        """
        try:
            with open(file_path, 'r') as f:
                # Check first few lines for expected format
                for _ in range(10):
                    line = f.readline()
                    if not line:
                        break
                    if line.startswith('# ACCL:'):
                        return True
            return False
        except Exception:
            return False

    def get_available_channels(self, file_path: Path) -> List[str]:
        """
        Get list of available channels in a data file.

        Args:
            file_path: Path to the data file

        Returns:
            List of channel names found in the file
        """
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    if line.startswith('# ACCL:'):
                        return line.strip('# \n').split()
            return []
        except Exception as e:
            self.loadError.emit(f"Error reading channels: {str(e)}")
            return []
