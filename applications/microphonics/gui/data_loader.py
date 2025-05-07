import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from applications.microphonics.gui.statistics_calculator import StatisticsCalculator
from applications.microphonics.utils.file_parser import load_and_process_file, FileParserError


@dataclass
class LoadedData:
    """Container for loaded data and metadata"""
    channels: Dict[str, np.ndarray]
    cavity_numbers: List[int]
    timestamp: str
    channel_names: List[str]
    file_path: Path


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
        self.stats_calculator = StatisticsCalculator()

    def load_file(self, file_path: Path):
        try:
            self.loadProgress.emit(10)  # Indicate start
            final_data_dict = load_and_process_file(file_path)
            self.loadProgress.emit(90)  # Indicate processing done
            print(f"DEBUG DataLoader: Emitting dataLoaded signal for file {file_path.name}...")
            self.dataLoaded.emit(final_data_dict)
            self.loadProgress.emit(100)
        except FileParserError as e:
            error_msg = f"Error processing file {file_path.name}: {str(e)}"
            print(f"ERROR: {error_msg}")
            self.loadError.emit(error_msg)
            self.loadProgress.emit(0)  # Reset progress on error
        except Exception as e:
            # Catch other unexpected errors
            error_msg = f"Unexpected error loading file {file_path.name}: {str(e)}"
            print(f"CRITICAL ERROR: {error_msg}")
            traceback.print_exc()
            self.loadError.emit(error_msg)
            self.loadProgress.emit(0)

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
