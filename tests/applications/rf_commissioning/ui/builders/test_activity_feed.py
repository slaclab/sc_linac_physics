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


@pytest.mark.parametrize("entry_type", ["info", "success", "progress"])
def test_valid_entry_types_accepted(feed, entry_type):
    feed.append("message", entry_type=entry_type)
    assert feed.count() == 1


def test_default_entry_type_is_info(feed):
    feed.append("plain message")
    assert feed.count() == 1
