import traceback
from pathlib import Path

from PyQt5.QtCore import QObject, pyqtSignal

from applications.microphonics.utils.file_parser import (
    load_and_process_file,
    FileParserError,
)


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
            self.loadProgress.emit(10)  # Indicate start
            final_data_dict = load_and_process_file(file_path)
            self.loadProgress.emit(90)  # Indicate processing done
            print(
                f"DEBUG DataLoader: Emitting dataLoaded signal for file {file_path.name}..."
            )
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
