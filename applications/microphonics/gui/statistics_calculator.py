from dataclasses import dataclass
from typing import Dict

import numpy as np


@dataclass
class CavityStatistics:
    """Container for cavity statistics"""

    mean: float
    std: float
    min: float
    max: float
    outliers: int
    rms: float
    peak_to_peak: float


class StatisticsCalculator:
    """
    Handles stat analysis of cavity data including:
    - Basic statistics (mean, std, min, max)
    - Outlier detection
    - RMS calculation
    - Peak-to-peak measurement
    """

    def __init__(self):
        self._outlier_threshold = 2.5  # Number of std devs for outlier detection

    def calculate_statistics(self, data: np.ndarray) -> CavityStatistics:
        """
        Calculate comprehensive statistics for a cavity's data

        Args:
            data: numpy array of cavity measurements

        Returns:
            CavityStatistics object containing all calculated statistics
        """
        # Basic statistics
        mean = np.mean(data)
        std = np.std(data)
        min_val = np.min(data)
        max_val = np.max(data)

        # RMS calculation
        rms = np.sqrt(np.mean(np.square(data)))

        # Peak to peak
        peak_to_peak = max_val - min_val

        # Outlier detection using z score method
        z_scores = np.abs((data - mean) / std)
        outliers = np.sum(z_scores > self._outlier_threshold)

        return CavityStatistics(
            mean=mean,
            std=std,
            min=min_val,
            max=max_val,
            outliers=int(outliers),
            rms=rms,
            peak_to_peak=peak_to_peak,
        )

    def convert_to_panel_format(self, stats: CavityStatistics) -> Dict:
        """
        Convert statistics to format expected by StatisticsPanel

        Args:
            stats: CavityStatistics object

        Returns:
            Dictionary formatted for StatisticsPanel.update_statistics()
        """
        return {
            "mean": stats.mean,
            "std": stats.std,
            "min": stats.min,
            "max": stats.max,
            "outliers": stats.outliers,
        }
