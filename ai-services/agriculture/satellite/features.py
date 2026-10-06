"""
TruthChain Agriculture
Satellite Feature Engineering
==============================

Feature construction for the Agriculture satellite evidence model.

The production satellite model operates on Sentinel-2 field-level
features rather than raw pixels directly.

This module:
    1. validates the twelve Sentinel-2 bands
    2. computes per-band statistics
    3. computes spectral ratios
    4. computes vegetation / moisture / burn / water indices
    5. returns the exact ordered feature vector expected by the
       Agriculture satellite evidence model
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from agriculture.core.constants import SENTINEL_BANDS


# ============================================================
# Feature order
# ============================================================

BAND_STATISTICS = (
    "mean",
    "cv",
    "std",
    "min",
    "max",
)


SPECTRAL_RATIOS = (
    "RATIO_B08_B04",
    "RATIO_B08_B03",
    "RATIO_B08_B02",
    "RATIO_B8A_B05",
    "RATIO_B8A_B06",
    "RATIO_B8A_B07",
    "RATIO_B11_B08",
    "RATIO_B12_B08",
    "RATIO_B11_B04",
)


SPECTRAL_INDICES = (
    "NDVI2",
    "GNDVI",
    "NDMI",
    "NBR",
    "MNDWI",
    "NDRE_B05",
    "NDRE_B06",
    "NDRE_B07",
)


FEATURE_NAMES: tuple[str, ...] = tuple(
    f"{band}_{stat}"
    for band in SENTINEL_BANDS
    for stat in BAND_STATISTICS
) + SPECTRAL_RATIOS + SPECTRAL_INDICES


# ============================================================
# Validation
# ============================================================

def _validate_bands(
    bands: Mapping[str, np.ndarray],
) -> None:
    """
    Validate that all required Sentinel-2 bands are present.
    """

    if not isinstance(bands, Mapping):
        raise TypeError(
            "bands must be a mapping of band name -> numpy array."
        )

    missing = [
        band
        for band in SENTINEL_BANDS
        if band not in bands
    ]

    if missing:
        raise ValueError(
            "Missing required Sentinel-2 bands: "
            + ", ".join(missing)
        )


def _validate_arrays(
    bands: Mapping[str, np.ndarray],
) -> None:
    """
    Validate that all band arrays are non-empty and have the
    same shape.
    """

    shapes: set[tuple[int, ...]] = set()

    for band in SENTINEL_BANDS:
        array = np.asarray(bands[band])

        if array.size == 0:
            raise ValueError(
                f"Band {band} contains no pixels."
            )

        if array.ndim != 1:
            raise ValueError(
                f"Band {band} must be a 1-D field-pixel array; "
                f"got shape {array.shape}."
            )

        if not np.issubdtype(
            array.dtype,
            np.number,
        ):
            raise TypeError(
                f"Band {band} must contain numeric values."
            )

        shapes.add(array.shape)

    if len(shapes) != 1:
        raise ValueError(
            "All Sentinel-2 band arrays must contain the same "
            "number of field pixels."
        )


# ============================================================
# Safe division
# ============================================================

def _safe_ratio(
    numerator: float,
    denominator: float,
) -> float:
    """
    Compute a stable ratio.

    The denominator uses absolute magnitude so negative
    numerical values cannot create an unstable division.
    """

    return float(
        numerator / (
            abs(denominator) + 1e-6
        )
    )


def _normalized_difference(
    left: float,
    right: float,
) -> float:
    """
    Compute a normalized-difference index:

        (left - right) / (left + right + 1e-6)
    """

    return float(
        (left - right)
        / (left + right + 1e-6)
    )


# ============================================================
# Band statistics
# ============================================================

def _band_statistics(
    values: np.ndarray,
) -> dict[str, float]:
    """
    Calculate the five field-level statistics used by the model:

        mean
        coefficient of variation
        standard deviation
        minimum
        maximum
    """

    values = np.asarray(
        values,
        dtype=np.float64,
    )

    mean = float(np.mean(values))

    std = float(np.std(values))

    cv = float(
        std / (
            abs(mean) + 1e-6
        )
    )

    return {
        "mean": mean,
        "cv": cv,
        "std": std,
        "min": float(np.min(values)),
        "max": float(np.max(values)),
    }


# ============================================================
# Feature extraction
# ============================================================

def extract_field_features(
    bands: Mapping[str, np.ndarray],
) -> dict[str, float]:
    """
    Convert field pixels from the twelve Sentinel-2 bands into
    the exact 77-feature representation used by the Agriculture
    satellite model.

    Input:
        {
            "B01": np.ndarray,
            "B02": np.ndarray,
            ...
            "B12": np.ndarray,
        }

    Every array must represent pixels belonging to the same
    agricultural field.
    """

    _validate_bands(bands)
    _validate_arrays(bands)

    arrays = {
        band: np.asarray(
            bands[band],
            dtype=np.float64,
        )
        for band in SENTINEL_BANDS
    }

    # --------------------------------------------------------
    # Per-band statistics
    # --------------------------------------------------------

    stats: dict[str, dict[str, float]] = {}

    for band in SENTINEL_BANDS:
        stats[band] = _band_statistics(
            arrays[band]
        )

    features: dict[str, float] = {}

    for band in SENTINEL_BANDS:
        for stat in BAND_STATISTICS:
            features[
                f"{band}_{stat}"
            ] = stats[band][stat]

    # Convenient aliases for mean values.
    mean = {
        band: stats[band]["mean"]
        for band in SENTINEL_BANDS
    }

    # --------------------------------------------------------
    # Spectral ratios
    # --------------------------------------------------------

    features["RATIO_B08_B04"] = _safe_ratio(
        mean["B08"],
        mean["B04"],
    )

    features["RATIO_B08_B03"] = _safe_ratio(
        mean["B08"],
        mean["B03"],
    )

    features["RATIO_B08_B02"] = _safe_ratio(
        mean["B08"],
        mean["B02"],
    )

    features["RATIO_B8A_B05"] = _safe_ratio(
        mean["B8A"],
        mean["B05"],
    )

    features["RATIO_B8A_B06"] = _safe_ratio(
        mean["B8A"],
        mean["B06"],
    )

    features["RATIO_B8A_B07"] = _safe_ratio(
        mean["B8A"],
        mean["B07"],
    )

    features["RATIO_B11_B08"] = _safe_ratio(
        mean["B11"],
        mean["B08"],
    )

    features["RATIO_B12_B08"] = _safe_ratio(
        mean["B12"],
        mean["B08"],
    )

    features["RATIO_B11_B04"] = _safe_ratio(
        mean["B11"],
        mean["B04"],
    )

    # --------------------------------------------------------
    # Spectral indices
    # --------------------------------------------------------

    # NDVI using B08 and B04.
    features["NDVI2"] = _normalized_difference(
        mean["B08"],
        mean["B04"],
    )

    # Green NDVI.
    features["GNDVI"] = _normalized_difference(
        mean["B08"],
        mean["B03"],
    )

    # Normalized Difference Moisture Index.
    features["NDMI"] = _normalized_difference(
        mean["B08"],
        mean["B11"],
    )

    # Normalized Burn Ratio.
    features["NBR"] = _normalized_difference(
        mean["B08"],
        mean["B12"],
    )

    # Modified Normalized Difference Water Index.
    features["MNDWI"] = _normalized_difference(
        mean["B03"],
        mean["B11"],
    )

    # Red-edge indices.
    #
    # IMPORTANT:
    # These use B8A, not B08.
    #
    # This distinction must remain unchanged because these
    # features belong to the trained satellite feature schema.

    features["NDRE_B05"] = _normalized_difference(
        mean["B8A"],
        mean["B05"],
    )

    features["NDRE_B06"] = _normalized_difference(
        mean["B8A"],
        mean["B06"],
    )

    features["NDRE_B07"] = _normalized_difference(
        mean["B8A"],
        mean["B07"],
    )

    # --------------------------------------------------------
    # Final validation
    # --------------------------------------------------------

    missing_features = [
        name
        for name in FEATURE_NAMES
        if name not in features
    ]

    if missing_features:
        raise RuntimeError(
            "Satellite feature extraction produced an incomplete "
            "feature vector. Missing: "
            + ", ".join(missing_features)
        )

    extra_features = [
        name
        for name in features
        if name not in FEATURE_NAMES
    ]

    if extra_features:
        raise RuntimeError(
            "Satellite feature extraction produced unexpected "
            "features: "
            + ", ".join(extra_features)
        )

    return {
        name: float(features[name])
        for name in FEATURE_NAMES
    }


# ============================================================
# Ordered model vector
# ============================================================

def features_to_vector(
    features: Mapping[str, float],
) -> np.ndarray:
    """
    Convert the feature dictionary into the exact ordered
    NumPy vector expected by the trained model.
    """

    missing = [
        name
        for name in FEATURE_NAMES
        if name not in features
    ]

    if missing:
        raise ValueError(
            "Feature mapping is missing required features: "
            + ", ".join(missing)
        )

    vector = np.asarray(
        [
            float(features[name])
            for name in FEATURE_NAMES
        ],
        dtype=np.float32,
    )

    if vector.shape != (len(FEATURE_NAMES),):
        raise RuntimeError(
            "Unexpected satellite feature vector shape: "
            f"{vector.shape}"
        )

    return vector


# ============================================================
# Combined helper
# ============================================================

def extract_feature_vector(
    bands: Mapping[str, np.ndarray],
) -> np.ndarray:
    """
    Extract the complete ordered satellite feature vector
    directly from field pixels.
    """

    features = extract_field_features(
        bands
    )

    return features_to_vector(
        features
    )


# ============================================================
# Public exports
# ============================================================

__all__ = [
    "BAND_STATISTICS",
    "SPECTRAL_RATIOS",
    "SPECTRAL_INDICES",
    "FEATURE_NAMES",
    "extract_field_features",
    "features_to_vector",
    "extract_feature_vector",
]