import sys
from unittest.mock import patch

import pytest
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QGroupBox,
    QAbstractScrollArea,
    QWidget,
)

# Import your module with the correct path
from sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display import DecoderDisplay, Row


# Fixture to ensure QApplication exists
@pytest.fixture(scope="session")
def qapp():
    """Create QApplication for testing."""
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    yield app


@pytest.fixture
def mock_csv_data():
    """Mock CSV data for testing."""
    return [
        {
            "Three Letter Code": "ABC",
            "Long Description": "A test fault description",
            "Generic Short Description for Decoder": "Test Fault",
            "Recommended Corrective Actions": "Check connections",
        },
        {
            "Three Letter Code": "XYZ",
            "Long Description": "Another test fault",
            "Generic Short Description for Decoder": "Another Test",
            "Recommended Corrective Actions": "Reset system",
        },
        {
            "Three Letter Code": "DEF",
            "Long Description": "Third test fault",
            "Generic Short Description for Decoder": "Third Test",
            "Recommended Corrective Actions": "Replace component",
        },
    ]


# Create a mock Display class that accepts any arguments
class MockDisplay(QWidget):
    def __init__(self, *args, **kwargs):
        # Extract parent if provided, default to None
        parent = args[0] if args else kwargs.get("parent", None)
        super().__init__(parent)


@pytest.fixture
def decoder_display(qapp, mock_csv_data):
    """Create a DecoderDisplay instance for testing."""
    with patch("sc_linac_physics.displays.cavity_display.utils.utils.parse_csv", return_value=mock_csv_data):
        # Patch Display at the correct import location
        with patch("sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display.Display", MockDisplay):
            display = DecoderDisplay()
            yield display
            display.deleteLater()


class TestRow:
    """Test the Row dataclass."""

    def test_row_creation(self):
        """Test creating a Row instance."""
        row = Row(tlc="ABC", long_desc="Test description", gen_short_desc="Test", corrective_action="Test action")
        assert row.tlc == "ABC"
        assert row.long_desc == "Test description"
        assert row.gen_short_desc == "Test"
        assert row.corrective_action == "Test action"

    def test_row_comparison_gt(self):
        """Test Row greater than comparison."""
        row1 = Row("ABC", "desc1", "short1", "action1")
        row2 = Row("XYZ", "desc2", "short2", "action2")
        row3 = Row("DEF", "desc3", "short3", "action3")

        assert row2 > row1  # "XYZ" > "ABC"
        assert row3 > row1  # "DEF" > "ABC"
        assert row2 > row3  # "XYZ" > "DEF"

    def test_row_comparison_eq(self):
        """Test Row equality comparison."""
        row1 = Row("ABC", "desc1", "short1", "action1")
        row2 = Row("ABC", "desc2", "short2", "action2")  # Same TLC, different other fields
        row3 = Row("XYZ", "desc1", "short1", "action1")  # Different TLC, same other fields

        assert row1 == row2  # Same TLC
        assert not (row1 == row3)  # Different TLC

    def test_row_sorting(self):
        """Test that rows can be sorted."""
        rows = [
            Row("XYZ", "desc1", "short1", "action1"),
            Row("ABC", "desc2", "short2", "action2"),
            Row("DEF", "desc3", "short3", "action3"),
        ]

        sorted_rows = sorted(rows)

        assert sorted_rows[0].tlc == "ABC"
        assert sorted_rows[1].tlc == "DEF"
        assert sorted_rows[2].tlc == "XYZ"


class TestDecoderDisplayInitialization:
    """Test DecoderDisplay initialization."""

    @patch("sc_linac_physics.displays.cavity_display.utils.utils.parse_csv")
    @patch("sc_linac_physics.displays.cavity_display.frontend.fault_decoder_display.Display")
    def test_initialization_with_empty_csv(self, mock_display_class, mock_parse_csv, qapp):
        """Test initialization with empty CSV data."""
        # Configure the mock Display class
        mock_display_instance = QWidget()
        mock_display_class.return_value = mock_display_instance

        mock_parse_csv.return_value = []

        display = DecoderDisplay()

        assert display.windowTitle() == "Three Letter Codes"
        assert isinstance(display.layout(), QVBoxLayout)
        assert isinstance(display.scroll_area, QScrollArea)
        assert isinstance(display.groupbox, QGroupBox)

        display.deleteLater()

    def test_initialization_with_csv_data(self, decoder_display, mock_csv_data):
        """Test initialization with CSV data."""
        assert decoder_display.windowTitle() == "Three Letter Codes"
        assert isinstance(decoder_display.layout(), QVBoxLayout)
        assert isinstance(decoder_display.scroll_area, QScrollArea)
        assert isinstance(decoder_display.groupbox, QGroupBox)

    def test_scroll_area_configuration(self, decoder_display):
        """Test scroll area is configured correctly."""
        scroll_area = decoder_display.scroll_area

        assert scroll_area.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOn
        assert scroll_area.sizeAdjustPolicy() == QAbstractScrollArea.AdjustToContents
        assert scroll_area.widgetResizable() is True
        assert scroll_area.widget() == decoder_display.groupbox


class TestDecoderDisplayLayout:
    """Test DecoderDisplay layout structure."""

    def test_main_layout_structure(self, decoder_display):
        """Test the main layout structure."""
        main_layout = decoder_display.layout()
        assert isinstance(main_layout, QVBoxLayout)
        assert main_layout.count() == 1  # Should contain scroll area
        assert main_layout.itemAt(0).widget() == decoder_display.scroll_area

    def test_scroll_area_layout_structure(self, decoder_display):
        """Test the scroll area layout structure."""
        groupbox_layout = decoder_display.groupbox.layout()
        assert isinstance(groupbox_layout, QVBoxLayout)

        # Should have header layout + data rows
        # With 3 mock rows, should have 4 items total (1 header + 3 data rows)
        assert groupbox_layout.count() == 4

    def test_header_layout_exists(self, decoder_display):
        """Test that header layout is created correctly."""
        groupbox_layout = decoder_display.groupbox.layout()
        header_item = groupbox_layout.itemAt(0)

        assert header_item is not None
        assert isinstance(header_item.layout(), QHBoxLayout)

        header_layout = header_item.layout()
        assert header_layout.count() == 4  # Code, Name, Description, Action

    def test_header_labels_content(self, decoder_display):
        """Test header labels have correct content."""
        groupbox_layout = decoder_display.groupbox.layout()
        header_layout = groupbox_layout.itemAt(0).layout()

        # Get header labels
        code_label = header_layout.itemAt(0).widget()
        name_label = header_layout.itemAt(1).widget()
        desc_label = header_layout.itemAt(2).widget()
        action_label = header_layout.itemAt(3).widget()

        assert isinstance(code_label, QLabel)
        assert isinstance(name_label, QLabel)
        assert isinstance(desc_label, QLabel)
        assert isinstance(action_label, QLabel)

        assert code_label.text() == "Code"
        assert name_label.text() == "Name"
        assert desc_label.text() == "Description"
        assert action_label.text() == "Corrective Action"

    def test_header_labels_styling(self, decoder_display):
        """Test header labels have underline styling."""
        groupbox_layout = decoder_display.groupbox.layout()
        header_layout = groupbox_layout.itemAt(0).layout()

        for i in range(header_layout.count()):
            label = header_layout.itemAt(i).widget()
            assert "text-decoration: underline" in label.styleSheet()


class TestDecoderDisplayDataRows:
    """Test data row creation and content."""

    def test_data_rows_created(self, decoder_display, mock_csv_data):
        """Test that data rows are created for each CSV entry."""
        groupbox_layout = decoder_display.groupbox.layout()

        # Should have 1 header + 3 data rows
        assert groupbox_layout.count() == 4

        # Check that rows 1-3 are data rows
        for i in range(1, 4):
            item = groupbox_layout.itemAt(i)
            assert item is not None
            assert isinstance(item.layout(), QHBoxLayout)

    def test_data_rows_sorted(self, decoder_display):
        """Test that data rows are sorted by TLC."""
        groupbox_layout = decoder_display.groupbox.layout()

        # Get TLC from each data row (first widget in each row layout)
        tlcs = []
        for i in range(1, 4):  # Skip header row
            row_layout = groupbox_layout.itemAt(i).layout()
            tlc_label = row_layout.itemAt(0).widget()
            tlcs.append(tlc_label.text())

        # Should be sorted: ABC, DEF, XYZ
        assert tlcs == ["ABC", "DEF", "XYZ"]

    def test_data_row_content(self, decoder_display, mock_csv_data):
        """Test that data rows contain correct content."""
        groupbox_layout = decoder_display.groupbox.layout()

        # Test first data row (should be ABC after sorting)
        first_row_layout = groupbox_layout.itemAt(1).layout()

        code_label = first_row_layout.itemAt(0).widget()
        name_label = first_row_layout.itemAt(1).widget()
        desc_label = first_row_layout.itemAt(2).widget()
        action_label = first_row_layout.itemAt(3).widget()

        assert code_label.text() == "ABC"
        assert name_label.text() == "Test Fault"
        assert desc_label.text() == "A test fault description"
        assert action_label.text() == "Check connections"


# Simplified tests to avoid further mocking issues
class TestDecoderDisplaySimplified:
    """Simplified tests that focus on core functionality."""

    def test_row_creation_logic(self):
        """Test the row creation logic without UI."""
        test_data = [
            {
                "Three Letter Code": "ABC",
                "Long Description": "Test description",
                "Generic Short Description for Decoder": "Test",
                "Recommended Corrective Actions": "Test action",
            }
        ]

        rows = []
        for fault_row_dict in test_data:
            rows.append(
                Row(
                    tlc=fault_row_dict.get("Three Letter Code", ""),
                    long_desc=fault_row_dict.get("Long Description", ""),
                    gen_short_desc=fault_row_dict.get("Generic Short Description for Decoder", ""),
                    corrective_action=fault_row_dict.get("Recommended Corrective Actions", ""),
                )
            )

        assert len(rows) == 1
        assert rows[0].tlc == "ABC"
        assert rows[0].long_desc == "Test description"

    def test_row_sorting_logic(self):
        """Test row sorting without UI."""
        rows = [
            Row("ZZZ", "desc1", "short1", "action1"),
            Row("AAA", "desc2", "short2", "action2"),
            Row("MMM", "desc3", "short3", "action3"),
        ]

        sorted_rows = sorted(rows)

        assert [row.tlc for row in sorted_rows] == ["AAA", "MMM", "ZZZ"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
