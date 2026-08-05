import numpy as np
import matplotlib.pyplot as plt

from datetime import datetime
from scipy.optimize import curve_fit
from sc_linac_physics.applications.field_emission.measurements import find_dataframes, get_columns


def plot_amp_vs_rad(df, titles, ax, r_channels, fit):
    """plot amplitude on x-axis and radiation on y-axis, locking colors to channels"""
    x_amplitude, rad_cols = get_columns(df, r_channels)
    color_cycle = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    for i, col in enumerate(rad_cols.columns):
        print(f"channel {col}")  # debug line
        color = color_cycle[i % len(color_cycle)]
        y_rad = rad_cols[col]
        ax.scatter(
            x_amplitude, y_rad, label=f"Ch {col}", marker=".", color=color
        )
        if fit:
            mask = (
                (y_rad > 0) & np.isfinite(x_amplitude) & np.isfinite(y_rad)
            )  # filter for 0 and NaN
            x = x_amplitude[mask].to_numpy()
            y = y_rad[mask].to_numpy()
            add_poly_fit(x, y, ax, color=color)
    plt.setp(ax.get_xticklabels(), fontsize="x-small")
    plt.setp(ax.get_yticklabels(), fontsize="x-small")
    ax.grid(True)


def fit_equation(amp, c1, c2):
    """fit line equation currently y = C1(E0)^(2.5) * exp(-C2/E0)"""
    return c1 * (amp**2.5) * np.exp((-c2) / amp)


def add_poly_fit(amp, rad, axis, color):
    """overlay amp vs rad plot with polynomial fit"""
    if rad.size > 0:
        try:
            param, param_covar = curve_fit(fit_equation, amp, rad, maxfev=5500)
            x = np.linspace(amp.min(), amp.max(), 250)
            y = fit_equation(x, *param)
            axis.plot(x, y, ls="-", color=color)
            print(
                f"C1: {param[0]}\tC2: {param[1]}"
            )  # display fit line coefficients
            # print(f"covar: {param_covar}\n\n")
            return param, param_covar
        except RuntimeError:
            print("RuntimeError: fit did not converge. Skipping channel")
            return None, None
    else:
        return None, None


if __name__ == "__main__":
    cryo = 34
    day = datetime(2025, 5, 1, 16, 33)
    cav = [True, False, True, True, True, True, True, True]
    reads = "Average"
    r_chan = [True, False, False, False, False, False, False, False]
    fit_line = True

    data, label0, num0 = find_dataframes(cryo, day, cav, reads)
    for dat in data.values():
        x_axis, columns = get_columns(dat, r_chan)
        fig, axes = plt.subplots(1, 1, figsize=(5, 4))
        plot_amp_vs_rad(dat, label0, axes, r_chan, fit_line)
        plt.show()
