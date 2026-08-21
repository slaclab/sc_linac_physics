"""Guard the hand-copied constants in docs/explainers/auto_tune.html.

The explainer restates stepper_tol_factor's outputs in JavaScript so the page
works offline. Its in-page selfCheck() only proves the page agrees with itself.
These tests re-derive every oracle row from the real Python function, so a
change to linac_utils.py fails here instead of silently making the page lie.
"""

import re
from pathlib import Path

import pytest

from sc_linac_physics.utils.sc_linac.linac_utils import stepper_tol_factor

EXPLAINER = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "explainers"
    / "auto_tune.html"
)
HTML = EXPLAINER.read_text()


def _oracle_rows():
    """Pull the [num_steps, expected] pairs out of the page's TOL_ORACLE."""
    block = re.search(r"const TOL_ORACLE = \[(.*?)\n\];", HTML, re.S)
    assert block, "TOL_ORACLE not found in the explainer"
    pairs = re.findall(r"\[\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]", block.group(1))
    return [(int(n), float(want)) for n, want in pairs]


def test_oracle_row_count():
    assert len(_oracle_rows()) == 14


@pytest.mark.parametrize("num_steps,expected", _oracle_rows())
def test_oracle_matches_python(num_steps, expected):
    assert stepper_tol_factor(num_steps) == pytest.approx(expected, abs=1e-5)


def test_no_inner_html():
    """A repo hook rejects innerHTML; the page builds DOM via createElement."""
    assert "innerHTML" not in HTML


def test_no_external_references():
    """The page is opened offline on control-room machines."""
    assert not re.search(r"https?://", HTML)
