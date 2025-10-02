from typing import Dict, List, Optional, Callable, Tuple, Any, Union

from PyQt5.QtWidgets import QTabWidget
from PyQt5.QtWidgets import (
    QWidget,
    QCheckBox,
    QLabel,
    QPushButton,
    QProgressBar,
    QLayout,
    QGridLayout,
)


def create_checkboxes(
    parent: "QWidget",
    items: Dict[int, str],
    layout: QLayout,
    checked: bool = False,
    enabled: bool = True,
    callback: Optional[Callable] = None,
    grid_layout: bool = False,
    max_cols: int = 4,
) -> Dict[int, QCheckBox]:
    """
    Create group of checkboxes w/ consistent configuration
    Args:
        parent: Parent Widget
        items: Dictionary mapping identifier to label text
        layout: Layout to add checkboxes to
        checked: Initial checked state
        enabled: Initial enabled state
        callback: Optional callback function for stateChanged signal
        grid_layout: If True, arrange in grid pattern
        max_cols: Maximum columns when using grid layout
     Returns:
        Dictionary of created QCheckbox widgets indexed by their identifiers
    """
    checkboxes = {}
    # If grid layout is True and layout is not a QGridLayout
    if grid_layout and not isinstance(layout, QGridLayout):
        raise TypeError("Grid layout required for grid_layout=True")

    row = col = 0
    for item_id, label in items.items():
        checkbox = QCheckBox(label)
        checkbox.setChecked(checked)
        checkbox.setEnabled(enabled)
        if callback:
            checkbox.stateChanged.connect(callback)
        checkboxes[item_id] = checkbox
        if grid_layout:
            layout.addWidget(checkbox, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        else:
            layout.addWidget(checkbox)
    return checkboxes


def create_pushbuttons(
    parent: QWidget,
    items: Dict[Any, str],
    layout: QLayout,
    checkable: bool = False,
    connect_to: Optional[Callable] = None,
    custom_properties: Optional[Dict[str, Dict[str, Any]]] = None,
    grid_layout: bool = False,
    max_cols: int = 4,
) -> Dict[Any, QPushButton]:
    """
    Create group of push buttons w/ consistent configuration.

    Args:
        parent: Parent widget
        items: Dictionary mapping identifier to button text
        layout: Layout to add buttons to
        checkable: Whether buttons should be checkable
        connect_to: Function to connect clicked signal to (will be called with the item_id)
        custom_properties: Dictionary mapping item_id to dict of custom properties to set
        grid_layout: If True, arrange in grid pattern
        max_cols: Maximum columns when using grid layout

    Returns:
        Dictionary of created QPushButton widgets indexed by their identifiers
    """
    buttons = {}

    if grid_layout and not isinstance(layout, QGridLayout):
        raise TypeError("Grid layout required for grid_layout=True")

    row = col = 0
    for item_id, text in items.items():
        btn = QPushButton(text)
        btn.setCheckable(checkable)

        if connect_to:
            btn.clicked.connect(lambda checked, btn_id=item_id: connect_to(btn_id))

        if custom_properties and item_id in custom_properties:
            for prop_name, prop_value in custom_properties[item_id].items():
                btn.setProperty(prop_name, prop_value)

        buttons[item_id] = btn

        if grid_layout:
            layout.addWidget(btn, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        else:
            layout.addWidget(btn)

    return buttons


def create_status_widgets(
    parent: QWidget,
    items: List[int],
    grid_layout: QGridLayout,
    headers: List[str] = ["Cavity", "Status", "Progress", "Message"],
    initial_status: str = "Not configured",
    initial_message: str = "",
) -> Dict[int, Dict[str, QWidget]]:
    """
    Create status widgets (labels, progress bars) for items like cavities.

    Args:
        parent: Parent widget
        items: List of item identifiers (like cavity numbers)
        grid_layout: Grid layout to add widgets to
        headers: Header labels for columns
        initial_status: Initial status text
        initial_message: Initial message text

    Returns:
        Nested dictionary of created widgets
    """
    # Add headers
    for col, header in enumerate(headers):
        label = QLabel(header)
        label.setStyleSheet("font-weight: bold")
        grid_layout.addWidget(label, 0, col)

    # Create status widgets for each item
    status_widgets = {}
    for row, item_id in enumerate(items, 1):
        # Item identifier/number
        grid_layout.addWidget(QLabel(f"Cavity {item_id}"), row, 0)

        # Status label
        status_label = QLabel(initial_status)
        grid_layout.addWidget(status_label, row, 1)

        # Progress bar
        progress_bar = QProgressBar()
        progress_bar.setMinimum(0)
        progress_bar.setMaximum(100)
        grid_layout.addWidget(progress_bar, row, 2)

        # Message label
        msg_label = QLabel(initial_message)
        grid_layout.addWidget(msg_label, row, 3)

        # Store references to widgets
        status_widgets[item_id] = {
            "status": status_label,
            "progress": progress_bar,
            "message": msg_label,
        }

    return status_widgets


def create_cavity_selection_tabs(
    parent: QWidget,
    rack_config: Dict[str, Dict[str, Union[str, List[int]]]],
    select_all_callback: Callable[[str], None],
) -> Tuple[Dict[str, Dict[int, QCheckBox]], Dict[str, QPushButton]]:
    """
    Create cavity selection tabs with select all buttons for each rack.

    Args:
        parent: Parent widget
        rack_config: Configuration for each rack
                     Example: {
                        'A': {'title': 'Rack A (1-4)', 'cavities': [1, 2, 3, 4]},
                        'B': {'title': 'Rack B (5-8)', 'cavities': [5, 6, 7, 8]}
                     }
        select_all_callback: Callback function for select all button clicks

    Returns:
        Tuple of (cavity_checkboxes, select_all_buttons)
    """

    tabs = QTabWidget(parent)
    cavity_checkboxes = {}
    select_all_buttons = {}

    for rack_id, config in rack_config.items():
        tab = QWidget()
        layout = QGridLayout(tab)

        # Create cavity checkboxes
        cavity_items = {cav_num: f"Cavity {cav_num}" for cav_num in config["cavities"]}
        checkboxes = create_checkboxes(
            tab,
            cavity_items,
            layout,
            grid_layout=True,
            max_cols=len(config["cavities"]),
        )
        cavity_checkboxes[rack_id] = checkboxes

        # Create Select All button
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(lambda _, r=rack_id: select_all_callback(r))
        layout.addWidget(select_all_btn, 1, 0, 1, len(config["cavities"]))  # Span all columns
        select_all_buttons[rack_id] = select_all_btn

        tabs.addTab(tab, config["title"])

    return cavity_checkboxes, select_all_buttons
