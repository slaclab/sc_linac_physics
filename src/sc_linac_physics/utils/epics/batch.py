from typing import List, Any

import epics

from sc_linac_physics.utils.epics.logger import get_logger


class PVBatch:
    """Utilities for batch PV operations using raw EPICS calls"""

    @staticmethod
    def get_values(
        pv_names: List[str],
        timeout: float = 0.5,
    ) -> List[Any]:
        """
        Batch read multiple PV values efficiently using epics.caget_many().

        This is faster than creating PV objects when you only need to read
        values once and don't need the full PV interface.

        Args:
            pv_names: List of PV names to read
            timeout: Timeout for the batch operation

        Returns:
            List of values in same order as pv_names (None for failed/disconnected PVs)

        Example:
            >>> from sc_linac_physics.utils.epics.batch import PVBatch
            >>> pv_names = ["PV:1", "PV:2", "PV:3"]
            >>> values = PVBatch.get_values(pv_names, timeout=1.0)
        """
        if not pv_names:
            return []

        try:
            values = epics.caget_many(pv_names, timeout=timeout)
            return values
        except Exception as e:
            get_logger().warning(
                f"caget_many failed for {len(pv_names)} PVs: {e}, "
                f"falling back to individual gets"
            )
            # Fallback to individual caget calls
            values = []
            for pv_name in pv_names:
                try:
                    values.append(epics.caget(pv_name, timeout=timeout))
                except Exception:
                    values.append(None)
            return values

    @staticmethod
    def put_values(
        pv_names: List[str],
        values: List[Any],
        timeout: float = 1.0,
        wait: bool = True,
    ) -> List[bool]:
        """
        Batch write multiple PV values efficiently.

        Args:
            pv_names: List of PV names to write
            values: List of values to write (must match length of pv_names)
            timeout: Timeout for each put operation
            wait: Wait for completion

        Returns:
            List of success status (True/False) for each PV

        Raises:
            ValueError: If pv_names and values lengths don't match
        """
        if len(pv_names) != len(values):
            raise ValueError(
                f"Length mismatch: {len(pv_names)} PVs but {len(values)} values"
            )

        results = []
        for pv_name, value in zip(pv_names, values):
            try:
                status = epics.caput(pv_name, value, wait=wait, timeout=timeout)
                results.append(status == 1)
            except Exception as e:
                get_logger().warning(f"Failed to put {pv_name}={value}: {e}")
                results.append(False)

        return results
