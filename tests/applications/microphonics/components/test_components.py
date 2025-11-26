"""
Comprehensive unit test suite for microphonics UI components.

Tests cover ChannelSelectionGroup and DataLoadingGroup using pytest-qt.
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

    def test_returns_preferred_path_when_it_exists(self, qtbot, monkeypatch):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        monkeypatch.setattr(Path, "is_dir", lambda self: True)

        result = widget._get_start_directory()

        assert result == str(widget.PREFERRED_DEFAULT_DATA_PATH)

    def test_returns_home_path_when_preferred_does_not_exist(
        self, qtbot, monkeypatch
    ):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        fake_home = Path("/fake/home/directory")
        call_count = {"n": 0}

        def mock_is_dir(self):
            call_count["n"] += 1
            return call_count["n"] > 1

        monkeypatch.setattr(Path, "is_dir", mock_is_dir)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

        result = widget._get_start_directory()

        assert result == str(fake_home)

    def test_returns_current_directory_as_fallback(self, qtbot, monkeypatch):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        fake_home = Path("/nonexistent/home")

        monkeypatch.setattr(Path, "is_dir", lambda self: False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

        result = widget._get_start_directory()

        assert result == "."


class TestDataLoadingGroupShowFileDialog:

    def test_success_scenario_emits_signal_and_updates_label(
        self, qtbot, monkeypatch
    ):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        selected_path = "/some/directory/test_data.dat"
        monkeypatch.setattr(
            QFileDialog,
            "getOpenFileName",
            lambda *args, **kwargs: (selected_path, "All Files (*)"),
        )
        monkeypatch.setattr(
            widget, "_get_start_directory", lambda: "/start/dir"
        )

        with qtbot.waitSignal(widget.file_selected, timeout=1000) as blocker:
            widget._show_file_dialog()

        emitted_path = blocker.args[0]
        assert isinstance(emitted_path, Path)
        assert emitted_path == Path(selected_path)
        assert widget.file_info_label.text() == "Selected: test_data.dat"

    def test_cancel_scenario_no_signal_and_label_unchanged(
        self, qtbot, monkeypatch
    ):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        original_label_text = widget.file_info_label.text()

        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", lambda *args, **kwargs: ("", "")
        )
        monkeypatch.setattr(
            widget, "_get_start_directory", lambda: "/start/dir"
        )

        signal_received = []
        widget.file_selected.connect(lambda p: signal_received.append(p))

        widget._show_file_dialog()

        assert len(signal_received) == 0
        assert widget.file_info_label.text() == original_label_text

    def test_file_dialog_called_with_correct_parameters(
        self, qtbot, monkeypatch
    ):
        widget = DataLoadingGroup()
        qtbot.addWidget(widget)

        start_dir = "/test/start/directory"
        monkeypatch.setattr(widget, "_get_start_directory", lambda: start_dir)

        captured_args = {}

        def mock_get_open_filename(parent, title, directory, filters):
            captured_args["parent"] = parent
            captured_args["title"] = title
            captured_args["directory"] = directory
            captured_args["filters"] = filters
            return ("", "")

        monkeypatch.setattr(
            QFileDialog, "getOpenFileName", mock_get_open_filename
        )

        widget._show_file_dialog()

        expected_filters = (
            "All Files (*);;Text Files (*.txt);;Data Files (*.dat)"
        )
        assert captured_args["parent"] is widget
        assert captured_args["title"] == "Load Previous Data"
        assert captured_args["directory"] == start_dir
        assert captured_args["filters"] == expected_filters
