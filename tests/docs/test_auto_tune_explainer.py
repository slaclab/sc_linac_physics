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
HTML = EXPLAINER.read_text(encoding="utf-8")


def _oracle_rows():
    """Pull the [num_steps, expected] pairs out of the page's TOL_ORACLE."""
    block = re.search(r"const TOL_ORACLE = \[(.*?)\n\];", HTML, re.S)
    assert block, "TOL_ORACLE not found in the explainer"
    pairs = re.findall(r"\[\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\]", block.group(1))
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


def test_no_inner_html():
    """A repo hook rejects innerHTML; the page builds DOM via createElement."""
    assert "innerHTML" not in HTML


# Anything the browser fetches in order to render: script, stylesheet, webfont,
# image, media. Protocol-relative "//host/..." counts.
EXTERNAL_LOAD = re.compile(
    r"<(?:script|link|img|iframe|embed|source|audio|video|object)\b[^>]*?"
    r"\b(?:src|href|data)\s*=\s*[\"']?\s*(?:https?:)?//",
    re.I,
)


def test_no_external_resource_loads():
    """The page must render and run with no network.

    Deliberately narrower than "no URLs anywhere", which is what this asserted
    first and which banned the thing the page most needs: a citation for the
    hardware numbers it quotes. A URL a reader may follow later costs nothing
    offline -- at worst the click fails. What breaks a control-room machine
    with no route out is a *load*, because the page then renders wrong or
    hangs waiting for it.
    """
    assert not EXTERNAL_LOAD.search(HTML)


def test_no_external_css_urls():
    """@font-face and background-image fetches are loads too."""
    assert not re.search(r"url\(\s*[\"']?\s*(?:https?:)?//", HTML, re.I)


@pytest.mark.parametrize(
    "markup",
    [
        '<script src="https://cdn.example/x.js"></script>',
        '<link rel="stylesheet" href="https://fonts.example/f.css">',
        '<link rel="stylesheet" href="//fonts.example/f.css">',
        '<img src="http://example.test/x.png">',
        '<iframe src="https://example.test/"></iframe>',
    ],
)
def test_external_load_guard_catches_loads(markup):
    """The guard is a regex, so pin what it must still catch.

    Narrowing it from "no URLs anywhere" is only safe if it still fails on the
    thing that actually breaks offline.
    """
    assert EXTERNAL_LOAD.search(markup)


@pytest.mark.parametrize(
    "markup",
    [
        '<a href="https://proceedings.jacow.org/IPAC2015/papers/wepty035.pdf">W</a>',
        "<p>See https://example.test/paper.pdf for the measurement.</p>",
        "// https://example.test/paper.pdf",
    ],
)
def test_external_load_guard_allows_citations(markup):
    """A URL a reader may follow later is not a load."""
    assert not EXTERNAL_LOAD.search(markup)
