import time
from unittest.mock import Mock, patch, MagicMock

import pytest
from PyQt5.QtCore import QProcess, QByteArray, QTimer

from sc_linac_physics.applications.microphonics.gui.data_acquisition import (
    DataAcquisitionManager,
)


class TestDataAcquisition:
    @pytest.fixture
    def acquisition_manager(self):
        """Fixture to create the acquisition manager instance"""
        return DataAcquisitionManager()

    @pytest.fixture
    def mock_process_info(self, tmp_path):
        """Fixture for process info dictionary"""
        output_file = tmp_path / "output.dat"
        output_file.touch()

        # Create a properly mocked QProcess
        mock_process = Mock(spec=QProcess)
        mock_process.readAllStandardOutput.return_value = QByteArray(b"")
        mock_process.readAllStandardError.return_value = QByteArray(b"")

        # Mock the signal attributes
        mock_process.readyReadStandardOutput = MagicMock()
        mock_process.readyReadStandardError = MagicMock()
        mock_process.finished = MagicMock()
        mock_process.state.return_value = QProcess.NotRunning

        return {
            "process": mock_process,
            "output_path": output_file,
            "decimation": 1,
            "expected_buffers": 100,
            "completion_signal_received": False,
            "last_progress": 0,
            "cavities": [1, 2],
        }

    @pytest.fixture
    def sample_config(self):
        """Fixture for acquisition config"""
        from types import SimpleNamespace

        measurement_cfg = SimpleNamespace(
            decimation=1, buffer_count=100, channels=["0", "1"]
        )

        return {
            "pv_base": "ACCL:L1B:0300:RESA",
            "cavities": [1, 2],
            "config": measurement_cfg,
        }

    # ===== Directory Creation Tests =====

    def test_create_data_directory_valid_chassis(
        self, acquisition_manager, tmp_path
    ):
        """Test directory creation with valid chassis ID"""
        acquisition_manager.base_path = tmp_path
        chassis_id = "ACCL:L1B:0300:RESA"

        result_path = acquisition_manager._create_data_directory(chassis_id)

        assert result_path.exists()
        assert "LCLS" in str(result_path)
        assert "L1B" in str(result_path)
        assert "CM03" in str(result_path)

    def test_create_data_directory_invalid_chassis(self, acquisition_manager):
        """Test directory creation with invalid chassis ID"""
        with pytest.raises(ValueError, match="Invalid chassis_id format"):
            acquisition_manager._create_data_directory("INVALID")

    def test_create_data_directory_creates_hierarchy(
        self, acquisition_manager, tmp_path
    ):
        """Test that full directory hierarchy is created"""
        acquisition_manager.base_path = tmp_path
        chassis_id = "ACCL:L2B:1234:RESA"

        acquisition_manager._create_data_directory(chassis_id)

        # Check all levels exist
        assert (tmp_path / "LCLS").exists()
        assert (tmp_path / "LCLS" / "L2B").exists()
        assert (tmp_path / "LCLS" / "L2B" / "CM12").exists()

    # ===== Environment Preparation Tests =====

    def test_prepare_acquisition_environment_no_cavities(
        self, acquisition_manager, sample_config
    ):
        """Test preparation fails when no cavities specified"""
        sample_config["cavities"] = []

        with pytest.raises(ValueError, match="No cavities specified"):
            acquisition_manager._prepare_acquisition_environment(
                "ACCL:L1B:0300:RESA", sample_config
            )

    def test_prepare_acquisition_environment_no_config(
        self, acquisition_manager
    ):
        """Test preparation fails when config is missing"""
        bad_config = {"cavities": [1, 2]}

        with pytest.raises(ValueError, match="MeasurementConfig missing"):
            acquisition_manager._prepare_acquisition_environment(
                "ACCL:L1B:0300:RESA", bad_config
            )

    def test_prepare_acquisition_environment_filename_format(
        self, acquisition_manager, sample_config, tmp_path
    ):
        """Test output filename format is correct"""
        acquisition_manager.base_path = tmp_path
        chassis_id = "ACCL:L1B:0300:RESA"

        (
            output_path,
            cavities,
        ) = acquisition_manager._prepare_acquisition_environment(
            chassis_id, sample_config
        )

        filename = output_path.name
        assert filename.startswith("res_CM03_cav12_c100_")
        assert filename.endswith(".dat")
        assert cavities == [1, 2]

    # ===== Build Args Tests =====

    def test_build_acquisition_args_structure(
        self, acquisition_manager, sample_config, tmp_path
    ):
        """Test argument list structure"""
        output_path = tmp_path / "test.dat"
        selected_cavities = [1, 2]

        args = acquisition_manager._build_acquisition_args(
            sample_config, output_path, selected_cavities
        )

        assert str(acquisition_manager.script_path) in args
        assert "-D" in args
        assert str(output_path.parent) in args
        assert "-a" in args
        assert sample_config["pv_base"] in args
        assert "-wsp" in args
        assert "1" in args  # decimation
        assert "-acav" in args
        assert "1" in args and "2" in args  # cavities
        assert "-ch" in args
        assert "0" in args and "1" in args  # channels
        assert "-c" in args
        assert "100" in args  # buffer count
        assert "-F" in args
        assert output_path.name in args

    # ===== Start Acquisition Tests =====

    def test_start_acquisition_success(
        self, acquisition_manager, sample_config, tmp_path
    ):
        """Test successful acquisition start"""
        acquisition_manager.base_path = tmp_path
        chassis_id = "ACCL:L1B:0300:RESA"

        # Create a mock QProcess instance
        mock_process = Mock(spec=QProcess)
        mock_process.readyReadStandardOutput = MagicMock()
        mock_process.readyReadStandardError = MagicMock()
        mock_process.finished = MagicMock()
        mock_process.waitForStarted.return_value = True

        # Patch the QProcess class constructor
        with patch(
            "sc_linac_physics.applications.microphonics.gui.data_acquisition.QProcess",
            return_value=mock_process,
        ):
            acquisition_manager.start_acquisition(chassis_id, sample_config)

            assert chassis_id in acquisition_manager.active_processes
            process_info = acquisition_manager.active_processes[chassis_id]
            assert process_info["decimation"] == 1
            assert process_info["expected_buffers"] == 100
            assert process_info["cavities"] == [1, 2]
            assert not process_info["completion_signal_received"]
            mock_process.start.assert_called_once()

    def test_start_acquisition_process_fails_to_start(
        self, acquisition_manager, sample_config, tmp_path
    ):
        """Test handling when process fails to start"""
        acquisition_manager.base_path = tmp_path
        chassis_id = "ACCL:L1B:0300:RESA"

        mock_process = Mock(spec=QProcess)
        mock_process.readyReadStandardOutput = MagicMock()
        mock_process.readyReadStandardError = MagicMock()
        mock_process.finished = MagicMock()
        mock_process.waitForStarted.return_value = False
        mock_process.errorString.return_value = "Failed to execute"

        with (
            patch(
                "sc_linac_physics.applications.microphonics.gui.data_acquisition.QProcess",
                return_value=mock_process,
            ),
            patch.object(acquisition_manager, "acquisitionError") as mock_error,
        ):
            acquisition_manager.start_acquisition(chassis_id, sample_config)

            assert chassis_id not in acquisition_manager.active_processes
            mock_error.emit.assert_called_once()
            assert "Failed to start process" in mock_error.emit.call_args[0][1]

    def test_start_acquisition_exception_handling(
        self, acquisition_manager, sample_config
    ):
        """Test exception handling during start"""
        chassis_id = "ACCL:L1B:0300:RESA"

        with (
            patch.object(
                acquisition_manager,
                "_prepare_acquisition_environment",
                side_effect=Exception("Test error"),
            ),
            patch.object(acquisition_manager, "acquisitionError") as mock_error,
        ):
            acquisition_manager.start_acquisition(chassis_id, sample_config)

            mock_error.emit.assert_called_once()
            assert (
                "Failed to start acquisition" in mock_error.emit.call_args[0][1]
            )

    # ===== Progress Checking Tests =====

    def test_check_progress_valid_input(self, acquisition_manager):
        """Test progress parsing with valid input"""
        chassis_id = "chassis_1"
        process_info = {"last_progress": 0, "cavities": [1, 2]}
        line = "Acquired 50 / 100 buffers"

        with patch.object(
            acquisition_manager, "acquisitionProgress"
        ) as mock_signal:
            acquisition_manager._check_progress(line, chassis_id, process_info)

            assert process_info["last_progress"] == 50
            assert mock_signal.emit.call_count == 2  # One per cavity

            # Verify calls
            calls = mock_signal.emit.call_args_list
            assert calls[0][0] == (chassis_id, 1, 50)
            assert calls[1][0] == (chassis_id, 2, 50)

    def test_check_progress_invalid_input(self, acquisition_manager):
        """Test progress parsing with invalid input"""
        process_info = {"last_progress": 0, "cavities": [1, 2]}
        line = "Some random log line"

        acquisition_manager._check_progress(line, "chassis_1", process_info)
        assert process_info["last_progress"] == 0

    def test_check_progress_zero_total(self, acquisition_manager):
        """Test progress with zero total buffers"""
        process_info = {"last_progress": 0, "cavities": [1]}
        line = "Acquired 10 / 0 buffers"

        with patch.object(
            acquisition_manager, "acquisitionProgress"
        ) as mock_signal:
            acquisition_manager._check_progress(line, "chassis_1", process_info)

            # Should not emit when total is 0
            mock_signal.emit.assert_not_called()
            assert process_info["last_progress"] == 0

    def test_check_progress_100_percent(self, acquisition_manager):
        """Test progress at 100%"""
        process_info = {"last_progress": 0, "cavities": [1]}
        line = "Acquired 100 / 100 buffers"

        with patch.object(
            acquisition_manager, "acquisitionProgress"
        ) as mock_signal:
            acquisition_manager._check_progress(line, "chassis_1", process_info)

            assert process_info["last_progress"] == 100
            mock_signal.emit.assert_called_once_with("chassis_1", 1, 100)

    def test_check_progress_no_update_if_lower(self, acquisition_manager):
        """Test that progress doesn't emit if value is lower than last"""
        process_info = {"last_progress": 75, "cavities": [1]}
        line = "Acquired 50 / 100 buffers"

        with patch.object(
            acquisition_manager, "acquisitionProgress"
        ) as mock_signal:
            acquisition_manager._check_progress(line, "chassis_1", process_info)

            # Should not emit since 50% < 75%
            mock_signal.emit.assert_not_called()
            assert process_info["last_progress"] == 75

    def test_check_progress_parsing_error(self, acquisition_manager):
        """Test handling of parsing errors"""
        process_info = {"last_progress": 0, "cavities": [1]}
        line = "Acquired bad / wrong buffers"

        # Should not raise, just log warning
        acquisition_manager._check_progress(line, "chassis_1", process_info)
        assert process_info["last_progress"] == 0

    # ===== Stdout Processing Tests =====

    def test_process_stdout_line_completion_marker(self, acquisition_manager):
        """Test detection of completion markers"""
        process_info = {
            "completion_signal_received": False,
            "last_progress": 50,
            "cavities": [1, 2],
        }

        with patch.object(
            acquisition_manager, "acquisitionProgress"
        ) as mock_signal:
            acquisition_manager._process_stdout_line(
                "Restoring acquisition settings...", "chassis_1", process_info
            )

            assert process_info["completion_signal_received"]
            assert process_info["last_progress"] == 100
            # Should emit 100% for all cavities
            assert mock_signal.emit.call_count == 2

    def test_process_stdout_line_already_completed(self, acquisition_manager):
        """Test that completed acquisitions don't process more lines"""
        process_info = {
            "completion_signal_received": True,
            "last_progress": 100,
            "cavities": [1],
        }

        with patch.object(acquisition_manager, "_check_progress") as mock_check:
            acquisition_manager._process_stdout_line(
                "Acquired 50 / 100 buffers", "chassis_1", process_info
            )

            # Should not check progress if already completed
            mock_check.assert_not_called()

    def test_process_stdout_line_progress_update(self, acquisition_manager):
        """Test normal progress line processing"""
        process_info = {
            "completion_signal_received": False,
            "last_progress": 0,
            "cavities": [1],
        }

        with patch.object(acquisition_manager, "_check_progress") as mock_check:
            acquisition_manager._process_stdout_line(
                "Acquired 50 / 100 buffers", "chassis_1", process_info
            )

            mock_check.assert_called_once_with(
                "Acquired 50 / 100 buffers", "chassis_1", process_info
            )

    def test_handle_stdout_multiple_lines(
        self, acquisition_manager, mock_process_info
    ):
        """Test handling multiple stdout lines at once"""
        chassis_id = "chassis_1"
        acquisition_manager.active_processes[chassis_id] = mock_process_info

        mock_process = mock_process_info["process"]
        output_data = b"Acquired 25 / 100 buffers\nAcquired 50 / 100 buffers\nAcquired 75 / 100 buffers"
        mock_process.readAllStandardOutput.return_value = QByteArray(
            output_data
        )

        with patch.object(
            acquisition_manager, "_process_stdout_line"
        ) as mock_process_line:
            acquisition_manager.handle_stdout(chassis_id, mock_process)

            assert mock_process_line.call_count == 3

    def test_handle_stdout_no_active_process(self, acquisition_manager):
        """Test stdout handling when process is not active"""
        mock_process = Mock(spec=QProcess)

        # Should return early without error
        acquisition_manager.handle_stdout("nonexistent_chassis", mock_process)

    def test_handle_stdout_empty_output(
        self, acquisition_manager, mock_process_info
    ):
        """Test handling empty stdout"""
        chassis_id = "chassis_1"
        acquisition_manager.active_processes[chassis_id] = mock_process_info

        mock_process = mock_process_info["process"]
        mock_process.readAllStandardOutput.return_value = QByteArray(
            b"   \n\n   "
        )

        with patch.object(
            acquisition_manager, "_process_stdout_line"
        ) as mock_process_line:
            acquisition_manager.handle_stdout(chassis_id, mock_process)

            # Empty lines should be skipped
            mock_process_line.assert_not_called()

    def test_handle_stdout_exception_handling(
        self, acquisition_manager, mock_process_info
    ):
        """Test exception handling in stdout processing"""
        chassis_id = "chassis_1"
        acquisition_manager.active_processes[chassis_id] = mock_process_info

        mock_process = mock_process_info["process"]
        mock_process.readAllStandardOutput.side_effect = Exception("Read error")

        with patch.object(
            acquisition_manager, "acquisitionError"
        ) as mock_error:
            acquisition_manager.handle_stdout(chassis_id, mock_process)

            mock_error.emit.assert_called_once()
            assert "Internal error" in mock_error.emit.call_args[0][1]

    # ===== Stderr Processing Tests =====

    def test_handle_stderr_with_error(self, acquisition_manager):
        """Test stderr handling with error message"""
        mock_process = Mock(spec=QProcess)
        mock_process.readAllStandardError.return_value = QByteArray(
            b"Error: something went wrong"
        )

        with patch.object(
            acquisition_manager, "acquisitionError"
        ) as mock_error:
            acquisition_manager.handle_stderr("chassis_1", mock_process)

            mock_error.emit.assert_called_once_with(
                "chassis_1", "Error: something went wrong"
            )

    def test_handle_stderr_empty(self, acquisition_manager):
        """Test stderr handling with no error"""
        mock_process = Mock(spec=QProcess)
        mock_process.readAllStandardError.return_value = QByteArray(b"")

        with patch.object(
            acquisition_manager, "acquisitionError"
        ) as mock_error:
            acquisition_manager.handle_stderr("chassis_1", mock_process)

            mock_error.emit.assert_not_called()

    def test_handle_stderr_exception(self, acquisition_manager):
        """Test exception handling in stderr processing"""
        mock_process = Mock(spec=QProcess)
        mock_process.readAllStandardError.side_effect = Exception("Read error")

        # Should not raise, just log
        acquisition_manager.handle_stderr("chassis_1", mock_process)

    # ===== Acquisition Success Tests =====

    @pytest.mark.parametrize(
        "exit_code,exit_status,completion_received,has_output,expected_success",
        [
            (0, QProcess.NormalExit, True, True, True),  # Success
            (1, QProcess.NormalExit, True, True, False),  # Bad exit code
            (0, QProcess.CrashExit, True, True, False),  # Crashed
            (
                0,
                QProcess.NormalExit,
                False,
                True,
                False,
            ),  # No completion signal
            (0, QProcess.NormalExit, True, False, False),  # No output path
        ],
    )
    def test_was_acquisition_successful(
        self,
        acquisition_manager,
        mock_process_info,
        exit_code,
        exit_status,
        completion_received,
        has_output,
        expected_success,
    ):
        """Test various success/failure scenarios"""
        mock_process_info["completion_signal_received"] = completion_received

        if not has_output:
            mock_process_info["output_path"] = None

        result = acquisition_manager._was_acquisition_successful(
            exit_code, exit_status, mock_process_info
        )

        if expected_success:
            assert result == mock_process_info["output_path"]
        else:
            assert not result

    def test_was_acquisition_successful_checks_final_stdout(
        self, acquisition_manager, mock_process_info
    ):
        """Test that success check reads final stdout for completion markers"""
        mock_process_info["completion_signal_received"] = False
        mock_process = mock_process_info["process"]
        mock_process.readAllStandardOutput.return_value = QByteArray(
            b"Restoring acquisition settings...\nDone"
        )

        result = acquisition_manager._was_acquisition_successful(
            0, QProcess.NormalExit, mock_process_info
        )

        # Should detect completion from stdout
        assert mock_process_info["completion_signal_received"]
        assert result == mock_process_info["output_path"]

    # ===== Failure Reporting Tests =====

    def test_report_acquisition_failure_crash(self, acquisition_manager):
        """Test failure reporting for crashed process"""
        with patch.object(
            acquisition_manager, "acquisitionError"
        ) as mock_error:
            acquisition_manager._report_acquisition_failure(
                "chassis_1",
                exit_code=1,
                exit_status=QProcess.CrashExit,
                stderr="Segmentation fault",
                completion_received=False,
            )

            error_msg = mock_error.emit.call_args[0][1]
            assert "failed" in error_msg.lower()
            assert "crashed" in error_msg.lower()
            assert "Segmentation fault" in error_msg

    def test_report_acquisition_failure_no_completion(
        self, acquisition_manager
    ):
        """Test failure reporting when completion signal not received"""
        with patch.object(
            acquisition_manager, "acquisitionError"
        ) as mock_error:
            acquisition_manager._report_acquisition_failure(
                "chassis_1",
                exit_code=0,
                exit_status=QProcess.NormalExit,
                stderr="",
                completion_received=False,
            )

            error_msg = mock_error.emit.call_args[0][1]
            assert "did not signal completion" in error_msg

    def test_report_acquisition_failure_bad_exit_code(
        self, acquisition_manager
    ):
        """Test failure reporting with non-zero exit code"""
        with patch.object(
            acquisition_manager, "acquisitionError"
        ) as mock_error:
            acquisition_manager._report_acquisition_failure(
                "chassis_1",
                exit_code=42,
                exit_status=QProcess.NormalExit,
                stderr="",
                completion_received=True,
            )

            error_msg = mock_error.emit.call_args[0][1]
            assert "Exit Code: 42" in error_msg

    # ===== File Processing Tests =====

    def test_process_output_file_wrapper_success(
        self, acquisition_manager, mock_process_info, tmp_path
    ):
        """Test successful file processing"""
        chassis_id = "chassis_1"
        output_file = tmp_path / "valid_output.dat"
        output_file.write_text("Some data content")

        acquisition_manager.active_processes[chassis_id] = mock_process_info
        mock_process_info["output_path"] = output_file
        mock_process_info["decimation"] = 2

        with patch(
            "sc_linac_physics.applications.microphonics.gui.data_acquisition.load_and_process_file"
        ) as mock_parser:
            mock_parser.return_value = {
                "cavities": {
                    "cav1": {"data": [1, 2, 3]},
                    "cav2": {"data": [4, 5, 6]},
                }
            }

            with (
                patch.object(acquisition_manager, "dataReceived") as mock_data,
                patch.object(
                    acquisition_manager, "acquisitionComplete"
                ) as mock_complete,
            ):
                acquisition_manager._process_output_file_wrapper(
                    chassis_id, output_file, mock_process_info
                )

                mock_parser.assert_called_once_with(output_file)

                # Check dataReceived emission
                mock_data.emit.assert_called_once()
                emitted_data = mock_data.emit.call_args[0][1]
                assert emitted_data["source"] == chassis_id
                assert emitted_data["decimation"] == 2
                assert "cavities" in emitted_data

                # Check acquisitionComplete emission
                mock_complete.emit.assert_called_once_with(chassis_id)

                # Verify cleanup
                assert chassis_id not in acquisition_manager.active_processes

    def test_process_output_file_wrapper_missing_file(
        self, acquisition_manager, tmp_path
    ):
        """Test handling of missing output file"""
        chassis_id = "chassis_1"
        output_file = tmp_path / "missing.dat"
        process_info = {"output_path": output_file, "cavities": []}

        with patch.object(
            acquisition_manager, "acquisitionError"
        ) as mock_error:
            acquisition_manager._process_output_file_wrapper(
                chassis_id, output_file, process_info
            )

            mock_error.emit.assert_called_once()
            error_message = mock_error.emit.call_args[0][1]
            assert (
                "missing" in error_message.lower()
                or "not found" in error_message.lower()
            )

    def test_process_output_file_wrapper_empty_file(
        self, acquisition_manager, tmp_path
    ):
        """Test handling of empty output file"""
        chassis_id = "chassis_1"
        output_file = tmp_path / "empty.dat"
        output_file.touch()

        process_info = {"output_path": output_file, "cavities": []}

        with patch.object(
            acquisition_manager, "acquisitionError"
        ) as mock_error:
            acquisition_manager._process_output_file_wrapper(
                chassis_id, output_file, process_info
            )

            mock_error.emit.assert_called_once()
            error_message = mock_error.emit.call_args[0][1]
            assert "empty" in error_message.lower()

    def test_process_output_file_wrapper_no_cavity_data(
        self, acquisition_manager, tmp_path
    ):
        """Test handling when parsed data has no cavities"""
        chassis_id = "chassis_1"
        output_file = tmp_path / "invalid.dat"
        output_file.write_text("data")
        process_info = {
            "output_path": output_file,
            "cavities": [],
            "decimation": 1,
        }

        acquisition_manager.active_processes[chassis_id] = process_info

        with patch(
            "sc_linac_physics.applications.microphonics.gui.data_acquisition.load_and_process_file"
        ) as mock_parser:
            mock_parser.return_value = {}  # No cavities

            with patch.object(
                acquisition_manager, "acquisitionError"
            ) as mock_error:
                acquisition_manager._process_output_file_wrapper(
                    chassis_id, output_file, process_info
                )

                mock_error.emit.assert_called_once()
                assert (
                    "Failed to parse valid data"
                    in mock_error.emit.call_args[0][1]
                )

    def test_process_output_file_wrapper_parser_exception(
        self, acquisition_manager, tmp_path
    ):
        """Test handling of parser exceptions"""
        from sc_linac_physics.applications.microphonics.utils.file_parser import (
            FileParserError,
        )

        chassis_id = "chassis_1"
        output_file = tmp_path / "bad.dat"
        output_file.write_text("bad data")
        process_info = {"output_path": output_file, "cavities": []}

        with patch(
            "sc_linac_physics.applications.microphonics.gui.data_acquisition.load_and_process_file",
            side_effect=FileParserError("Parse failed"),
        ):
            with patch.object(
                acquisition_manager, "acquisitionError"
            ) as mock_error:
                acquisition_manager._process_output_file_wrapper(
                    chassis_id, output_file, process_info
                )

                mock_error.emit.assert_called_once()
                assert "Parse failed" in mock_error.emit.call_args[0][1]

    def test_process_output_file_wrapper_unexpected_exception(
        self, acquisition_manager, tmp_path
    ):
        """Test handling of unexpected exceptions"""
        chassis_id = "chassis_1"
        output_file = tmp_path / "test.dat"
        output_file.write_text("data")
        process_info = {
            "output_path": output_file,
            "cavities": [],
            "decimation": 1,
        }

        acquisition_manager.active_processes[chassis_id] = process_info

        with patch(
            "sc_linac_physics.applications.microphonics.gui.data_acquisition.load_and_process_file",
            side_effect=RuntimeError("Unexpected error"),
        ):
            with patch.object(
                acquisition_manager, "acquisitionError"
            ) as mock_error:
                acquisition_manager._process_output_file_wrapper(
                    chassis_id, output_file, process_info
                )

                mock_error.emit.assert_called_once()
                assert "Unexpected error" in mock_error.emit.call_args[0][1]

    # ===== Cleanup Tests =====

    def test_cleanup_process_resources(
        self, acquisition_manager, mock_process_info
    ):
        """Test process cleanup"""
        mock_process = mock_process_info["process"]

        acquisition_manager._cleanup_process_resources(mock_process_info)

        # Verify disconnections were attempted
        mock_process.readyReadStandardOutput.disconnect.assert_called()
        mock_process.readyReadStandardError.disconnect.assert_called()
        mock_process.finished.disconnect.assert_called()

        # Verify process is set to None
        assert mock_process_info["process"] is None

    def test_cleanup_process_resources_already_disconnected(
        self, acquisition_manager, mock_process_info
    ):
        """Test cleanup when signals are already disconnected"""
        mock_process = mock_process_info["process"]
        mock_process.readyReadStandardOutput.disconnect.side_effect = TypeError(
            "Not connected"
        )

        # Should not raise
        acquisition_manager._cleanup_process_resources(mock_process_info)
        assert mock_process_info["process"] is None

    def test_cleanup_process_resources_no_process(self, acquisition_manager):
        """Test cleanup when process is None"""
        process_info = {"process": None}

        # Should not raise
        acquisition_manager._cleanup_process_resources(process_info)

    # ===== Handle Finished Tests =====

    def test_handle_finished_success_flow(
        self, acquisition_manager, mock_process_info
    ):
        """Test successful completion flow"""
        chassis_id = "chassis_1"
        acquisition_manager.active_processes[chassis_id] = mock_process_info
        mock_process_info["completion_signal_received"] = True

        mock_process = mock_process_info["process"]

        with (
            patch.object(acquisition_manager, "_process_output_file_wrapper"),
            patch("PyQt5.QtCore.QTimer.singleShot") as mock_timer,
        ):
            acquisition_manager.handle_finished(
                chassis_id, mock_process, 0, QProcess.NormalExit
            )

            # Verify timer was called for file processing
            assert any(
                call[0][0] == 20000 for call in mock_timer.call_args_list
            )

    def test_handle_finished_failure_flow(
        self, acquisition_manager, mock_process_info
    ):
        """Test failure handling in handle_finished"""
        chassis_id = "chassis_1"
        acquisition_manager.active_processes[chassis_id] = mock_process_info
        mock_process_info["completion_signal_received"] = False

        mock_process = mock_process_info["process"]
        mock_process.readAllStandardError.return_value = QByteArray(
            b"Error occurred"
        )

        with patch.object(
            acquisition_manager, "acquisitionError"
        ) as mock_error:
            acquisition_manager.handle_finished(
                chassis_id, mock_process, 1, QProcess.NormalExit
            )

            mock_error.emit.assert_called_once()
            assert chassis_id not in acquisition_manager.active_processes

    def test_handle_finished_no_active_process(self, acquisition_manager):
        """Test handle_finished when process is not in active list"""
        mock_process = Mock(spec=QProcess)

        # Should return early without error
        acquisition_manager.handle_finished(
            "nonexistent", mock_process, 0, QProcess.NormalExit
        )

    def test_handle_finished_exception_handling(
        self, acquisition_manager, mock_process_info
    ):
        """Test exception handling in handle_finished"""
        chassis_id = "chassis_1"
        acquisition_manager.active_processes[chassis_id] = mock_process_info

        mock_process = mock_process_info["process"]

        with (
            patch.object(
                acquisition_manager,
                "_was_acquisition_successful",
                side_effect=Exception("Unexpected error"),
            ),
            patch.object(acquisition_manager, "acquisitionError") as mock_error,
        ):
            acquisition_manager.handle_finished(
                chassis_id, mock_process, 0, QProcess.NormalExit
            )

            mock_error.emit.assert_called()
            assert "Unexpected error" in mock_error.emit.call_args[0][1]
            assert chassis_id not in acquisition_manager.active_processes

    def test_handle_finished_cleanup_always_called(
        self, acquisition_manager, mock_process_info
    ):
        """Test that cleanup is always called even on exception"""
        chassis_id = "chassis_1"
        acquisition_manager.active_processes[chassis_id] = mock_process_info

        mock_process = mock_process_info["process"]

        with (
            patch.object(
                acquisition_manager,
                "_was_acquisition_successful",
                side_effect=Exception("Error"),
            ),
            patch.object(
                acquisition_manager, "_cleanup_process_resources"
            ) as mock_cleanup,
            patch.object(acquisition_manager, "acquisitionError"),
        ):
            acquisition_manager.handle_finished(
                chassis_id, mock_process, 0, QProcess.NormalExit
            )

            # Cleanup should be called in finally block
            mock_cleanup.assert_called_once_with(mock_process_info)

    # ===== Stop Acquisition Tests =====

    def test_stop_acquisition_running_process(self, acquisition_manager):
        """Test stopping a running process"""
        chassis_id = "chassis_1"
        mock_process = Mock(spec=QProcess)
        mock_process.state.return_value = QProcess.Running
        mock_process.waitForFinished.return_value = True

        acquisition_manager.active_processes[chassis_id] = {
            "process": mock_process
        }

        acquisition_manager.stop_acquisition(chassis_id)

        mock_process.terminate.assert_called_once()
        mock_process.waitForFinished.assert_called_with(2000)
        assert chassis_id not in acquisition_manager.active_processes

    def test_stop_acquisition_force_kill(self, acquisition_manager):
        """Test force killing process that doesn't terminate"""
        chassis_id = "chassis_1"
        mock_process = Mock(spec=QProcess)
        mock_process.state.return_value = QProcess.Running
        mock_process.waitForFinished.side_effect = [
            False,
            True,
        ]  # First call fails, second succeeds

        acquisition_manager.active_processes[chassis_id] = {
            "process": mock_process
        }

        acquisition_manager.stop_acquisition(chassis_id)

        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        assert mock_process.waitForFinished.call_count == 2

    def test_stop_acquisition_not_running(self, acquisition_manager):
        """Test stopping a process that's not running"""
        chassis_id = "chassis_1"
        mock_process = Mock(spec=QProcess)
        mock_process.state.return_value = QProcess.NotRunning

        acquisition_manager.active_processes[chassis_id] = {
            "process": mock_process
        }

        acquisition_manager.stop_acquisition(chassis_id)

        mock_process.terminate.assert_not_called()
        assert chassis_id not in acquisition_manager.active_processes

    def test_stop_acquisition_nonexistent(self, acquisition_manager):
        """Test stopping a process that doesn't exist"""
        # Should not raise
        acquisition_manager.stop_acquisition("nonexistent")

    # ===== Stop All Tests =====

    def test_stop_all_multiple_processes(self, acquisition_manager):
        """Test stopping all active processes"""
        mock_process1 = Mock(spec=QProcess)
        mock_process1.state.return_value = QProcess.Running
        mock_process1.waitForFinished.return_value = True

        mock_process2 = Mock(spec=QProcess)
        mock_process2.state.return_value = QProcess.Running
        mock_process2.waitForFinished.return_value = True

        acquisition_manager.active_processes = {
            "chassis_1": {"process": mock_process1},
            "chassis_2": {"process": mock_process2},
        }

        acquisition_manager.stop_all()

        mock_process1.terminate.assert_called_once()
        mock_process2.terminate.assert_called_once()
        assert len(acquisition_manager.active_processes) == 0

    def test_stop_all_no_processes(self, acquisition_manager):
        """Test stop_all with no active processes"""
        acquisition_manager.stop_all()
        assert len(acquisition_manager.active_processes) == 0

    def test_progress_timer_updates_and_stops(
        self, acquisition_manager, sample_config, tmp_path
    ):
        """Test that progress timer works and stops when real progress arrives"""
        acquisition_manager.base_path = tmp_path
        chassis_id = "ACCL:L1B:0300:RESA"

        mock_process = Mock(spec=QProcess)
        mock_process.readyReadStandardOutput = MagicMock()
        mock_process.readyReadStandardError = MagicMock()
        mock_process.finished = MagicMock()
        mock_process.waitForStarted.return_value = True

        mock_timer = Mock(spec=QTimer)

        with patch(
            "sc_linac_physics.applications.microphonics.gui.data_acquisition.QProcess",
            return_value=mock_process,
        ):
            with patch(
                "sc_linac_physics.applications.microphonics.gui.data_acquisition.QTimer",
                return_value=mock_timer,
            ):
                acquisition_manager.start_acquisition(chassis_id, sample_config)

                mock_timer.start.assert_called_once_with(2000)

                process_info = acquisition_manager.active_processes[chassis_id]
                process_info["progress_timer"] = mock_timer
                mock_timer.isActive.return_value = True

                line = "Acquired 50 / 100 buffers"
                acquisition_manager._check_progress(
                    line, chassis_id, process_info
                )

                mock_timer.stop.assert_called_once()
                assert process_info["actual_progress_received"] is True

    def test_progress_estimate_calculation(self, acquisition_manager):
        """Test progress calculation and 90% cap"""
        chassis_id = "ACCL:L1B:0300:RESA"

        mock_timer = Mock(spec=QTimer)

        # Test 50% progress
        acquisition_manager.active_processes[chassis_id] = {
            "start_time": time.time() - 8.0,
            "expected_duration": 16.0,
            "last_progress": 0,
            "cavities": [1],
            "actual_progress_received": False,
            "progress_timer": mock_timer,
        }

        with patch.object(
            acquisition_manager, "acquisitionProgress"
        ) as mock_signal:
            acquisition_manager._update_progress_estimate(chassis_id)
            mock_signal.emit.assert_called_with(chassis_id, 1, 50)

        acquisition_manager.active_processes[chassis_id]["start_time"] = (
            time.time() - 20.0
        )
        acquisition_manager.active_processes[chassis_id]["last_progress"] = 0

        with patch.object(
            acquisition_manager, "acquisitionProgress"
        ) as mock_signal:
            acquisition_manager._update_progress_estimate(chassis_id)
            mock_signal.emit.assert_called_with(
                chassis_id, 1, 90
            )  # Capped at 90%

    def test_progress_timer_cleanup(self, acquisition_manager):
        """Test timer is cleaned up properly"""
        mock_timer = Mock(spec=QTimer)
        mock_timer.isActive.return_value = True

        mock_process = Mock(spec=QProcess)
        mock_process.readyReadStandardOutput = MagicMock()
        mock_process.readyReadStandardError = MagicMock()
        mock_process.finished = MagicMock()

        process_info = {"progress_timer": mock_timer, "process": mock_process}

        acquisition_manager._cleanup_process_resources(process_info)

        mock_timer.stop.assert_called_once()
        mock_timer.deleteLater.assert_called_once()

    # ===== Integration Tests =====

    def test_full_acquisition_cycle_success(
        self, acquisition_manager, sample_config, tmp_path
    ):
        """Integration test for complete successful acquisition cycle"""
        acquisition_manager.base_path = tmp_path
        chassis_id = "ACCL:L1B:0300:RESA"

        # Track signal emissions
        progress_calls = []
        complete_calls = []
        data_calls = []

        acquisition_manager.acquisitionProgress.connect(
            lambda *args: progress_calls.append(args)
        )
        acquisition_manager.acquisitionComplete.connect(
            lambda *args: complete_calls.append(args)
        )
        acquisition_manager.dataReceived.connect(
            lambda *args: data_calls.append(args)
        )

        # Create a mock QProcess
        mock_process = Mock(spec=QProcess)
        mock_process.readyReadStandardOutput = MagicMock()
        mock_process.readyReadStandardError = MagicMock()
        mock_process.finished = MagicMock()
        mock_process.waitForStarted.return_value = True
        mock_process.readAllStandardOutput.return_value = QByteArray(b"")
        mock_process.readAllStandardError.return_value = QByteArray(b"")

        with patch(
            "sc_linac_physics.applications.microphonics.gui.data_acquisition.QProcess",
            return_value=mock_process,
        ):
            # Start acquisition
            acquisition_manager.start_acquisition(chassis_id, sample_config)
            assert chassis_id in acquisition_manager.active_processes

            # Simulate progress updates
            process_info = acquisition_manager.active_processes[chassis_id]

            # Update the mock's return value for this specific call
            mock_process.readAllStandardOutput.return_value = QByteArray(
                b"Acquired 50 / 100 buffers"
            )
            acquisition_manager.handle_stdout(chassis_id, mock_process)

            assert len(progress_calls) > 0

            # Simulate completion
            mock_process.readAllStandardOutput.return_value = QByteArray(
                b"Done"
            )
            acquisition_manager.handle_stdout(chassis_id, mock_process)

            assert process_info["completion_signal_received"]

            # Create output file
            output_file = process_info["output_path"]
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text("test data")

            # Simulate process finished
            with patch(
                "sc_linac_physics.applications.microphonics.gui.data_acquisition.load_and_process_file"
            ) as mock_parser:
                mock_parser.return_value = {
                    "cavities": {"cav1": {"data": [1, 2, 3]}}
                }

                # Process file directly (skip timer)
                acquisition_manager._process_output_file_wrapper(
                    chassis_id, output_file, process_info
                )

                assert len(data_calls) > 0
                assert len(complete_calls) > 0

    def test_multiple_concurrent_acquisitions(
        self, acquisition_manager, sample_config, tmp_path
    ):
        """Test handling multiple concurrent acquisitions"""
        acquisition_manager.base_path = tmp_path

        chassis_ids = [
            "ACCL:L1B:0300:RESA",
            "ACCL:L1B:0400:RESA",
            "ACCL:L2B:0100:RESA",
        ]

        # Create mock processes
        mock_processes = []
        for _ in chassis_ids:
            mock_process = Mock(spec=QProcess)
            mock_process.readyReadStandardOutput = MagicMock()
            mock_process.readyReadStandardError = MagicMock()
            mock_process.finished = MagicMock()
            mock_process.waitForStarted.return_value = True
            mock_process.state.return_value = QProcess.Running
            mock_process.waitForFinished.return_value = True
            mock_processes.append(mock_process)

        with patch(
            "sc_linac_physics.applications.microphonics.gui.data_acquisition.QProcess",
            side_effect=mock_processes,
        ):
            for chassis_id in chassis_ids:
                acquisition_manager.start_acquisition(chassis_id, sample_config)

            assert len(acquisition_manager.active_processes) == 3

            # Stop all
            acquisition_manager.stop_all()
            assert len(acquisition_manager.active_processes) == 0
