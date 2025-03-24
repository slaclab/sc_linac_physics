import numpy as np
from scipy import signal


def calculate_fft(data, original_sample_rate=2000, target_sample_rate=None):
    """
    Calculate FFT of input data w? correct frequency mapping

    Args:
        data (np.ndarray): Input time domain data
        original_sample_rate (float): Original sample rate in Hz (unused)
        target_sample_rate (float): Target sample rate (unused)

    Returns:
        tuple: (frequencies, amplitudes) arrays in linear scale
    """
    import numpy as np
    from scipy.fftpack import fft, fftfreq

    # Handle empty or invalid data
    if data is None or len(data) == 0:
        return np.array([]), np.array([])

    # Make sure data is a numpy array
    data = np.asarray(data)

    # Remove NaN values if any
    data = data[~np.isnan(data)]

    # Check if we still have valid data
    if len(data) == 0:
        return np.array([]), np.array([])

    try:
        # I did this: To use the exact sample spacing from the original code (this fixed my frequency mapping)

        sample_spacing = 1.0 / 1000

        # Get number of points
        num_points = len(data)

        # Calculate FFT directly (no resampling, no filtering)
        yf = fft(data)

        # Calculate frequency bins with the fixed sample spacing
        xf = fftfreq(num_points, sample_spacing)[:num_points // 2]

        # Calculate amplitudes with the same scaling as original
        amplitudes = 2.0 / num_points * np.abs(yf[0:num_points // 2])

        # Apply frequency mask to limit to 150 Hz for display
        mask = xf <= 150

        return xf[mask], amplitudes[mask]
    except Exception as e:
        print(f"Error calculating FFT: {e}")
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
