"""Shared style constants for RF commissioning UI builders."""

import sys

if sys.platform == "darwin":
    MONO_FONT_STACK = (
        "'Menlo', 'Monaco', 'Consolas', 'DejaVu Sans Mono', "
        "'Liberation Mono', 'Noto Sans Mono'"
    )
elif sys.platform.startswith("linux"):
    MONO_FONT_STACK = (
        "'DejaVu Sans Mono', 'Liberation Mono', 'Noto Sans Mono', "
        "'Consolas', 'Menlo', 'Monaco'"
    )
else:
    MONO_FONT_STACK = (
        "'Consolas', 'DejaVu Sans Mono', 'Liberation Mono', "
        "'Noto Sans Mono', 'Menlo', 'Monaco'"
    )

PV_LABEL_STYLE = """
    background: #1a2a3a;
    padding: 2px 6px;
    border: 1px solid #4a9eff;
    border-left: 3px solid #4a9eff;
    font-size: 11px;
"""

PV_CAP_STYLE = """
    background-color: #1a2a00;
    padding: 2px 6px;
    border: 1px solid #4a9eff;
    border-left: 3px solid #4a9eff;
    font-family: %s;
    font-size: 11px;
""" % MONO_FONT_STACK

LOCAL_LABEL_STYLE = """
    background: #2a2a1a;
    padding: 2px 6px;
    border: 1px solid #ff9a4a;
    border-left: 3px solid #ff9a4a;
    font-size: 11px;
"""

LOCAL_CAP_STYLE = """
    background-color: #2a2a00;
    padding: 2px 6px;
    border: 1px solid #ff9a4a;
    border-left: 3px solid #ff9a4a;
    font-family: %s;
    font-size: 11px;
""" % MONO_FONT_STACK
