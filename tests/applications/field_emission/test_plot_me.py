import numpy as np
import pandas as pd
import pytest
import matplotlib
import matplotlib.pyplot as plt
from unittest.mock import patch, MagicMock

from sc_linac_physics.applications.field_emission import plot_me
# Use a non-interactive backend so tests never try to open a window.
matplotlib.use("Agg")


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "amps": [3.0, 7.0, 5.0, 2.0],
        "ch1": [0.0, 0.4, 1.6, 2.4],
        "ch2": [0.4, 0.4, 0.8, 1.6],
        "ch3": [0.8, 2.4, 1.6, 1.2],
    })


@pytest.fixture
def three_channel_mask():
    # first three radiation channels selected
    return [True, True, True, False, False, False, False, False, False, False]


@pytest.fixture(autouse=True)
def close_all_figs():
    """Ensure no figures leak between tests."""
    yield
    plt.close("all")


# ===========================================================================
# fit_equation
# ===========================================================================
class TestFitEquation:
    def test_returns_array_matching_input_shape(self):
        amps = np.array([3.0, 7.0, 5.0, 2.0])
        out = plot_me.fit_equation(amps, 1.0, 1.0)
        assert out.shape == amps.shape

    def test_all_finite_for_positive_amps(self):
        amps = np.array([3.0, 7.0, 5.0, 2.0])
        out = plot_me.fit_equation(amps, 1.0, 1.0)
        assert np.all(np.isfinite(out))

    def test_matches_closed_form_math(self):
        # y = c1 * amp^2.5 * exp(-c2/amp)
        amp = np.array([4.0])
        c1, c2 = 2.0, 3.0
        expected = c1 * (amp ** 2.5) * np.exp(-c2 / amp)
        out = plot_me.fit_equation(amp, c1, c2)
        np.testing.assert_allclose(out, expected, rtol=1e-12)

    def test_scalar_input(self):
        val = plot_me.fit_equation(5.0, 1.0, 1.0)
        expected = 1.0 * (5.0 ** 2.5) * np.exp(-1.0 / 5.0)
        assert np.isclose(val, expected)

    def test_zero_c1_gives_zeros(self):
        amps = np.array([1.0, 2.0, 3.0])
        out = plot_me.fit_equation(amps, 0.0, 1.0)
        np.testing.assert_array_equal(out, np.zeros_like(amps))


# ===========================================================================
# add_poly_fit
# ===========================================================================
class TestAddPolyFit:
    def test_empty_dataset_returns_none_none(self):
        fig, ax = plt.subplots()
        result = plot_me.add_poly_fit(np.array([]), np.array([]), ax, "blue")
        assert result == (None, None)
        assert len(ax.lines) == 0

    def test_successful_fit_returns_params_and_covariance(self):
        fig, ax = plt.subplots()
        # Generate data that follows the fit equation exactly -> guaranteed convergence
        amp = np.linspace(2.0, 10.0, 30)
        rad = plot_me.fit_equation(amp, 1.5, 4.0)
        param, covar = plot_me.add_poly_fit(amp, rad, ax, "red")
        assert param is not None
        assert covar is not None
        assert len(param) == 2
        # recovered coefficients should be close to the ones we generated with
        np.testing.assert_allclose(param, [1.5, 4.0], rtol=1e-2)

    def test_successful_fit_draws_one_line(self):
        fig, ax = plt.subplots()
        amp = np.linspace(2.0, 10.0, 30)
        rad = plot_me.fit_equation(amp, 1.5, 4.0)
        plot_me.add_poly_fit(amp, rad, ax, "green")
        assert len(ax.lines) == 1

    def test_fit_line_has_250_points(self):
        fig, ax = plt.subplots()
        amp = np.linspace(2.0, 10.0, 30)
        rad = plot_me.fit_equation(amp, 1.0, 2.0)
        plot_me.add_poly_fit(amp, rad, ax, "blue")
        xdata = ax.lines[0].get_xdata()
        assert len(xdata) == 250

    def test_runtime_error_returns_none_none(self):
        """If curve_fit raises RuntimeError (no convergence), gracefully return."""
        fig, ax = plt.subplots()
        amp = np.array([1.0, 2.0, 3.0])
        rad = np.array([1.0, 2.0, 3.0])
        with patch.object(plot_me, "curve_fit",
                          side_effect=RuntimeError("no convergence")):
            result = plot_me.add_poly_fit(amp, rad, ax, "blue")
        assert result == (None, None)
        assert len(ax.lines) == 0

    def test_curve_fit_called_with_maxfev(self):
        fig, ax = plt.subplots()
        amp = np.array([2.0, 3.0, 4.0])
        rad = np.array([1.0, 2.0, 3.0])
        fake_param = np.array([1.0, 1.0])
        fake_covar = np.eye(2)
        with patch.object(plot_me, "curve_fit",
                          return_value=(fake_param, fake_covar)) as mock_fit:
            plot_me.add_poly_fit(amp, rad, ax, "blue")
        assert mock_fit.called
        # maxfev is passed as a keyword in the source
        _, kwargs = mock_fit.call_args
        assert kwargs.get("maxfev") == 5500


# ===========================================================================
# plot_amp_vs_rad  (using the real get_columns via a real DataFrame)
# ===========================================================================
class TestPlotAmpVsRadRealColumns:
    """
    These mirror your original tests and exercise the real get_columns path.
    """

    def test_one_scatter_per_channel(self, sample_df, three_channel_mask):
        fig, ax = plt.subplots()
        plot_me.plot_amp_vs_rad(sample_df, ax, three_channel_mask, False)
        assert len(ax.collections) == 3

    def test_no_fit_when_false(self, sample_df, three_channel_mask):
        fig, ax = plt.subplots()
        plot_me.plot_amp_vs_rad(sample_df, ax, three_channel_mask, fit=False)
        assert len(ax.collections) == 3
        assert len(ax.lines) == 0

    def test_line_when_fit_true(self, sample_df, three_channel_mask):
        fig, ax = plt.subplots()
        plot_me.plot_amp_vs_rad(sample_df, ax, three_channel_mask, fit=True)
        assert len(ax.collections) == 3
        assert len(ax.lines) >= 1

    def test_grid_enabled(self, sample_df, three_channel_mask):
        fig, ax = plt.subplots()
        plot_me.plot_amp_vs_rad(sample_df, ax, three_channel_mask, False)
        # At least one axis has gridlines visible
        x_grid_on = any(g.get_visible() for g in ax.get_xgridlines())
        y_grid_on = any(g.get_visible() for g in ax.get_ygridlines())
        assert x_grid_on and y_grid_on

    def test_scatter_labels_present(self, sample_df, three_channel_mask):
        fig, ax = plt.subplots()
        plot_me.plot_amp_vs_rad(sample_df, ax, three_channel_mask, False)
        handles, labels = ax.get_legend_handles_labels()
        assert len(labels) == 3
        assert all(label.startswith("Ch ") for label in labels)


# ===========================================================================
# plot_amp_vs_rad  (mocking get_columns to isolate plotting logic)
# ===========================================================================
class TestPlotAmpVsRadMockedColumns:
    """
    Mock get_columns so we control exactly what x/y data plot_amp_vs_rad sees.
    Contract assumed: get_columns(df, r_channels) -> (x_amplitude_Series, rad_DataFrame)
    """

    def _mock_columns(self, x_vals, rad_dict):
        x = pd.Series(x_vals)
        rad = pd.DataFrame(rad_dict)
        return x, rad

    def test_no_channels_no_scatter(self):
        fig, ax = plt.subplots()
        x, rad = self._mock_columns([1.0, 2.0], {})  # empty rad DataFrame
        with patch.object(plot_me, "get_columns", return_value=(x, rad)):
            plot_me.plot_amp_vs_rad(MagicMock(), ax, [False] * 10, False)
        assert len(ax.collections) == 0

    def test_calls_add_poly_fit_once_per_channel_when_fit(self):
        fig, ax = plt.subplots()
        x, rad = self._mock_columns(
            [1.0, 2.0, 3.0],
            {"ch1": [0.1, 0.2, 0.3], "ch2": [0.5, 0.6, 0.7]},
        )
        with patch.object(plot_me, "get_columns", return_value=(x, rad)), \
             patch.object(plot_me, "add_poly_fit",
                          return_value=(np.array([1, 1]), np.eye(2))) as mock_fit:
            plot_me.plot_amp_vs_rad(MagicMock(), ax, [True] * 10, fit=True)
        assert mock_fit.call_count == 2

    def test_add_poly_fit_not_called_when_no_fit(self):
        fig, ax = plt.subplots()
        x, rad = self._mock_columns(
            [1.0, 2.0, 3.0],
            {"ch1": [0.1, 0.2, 0.3]},
        )
        with patch.object(plot_me, "get_columns", return_value=(x, rad)), \
             patch.object(plot_me, "add_poly_fit") as mock_fit:
            plot_me.plot_amp_vs_rad(MagicMock(), ax, [True] * 10, fit=False)
        mock_fit.assert_not_called()

    def test_fit_mask_filters_zero_and_nan(self):
        """
        The fit mask keeps only y>0 and finite x & y.
        Given the data below, only rows with y>0 and finite x/y survive.
        """
        fig, ax = plt.subplots()
        x = pd.Series([1.0, 2.0, np.nan, 4.0, 5.0])
        rad = pd.DataFrame({"ch1": [0.0, 3.0, 4.0, np.nan, 6.0]})
        with patch.object(plot_me, "get_columns", return_value=(x, rad)), \
             patch.object(plot_me, "add_poly_fit",
                          return_value=(None, None)) as mock_fit:
            plot_me.plot_amp_vs_rad(MagicMock(), ax, [True] * 10, fit=True)

        # Inspect the filtered arrays passed into add_poly_fit
        args = mock_fit.call_args.args
        x_passed, y_passed = args[0], args[1]
        # Row-by-row: (y>0 & finite x & finite y)
        #   idx0: y=0    -> excluded
        #   idx1: y=3, x=2 finite -> included
        #   idx2: x=NaN  -> excluded
        #   idx3: y=NaN  -> excluded
        #   idx4: y=6, x=5 finite -> included
        np.testing.assert_array_equal(x_passed, np.array([2.0, 5.0]))
        np.testing.assert_array_equal(y_passed, np.array([3.0, 6.0]))

    def test_colors_cycle_and_repeat(self):
        """More channels than colors -> colors wrap using modulo."""
        fig, ax = plt.subplots()
        color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        n = len(color_cycle) + 2  # force wraparound
        rad_dict = {f"ch{i}": list(np.random.rand(3)) for i in range(n)}
        x, rad = pd.Series([1.0, 2.0, 3.0]), pd.DataFrame(rad_dict)

        with patch.object(plot_me, "get_columns", return_value=(x, rad)):
            plot_me.plot_amp_vs_rad(MagicMock(), ax, [True] * 10, fit=False)

        assert len(ax.collections) == n
        first = ax.collections[0].get_facecolor()[0]
        wrapped = ax.collections[len(color_cycle)].get_facecolor()[0]
        # channel 0 and channel len(color_cycle) should share the same color
        np.testing.assert_allclose(first, wrapped, atol=1e-6)


# ===========================================================================
# Integration-ish: fit line actually overlays scatter for real data
# ===========================================================================
class TestPlotIntegration:
    def test_fit_line_within_plot_when_convergent(self, sample_df):
        """
        Use a single channel that follows the fit model so curve_fit converges,
        then confirm a fit line was drawn on top of the scatter.
        """
        amp = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
        rad = plot_me.fit_equation(amp, 1.0, 3.0)
        df = pd.DataFrame({"amps": amp, "ch1": rad})
        mask = [True] + [False] * 9

        fig, ax = plt.subplots()
        plot_me.plot_amp_vs_rad(df, ax, mask, fit=True)
        assert len(ax.collections) == 1  # scatter
        assert len(ax.lines) == 1        # fit line
        plt.close(fig)
