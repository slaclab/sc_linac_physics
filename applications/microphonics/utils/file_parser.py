# Constants
import io
import logging
import traceback
from pathlib import Path
from typing import Tuple, List, Optional, Dict, Any

import numpy as np

from applications.microphonics.utils.pv_utils import extract_cavity_channel_from_pv

HEADER_MARKER = '# ACCL:'
COMMENT_MARKER = '#'
DECIMATION_HEADER_KEY = '# wave_samp_per'


# Exception
class FileParserError(Exception):
    """Custom exception for file parsing errors."""
    pass


# Helper Functions
def _read_and_parse_header(file_path: Path) -> Tuple[List[str], List[str], int, Optional[int]]:
    """Reads the file, separates header and data lines, and parses decimation

    Args:
        file_path: Path to the data file

    Returns:
        Tuple with:
        - header_lines
        - data_content
        - decimation
        - marker_index

    Raises:
        FileParserError: If file cant be read or header marker is not there
    """
    # Initialize empty lists to store our header and data sections
    header_lines: List[str] = []
    data_content_lines: List[str] = []
    # Storing our position of our marker line for later reference
    marker_index: Optional[int] = None
    # Default decimation (I will move this)
    decimation: int = 2

    try:
        # Open file and read all lines at once and using error handling for encoding problems
        with file_path.open('r', encoding='utf-8', errors='ignore') as f:
            all_lines = f.readlines()
        # Loop through each line to separate header from data content and get important values
        for i, line in enumerate(all_lines):
            stripped_line = line.strip()
            # Checking if this is our special marker line (# ACCL:) for channels
            if stripped_line.startswith(HEADER_MARKER):
                marker_index = i
            # Looking for decimation setting (wave_samp_per) in header
            elif stripped_line.startswith(DECIMATION_HEADER_KEY):
                try:
                    # Parse out value after colon
                    value_str = stripped_line.split(':')[1].strip()
                    # Convert to int
                    decimation = int(value_str, 0)
                    logging.debug(f"Parsed decimation '{decimation}' from header")
                except (IndexError, ValueError, TypeError) as e:
                    # Log warning but keep going with default if we cant parse it
                    logging.warning(
                        f"Could not parse decimation from line: '{stripped_line}'. Using default {decimation}. Error: {e}")
            # Separating header lines (before marker) from data content (after marker)
            if marker_index is None:
                # Still in header section before channel marker
                header_lines.append(line)
            elif i == marker_index:
                # This is marker line itself, add to header
                header_lines.append(line)
            # Add non comment data lines that come after marker
            if marker_index is not None and i > marker_index:
                if stripped_line and not stripped_line.startswith(COMMENT_MARKER):
                    data_content_lines.append(line)
        # We need the marker line so fail if we do not find it
        if marker_index is None:
            raise FileParserError(f"Essential channel header line ('{HEADER_MARKER}') not found in {file_path.name}")
        # Return separated header lines, data content, decimation value, and marker index
        return header_lines, data_content_lines, decimation, marker_index
    except Exception as e:
        # Log full traceback for debugging but raise cleaner error for user
        logging.error(f"Unexpected error reading or parsing header for {file_path.name}: {e}\n{traceback.format_exc()}")
        raise FileParserError(f"Error reading file {file_path.name}: {e}")


def _parse_channel_pvs(header_lines: List[str], marker_index: int) -> List[str]:
    """Parses PV channel names from header marker line

    Args:
        header_lines: List of header lines
        marker_index: Index where the HEADER_MAKER was found

    Returns:
        List of parsed PV names

    Raises:
        FileParserError: If the marker line cant be parsed
    """
    if marker_index >= len(header_lines):
        raise FileParserError("Internal error: Marker index out of bounds for header lines")

    channel_line = header_lines[marker_index].strip()

    if not channel_line.startswith(HEADER_MARKER):
        logging.warning(f"Line at marker index {marker_index} doesn't start with {HEADER_MARKER}: '{channel_line}'")

    try:
        parsed_channels = channel_line.strip('# \n').split()

        if not parsed_channels:
            raise FileParserError(f"Found '{HEADER_MARKER}' line but no channels listed after it: '{channel_line}'")

        stripped_result_for_log = channel_line.strip('# \n')
        logging.debug(f"Original channel line: '{channel_line}'")
        logging.debug(f"Result of strip('# \\n'): '{stripped_result_for_log}'")
        logging.debug(f"Parsed {len(parsed_channels)} channel PVs = {parsed_channels}")

        return parsed_channels
    except Exception as e:
        logging.error(f"Failed to split/parse the channel marker line: {channel_line} - {e}")
        raise FileParserError(f"Failed to parse channel PVs from header line: {channel_line}")


def _parse_numerical_data(data_content_lines: List[str], num_expected_columns: int, file_path: Path) -> np.ndarray:
    """Parses numerical data from data lines using numpy"""
    if not data_content_lines:
        print(f"Warning (FileParser): No numerical data lines found.")
        return np.empty((0, num_expected_columns), dtype=float)

    data_io = io.StringIO("".join(data_content_lines))
    try:
        data_array = np.loadtxt(data_io, comments='#', ndmin=2, dtype=float)
        if data_array.size == 0 and len(data_content_lines) > 0:
            raise FileParserError("np.loadtxt failed to parse data content.")
        return data_array
    except ValueError as e:
        raise FileParserError(f"Could not parse numerical data: {e}")


def _structure_parsed_data(channel_pvs: List[str], data_array: np.ndarray, file_path: Path, decimation: int = 1) -> \
        Dict[str, Any]:
    """Structures the parsed PVs and data array into the final dictionary"""
    output_data: Dict[str, Any] = {
        'cavities': {},
        'cavity_list': [],
        'decimation': decimation,
        'filepath': str(file_path),
        'source': 'file'
    }

    cavity_numbers_found = set()
    expected_cols = len(channel_pvs)
    actual_cols = data_array.shape[1] if data_array.ndim == 2 else 0

    if data_array.size > 0 and actual_cols != expected_cols:
        print(
            f"Warning (FileParser): Column mismatch in {file_path.name}! Header={expected_cols}, Data={actual_cols}. Assigning empty data.")
        data_array = np.empty((0, expected_cols), dtype=float)
        actual_cols = expected_cols

    for idx, pv_name in enumerate(channel_pvs):
        logging.debug(f"Structuring data for index {idx}, pv_name: '{pv_name}'")
        parsed_info = extract_cavity_channel_from_pv(pv_name)
        if parsed_info:
            cav_num, channel_type = parsed_info
            cavity_numbers_found.add(cav_num)

            if cav_num not in output_data['cavities']:
                output_data['cavities'][cav_num] = {}

            if data_array.ndim == 2 and idx < actual_cols and data_array.shape[0] > 0:
                column_data = data_array[:, idx]
                output_data['cavities'][cav_num][channel_type] = column_data
            else:
                output_data['cavities'][cav_num][channel_type] = np.array([], dtype=float)
        else:
            print(f"Warning (FileParser): Skipping data column {idx} due to PV parsing failure: {pv_name}")

    output_data['cavity_list'] = sorted(list(cavity_numbers_found))
    return output_data


def load_and_process_file(file_path: Path) -> Dict[str, Any]:
    """Main function to orchestrate the file loading and processing."""
    print(f"DEBUG (FileParser): Processing file {file_path.name}")
    try:
        header_lines, data_content_lines, decimation, marker_index = _read_and_parse_header(file_path)
        channel_pvs = _parse_channel_pvs(header_lines, marker_index)
        data_array = _parse_numerical_data(data_content_lines, len(channel_pvs), file_path)
        structured_data = _structure_parsed_data(channel_pvs, data_array, file_path, decimation)
        print(
            f"DEBUG (FileParser): Successfully processed {file_path.name}. Cavities: {structured_data['cavity_list']}")
        return structured_data
    except FileParserError as e:
        print(f"ERROR (FileParser): {e}")
        raise
