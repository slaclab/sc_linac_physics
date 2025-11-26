"""
Comprehensive unit test suite for microphonics UI components.

Tests cover ChannelSelectionGroup and DataLoadingGroup using pytest-qt and pytest-mock.
"""

from pathlib import Path

from PyQt5.QtWidgets import QCheckBox, QFileDialog

from sc_linac_physics.applications.microphonics.components.components import (
    ChannelSelectionGroup,
    DataLoadingGroup,
)


class TestChannelSelectionGroup:

    def test_ui_initializes_with_df_channel_checked(self, qtbot):
        widget = ChannelSelectionGroup()
        qtbot.addWidget(widget)

        df_checkbox = widget.channel_widgets.get("DF")

        assert df_checkbox is not None, "DF checkbox should exist"
        assert isinstance(df_checkbox, QCheckBox)
        assert df_checkbox.isChecked() is True

    def test_ui_initializes_with_df_channel_disabled(self, qtbot):
        widget = ChannelSelectionGroup()
        qtbot.addWidget(widget)

        df_checkbox = widget.channel_widgets["DF"]

        assert df_checkbox.isEnabled() is False

    def test_get_selected_channels_returns_df_by_default(self, qtbot):
        widget = ChannelSelectionGroup()
        qtbot.addWidget(widget)

        selected = widget.get_selected_channels()

        assert selected == ["DF"]

    def test_group_box_title_is_channel_selection(self, qtbot):
        widget = ChannelSelectionGroup()
        qtbot.addWidget(widget)

        assert widget.title() == "Channel Selection"


class TestDataLoadingGroup:

    def test_ui_initializes_with_correct_label_text(self, qtbot):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        assert widget.file_info_label.text() == "No file loaded"

    def test_group_box_title_is_data_loading(self, qtbot):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        assert widget.title() == "Data Loading"

    def test_load_button_text(self, qtbot):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        assert widget.load_button.text() == "Load Previous Data"

    def test_update_file_info_updates_label(self, qtbot):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        widget.update_file_info("Loading complete")

        assert widget.file_info_label.text() == "Loading complete"


class TestDataLoadingGroupGetStartDirectory:

    def test_returns_preferred_path_when_it_exists(self, qtbot, mocker):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        mocker.patch.object(Path, "is_dir", return_value=True)

        result = widget._get_start_directory()

        assert result == str(widget.PREFERRED_DEFAULT_DATA_PATH)

    def test_returns_home_path_when_preferred_does_not_exist(
        self, qtbot, mocker
    ):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        fake_home = Path("/fake/home/directory")

        mocker.patch.object(Path, "is_dir", side_effect=[False, True])
        mocker.patch.object(Path, "home", return_value=fake_home)

        result = widget._get_start_directory()

        assert result == str(fake_home)

    def test_returns_current_directory_as_fallback(self, qtbot, mocker):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        fake_home = Path("/nonexistent/home")

        mocker.patch.object(Path, "is_dir", side_effect=[False, False])
        mocker.patch.object(Path, "home", return_value=fake_home)

        result = widget._get_start_directory()

        assert result == "."


class TestDataLoadingGroupShowFileDialog:

    def test_success_scenario_emits_signal_and_updates_label(
        self, qtbot, mocker
    ):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        selected_path = "/some/directory/test_data.dat"
        mocker.patch.object(
            QFileDialog,
            "getOpenFileName",
            return_value=(selected_path, "All Files (*)"),
        )
        mocker.patch.object(
            widget, "_get_start_directory", return_value="/start/dir"
        )

        with qtbot.waitSignal(widget.file_selected, timeout=1000) as blocker:
            widget._show_file_dialog()

        emitted_path = blocker.args[0]
        assert isinstance(emitted_path, Path)
        assert emitted_path == Path(selected_path)
        assert widget.file_info_label.text() == "Selected: test_data.dat"

    def test_cancel_scenario_no_signal_and_label_unchanged(self, qtbot, mocker):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        original_label_text = widget.file_info_label.text()

        mocker.patch.object(
            QFileDialog, "getOpenFileName", return_value=("", "")
        )
        mocker.patch.object(
            widget, "_get_start_directory", return_value="/start/dir"
        )

        signal_received = []
        widget.file_selected.connect(lambda p: signal_received.append(p))

        widget._show_file_dialog()

        assert len(signal_received) == 0
        assert widget.file_info_label.text() == original_label_text

    def test_file_dialog_called_with_correct_parameters(self, qtbot, mocker):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        start_dir = "/test/start/directory"
        mocker.patch.object(
            widget, "_get_start_directory", return_value=start_dir
        )

        mock_dialog = mocker.patch.object(
            QFileDialog, "getOpenFileName", return_value=("", "")
        )

        widget._show_file_dialog()

        expected_filters = (
            "All Files (*);;Text Files (*.txt);;Data Files (*.dat)"
        )
        mock_dialog.assert_called_once_with(
            widget, "Load Previous Data", start_dir, expected_filters
        )
