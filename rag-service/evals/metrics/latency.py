"""
Latency aggregation and statistics metric module.
"""

from __future__ import annotations

from collections.abc import Sequence
import numpy as np


def compute_latency_stats(latencies: Sequence[float]) -> dict[str, float]:
    """
    Compute mean, median, and p95 for a sequence of latency measurements (ms).

    Args:
        latencies: Sequence of latency float values.

    Returns:
        dict containing:
            'mean_ms': arithmetic mean
            'median_ms': 50th percentile
            'p95_ms': 95th percentile
            'min_ms': minimum
            'max_ms': maximum
            'count': number of samples
    """
    if not latencies:
        return {
            "mean_ms": 0.0,
            "median_ms": 0.0,
            "p95_ms": 0.0,
            "min_ms": 0.0,
            "max_ms": 0.0,
            "count": 0.0,
        }

    arr = np.array(latencies, dtype=float)
    return {
        "mean_ms": round(float(np.mean(arr)), 2),
        "median_ms": round(float(np.median(arr)), 2),
        "p95_ms": round(float(np.percentile(arr, 95)), 2),
        "min_ms": round(float(np.min(arr)), 2),
        "max_ms": round(float(np.max(arr)), 2),
        "count": float(len(arr)),
    }
