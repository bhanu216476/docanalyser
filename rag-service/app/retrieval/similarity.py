"""Dense-vector similarity functions."""

from __future__ import annotations

from collections.abc import Sequence
import math

import numpy as np


def _as_vector(vector: Sequence[float], *, name: str) -> np.ndarray:
    """Convert and validate one dense vector."""
    try:
        array = np.asarray(vector, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must contain numeric values") from exc

    if array.ndim != 1:
        raise ValueError(f"{name} must be a one-dimensional vector")
    if array.size == 0:
        raise ValueError(f"{name} cannot be empty")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values")
    return array


def cosine_similarity(
    first: Sequence[float],
    second: Sequence[float],
) -> float:
    """Return cosine similarity, safely treating zero vectors as 0.0."""
    first_vector = _as_vector(first, name="first vector")
    second_vector = _as_vector(second, name="second vector")

    if first_vector.shape != second_vector.shape:
        raise ValueError(
            "Vector dimensions must match: "
            f"{first_vector.size} != {second_vector.size}"
        )

    first_norm = np.linalg.norm(first_vector)
    second_norm = np.linalg.norm(second_vector)
    if first_norm == 0.0 or second_norm == 0.0:
        return 0.0

    score = float(np.dot(first_vector, second_vector) / (first_norm * second_norm))
    if not math.isfinite(score):
        raise ValueError("cosine similarity must be finite")
    return score
