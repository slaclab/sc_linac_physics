import logging
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal

from sc_linac_physics.applications.microphonics.utils.file_parser import (
    load_and_process_file,
    FileParserError,
)

logger = logging.getLogger(__name__)


class DataLoader(QObject):
    """Handles loading and processing of Microphonics GUI data files"""

    # Signals for progress and error reporting
    dataLoaded = pyqtSignal(dict)  # Emits processed data for a cavity
    loadError = pyqtSignal(str)  # Emits error messages
    loadProgress = pyqtSignal(int)  # Emits progress percentage

    def __init__(self):
        """
        Initialize DataLoader.
        """
        super().__init__()

    def load_file(self, file_path: Path):
        try:
            self.loadProgress.emit(10)
            final_data_dict = load_and_process_file(file_path)
            self.loadProgress.emit(90)
            logger.debug(f"Emitting dataLoaded signal for file {file_path.name}...")
            self.dataLoaded.emit(final_data_dict)
            self.loadProgress.emit(100)
        except FileParserError as e:
            error_msg = f"Error processing file {file_path.name}: {str(e)}"
            logger.error(error_msg)
            self.loadError.emit(error_msg)
            self.loadProgress.emit(0)
        except Exception as e:
            # Catch other unexpected errors
            error_msg = f"Unexpected error loading file {file_path.name}: {str(e)}"
            logger.critical(error_msg, exc_info=True)
            self.loadError.emit(error_msg)
            self.loadProgress.emit(0)
