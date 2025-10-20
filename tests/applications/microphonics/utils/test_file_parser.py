import tempfile
from pathlib import Path

import numpy as np
import pytest

from sc_linac_physics.applications.microphonics.utils.file_parser import (
    _read_and_parse_header,
    _parse_channel_pvs,
    _parse_decimation,
    _parse_numerical_data,
    load_and_process_file,
    FileParserError,
)


# Fixtures
@pytest.fixture
def sample_data_file():
    """Creates a temporary file with your example data"""
    content = """# 2024-05-28T11:40:05.113479
# ## Cavity 1
# wave_samp_per : 4
# wave_shift : 2
# chan_keep : 100
# chirp_en : 0
# chirp_acq_per : 0
# ## Cavity 2
# wave_samp_per : 4
# wave_shift : 2
# chan_keep : 100
# chirp_en : 0
# chirp_acq_per : 0
# ## Cavity 3
# wave_samp_per : 4
# wave_shift : 2
# chan_keep : 100
# chirp_en : 0
# chirp_acq_per : 0
# ## Cavity 4
# wave_samp_per : 4
# wave_shift : 2
# chan_keep : 100
# chirp_en : 0
# chirp_acq_per : 0
#

# ACCL:L1B:0210:PZT:DF:WF ACCL:L1B:0220:PZT:DF:WF ACCL:L1B:0230:PZT:DF:WF ACCL:L1B:0240:PZT:DF:WF
# First buffer EPICS timestamp 2024-05-28T11:41:24.662037
#
  1.34000  -0.12400  -0.40800  -0.03200
  0.24400  -0.28000  -0.30000  -0.26400
 -0.36400  -0.26800  -0.22000  -0.40400
 -0.95200   0.32400   0.63600  -0.36000
 -1.41600   0.75600   0.99600  -0.26400
 -1.00000   0.48400   0.46400   0.59200
 -0.13600   0.13200   0.26800   0.73600
 -0.36400  -0.30400  -0.35600   0.38000
  0.43200  -0.56400  -0.84400   0.00000
  0.69200  -0.86800  -0.37200  -0.28000
  1.09200  -0.79600   0.10800  -0.44000
  1.33600  -0.48800   0.61600   0.12000
  1.00800   0.35600   1.39600   0.89600
  0.44000   1.76000   1.46800   1.58000
 -0.22000   1.58800   0.36400   1.01200
 -1.02000   0.86400  -0.14400  -0.38000
 -1.46800  -0.08000  -0.15600  -1.00000
 -1.18400  -1.25200  -0.50400  -0.92800
 -0.70800  -0.97200   0.00000   0.33200
  0.12000  -0.14800  -0.61200   0.79200
"""
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=".txt"
    ) as f:
        f.write(content)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink()


# Test _read_and_parse_header
class TestReadAndParseHeader:
    def test_basic_parsing(self, sample_data_file):
        (
            header_lines,
            data_lines,
            decimation,
            marker_idx,
        ) = _read_and_parse_header(sample_data_file)

        assert marker_idx is not None
        assert decimation == 4  # from wave_samp_per
        assert len(data_lines) == 20  # 20 data rows
        assert len(header_lines) > 0

    def test_marker_index_found(self, sample_data_file):
        (
            header_lines,
            data_lines,
            decimation,
            marker_idx,
        ) = _read_and_parse_header(sample_data_file)

        # Check that the header lines contain the ACCL marker at marker_idx
        assert marker_idx < len(header_lines)
        assert "# ACCL:" in header_lines[marker_idx]

    def test_file_not_found(self):
        """Test that FileParserError is raised for non-existent files"""
        with pytest.raises(FileParserError, match="Error reading file"):
            _read_and_parse_header(Path("nonexistent_file.txt"))

    def test_missing_header_marker(self):
        """Test file without ACCL marker raises error"""
        content = """# Some header
# wave_samp_per : 4
1.0 2.0 3.0
"""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt"
        ) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            with pytest.raises(
                FileParserError, match="Essential channel header line"
            ):
                _read_and_parse_header(temp_path)
        finally:
            temp_path.unlink()


# Test _parse_channel_pvs
class TestParseChannelPVs:
    def test_valid_channel_line(self):
        header_lines = [
            "# Some header\n",
            "# ACCL:L1B:0210:PZT:DF:WF ACCL:L1B:0220:PZT:DF:WF ACCL:L1B:0230:PZT:DF:WF ACCL:L1B:0240:PZT:DF:WF\n",
            "# More lines\n",
        ]
        marker_idx = 1

        pvs = _parse_channel_pvs(header_lines, marker_idx)

        assert len(pvs) == 4
        assert pvs[0] == "ACCL:L1B:0210:PZT:DF:WF"
        assert pvs[1] == "ACCL:L1B:0220:PZT:DF:WF"
        assert pvs[2] == "ACCL:L1B:0230:PZT:DF:WF"
        assert pvs[3] == "ACCL:L1B:0240:PZT:DF:WF"

    def test_empty_channel_line(self):
        header_lines = ["# \n"]
        marker_idx = 0

        # The actual error message is "Failed to parse channel PVs from header line"
        with pytest.raises(
            FileParserError, match="Failed to parse channel PVs"
        ):
            _parse_channel_pvs(header_lines, marker_idx)

    def test_single_channel(self):
        header_lines = ["# ACCL:L1B:0210:PZT:DF:WF\n"]
        marker_idx = 0

        pvs = _parse_channel_pvs(header_lines, marker_idx)
        assert len(pvs) == 1
        assert pvs[0] == "ACCL:L1B:0210:PZT:DF:WF"

    def test_marker_index_out_of_bounds(self):
        header_lines = ["# Some header\n"]
        marker_idx = 10  # Out of bounds

        with pytest.raises(FileParserError, match="Marker index out of bounds"):
            _parse_channel_pvs(header_lines, marker_idx)


# Test _parse_decimation
class TestParseDecimation:
    def test_valid_decimation(self):
        line = "# wave_samp_per : 4"
        decimation = _parse_decimation(line, default=2)
        assert decimation == 4

    def test_hexadecimal_decimation(self):
        line = "# wave_samp_per : 0x10"
        decimation = _parse_decimation(line, default=2)
        assert decimation == 16

    def test_invalid_decimation_uses_default(self):
        line = "# wave_samp_per : invalid"
        decimation = _parse_decimation(line, default=2)
        assert decimation == 2

    def test_missing_colon_uses_default(self):
        line = "# wave_samp_per 4"
        decimation = _parse_decimation(line, default=2)
        assert decimation == 2

    def test_octal_decimation(self):
        line = "# wave_samp_per : 0o10"
        decimation = _parse_decimation(line, default=2)
        assert decimation == 8


# Test _parse_numerical_data
class TestParseNumericalData:
    def test_valid_data(self, sample_data_file):
        # Read the data lines
        with sample_data_file.open("r") as f:
            lines = f.readlines()

        # Extract only numerical data lines (skip header and comments)
        data_lines = [
            line
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]

        data_array = _parse_numerical_data(data_lines, 4, sample_data_file)

        assert data_array.shape == (20, 4)
        assert data_array[0, 0] == pytest.approx(1.34000)
        assert data_array[0, 3] == pytest.approx(-0.03200)
        assert data_array[19, 0] == pytest.approx(0.12000)
        assert data_array[19, 3] == pytest.approx(0.79200)

    def test_empty_data_lines(self):
        data_array = _parse_numerical_data([], 4, Path("dummy.txt"))
        assert data_array.shape == (0, 4)

    def test_column_mismatch(self):
        """Test data with fewer columns than expected"""
        # The parser uses the actual number of columns present, not the expected count
        invalid_lines = [
            "1.0 2.0 3.0\n",
            "4.0 5.0 6.0\n",
        ]  # Only 3 columns, expecting 4
        data_array = _parse_numerical_data(invalid_lines, 4, Path("dummy.txt"))
        # It creates a 2x3 array (actual columns) rather than padding to 2x4
        assert data_array.shape == (2, 3)
        assert data_array[0, 0] == pytest.approx(1.0)
        assert data_array[0, 2] == pytest.approx(3.0)
        assert data_array[1, 0] == pytest.approx(4.0)

    def test_non_numeric_data(self):
        """Test data with non-numeric values"""
        invalid_lines = ["1.0 2.0 not_a_number 4.0\n"]
        with pytest.raises(
            FileParserError, match="Could not parse numerical data"
        ):
            _parse_numerical_data(invalid_lines, 4, Path("dummy.txt"))


# Integration test
class TestFullFileIntegration:
    def test_complete_file_parsing(self, sample_data_file):
        """Test the full parsing pipeline"""
        (
            header_lines,
            data_lines,
            decimation,
            marker_idx,
        ) = _read_and_parse_header(sample_data_file)

        # Verify decimation
        assert decimation == 4

        # Parse channel PVs
        pvs = _parse_channel_pvs(header_lines, marker_idx)
        assert len(pvs) == 4

        # Parse numerical data
        data_array = _parse_numerical_data(
            data_lines, len(pvs), sample_data_file
        )
        assert data_array.shape[0] == 20
        assert data_array.shape[1] == 4

        # Verify some specific values
        assert data_array[0, 0] == pytest.approx(1.34)
        assert np.all(~np.isnan(data_array))

    def test_load_and_process_file(self, sample_data_file):
        """Test the main entry point function"""
        result = load_and_process_file(sample_data_file)

        # Check structure
        assert "cavity_list" in result
        assert "decimation" in result
        assert "cavities" in result

        # Check decimation
        assert result["decimation"] == 4

        # Check that we have 4 cavities
        cavity_list = result["cavity_list"]
        assert (
            len(cavity_list) == 4
        ), f"Expected 4 cavities, got {len(cavity_list)}"
        assert cavity_list == [1, 2, 3, 4]

        # Check cavities dictionary structure
        cavities_dict = result["cavities"]
        assert len(cavities_dict) == 4

        # Check each cavity has data
        for cav_num in [1, 2, 3, 4]:
            assert cav_num in cavities_dict
            cavity_data = cavities_dict[cav_num]
            # Check if it has PZT:DF:WF channel data
            if "PZT:DF:WF" in cavity_data:
                channel_data = cavity_data["PZT:DF:WF"]
                assert len(channel_data) == 20  # 20 time points


# Edge cases
class TestEdgeCases:
    def test_file_with_only_header(self):
        """Test file with header but no data"""
        content = """# wave_samp_per : 4
# ACCL:L1B:0210:PZT:DF:WF
"""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt"
        ) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            (
                header_lines,
                data_lines,
                decimation,
                marker_idx,
            ) = _read_and_parse_header(temp_path)
            assert len(data_lines) == 0
            assert decimation == 4
        finally:
            temp_path.unlink()

    def test_multiple_decimation_headers(self):
        """Test that last decimation value wins"""
        content = """# wave_samp_per : 4
# wave_samp_per : 8
# ACCL:L1B:0210:PZT:DF:WF
1.0
"""
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt"
        ) as f:
            f.write(content)
            temp_path = Path(f.name)

        try:
            (
                header_lines,
                data_lines,
                decimation,
                marker_idx,
            ) = _read_and_parse_header(temp_path)
            assert decimation == 8  # Last value should be used
        finally:
            temp_path.unlink()
