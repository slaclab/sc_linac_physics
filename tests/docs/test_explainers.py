"""Checks every page in docs/explainers/ must pass.

Explainers are opened on control-room machines that may have no route out,
so a page must render and run with nothing fetched from the network.

There is no innerHTML rule. The pages insert only strings they contain
themselves, so there is nothing for innerHTML to inject.
"""

import re
from pathlib import Path

import pytest

EXPLAINERS = sorted(
    (Path(__file__).resolve().parents[2] / "docs" / "explainers").glob("*.html")
)

# Anything the browser fetches in order to render: script, stylesheet, webfont,
# image, media. Protocol-relative "//host/..." counts.
EXTERNAL_LOAD = re.compile(
    r"<(?:script|link|img|iframe|embed|source|audio|video|object)\b[^>]*?"
    r"\b(?:src|href|data)\s*=\s*[\"']?\s*(?:https?:)?//",
    re.I,
)
EXTERNAL_CSS_URL = re.compile(r"url\(\s*[\"']?\s*(?:https?:)?//", re.I)


def test_explainers_found():
    """Guard the glob: a moved directory must not pass by checking nothing."""
    assert EXPLAINERS


@pytest.mark.parametrize("page", EXPLAINERS, ids=lambda p: p.name)
def test_no_external_resource_loads(page):
    """The page must render and run with no network.

    Deliberately narrower than "no URLs anywhere", which is what this asserted
    first and which banned the thing the page most needs: a citation for the
    hardware numbers it quotes. A URL a reader may follow later costs nothing
    offline -- at worst the click fails. What breaks a control-room machine
    with no route out is a *load*, because the page then renders wrong or
    hangs waiting for it.
    """
    assert not EXTERNAL_LOAD.search(page.read_text(encoding="utf-8"))


@pytest.mark.parametrize("page", EXPLAINERS, ids=lambda p: p.name)
def test_no_external_css_urls(page):
    """@font-face and background-image fetches are loads too."""
    assert not EXTERNAL_CSS_URL.search(page.read_text(encoding="utf-8"))


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


def test_css_url_guard_catches_fetch():
    assert EXTERNAL_CSS_URL.search(
        "@font-face { src: url('https://fonts.example/f.woff2'); }"
    )
