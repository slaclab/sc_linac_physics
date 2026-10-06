"""Matplotlib helpers for data from utils/archiver.py."""

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from sc_linac_physics.utils.archiver import LOCAL_TZ


def plot_over_time(*series: pd.Series, ax=None):
    """Plot each Series against time, each with its own y-axis.

    Archived values hold until the next sample, so they are drawn as steps.
    The y-axes are labelled with the Series' names, in matching colors.
    Returns (fig, list of axes).
    """
    if ax is None:
        _, ax = plt.subplots()
    axes = [ax] + [ax.twinx() for _ in series[1:]]
    for i, (axis, data) in enumerate(zip(axes, series)):
        color = f"C{i}"
        axis.step(data.index, data.to_numpy(), where="post", color=color)
        axis.set_ylabel(data.name, color=color)
        if i > 1:  # stack extra right-hand axes outward so labels don't clash
            axis.spines["right"].set_position(("outward", 60 * (i - 1)))
    # matplotlib's default labels show only the day of month and the time.
    # This puts times on the ticks and the full date once, at the axis end.
    locator = mdates.AutoDateLocator(tz=LOCAL_TZ)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(
        mdates.ConciseDateFormatter(locator, tz=LOCAL_TZ)
    )
    return ax.figure, axes
