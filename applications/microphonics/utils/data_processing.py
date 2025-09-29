import traceback

import numpy as np
from scipy import signal
from scipy.fftpack import fft, fftfreq


def _validate_fft_inputs(data, effective_sample_rate):
    """Validate and prepare FFT input data."""
    if data is None or len(data) == 0:
        print("Warning: calculate_fft received empty data.")
        return None

    if not isinstance(data, np.ndarray):
        try:
            data = np.asarray(data, dtype=np.float64)
        except (TypeError, ValueError) as e:
            print(f"Error (calculate_fft): Could not convert input data to NumPy array: {e}")
            return None

    nan_mask = np.isnan(data)
    if np.any(nan_mask):
        data = data[~nan_mask]
        print(f"Warning (calculate_fft): Removed {np.sum(nan_mask)} NaN value(s).")

    if data.size == 0:
        print("Warning (calculate_fft): Data array is empty after removing NaNs.")
        return None

    if effective_sample_rate <= 0:
        print(f"Error calculating FFT: Invalid effective_sample_rate ({effective_sample_rate})")
        return None

    return data


def _compute_fft_results(data, effective_sample_rate):
    """Compute FFT frequencies and amplitudes."""
    num_points = data.size
    sample_spacing = 1.0 / effective_sample_rate

    yf = fft(data)

    if num_points == 1:
        return np.array([0.0]), np.abs(yf)

    xf = fftfreq(num_points, sample_spacing)[: num_points // 2]
    amplitudes = 2.0 / num_points * np.abs(yf[0:num_points // 2])

    min_len = min(len(xf), len(amplitudes))
    if len(xf) != min_len or len(amplitudes) != min_len:
        print("Warning (calculate_fft): Adjusting length mismatch between freqs and amps.")
        xf = xf[:min_len]
        amplitudes = amplitudes[:min_len]

    return xf, amplitudes


def calculate_fft(data: np.ndarray, effective_sample_rate: float):
    """
    Calculate FFT of input data w/ correct frequency mapping

    Args:
        data (np.ndarray): Input time domain data.
        effective_sample_rate (float): The effective sample rate of input data in Hz, after considering any decimation.

    Returns:
        tuple: (frequencies, amplitudes) arrays in linear scale
    """
    validated_data = _validate_fft_inputs(data, effective_sample_rate)
    if validated_data is None:
        return np.array([]), np.array([])

    # Compute FFT
    try:
        return _compute_fft_results(validated_data, effective_sample_rate)
    except Exception as e:
        print(f"Error calculating FFT: {e}")
        traceback.print_exc()
        return np.array([]), np.array([])


def calculate_histogram(data, bin_range=None, num_bins=140):
    """
    Calculate histogram data for the detuning values

    Args:
        data (np.ndarray): Input detuning data
        bin_range (tuple, optional): Range for histogram bins (min, max)
        num_bins (int): Number of histogram bins

    Returns:
        tuple: (bins, counts)
    """
    data = np.asarray(data)
    if data.size == 0:
        # Handle empty data return default bins/counts
        default_range = bin_range if bin_range else (-1, 1)
        counts = np.zeros(num_bins, dtype=int)
        bins = np.linspace(default_range[0], default_range[1], num_bins + 1)
        print("Warning: calculate_histogram received empty data.")
        return bins, counts
    try:
        counts, bins = np.histogram(data, bins=num_bins, range=bin_range)
    except Exception as e:
        print(f"Error during np.histogram calculation: {e}")
        # Fallback for safety
        default_range = bin_range if bin_range else (-1, 1)
        counts = np.zeros(num_bins, dtype=int)
        bins = np.linspace(default_range[0], default_range[1], num_bins + 1)

    return bins, counts


def calculate_spectrogram(data, sample_rate=2000, nperseg=None):
    """
    Calculate spectrogram using scipy.signal.spectrogram

    Args:
        data (np.ndarray): Input time-domain data
        sample_rate (float): Sample rate in Hz
        nperseg (int, optional): Length of each segment. If None, uses min(256, len(data))

    Returns:
        tuple: (f, t, Sxx) where:
            - f is array of frequency bins
            - t is array of time bins
            - Sxx is 2D array of spectrogram values in dB scale
    """
    data = np.asarray(data)
    if data.size < 2 or sample_rate <= 0:
        return np.array([]), np.array([]), np.array([[]])

    if nperseg is None:
        nperseg = min(max(len(data) // 8, 1), 256)

    nperseg = min(nperseg, len(data))
    noverlap = nperseg // 2

    # Calculate spectrogram
    try:
        f, t, Sxx = signal.spectrogram(
            data,
            fs=sample_rate,
            nperseg=nperseg,
            noverlap=noverlap,
            window="hann",  # Use Hann window for consistency w/ FFT
            scaling="density",
        )

        # Convert to dB scale w/ safety floor to avoid log(0)
        Sxx_db = 10 * np.log10(Sxx + 1e-12)
    except ValueError as e:
        print(f"Error calculating spectrogram (likely due to segment length/data size): {e}")
        return np.array([]), np.array([]), np.array([[]])
    except Exception as e:
        print(f"Unexpected error calculating spectrogram: {e}")
        return np.array([]), np.array([]), np.array([[]])

    return f, t, Sxx_db
