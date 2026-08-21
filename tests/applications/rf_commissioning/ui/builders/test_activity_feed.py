"""Tests for ActivityFeedWidget."""

import pytest

from sc_linac_physics.applications.rf_commissioning.ui.builders.activity_feed import (
    ActivityFeedWidget,
)


@pytest.fixture
def feed(qtbot):
    widget = ActivityFeedWidget()
    qtbot.addWidget(widget)
    return widget


def test_starts_empty(feed):
    assert feed.count() == 0


def test_append_increments_count(feed):
    feed.append("Step done")
    assert feed.count() == 1


def test_append_multiple(feed):
    feed.append("First")
    feed.append("Second")
    feed.append("Third")
    assert feed.count() == 3


def test_clear_resets_count(feed):
    feed.append("Step A")
    feed.append("Step B")
    feed.clear()
    assert feed.count() == 0


def test_clear_on_empty_is_safe(feed):
    feed.clear()
    assert feed.count() == 0


def test_append_after_clear(feed):
    feed.append("Before")
    feed.clear()
    feed.append("After")
    assert feed.count() == 1


@pytest.mark.parametrize("entry_type", ["info", "success", "progress", "error"])
def test_valid_entry_types_accepted(feed, entry_type):
    feed.append("message", entry_type=entry_type)
    assert feed.count() == 1


def test_default_entry_type_is_info(feed):
    feed.append("plain message")
    assert feed.count() == 1


def _messages(feed):
    """Return the visible message text of every row, top to bottom."""
    from PyQt5.QtWidgets import QLabel

    texts = []
    # Last item is the trailing stretch, not a row.
    for i in range(feed._feed_layout.count() - 1):
        row = feed._feed_layout.itemAt(i).widget()
        if row is not None:
            texts.append(row.findChildren(QLabel)[1].text())
    return texts


def test_resolve_rewrites_keyed_row_in_place(feed):
    """A step that starts and finishes occupies one row, not two.

    The feed previously showed every substep twice — "▶ Probing stepper
    direction..." followed by "✓ Probing stepper direction" — which doubled its
    length without adding information.
    """
    feed.append("▶ Probing stepper direction...", "progress", key="probe")
    assert feed.count() == 1

    assert feed.resolve("probe", "✓ Probing stepper direction") is True

    assert feed.count() == 1
    assert _messages(feed) == ["✓ Probing stepper direction"]


def test_resolve_unknown_key_appends_instead(feed):
    """An outcome whose start was never logged still has to show up."""
    assert feed.resolve("never-started", "✓ Something") is False
    assert feed.count() == 1
    assert _messages(feed) == ["✓ Something"]


def test_resolve_twice_appends_the_second_time(feed):
    """A key is consumed on resolve, so a repeat cannot silently overwrite."""
    feed.append("▶ Working...", "progress", key="step")
    feed.resolve("step", "✓ Done")
    feed.resolve("step", "✗ Failed", "error")
    assert feed.count() == 2
    assert _messages(feed) == ["✓ Done", "✗ Failed"]


def test_resolve_preserves_unkeyed_rows_around_it(feed):
    feed.append("Stage 2 starting")
    feed.append("▶ Working...", "progress", key="step")
    feed.append("note in between")
    feed.resolve("step", "✓ Done")
    assert _messages(feed) == [
        "Stage 2 starting",
        "✓ Done",
        "note in between",
    ]


def test_clear_forgets_keys(feed):
    feed.append("▶ Working...", "progress", key="step")
    feed.clear()
    assert feed.resolve("step", "✓ Done") is False
    assert feed.count() == 1
