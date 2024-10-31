import unittest
from unittest.mock import patch, mock_open
from PyQt5.QtWidgets import QApplication, QSizePolicy, QAbstractScrollArea
from PyQt5.QtCore import Qt
from displays.cavity_display.frontend.decoder import DecoderDisplay, Row, rows


class TestDecoderDisplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Need to create a QApplication instance before running any PyQt tests
        if not QApplication.instance():
            cls.app = QApplication([])
        else:
            cls.app = QApplication.instance()

    @classmethod
    def tearDownClass(cls):
        cls.app.quit()

    def setUp(self):
        rows.clear()

    def tearDown(self):
        rows.clear()

    def populate_rows(self, mock_data):
        """Helper method to populate the rows dictionary from mock data"""
        # This saves us from having to copy & paste the same row creation for every test
        for row_data in mock_data:
            tlc = row_data['Three Letter Code']
            rows[tlc] = Row(
                tlc=tlc,
                long_desc=row_data['Long Description'],
                gen_short_desc=row_data['Generic Short Description for Decoder'],
                corrective_action=row_data['Recommended Corrective Actions']
            )

    def verify_layout_structure(self, layout, expected_count):
        """Helper method to verify layout structure"""
        self.assertIsNotNone(layout, "Layout should not be None")
        actual_count = layout.count()
        # This makes our test failures better by showing what we expected vs what we got
        self.assertEqual(actual_count, expected_count,
                         f"Layout count mismatch. Expected {expected_count}, got {actual_count}")

    @patch('builtins.open', new_callable=mock_open)
    @patch('displays.cavity_display.utils.utils.parse_csv')
    def test_initialization(self, mock_parse_csv, mock_file):
        # Testing basic setup stuff, .i.e window and main components exists
        mock_data = [
            {'Three Letter Code': 'ABC', 'Long Description': 'Test Description',
             'Generic Short Description for Decoder': 'Test Short', 'Recommended Corrective Actions': 'Test Action'},
            {'Three Letter Code': 'XYZ', 'Long Description': 'Another Description',
             'Generic Short Description for Decoder': 'Another Short',
             'Recommended Corrective Actions': 'Another Action'}
        ]
        mock_parse_csv.return_value = mock_data
        self.populate_rows(mock_data)

        display = DecoderDisplay()
        # Does our window have the right title and components?
        self.assertEqual(display.windowTitle(), "Three Letter Codes")
        self.assertIsNotNone(display.scroll_area)
        self.assertIsNotNone(display.groupbox)

    @patch('builtins.open', new_callable=mock_open)
    @patch('displays.cavity_display.utils.utils.parse_csv')
    def test_layout_creation(self, mock_parse_csv, mock_file):
        # Checking if our layout structure is right, esp for header
        mock_data = [
            {'Three Letter Code': 'ABC', 'Long Description': 'Test Description',
             'Generic Short Description for Decoder': 'Test Short', 'Recommended Corrective Actions': 'Test Action'}
        ]
        mock_parse_csv.return_value = mock_data
        self.populate_rows(mock_data)

        display = DecoderDisplay()
        scroll_area_layout = display.groupbox.layout()
        self.assertIsNotNone(scroll_area_layout)
        # Want to make sure our header has all the right column titles
        header_layout = scroll_area_layout.itemAt(0).layout()
        self.assertIsNotNone(header_layout)
        self.assertEqual(header_layout.count(), 4)
        self.assertEqual(header_layout.itemAt(0).widget().text(), "Code")
        self.assertEqual(header_layout.itemAt(1).widget().text(), "Name")
        self.assertEqual(header_layout.itemAt(2).widget().text(), "Description")
        self.assertEqual(header_layout.itemAt(3).widget().text(), "Corrective Action")

    @patch('builtins.open', new_callable=mock_open)
    @patch('displays.cavity_display.utils.utils.parse_csv')
    def test_visual_properties(self, mock_parse_csv, mock_file):
        mock_data = [{'Three Letter Code': 'ABC', 'Long Description': 'Test Description',
                      'Generic Short Description for Decoder': 'Test Short',
                      'Recommended Corrective Actions': 'Test Action'}]
        mock_parse_csv.return_value = mock_data
        self.populate_rows(mock_data)

        display = DecoderDisplay()
        scroll_area_layout = display.groupbox.layout()

        # Test header styling and properties
        header_layout = scroll_area_layout.itemAt(0).layout()
        header_properties = {
            0: ("Code", 30, 30, QSizePolicy.Preferred),
            1: ("Name", 100, 30, QSizePolicy.Preferred),
            2: ("Description", 100, 30, QSizePolicy.Minimum),
            3: ("Corrective Action", 100, 30, QSizePolicy.Minimum)
        }

        for idx, (text, min_width, min_height, size_policy) in header_properties.items():
            label = header_layout.itemAt(idx).widget()
            # Every header should be underlined & sized right
            self.assertEqual(label.styleSheet(), "text-decoration: underline")
            self.assertEqual(label.minimumSize().width(), min_width)
            self.assertEqual(label.minimumSize().height(), min_height)
            self.assertEqual(label.sizePolicy().horizontalPolicy(), size_policy)
            self.assertEqual(label.sizePolicy().verticalPolicy(), QSizePolicy.Preferred)

        # Checking actual data row properties
        row_layout = scroll_area_layout.itemAt(1).layout()

        # Test description label
        description_label = row_layout.itemAt(2).widget()
        self.assertTrue(description_label.wordWrap())
        self.assertEqual(description_label.minimumSize().width(), 100)
        self.assertEqual(description_label.minimumSize().height(), 50)
        self.assertEqual(description_label.sizePolicy().horizontalPolicy(), QSizePolicy.Minimum)
        self.assertEqual(description_label.sizePolicy().verticalPolicy(), QSizePolicy.Minimum)

        # Same for action
        action_label = row_layout.itemAt(3).widget()
        self.assertTrue(action_label.wordWrap())
        self.assertEqual(action_label.minimumSize().width(), 100)
        self.assertEqual(action_label.minimumSize().height(), 50)
        self.assertEqual(action_label.sizePolicy().horizontalPolicy(), QSizePolicy.Minimum)
        self.assertEqual(action_label.sizePolicy().verticalPolicy(), QSizePolicy.Minimum)

    @patch('builtins.open', new_callable=mock_open)
    @patch('displays.cavity_display.utils.utils.parse_csv')
    def test_scroll_area_configuration(self, mock_parse_csv, mock_file):
        # Making sure our scroll area behaves right
        mock_data = [{'Three Letter Code': 'ABC', 'Long Description': 'Test Description',
                      'Generic Short Description for Decoder': 'Test Short',
                      'Recommended Corrective Actions': 'Test Action'}]
        mock_parse_csv.return_value = mock_data
        self.populate_rows(mock_data)

        display = DecoderDisplay()

        # Test all scroll area properties
        # Vertical scrollbar should always be visible
        self.assertEqual(display.scroll_area.verticalScrollBarPolicy(), Qt.ScrollBarAlwaysOn)
        # Content should resize with the window
        self.assertTrue(display.scroll_area.widgetResizable())
        # Scroll area should adjust to show all the content
        self.assertEqual(display.scroll_area.sizeAdjustPolicy(),
                         QAbstractScrollArea.AdjustToContents)

    @patch('builtins.open', new_callable=mock_open)
    @patch('displays.cavity_display.utils.utils.parse_csv')
    def test_row_creation(self, mock_parse_csv, mock_file):
        # Testing if 1 row of data gets displayed right (does the data show up)
        mock_data = [
            {'Three Letter Code': 'ABC', 'Long Description': 'Test Description',
             'Generic Short Description for Decoder': 'Test Short', 'Recommended Corrective Actions': 'Test Action'}
        ]
        mock_parse_csv.return_value = mock_data
        self.populate_rows(mock_data)

        display = DecoderDisplay()
        scroll_area_layout = display.groupbox.layout()
        # Header + 1 row
        self.verify_layout_structure(scroll_area_layout, 2)
        # Row details
        row_item = scroll_area_layout.itemAt(1)
        self.assertIsNotNone(row_item, "Row item should not be None")
        # Make sure all our data fields show up in the right order
        row_layout = row_item.layout()
        self.assertIsNotNone(row_layout, "Row layout should not be None")
        self.assertEqual(row_layout.count(), 4)
        self.assertEqual(row_layout.itemAt(0).widget().text().strip(), "ABC")
        self.assertEqual(row_layout.itemAt(1).widget().text().strip(), "Test Short")
        self.assertEqual(row_layout.itemAt(2).widget().text().strip(), "Test Description")
        self.assertEqual(row_layout.itemAt(3).widget().text().strip(), "Test Action")

    @patch('builtins.open', new_callable=mock_open)
    @patch('displays.cavity_display.utils.utils.parse_csv')
    def test_multiple_rows_creation(self, mock_parse_csv, mock_file):
        # Now testing with multiple rows
        # Layout should grow right
        mock_data = [
            {'Three Letter Code': 'ABC', 'Long Description': 'Test Description',
             'Generic Short Description for Decoder': 'Test Short', 'Recommended Corrective Actions': 'Test Action'},
            {'Three Letter Code': 'XYZ', 'Long Description': 'Another Description',
             'Generic Short Description for Decoder': 'Another Short',
             'Recommended Corrective Actions': 'Another Action'}
        ]
        mock_parse_csv.return_value = mock_data
        self.populate_rows(mock_data)

        display = DecoderDisplay()
        scroll_area_layout = display.groupbox.layout()
        self.verify_layout_structure(scroll_area_layout, 3)

        row1_layout = scroll_area_layout.itemAt(1).layout()
        self.assertEqual(row1_layout.itemAt(0).widget().text().strip(), "ABC")

        row2_layout = scroll_area_layout.itemAt(2).layout()
        self.assertEqual(row2_layout.itemAt(0).widget().text().strip(), "XYZ")

    @patch('builtins.open', new_callable=mock_open)
    @patch('displays.cavity_display.utils.utils.parse_csv')
    def test_sorting(self, mock_parse_csv, mock_file):
        # Testing if rows get sorted alphabetically by TLC
        mock_data = [
            {'Three Letter Code': 'XYZ', 'Long Description': 'Another Description',
             'Generic Short Description for Decoder': 'Another Short',
             'Recommended Corrective Actions': 'Another Action'},
            {'Three Letter Code': 'ABC', 'Long Description': 'Test Description',
             'Generic Short Description for Decoder': 'Test Short', 'Recommended Corrective Actions': 'Test Action'}
        ]
        mock_parse_csv.return_value = mock_data
        self.populate_rows(mock_data)

        display = DecoderDisplay()
        scroll_area_layout = display.groupbox.layout()
        self.verify_layout_structure(scroll_area_layout, 3)
        # ABC should appear first in the display (bc sorting)
        row1_layout = scroll_area_layout.itemAt(1).layout()
        self.assertEqual(row1_layout.itemAt(0).widget().text().strip(), "ABC")

        row2_layout = scroll_area_layout.itemAt(2).layout()
        self.assertEqual(row2_layout.itemAt(0).widget().text().strip(), "XYZ")

    @patch('builtins.open', new_callable=mock_open)
    @patch('displays.cavity_display.utils.utils.parse_csv')
    def test_empty_csv(self, mock_parse_csv, mock_file):
        # Edge case: what happens when there's no data
        mock_parse_csv.return_value = []
        display = DecoderDisplay()
        scroll_area_layout = display.groupbox.layout()
        # Should just have the header row and nothing else
        self.verify_layout_structure(scroll_area_layout, 1)


if __name__ == '__main__':
    unittest.main()
