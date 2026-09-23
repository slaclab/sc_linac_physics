import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatch

from scipy.optimize import curve_fit
from sc_linac_physics.applications.field_emission.measurements import (
    get_columns,
)
from sc_linac_physics.applications.field_emission.constants import (
    NUM_FIT_POINTS,
    NUM_FIT_ITERATIONS,
)


def plot_amp_vs_rad(df, ax, r_channels, fit):
    """plot amplitude on x-axis and radiation on y-axis, locking colors to channels"""
    x_amplitude, rad_cols = get_columns(df, r_channels)
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    fit_patches = []

    for col in rad_cols.columns:
        label = f"Ch {col}"
        color = color_cycle[(col - 1) % len(color_cycle)]
        y_rad = rad_cols[col]
        ax.scatter(x_amplitude, y_rad, label=label, marker=".", color=color)
        if fit:
            mask = (
                (y_rad > 0) & np.isfinite(x_amplitude) & np.isfinite(y_rad)
            )  # filter for 0 and NaN
            x = x_amplitude[mask].to_numpy()
            y = y_rad[mask].to_numpy()
            result = add_poly_fit(x, y, ax, label, color=color)
            if result is not None:
                _, patch = result
                fit_patches.append(patch)

    if fit_patches:
        ax.legend(handles=fit_patches, loc="upper left", fontsize="x-small")
    plt.setp(ax.get_xticklabels(), fontsize="x-small")
    plt.setp(ax.get_yticklabels(), fontsize="x-small")
    ax.grid(True)


def fit_equation(amp, c1, c2):
    """fit line equation currently y = C1(E0)^(2.5) * exp(-C2/E0)"""
    return c1 * (amp**2.5) * np.exp((-c2) / amp)


def add_poly_fit(amp, rad, axis, label, color):
    """overlay amp vs rad plot with polynomial fit"""
    if rad.size < 2:  # skip fitting when less than two samples are available
        return None
    try:
        param, param_covar = curve_fit(
            fit_equation, amp, rad, maxfev=NUM_FIT_ITERATIONS
        )
    except RuntimeError:
        print("RuntimeError: fit did not converge. Skipping channel")
        return None

    x = np.linspace(amp.min(), amp.max(), NUM_FIT_POINTS)
    y = fit_equation(x, *param)
    (line,) = axis.plot(x, y, ls="-", label=label, color=color)
    patch = mpatch.Patch(
        color=color, label=f"C1: {param[0]:.1g}    C2: {param[1]:.1f}"
    )
    return line, patch


def unify_legends(axes):
    """combine legend labels from subplots into one joint legend"""
    # Build summary legend
    all_handles = []
    all_labels = []
    for ax in axes:
        handles, labels = ax.get_legend_handles_labels()
        for h, l in zip(handles, labels):
            if l not in all_labels:
                all_handles.append(h)
                all_labels.append(l)
    return all_handles, all_labels


def unify_axes(axes):
    """plot all subplots on a common pair of axes for easier comparison"""
    if not axes:
        return

    # Find the overall min/max across every subplot
    x_mins, x_maxs, y_mins, y_maxs = [], [], [], []
    for ax in axes:
        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()
        x_mins.append(x_min)
        x_maxs.append(x_max)
        y_mins.append(y_min)
        y_maxs.append(y_max)

    x_range = (min(x_mins), max(x_maxs))
    y_range = (min(y_mins), max(y_maxs))

    for ax in axes:
        ax.set_xlim(x_range)
        ax.set_ylim(y_range)
