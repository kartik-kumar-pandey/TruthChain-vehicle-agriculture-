"""
TruthChain Agriculture
Core Constants
=====================

Central definitions shared by all agriculture agents.

These constants are intentionally kept in one place so that
the satellite agent, image agent, sensor agent, cross-modal
agent, consensus engine, and evidence layer all use the same
domain definitions.
"""

from __future__ import annotations


# ============================================================
# Domain
# ============================================================

DOMAIN_NAME = "agriculture"

INSURANCE_SCHEME = "PMFBY"

DOMAIN_VERSION = "1.0.0"


# ============================================================
# Agent Decision States
# ============================================================

AGENT_PASS = "PASS"

AGENT_SUSPICIOUS = "SUSPICIOUS"

AGENT_FAIL = "FAIL"

AGENT_DECISIONS = (
    AGENT_PASS,
    AGENT_SUSPICIOUS,
    AGENT_FAIL,
)


# ============================================================
# Final Claim Decision States
# ============================================================

FINAL_VERIFIED = "VERIFIED"

FINAL_REVIEW_REQUIRED = "REVIEW_REQUIRED"

FINAL_REJECTED = "REJECTED"

FINAL_UNCERTAIN = "UNCERTAIN"

FINAL_DECISIONS = (
    FINAL_VERIFIED,
    FINAL_REVIEW_REQUIRED,
    FINAL_REJECTED,
    FINAL_UNCERTAIN,
)


# ============================================================
# Satellite Evidence States
# ============================================================

SATELLITE_SUPPORT = "SUPPORT"

SATELLITE_CONTRADICTION = "CONTRADICTION"

SATELLITE_UNCERTAIN = "UNCERTAIN"

SATELLITE_EVIDENCE_DECISIONS = (
    SATELLITE_SUPPORT,
    SATELLITE_CONTRADICTION,
    SATELLITE_UNCERTAIN,
)


# ============================================================
# Sentinel-2 Required Bands
# ============================================================

# Exact 12-band set used by the recovered Satellite-CropAgent
# feature pipeline.

SENTINEL_BANDS = (
    "B01",
    "B02",
    "B03",
    "B04",
    "B05",
    "B06",
    "B07",
    "B08",
    "B8A",
    "B09",
    "B11",
    "B12",
)


# Number of spectral bands used by the agriculture satellite model.
SENTINEL_BAND_COUNT = len(SENTINEL_BANDS)


# ============================================================
# Sentinel-2 Scene Classification Layer
# ============================================================

# Invalid pixels excluded from field-level model inference:
#
# 0  = No data
# 1  = Saturated / defective
# 3  = Cloud shadow
# 7  = Unclassified
# 8  = Cloud medium probability
# 9  = Cloud high probability
# 10 = Thin cirrus

INVALID_SCL_CLASSES = frozenset(
    {
        0,
        1,
        3,
        7,
        8,
        9,
        10,
    }
)


# ============================================================
# Sentinel-2 Data Mask
# ============================================================

# Process API dataMask convention:
#
# > 0 means usable source data
# <= 0 means unavailable/no-data

DATA_MASK_VALID_THRESHOLD = 0.5


# ============================================================
# Satellite Processing
# ============================================================

SATELLITE_DEFAULT_MAX_CLOUD_PERCENT = 20.0

SATELLITE_DEFAULT_LOOKBACK_DAYS = 30

SATELLITE_DEFAULT_SCALE = 0.01

SATELLITE_DEFAULT_GRID_WIDTH = 10

SATELLITE_DEFAULT_GRID_HEIGHT = 10


# Minimum percentage of field pixels that should remain usable
# after field geometry + SCL + dataMask filtering.

MIN_VALID_PIXEL_FRACTION = 0.60


# ============================================================
# Satellite Evidence Agent
# ============================================================

SATELLITE_MODEL_VERSION = "Satellite-CropAgent-v0.2"

SATELLITE_EVIDENCE_AGENT_VERSION = "SatelliteEvidenceAgent-v1"


# Thresholds recovered from the existing SatelliteEvidenceAgent v1.
#
# claimed-crop probability >= SUPPORT_THRESHOLD
#      -> SUPPORT
#
# claimed-crop probability <= CONTRADICTION_THRESHOLD
#      -> CONTRADICTION
#
# otherwise
#      -> UNCERTAIN

SATELLITE_SUPPORT_THRESHOLD = 0.8467158147365881

SATELLITE_CONTRADICTION_THRESHOLD = 0.14682232394585493


# ============================================================
# Agriculture Satellite Crop Classes
# ============================================================

# Original 13-class label set used by the recovered satellite
# CropAgent model.

SATELLITE_CROP_CLASSES = (
    "Wheat",
    "Mustard",
    "Lentil",
    "Fallow",
    "Green pea",
    "Sugarcane",
    "Garlic",
    "Maize",
    "Gram",
    "Coriander",
    "Potato",
    "Bersem",
    "Rice",
)


SATELLITE_CROP_CLASS_COUNT = len(SATELLITE_CROP_CLASSES)


# Original source labels associated with the 13 classes.
#
# The encoding follows the recovered training label mapping.

SATELLITE_SOURCE_LABEL_IDS = {
    "Wheat": 1,
    "Mustard": 2,
    "Lentil": 3,
    "Fallow": 4,
    "Green pea": 5,
    "Sugarcane": 6,
    "Garlic": 8,
    "Maize": 9,
    "Gram": 13,
    "Coriander": 14,
    "Potato": 15,
    "Bersem": 16,
    "Rice": 36,
}


# Model class-index mapping:
#
# 0 -> Wheat
# 1 -> Mustard
# ...
# 12 -> Rice

SATELLITE_CLASS_TO_INDEX = {
    crop: index
    for index, crop in enumerate(SATELLITE_CROP_CLASSES)
}


SATELLITE_INDEX_TO_CLASS = {
    index: crop
    for crop, index in SATELLITE_CLASS_TO_INDEX.items()
}


# ============================================================
# Agriculture Image Model
# ============================================================

AGRICULTURE_IMAGE_MODEL_VERSION = "image-agri-v1.0"

AGRICULTURE_DAMAGE_MODEL_VERSION = (
    "agriculture-disease-damage-v0.2"
)


# ============================================================
# Other Agent Versions
# ============================================================

WEATHER_AGENT_VERSION = "sensor-agri-v1.0"

TEXT_AGENT_VERSION = "text-agri-v1.0"

CROSS_MODAL_AGENT_VERSION = "crossmodal-agri-v1.0"

INVESTIGATION_AGENT_VERSION = "investigation-agri-v1.0"

ADVERSARIAL_AGENT_VERSION = "adversarial-agri-v1.0"


# ============================================================
# Agriculture Risk Weights
# ============================================================

# Starting agriculture weighting from the project design:
#
# Satellite/Image evidence : 0.25
# Sensor/Weather           : 0.25
# Text                     : 0.15
# Cross-Modal              : 0.25
# Adversarial Verifier     : 0.10
#
# These are starting configuration values, not claims of
# calibrated production performance.

AGRICULTURE_RISK_WEIGHTS = {
    "SatelliteEvidenceAgent": 0.25,
    "SensorAgent": 0.25,
    "TextAgent": 0.15,
    "CrossModalAgent": 0.25,
    "Verifier": 0.10,
}


# ============================================================
# Risk Decision Bands
# ============================================================

# Internal risk scale is 0.0 - 1.0.
#
# The project's documented decision bands correspond to:
#
# 0 - 20   -> VERIFIED
# 21 - 50  -> LOW RISK / REVIEW
# 51 - 75  -> SUSPICIOUS
# 76 - 100 -> REJECT
#
# We store the equivalent normalized boundaries here.

RISK_VERIFIED_MAX = 0.20

RISK_REVIEW_MAX = 0.50

RISK_SUSPICIOUS_MAX = 0.75

RISK_REJECT_MIN = 0.76


# ============================================================
# Claim Validation
# ============================================================

MIN_CLAIMED_LOSS_PERCENT = 0.0

MAX_CLAIMED_LOSS_PERCENT = 100.0


# ============================================================
# Utility Validation
# ============================================================

def is_supported_satellite_crop(crop: str) -> bool:
    """
    Return True when the supplied crop belongs to the
    recovered satellite model's 13-class vocabulary.
    """
    if not isinstance(crop, str):
        return False

    return crop.strip() in SATELLITE_CROP_CLASS_TO_INDEX


def normalize_crop_name(crop: str) -> str:
    """
    Normalize a crop name for exact class matching.

    This intentionally performs only whitespace normalization;
    it does not silently rename arbitrary crop names.
    """
    if not isinstance(crop, str):
        raise TypeError("crop must be a string")

    return crop.strip()


def validate_risk_weights() -> None:
    """
    Ensure agriculture risk weights form a valid weighted
    combination.
    """
    total = sum(AGRICULTURE_RISK_WEIGHTS.values())

    if abs(total - 1.0) > 1e-9:
        raise ValueError(
            "Agriculture risk weights must sum to 1.0. "
            f"Current total: {total}"
        )


def validate_satellite_classes() -> None:
    """
    Validate the recovered satellite class mapping.
    """
    if len(SATELLITE_CROP_CLASSES) != 13:
        raise ValueError(
            "Expected 13 satellite crop classes, "
            f"got {len(SATELLITE_CROP_CLASSES)}"
        )

    if set(SATELLITE_CLASS_TO_INDEX.keys()) != set(
        SATELLITE_CROP_CLASSES
    ):
        raise ValueError(
            "Satellite crop class mapping is inconsistent."
        )

    if set(SATELLITE_INDEX_TO_CLASS.keys()) != set(
        range(SATELLITE_CROP_CLASS_COUNT)
    ):
        raise ValueError(
            "Satellite class indices must be contiguous "
            "from 0 to 12."
        )


# ============================================================
# Import-time consistency checks
# ============================================================

validate_risk_weights()

validate_satellite_classes()


# ============================================================
# Public exports
# ============================================================

__all__ = [
    "DOMAIN_NAME",
    "INSURANCE_SCHEME",
    "DOMAIN_VERSION",
    "AGENT_PASS",
    "AGENT_SUSPICIOUS",
    "AGENT_FAIL",
    "AGENT_DECISIONS",
    "FINAL_VERIFIED",
    "FINAL_REVIEW_REQUIRED",
    "FINAL_REJECTED",
    "FINAL_UNCERTAIN",
    "FINAL_DECISIONS",
    "SATELLITE_SUPPORT",
    "SATELLITE_CONTRADICTION",
    "SATELLITE_UNCERTAIN",
    "SATELLITE_EVIDENCE_DECISIONS",
    "SENTINEL_BANDS",
    "SENTINEL_BAND_COUNT",
    "INVALID_SCL_CLASSES",
    "DATA_MASK_VALID_THRESHOLD",
    "SATELLITE_DEFAULT_MAX_CLOUD_PERCENT",
    "SATELLITE_DEFAULT_LOOKBACK_DAYS",
    "SATELLITE_DEFAULT_SCALE",
    "SATELLITE_DEFAULT_GRID_WIDTH",
    "SATELLITE_DEFAULT_GRID_HEIGHT",
    "MIN_VALID_PIXEL_FRACTION",
    "SATELLITE_MODEL_VERSION",
    "SATELLITE_EVIDENCE_AGENT_VERSION",
    "SATELLITE_SUPPORT_THRESHOLD",
    "SATELLITE_CONTRADICTION_THRESHOLD",
    "SATELLITE_CROP_CLASSES",
    "SATELLITE_CROP_CLASS_COUNT",
    "SATELLITE_SOURCE_LABEL_IDS",
    "SATELLITE_CLASS_TO_INDEX",
    "SATELLITE_INDEX_TO_CLASS",
    "AGRICULTURE_IMAGE_MODEL_VERSION",
    "AGRICULTURE_DAMAGE_MODEL_VERSION",
    "WEATHER_AGENT_VERSION",
    "TEXT_AGENT_VERSION",
    "CROSS_MODAL_AGENT_VERSION",
    "INVESTIGATION_AGENT_VERSION",
    "ADVERSARIAL_AGENT_VERSION",
    "AGRICULTURE_RISK_WEIGHTS",
    "RISK_VERIFIED_MAX",
    "RISK_REVIEW_MAX",
    "RISK_SUSPICIOUS_MAX",
    "RISK_REJECT_MIN",
    "MIN_CLAIMED_LOSS_PERCENT",
    "MAX_CLAIMED_LOSS_PERCENT",
    "is_supported_satellite_crop",
    "normalize_crop_name",
    "validate_risk_weights",
    "validate_satellite_classes",
]