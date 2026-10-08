"""Guard the hand-copied numbers in the auto-tune explainer.

The page is docs/explainers/auto_tune.md, and its simulator is the widget
docs/explainers/widgets/auto_tune_sim.html. The widget restates
stepper_tol_factor's outputs in JavaScript so it works offline, and its
selfCheck() only proves the widget agrees with itself. These tests tie the
widget to the Python and the page to the widget:

- every TOL_ORACLE row is re-derived from the real stepper_tol_factor, so a
  change to linac_utils.py fails here instead of silently making the page lie;
- the figures the page's prose quotes must equal the widget's PROSE_FIGURES,
  which selfCheck() recomputes in the browser;
- the page's failure table must name the same fault and exception pairs as
  the widget's FAILURE_ROWS, which selfCheck() runs in the simulator.
"""

import re
from pathlib import Path

import pytest

from sc_linac_physics.utils.sc_linac.linac_utils import stepper_tol_factor

EXPLAINERS = Path(__file__).resolve().parents[2] / "docs" / "explainers"
PAGE = (EXPLAINERS / "auto_tune.md").read_text(encoding="utf-8")
WIDGET = (EXPLAINERS / "widgets" / "auto_tune_sim.html").read_text(
    encoding="utf-8"
)


def _js_block(name, opener, closer):
    block = re.search(
        rf"const {name} = {re.escape(opener)}(.*?)\n{re.escape(closer)};",
        WIDGET,
        re.S,
    )
    assert block, f"{name} not found in the widget"
    return block.group(1)


def _oracle_rows():
    """Pull the [num_steps, expected] pairs out of the widget's TOL_ORACLE."""
    pairs = re.findall(
        r"\[\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]",
        _js_block("TOL_ORACLE", "[", "]"),
    )
    return [(int(n), float(want)) for n, want in pairs]


def test_oracle_row_count():
    """Guard the regex, not the oracle's size.

    A range, not a pin: adding a legitimate oracle row is good behaviour and
    must not fail here. The lower bound catches the regex silently matching
    nothing (renamed const, reformatted block); the upper bound catches it
    matching far too much, e.g. a greedy match that swallowed the array
    literals in the rest of the script.
    """
    assert 14 <= len(_oracle_rows()) < 100


@pytest.mark.parametrize("num_steps,expected", _oracle_rows())
def test_oracle_matches_python(num_steps, expected):
    assert stepper_tol_factor(num_steps) == pytest.approx(expected, abs=1e-5)


def test_prose_figures_match_widget():
    """The page quotes the simulator's numbers; they must be the same ones."""
    widget = dict(
        re.findall(
            r'"(fig-[a-z-]+)":\s*"([^"]*)"',
            _js_block("PROSE_FIGURES", "{", "}"),
        )
    )
    page = dict(
        re.findall(r'<span data-fig="(fig-[a-z-]+)">([^<]*)</span>', PAGE)
    )
    assert len(widget) >= 10, "PROSE_FIGURES regex matched too little"
    assert page == widget


def _failure_table():
    """(fault, raises) for each section 6 row that names a simulator fault."""
    section = PAGE[PAGE.index("## 6. How it fails") :]
    rows = []
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4 or not cells[3].startswith("`"):
            continue
        rows.append((cells[3].strip("`"), cells[1].strip("`")))
    return rows


def test_failure_table_matches_widget():
    """A fault on the wrong row shows the reader the other abort path."""
    widget = re.findall(
        r'\["([a-z_]+)",\s*"([A-Za-z]+)"\]',
        _js_block("FAILURE_ROWS", "[", "]"),
    )
    page = [(f, r) for f, r in _failure_table() if not r.startswith("—")]
    assert len(widget) >= 5, "FAILURE_ROWS regex matched too little"
    assert sorted(page) == sorted(widget)


def test_failure_table_faults_exist():
    """Every fault the table tells a reader to pick is in the simulator menu."""
    labels = set(
        re.findall(r"^  ([a-z_]+): ", _js_block("FAULT_LABELS", "{", "}"), re.M)
    )
    assert labels, "FAULT_LABELS regex matched nothing"
    for fault, _ in _failure_table():
        assert fault in labels
