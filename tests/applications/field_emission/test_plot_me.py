import numpy as np
import pandas as pd
import pytest
import matplotlib.pyplot as plt
import matplotlib.patches as mpatch
from unittest.mock import patch, MagicMock

from sc_linac_physics.applications.field_emission import plot_me


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------
@pytest.fixture
def sample_df():
    # NOTE: the new plot code treats column names as integers (col - 1),
    # so radiation channels must be integer-labeled columns.
    return pd.DataFrame(
        {
            "amps": [3.0, 7.0, 5.0, 2.0],
            1: [0.0, 0.4, 1.6, 2.4],
            2: [0.4, 0.4, 0.8, 1.6],
            3: [0.8, 2.4, 1.6, 1.2],
        }
    )


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
        expected = c1 * (amp**2.5) * np.exp(-c2 / amp)
        out = plot_me.fit_equation(amp, c1, c2)
        np.testing.assert_allclose(out, expected, rtol=1e-12)

    def test_scalar_input(self):
        val = plot_me.fit_equation(5.0, 1.0, 1.0)
        expected = 1.0 * (5.0**2.5) * np.exp(-1.0 / 5.0)
        assert np.isclose(val, expected)

    def test_zero_c1_gives_zeros(self):
        amps = np.array([1.0, 2.0, 3.0])
        out = plot_me.fit_equation(amps, 0.0, 1.0)
        np.testing.assert_array_equal(out, np.zeros_like(amps))


# ===========================================================================
# add_poly_fit
# ===========================================================================
class TestAddPolyFit:
    def test_empty_dataset_returns_none(self):
        fig, ax = plt.subplots()
        result = plot_me.add_poly_fit(
            np.array([]), np.array([]), ax, "Title", color="blue"
        )
        assert result is None
        assert len(ax.lines) == 0

    def test_successful_fit_returns_line_and_patch(self):
        fig, ax = plt.subplots()
        # Generate data that follows the fit equation exactly -> guaranteed convergence
        amp = np.linspace(2.0, 10.0, 30)
        rad = plot_me.fit_equation(amp, 1.5, 4.0)
        result = plot_me.add_poly_fit(amp, rad, ax, "Title", color="red")
        assert result is not None
        line, patch = result
        # line should be a Matplotlib Line2D that was added to the axis
        assert line in ax.lines
        # patch should be a Matplotlib Patch carrying the fit-coefficient label
        assert isinstance(patch, mpatch.Patch)
        assert "C1" in patch.get_label() and "C2" in patch.get_label()

    def test_successful_fit_draws_one_line(self):
        fig, ax = plt.subplots()
        amp = np.linspace(2.0, 10.0, 30)
        rad = plot_me.fit_equation(amp, 1.5, 4.0)
        plot_me.add_poly_fit(amp, rad, ax, "Title", color="green")
        assert len(ax.lines) == 1

    def test_fit_line_has_250_points(self):
        fig, ax = plt.subplots()
        amp = np.linspace(2.0, 10.0, 30)
        rad = plot_me.fit_equation(amp, 1.0, 2.0)
        plot_me.add_poly_fit(amp, rad, ax, "Title", color="blue")
        xdata = ax.lines[0].get_xdata()
        assert len(xdata) == 250

    def test_fit_line_uses_supplied_color(self):
        fig, ax = plt.subplots()
        amp = np.linspace(2.0, 10.0, 30)
        rad = plot_me.fit_equation(amp, 1.0, 2.0)
        line, patch = plot_me.add_poly_fit(amp, rad, ax, "Title", color="red")
        assert line.get_color() == "red"
        assert patch.get_edgecolor() is not None

    def test_fit_line_uses_supplied_label(self):
        fig, ax = plt.subplots()
        amp = np.linspace(2.0, 10.0, 30)
        rad = plot_me.fit_equation(amp, 1.0, 2.0)
        line, _ = plot_me.add_poly_fit(amp, rad, ax, "Ch 1", color="blue")
        assert line.get_label() == "Ch 1"

    def test_runtime_error_returns_none(self):
        """If curve_fit raises RuntimeError (no convergence), gracefully return None."""
        fig, ax = plt.subplots()
        amp = np.array([1.0, 2.0, 3.0])
        rad = np.array([1.0, 2.0, 3.0])
        with patch.object(
            plot_me, "curve_fit", side_effect=RuntimeError("no convergence")
        ):
            result = plot_me.add_poly_fit(amp, rad, ax, "Title", color="blue")
        assert result is None
        assert len(ax.lines) == 0

    def test_curve_fit_called_with_maxfev(self):
        fig, ax = plt.subplots()
        amp = np.array([2.0, 3.0, 4.0])
        rad = np.array([1.0, 2.0, 3.0])
        fake_param = np.array([1.0, 1.0])
        fake_covar = np.eye(2)
        with patch.object(
            plot_me, "curve_fit", return_value=(fake_param, fake_covar)
        ) as mock_fit:
            plot_me.add_poly_fit(amp, rad, ax, "Title", color="blue")
        assert mock_fit.called
        # maxfev is passed as a keyword in the source
        _, kwargs = mock_fit.call_args
        assert kwargs.get("maxfev") == 5500

    def test_patch_label_formats_coefficients(self):
        """Patch label should format C1 with %.1g and C2 with %.1f."""
        fig, ax = plt.subplots()
        amp = np.array([2.0, 3.0, 4.0])
        rad = np.array([1.0, 2.0, 3.0])
        fake_param = np.array([1234.0, 5.678])
        fake_covar = np.eye(2)
        with patch.object(
            plot_me, "curve_fit", return_value=(fake_param, fake_covar)
        ):
            _, patch_obj = plot_me.add_poly_fit(
                amp, rad, ax, "Title", color="blue"
            )
        label = patch_obj.get_label()
        assert label == "C1: 1e+03    C2: 5.7"


# ===========================================================================
# plot_amp_vs_rad  (using the real get_columns via a real DataFrame)
# ===========================================================================
class TestPlotAmpVsRadRealColumns:
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
        # With fit=False no legend is set via ax.legend(handles=...),
        # so pull labels directly from the scatter collections instead.
        scatter_labels = [c.get_label() for c in ax.collections]
        assert len(scatter_labels) == 3
        assert all(label.startswith("Ch ") for label in scatter_labels)


# ===========================================================================
# plot_amp_vs_rad  (mocking get_columns to isolate plotting logic)
# ===========================================================================
class TestPlotAmpVsRadMockedColumns:
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
            {1: [0.1, 0.2, 0.3], 2: [0.5, 0.6, 0.7]},
        )
        # add_poly_fit now returns (line, patch); provide a real line + patch
        fake_line = plt.Line2D([0, 1], [0, 1])
        fake_patch = mpatch.Patch(color="blue", label="C1: 1    C2: 1.0")
        with (
            patch.object(plot_me, "get_columns", return_value=(x, rad)),
            patch.object(
                plot_me,
                "add_poly_fit",
                return_value=(fake_line, fake_patch),
            ) as mock_fit,
        ):
            plot_me.plot_amp_vs_rad(MagicMock(), ax, [True] * 10, fit=True)
        assert mock_fit.call_count == 2

    def test_add_poly_fit_not_called_when_no_fit(self):
        fig, ax = plt.subplots()
        x, rad = self._mock_columns(
            [1.0, 2.0, 3.0],
            {1: [0.1, 0.2, 0.3]},
        )
        with (
            patch.object(plot_me, "get_columns", return_value=(x, rad)),
            patch.object(plot_me, "add_poly_fit") as mock_fit,
        ):
            plot_me.plot_amp_vs_rad(MagicMock(), ax, [True] * 10, fit=False)
        mock_fit.assert_not_called()

    def test_fit_mask_filters_zero_and_nan(self):
        """
        The fit mask keeps only y>0 and finite x & y.
        Given the data below, only rows with y>0 and finite x/y survive.
        """
        fig, ax = plt.subplots()
        x = pd.Series([1.0, 2.0, np.nan, 4.0, 5.0])
        rad = pd.DataFrame({1: [0.0, 3.0, 4.0, np.nan, 6.0]})
        with (
            patch.object(plot_me, "get_columns", return_value=(x, rad)),
            patch.object(
                plot_me, "add_poly_fit", return_value=None
            ) as mock_fit,
        ):
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
        """More channels than colors -> colors wrap using modulo (col - 1)."""
        fig, ax = plt.subplots()
        color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
        n = len(color_cycle) + 2  # force wraparound
        # Integer column names starting at 1; color index is (col - 1) % len
        rad_dict = {i + 1: list(np.random.rand(3)) for i in range(n)}
        x, rad = pd.Series([1.0, 2.0, 3.0]), pd.DataFrame(rad_dict)

        with patch.object(plot_me, "get_columns", return_value=(x, rad)):
            plot_me.plot_amp_vs_rad(MagicMock(), ax, [True] * 10, fit=False)

        assert len(ax.collections) == n
        # col=1 uses color_cycle[0]; col=len(color_cycle)+1 uses color_cycle[0] too
        first = ax.collections[0].get_facecolor()[0]
        wrapped = ax.collections[len(color_cycle)].get_facecolor()[0]
        np.testing.assert_allclose(first, wrapped, atol=1e-6)


# ===========================================================================
# unify_legends
# ===========================================================================
class TestUnifyLegends:
    def test_empty_axes_returns_empty_lists(self):
        handles, labels = plot_me.unify_legends([])
        assert handles == []
        assert labels == []

    def test_collects_labels_from_single_axis(self):
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1], label="A")
        ax.plot([0, 1], [1, 0], label="B")
        handles, labels = plot_me.unify_legends([ax])
        assert labels == ["A", "B"]
        assert len(handles) == 2

    def test_deduplicates_labels_across_axes(self):
        fig, (ax1, ax2) = plt.subplots(1, 2)
        ax1.plot([0, 1], [0, 1], label="Ch 1")
        ax2.plot([0, 1], [1, 0], label="Ch 1")  # duplicate label
        ax2.plot([0, 1], [0, 1], label="Ch 2")
        handles, labels = plot_me.unify_legends([ax1, ax2])
        assert labels == ["Ch 1", "Ch 2"]
        assert len(handles) == 2

    def test_preserves_first_occurrence_order(self):
        fig, (ax1, ax2) = plt.subplots(1, 2)
        ax1.plot([0, 1], [0, 1], label="B")
        ax2.plot([0, 1], [1, 0], label="A")
        ax2.plot([0, 1], [0, 1], label="B")  # duplicate, should not reorder
        handles, labels = plot_me.unify_legends([ax1, ax2])
        assert labels == ["B", "A"]

    def test_axis_without_labeled_artists(self):
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])  # no explicit label
        handles, labels = plot_me.unify_legends([ax])
        # Unlabeled artists get an auto-label prefixed with "_",
        # which get_legend_handles_labels() excludes.
        assert labels == []
        assert handles == []

    def test_mixed_labeled_and_unlabeled(self):
        fig, ax = plt.subplots()
        ax.plot([0, 1], [0, 1])  # unlabeled -> excluded
        ax.plot([0, 1], [1, 0], label="Keep me")
        handles, labels = plot_me.unify_legends([ax])
        assert labels == ["Keep me"]
        assert len(handles) == 1


# ===========================================================================
# unify_axes
# ===========================================================================
class TestUnifyAxes:
    def test_empty_axes_no_error(self):
        # Should simply return (None) without raising.
        assert plot_me.unify_axes([]) is None

    def test_sets_common_limits_across_axes(self):
        fig, (ax1, ax2) = plt.subplots(1, 2)
        ax1.set_xlim(0, 10)
        ax1.set_ylim(0, 5)
        ax2.set_xlim(2, 20)
        ax2.set_ylim(-3, 8)

        plot_me.unify_axes([ax1, ax2])

        # x range spans overall min/max: (0, 20)
        # y range spans overall min/max: (-3, 8)
        for ax in (ax1, ax2):
            np.testing.assert_allclose(ax.get_xlim(), (0.0, 20.0))
            np.testing.assert_allclose(ax.get_ylim(), (-3.0, 8.0))

    def test_single_axis_unchanged(self):
        fig, ax = plt.subplots()
        ax.set_xlim(1, 4)
        ax.set_ylim(2, 6)
        plot_me.unify_axes([ax])
        np.testing.assert_allclose(ax.get_xlim(), (1.0, 4.0))
        np.testing.assert_allclose(ax.get_ylim(), (2.0, 6.0))

    def test_applies_same_limits_to_all_axes(self):
        fig, axes = plt.subplots(1, 3)
        axes[0].set_xlim(-5, 1)
        axes[0].set_ylim(0, 2)
        axes[1].set_xlim(0, 3)
        axes[1].set_ylim(-1, 10)
        axes[2].set_xlim(1, 7)
        axes[2].set_ylim(4, 6)

        plot_me.unify_axes(list(axes))

        expected_x = (-5.0, 7.0)
        expected_y = (-1.0, 10.0)
        for ax in axes:
            np.testing.assert_allclose(ax.get_xlim(), expected_x)
            np.testing.assert_allclose(ax.get_ylim(), expected_y)

    def test_does_not_reverse_axis_direction(self):
        """Unified limits should keep (min, max) ordering, not invert."""
        fig, (ax1, ax2) = plt.subplots(1, 2)
        ax1.set_xlim(0, 10)
        ax1.set_ylim(0, 10)
        ax2.set_xlim(5, 15)
        ax2.set_ylim(5, 15)
        plot_me.unify_axes([ax1, ax2])
        for ax in (ax1, ax2):
            xlo, xhi = ax.get_xlim()
            ylo, yhi = ax.get_ylim()
            assert xlo < xhi
            assert ylo < yhi


# ===========================================================================
# Integration-ish: fit line actually overlays scatter for real data
# ===========================================================================
class TestPlotIntegration:
    def test_fit_line_within_plot_when_convergent(self):
        """
        Use a single channel that follows the fit model so curve_fit converges,
        then confirm a fit line was drawn on top of the scatter.
        """
        amp = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
        rad = plot_me.fit_equation(amp, 1.0, 3.0)
        # Integer column name for the radiation channel (col - 1 indexing).
        df = pd.DataFrame({"amps": amp, 1: rad})
        mask = [True] + [False] * 9

        fig, ax = plt.subplots()
        plot_me.plot_amp_vs_rad(df, ax, mask, fit=True)
        assert len(ax.collections) == 1  # scatter
        assert len(ax.lines) == 1  # fit line
        plt.close(fig)

    def test_legend_present_after_convergent_fit(self):
        """A convergent fit should produce a legend built from the fit patch."""
        amp = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
        rad = plot_me.fit_equation(amp, 1.0, 3.0)
        df = pd.DataFrame({"amps": amp, 1: rad})
        mask = [True] + [False] * 9

        fig, ax = plt.subplots()
        plot_me.plot_amp_vs_rad(df, ax, mask, fit=True)
        legend = ax.get_legend()
        assert legend is not None
        labels = [t.get_text() for t in legend.get_texts()]
        assert len(labels) == 1
        assert labels[0].startswith("C1:")
        assert "C2:" in labels[0]
        plt.close(fig)

    def test_multichannel_fit_and_scatter_counts(self):
        """Two convergent channels -> two scatters and two fit lines."""
        amp = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
        rad1 = plot_me.fit_equation(amp, 1.0, 3.0)
        rad2 = plot_me.fit_equation(amp, 2.0, 5.0)
        df = pd.DataFrame({"amps": amp, 1: rad1, 2: rad2})
        mask = [True, True] + [False] * 8

        fig, ax = plt.subplots()
        plot_me.plot_amp_vs_rad(df, ax, mask, fit=True)
        assert len(ax.collections) == 2  # two scatters
        assert len(ax.lines) == 2  # two fit lines
        plt.close(fig)
