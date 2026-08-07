import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from sc_linac_physics.applications.field_emission import plot_me


def test_plot_amp_vs_rad_one_scatter_per_channel():
    dset = pd.DataFrame({
        "amps": [3.0, 7.0, 5.0, 2.0],
        "ch1": [0.0, 0.4, 1.6, 2.4],
        "ch2": [0.4, 0.4, 0.8, 1.6],
        "ch3": [0.8, 2.4, 1.6, 1.2]
    })
    r_channels = [True, True, True, False, False, False, False, False, False, False]
    fig, ax = plt.subplots()
    plot_me.plot_amp_vs_rad(dset, ax, r_channels,False)
    assert len(ax.collections) == 3, (
        f"Expected 3 scatter series, got {len(ax.collections)}"
    )
    plt.close(fig)

def test_plot_amp_vs_rad_no_fit_when_false():
    dset = pd.DataFrame({
        "amps": [3.0, 7.0, 5.0, 2.0],
        "ch1": [0.0, 0.4, 1.6, 2.4],
        "ch2": [0.4, 0.4, 0.8, 1.6],
        "ch3": [0.8, 2.4, 1.6, 1.2]
    })
    r_channels = [True, True, True, False, False, False, False, False, False, False]
    fig, ax = plt.subplots()
    plot_me.plot_amp_vs_rad(dset, ax, r_channels, fit=False)
    assert len(ax.collections) == 3
    assert len(ax.lines) == 0
    plt.close(fig)

def test_plot_amp_vs_rad_line_when_fit_true():
    dset = pd.DataFrame({
        "amps": [3.0, 7.0, 5.0, 2.0],
        "ch1": [0.0, 0.4, 1.6, 2.4],
        "ch2": [0.4, 0.4, 0.8, 1.6],
        "ch3": [0.8, 2.4, 1.6, 1.2]
    })
    r_channels = [True, True, True, False, False, False, False, False, False, False]
    fig, ax = plt.subplots()
    plot_me.plot_amp_vs_rad(dset, ax, r_channels, fit=True)
    assert len(ax.collections) == 3
    assert len(ax.lines) >= 1
    plt.close(fig)

def test_fit_equation_takes_arrays():
    amps = np.array([3.0, 7.0, 5.0, 2.0])
    results = plot_me.fit_equation(amps, 1.0, 1.0)
    assert results.shape == amps.shape

def test_fit_equation_is_finite():
    amps = np.array([3.0, 7.0, 5.0, 2.0])
    results = plot_me.fit_equation(amps, 1.0, 1.0)
    assert np.all(np.isfinite(results))

def test_add_poly_fit_returns_none_for_empty_dataset():
    fig, ax = plt.subplots()
    result = plot_me.add_poly_fit(np.array([]), np.array([]), ax, "blue")
    assert result == (None, None)
    plt.close(fig)