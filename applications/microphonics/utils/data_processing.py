import numpy as np
from scipy import signal


def calculate_fft(data, sample_rate=2000):
    """
    Calculate FFT of input data w/ the right scaling and windowing

    Args:
        data (np.ndarray): Input time domain data
        sample_rate (float): Sample rate in Hz

    Returns:
        tuple: (frequencies, amplitudes) arrays
    """
    target_points = 4096

    # Safe resampling using FFT based method
    if len(data) > target_points:
        data = signal.resample(data, target_points)  # Proper anti aliasing
    else:
        data = np.pad(data, (0, target_points - len(data)), 'constant')

    # Applying Hann window w/ correct scaling
    window = np.hanning(len(data))
    fft = np.fft.rfft(data * window)
    freqs = np.fft.rfftfreq(len(data), d=1 / sample_rate)

    # Proper amplitude scaling
    magnitude = np.abs(fft) * 2 / np.sum(window)
    dB = 20 * np.log10(magnitude + 1e-12)

    # Apply frequency mask w/out downsampling
    mask = freqs <= 150
    return freqs[mask], dB[mask]


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
    # Auto calculate range w/ padding if its not provided
    if bin_range is None:
        min_val, max_val = np.min(data), np.max(data)
        padding = max(0.05 * (max_val - min_val), 5)  # At least 5 units of padding
        bin_range = (min_val - padding, max_val + padding)

    # Calculate histogram
    counts, bins = np.histogram(data, bins=num_bins, range=bin_range)

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
    # Use data length if smaller than default 256, otherwise use default
    if nperseg is None:
        nperseg = min(len(data), 256)

    # Calculate spectrogram
    f, t, Sxx = signal.spectrogram(
        data,
        fs=sample_rate,
        nperseg=nperseg,
        window='hann',  # Use Hann window for consistency w/ FFT
        scaling='density'  # Power spectral density
    )

    # Convert to dB scale w/ safety floor to avoid log(0)
    Sxx_db = 10 * np.log10(Sxx + 1e-12)

    return f, t, Sxx_db
