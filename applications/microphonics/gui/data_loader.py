from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

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
    def extract_cavity_number(channel_name: str) -> Optional[int]:
        """Extract cavity number from channel name"""
        try:
            parts = channel_name.split(':')
            # Example channel: ACCL:L1B:0210:PZT:DF:WF
            # parts[2] is "0210" → cavity number is third character ('1')
            cavity_part = parts[2]
            return int(cavity_part[2])
        except (IndexError, ValueError):
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

    def load_file(self, file_path: Path) -> LoadedData:
        """
        Load and process data from a file.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Could not find file: {file_path}")

        try:
            # Read the file
            with open(file_path, 'r') as f:
                lines = f.readlines()

            # Find channel names and data start
            channel_names = []
            timestamp = ""
            data_start = 0

            for i, line in enumerate(lines):
                if line.startswith('# ACCL:'):
                    channel_names = line.strip('# \n').split()
                    if i + 1 < len(lines):
                        timestamp = lines[i + 1].strip('# \n')
                    data_start = i + 2
                    break

            if not channel_names:
                raise ValueError("No channel names found in file")

            # Get numerical data
            data_values = []
            for line in lines[data_start:]:
                if line.strip() and not line.startswith('#'):
                    try:
                        values = [float(x) for x in line.strip().split()]
                        if values:  # Only add non-empty rows
                            data_values.append(values)
                    except ValueError:
                        continue

            # Convert to numpy array and transpose
            data_array = np.array(data_values)

            # Create dict w/ data for each cavity
            channels_data = {}
            for i, channel in enumerate(channel_names):
                cavity_num = self.processor.extract_cavity_number(channel)
                if cavity_num:
                    # Extract data for this cavity (column i)
                    cavity_data = data_array[:, i]
                    channels_data[cavity_num] = {
                        'DF': cavity_data,
                        'DAC': np.zeros_like(cavity_data)  # Placeholder for DAC data
                    }

                    # Emit data for this cavity
                    cavity_data_dict = {
                        'cavity': cavity_num,
                        'channels': {'DF': cavity_data},
                        'statistics': self.stats_calculator.calculate_statistics(cavity_data)
                    }
                    self.dataLoaded.emit(cavity_data_dict)

            self.loadProgress.emit(100)

            return LoadedData(
                channels=channels_data,
                cavity_numbers=sorted(list(channels_data.keys())),
                timestamp=timestamp,
                channel_names=channel_names,
                file_path=file_path
            )

        except Exception as e:
            error_msg = f"Error loading file: {str(e)}"
            self.loadError.emit(error_msg)
            raise

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
