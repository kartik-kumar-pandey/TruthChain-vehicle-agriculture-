"""
TruthChain 2.0 - SensorAgent v2

Purpose:
    Analyze vehicle telemetry using the frozen IsolationForest v2
    model and return a structured evidence result for the LangGraph
    pipeline.

IMPORTANT:
    SensorAgent detects telemetry anomalies.

    It does NOT determine whether a claim is fraudulent.

    risk_score is an anomaly-strength score, NOT a calibrated
    probability of fraud.

Frozen model:
    sensor_isolationforest_v2.pkl

Frozen feature list:
    1. speed
    2. accel_x
    3. accel_y
    4. accel_z
    5. acceleration_magnitude
    6. speed_change
    7. acceleration_change
    8. gps_distance
    9. gps_speed
    10. speed_gps_difference
    11. speed_gps_ratio
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd


# ============================================================
# PATHS
# ============================================================

# sensor_agent.py
#     ↓
# agents/
#     ↓
# ai-services/
#
# Therefore:
# parent       = agents
# parent.parent = ai-services

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_DIR = (
    BASE_DIR
    / "ml"
    / "models"
    / "sensor"
)

MODEL_PATH = (
    MODEL_DIR
    / "sensor_isolationforest_v2.pkl"
)

FEATURES_PATH = (
    MODEL_DIR
    / "sensor_features_v2.pkl"
)


# ============================================================
# MODEL CONFIGURATION
# ============================================================

MODEL_VERSION = "sensor-agent-v2.0"

DOMAIN = "motor"


# ============================================================
# FROZEN FEATURE CONTRACT
# ============================================================

# These are the raw telemetry fields expected from the caller.
#
# acceleration_magnitude is NOT required from the caller.
# It is derived internally from accel_x, accel_y, accel_z.
RAW_SENSOR_FEATURES = [
    "speed",
    "accel_x",
    "accel_y",
    "accel_z",
    "speed_change",
    "acceleration_change",
    "gps_distance",
    "gps_speed",
]


# Backward-compatible name used throughout this module.
#
# This intentionally contains only caller-supplied fields.
BASE_FEATURES = list(
    RAW_SENSOR_FEATURES
)


# Derived features calculated by SensorAgent v2.
#
# acceleration_magnitude is also derived internally because it
# is part of the frozen 11-feature model vector.
DERIVED_FEATURES = [
    "acceleration_magnitude",
    "speed_gps_difference",
    "speed_gps_ratio",
]


# Keep the historical name for compatibility.
V2_FEATURES = [
    "speed_gps_difference",
    "speed_gps_ratio",
]


# Exact feature order expected by the frozen model artifact.
#
# DO NOT CHANGE THIS ORDER.
EXPECTED_FEATURES = [
    "speed",
    "accel_x",
    "accel_y",
    "accel_z",
    "acceleration_magnitude",
    "speed_change",
    "acceleration_change",
    "gps_distance",
    "gps_speed",
    "speed_gps_difference",
    "speed_gps_ratio",
]


# ============================================================
# LOAD FROZEN MODEL
# ============================================================

if not MODEL_PATH.exists():
    raise FileNotFoundError(
        "SensorAgent model not found:\n"
        f"{MODEL_PATH}"
    )


if not FEATURES_PATH.exists():
    raise FileNotFoundError(
        "SensorAgent feature file not found:\n"
        f"{FEATURES_PATH}"
    )


# Load the already-trained production model.
sensor_model = joblib.load(
    MODEL_PATH
)


# Load the exact feature ordering used during training.
sensor_features = joblib.load(
    FEATURES_PATH
)


sensor_features = list(
    sensor_features
)


# ============================================================
# STRICT FEATURE VALIDATION
# ============================================================

# This is a critical deployment check.
#
# IsolationForest receives positional columns.
#
# Even if the same feature names are present, a different
# order would change the model input and invalidate inference.

if sensor_features != EXPECTED_FEATURES:

    raise ValueError(
        "SensorAgent v2 feature mismatch.\n\n"
        f"Expected:\n{EXPECTED_FEATURES}\n\n"
        f"Loaded from sensor_features_v2.pkl:\n"
        f"{sensor_features}"
    )


# ============================================================
# INPUT HELPERS
# ============================================================

def _safe_float(
    value: Any,
    field_name: str,
) -> float:
    """
    Convert an input value to a finite float.

    Raises:
        ValueError:
            If the value is missing, non-numeric, NaN,
            or infinite.
    """

    if value is None:

        raise ValueError(
            f"{field_name} is missing."
        )

    try:

        result = float(
            value
        )

    except (TypeError, ValueError):

        raise ValueError(
            f"{field_name} must be numeric. "
            f"Received: {value!r}"
        )

    if not np.isfinite(result):

        raise ValueError(
            f"{field_name} must be finite. "
            f"Received: {value!r}"
        )

    return result


# ============================================================
# REQUIRED FIELD VALIDATION
# ============================================================

def _missing_fields(
    sensor_data: dict[str, Any],
) -> list[str]:
    """
    Find required raw telemetry fields.
    Required minimum fields: speed, accel_x, accel_y, accel_z.
    Optional fields will be auto-derived if missing.
    """
    missing: list[str] = []
    # Primary required fields
    primary_fields = ["speed", "accel_x", "accel_y", "accel_z"]
    for field in primary_fields:
        if field not in sensor_data or sensor_data[field] is None:
            missing.append(field)
    
    # If primary fields exist, backfill sensible defaults for optional secondary telemetry
    if not missing:
        speed = float(sensor_data.get("speed", 0.0))
        if sensor_data.get("speed_change") is None:
            sensor_data["speed_change"] = 0.0
        if sensor_data.get("acceleration_change") is None:
            sensor_data["acceleration_change"] = 0.0
        if sensor_data.get("gps_distance") is None:
            sensor_data["gps_distance"] = round(speed * (1000.0 / 3600.0), 2)
        if sensor_data.get("gps_speed") is None:
            sensor_data["gps_speed"] = speed

    return missing


# ============================================================
# DERIVED SENSOR FEATURES
# ============================================================

def _calculate_derived_features(
    data: dict[str, float],
) -> None:
    """
    Calculate all internally-derived SensorAgent v2 features.

    Derived features:

        acceleration_magnitude
        speed_gps_difference
        speed_gps_ratio

    acceleration_magnitude:

        sqrt(
            accel_x^2
            + accel_y^2
            + accel_z^2
        )

    speed_gps_difference:

        abs(speed - gps_speed)

    speed_gps_ratio:

        speed / (abs(gps_speed) + 1)

    The +1 in speed_gps_ratio is part of the frozen v2
    feature definition and MUST NOT be changed.
    """

    # --------------------------------------------------------
    # Acceleration magnitude
    # --------------------------------------------------------

    data[
        "acceleration_magnitude"
    ] = float(
        np.sqrt(
            data["accel_x"] ** 2
            + data["accel_y"] ** 2
            + data["accel_z"] ** 2
        )
    )

    # --------------------------------------------------------
    # Speed / GPS difference
    # --------------------------------------------------------

    data[
        "speed_gps_difference"
    ] = abs(
        data["speed"]
        - data["gps_speed"]
    )

    # --------------------------------------------------------
    # Speed / GPS ratio
    #
    # +1.0 is part of the frozen v2 definition.
    # --------------------------------------------------------

    data[
        "speed_gps_ratio"
    ] = (
        data["speed"]
        / (
            abs(
                data["gps_speed"]
            )
            + 1.0
        )
    )


# Keep the previous helper name available internally.
_calculate_v2_features = (
    _calculate_derived_features
)


# ============================================================
# RISK SCORE
# ============================================================

def _calculate_risk_score(
    raw_score: float,
) -> float:
    """
    Convert IsolationForest decision_function output into
    the SensorAgent anomaly-strength score.

    IMPORTANT:
        This is NOT a probability.

    Formula:

        risk_score = clip(
            0.5 - raw_score,
            0,
            1
        )
    """

    if not np.isfinite(
        raw_score
    ):
        raise ValueError(
            "IsolationForest returned a non-finite "
            "decision_function score."
        )

    return float(
        np.clip(
            0.5 - raw_score,
            0.0,
            1.0,
        )
    )


# ============================================================
# CONFIDENCE
# ============================================================

def _calculate_confidence(
    anomaly: bool,
    risk_score: float,
) -> float:
    """
    Calculate SensorAgent confidence.

    This preserves the validated inference logic.
    """

    if anomaly:

        confidence = min(
            0.99,
            0.70
            + risk_score * 0.29,
        )

    else:

        confidence = min(
            0.99,
            0.70
            + (
                1.0
                - risk_score
            )
            * 0.29,
        )

    return float(
        confidence
    )


# ============================================================
# STANDARD RESPONSE
# ============================================================

def _base_response(
    *,
    confidence: float = 0.0,
    risk_score: float = 0.0,
    decision: str = "INSUFFICIENT_DATA",
    evidence: list[str] | None = None,
    contradictions: list[str] | None = None,
    anomaly: bool = False,
    model_score: float | None = None,
    features: dict[str, Any] | None = None,
    processing_time_ms: float | None = None,
) -> dict[str, Any]:
    """
    Build a consistent SensorAgent response.
    """

    result: dict[str, Any] = {

        "agent": "SensorAgent",

        "domain": DOMAIN,

        "confidence": round(
            float(confidence),
            4,
        ),

        "risk_score": round(
            float(risk_score),
            4,
        ),

        "decision": decision,

        "evidence": (
            evidence
            or []
        ),

        "contradictions": (
            contradictions
            or []
        ),

        "model_version": (
            MODEL_VERSION
        ),

        "anomaly": bool(
            anomaly
        ),

        "model_score": (
            None
            if model_score is None
            else round(
                float(model_score),
                4,
            )
        ),

        "features": (
            features
            or {}
        ),
    }

    if processing_time_ms is not None:

        result[
            "processing_time_ms"
        ] = round(
            float(
                processing_time_ms
            ),
            2,
        )

    return result


# ============================================================
# INSUFFICIENT DATA
# ============================================================

def _insufficient_data_response(
    missing_fields: list[str],
) -> dict[str, Any]:
    """
    Return a structured response when telemetry is incomplete.

    Missing telemetry is NOT treated as an anomaly.
    """

    return _base_response(

        confidence=0.0,

        risk_score=0.0,

        decision="INSUFFICIENT_DATA",

        evidence=[
            "Missing sensor fields: "
            + ", ".join(
                missing_fields
            )
        ],

        contradictions=[],

        anomaly=False,

        model_score=None,

        features={},
    )


# ============================================================
# ERROR RESPONSE
# ============================================================

def _error_response(
    error: Exception,
    processing_time_ms: float,
) -> dict[str, Any]:
    """
    Return a structured ERROR response.

    Runtime/model failures must NOT be converted into
    PASS or normal telemetry.

    The graph/risk engine can then fail closed.
    """

    return {

        "agent": "SensorAgent",

        "domain": DOMAIN,

        "confidence": 0.0,

        "risk_score": 0.0,

        "decision": "ERROR",

        "evidence": [
            "Sensor analysis failed: "
            + str(error)
        ],

        "contradictions": [],

        "model_version": MODEL_VERSION,

        "anomaly": False,

        "model_score": None,

        "features": {},

        "processing_time_ms": round(
            float(
                processing_time_ms
            ),
            2,
        ),

        "error_type": (
            type(error).__name__
        ),

        "error": str(error),
    }


# ============================================================
# MAIN SENSOR AGENT
# ============================================================

def analyze_sensor_data(
    sensor_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Run one telemetry record through SensorAgent v2.

    Required raw telemetry:

        speed
        accel_x
        accel_y
        accel_z
        speed_change
        acceleration_change
        gps_distance
        gps_speed

    Derived internally:

        acceleration_magnitude
        speed_gps_difference
        speed_gps_ratio

    Returns:
        Structured SensorAgent evidence result.
    """

    start_time = (
        time.perf_counter()
    )

    # ========================================================
    # INPUT TYPE
    # ========================================================

    if not isinstance(
        sensor_data,
        dict,
    ):

        return _base_response(

            confidence=0.0,

            risk_score=0.0,

            decision="INSUFFICIENT_DATA",

            evidence=[
                "Sensor telemetry must be "
                "provided as a dictionary."
            ],

            contradictions=[],

            anomaly=False,

            model_score=None,

            features={},

            processing_time_ms=(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000.0
            ),
        )

    # ========================================================
    # REQUIRED RAW FIELDS
    # ========================================================

    missing = _missing_fields(
        sensor_data
    )

    if missing:

        return _insufficient_data_response(
            missing
        )

    # ========================================================
    # NUMERIC CONVERSION
    # ========================================================

    try:

        data: dict[str, float] = {}

        for field in BASE_FEATURES:

            data[field] = _safe_float(
                sensor_data[field],
                field,
            )

    except ValueError as exc:

        processing_time_ms = (
            (
                time.perf_counter()
                - start_time
            )
            * 1000.0
        )

        return _base_response(

            confidence=0.0,

            risk_score=0.0,

            decision="INSUFFICIENT_DATA",

            evidence=[
                f"Invalid sensor telemetry: {exc}"
            ],

            contradictions=[],

            anomaly=False,

            model_score=None,

            features={},

            processing_time_ms=(
                processing_time_ms
            ),
        )

    # ========================================================
    # DERIVED FEATURES
    # ========================================================

    try:

        _calculate_derived_features(
            data
        )

    except Exception as exc:

        processing_time_ms = (
            (
                time.perf_counter()
                - start_time
            )
            * 1000.0
        )

        return _error_response(
            exc,
            processing_time_ms,
        )

    # ========================================================
    # DERIVED FEATURE VALIDATION
    # ========================================================

    try:

        for feature_name in DERIVED_FEATURES:

            if feature_name not in data:

                raise ValueError(
                    "Derived feature was not generated: "
                    f"{feature_name}"
                )

            if not np.isfinite(
                float(
                    data[feature_name]
                )
            ):

                raise ValueError(
                    "Derived feature is non-finite: "
                    f"{feature_name}"
                )

    except Exception as exc:

        processing_time_ms = (
            (
                time.perf_counter()
                - start_time
            )
            * 1000.0
        )

        return _error_response(
            exc,
            processing_time_ms,
        )

    # ========================================================
    # BUILD MODEL INPUT
    # ========================================================

    try:

        # Build the DataFrame using the EXACT frozen feature
        # ordering from sensor_features_v2.pkl.

        feature_vector = {
            feature_name: data[
                feature_name
            ]
            for feature_name in sensor_features
        }

        feature_frame = pd.DataFrame(
            [
                feature_vector
            ],
            columns=sensor_features,
        )

    except Exception as exc:

        processing_time_ms = (
            (
                time.perf_counter()
                - start_time
            )
            * 1000.0
        )

        return _error_response(
            exc,
            processing_time_ms,
        )

    # ========================================================
    # MODEL INFERENCE
    # ========================================================

    try:

        # IsolationForest decision_function:
        #
        # higher = more normal
        # lower  = more anomalous
        #
        # Do NOT replace this with predict_proba.
        #
        # IsolationForest does not provide a calibrated
        # fraud probability here.

        raw_score_array = (
            sensor_model.decision_function(
                feature_frame
            )
        )

        raw_score = float(
            raw_score_array[0]
        )

        if not np.isfinite(
            raw_score
        ):

            raise ValueError(
                "IsolationForest returned a non-finite "
                "decision_function score."
            )

        # IsolationForest prediction:
        #
        #  1  = normal
        # -1  = anomaly

        prediction_array = (
            sensor_model.predict(
                feature_frame
            )
        )

        prediction = int(
            prediction_array[0]
        )

        if prediction not in (
            -1,
            1,
        ):

            raise ValueError(
                "IsolationForest returned an invalid "
                f"prediction: {prediction}"
            )

        anomaly = (
            prediction == -1
        )

    except Exception as exc:

        processing_time_ms = (
            (
                time.perf_counter()
                - start_time
            )
            * 1000.0
        )

        return _error_response(
            exc,
            processing_time_ms,
        )

    # ========================================================
    # SENSOR RISK SIGNAL
    # ========================================================

    try:

        risk_score = (
            _calculate_risk_score(
                raw_score
            )
        )

    except Exception as exc:

        processing_time_ms = (
            (
                time.perf_counter()
                - start_time
            )
            * 1000.0
        )

        return _error_response(
            exc,
            processing_time_ms,
        )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    confidence = (
        _calculate_confidence(
            anomaly,
            risk_score,
        )
    )

    # ========================================================
    # DECISION
    # ========================================================

    if anomaly:

        decision = "ANOMALY_DETECTED"

        evidence = [

            "Vehicle telemetry was classified "
            "as anomalous by SensorAgent v2.",

            (
                "IsolationForest anomaly-strength "
                f"score: {risk_score:.4f}."
            ),

        ]

    else:

        decision = "PASS"

        evidence = [

            "Vehicle telemetry was classified "
            "as within the learned normal range "
            "by SensorAgent v2.",

            (
                "IsolationForest anomaly-strength "
                f"score: {risk_score:.4f}."
            ),

        ]

    # ========================================================
    # SUPPORTING GPS EVIDENCE
    # ========================================================

    speed_difference = data[
        "speed_gps_difference"
    ]

    speed_ratio = data[
        "speed_gps_ratio"
    ]

    # Prevent an unused-variable warning while retaining the
    # derived feature as part of the frozen output.
    _ = speed_ratio

    # This is supporting evidence only.
    #
    # Do NOT create another independent fraud score here.

    if speed_difference > 0:

        evidence.append(
            "Vehicle speed is inconsistent "
            "with the supplied GPS speed."
        )

    # ========================================================
    # PROCESSING TIME
    # ========================================================

    processing_time_ms = (
        (
            time.perf_counter()
            - start_time
        )
        * 1000.0
    )

    # ========================================================
    # STANDARDIZED RESULT
    # ========================================================

    return _base_response(

        confidence=confidence,

        risk_score=risk_score,

        decision=decision,

        evidence=evidence,

        contradictions=[],

        anomaly=anomaly,

        model_score=raw_score,

        features={
            feature_name: round(
                float(
                    data[
                        feature_name
                    ]
                ),
                6,
            )
            for feature_name
            in sensor_features
        },

        processing_time_ms=(
            processing_time_ms
        ),
    )


# ============================================================
# COMPATIBILITY ALIAS
# ============================================================

def analyze(
    sensor_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Compatibility wrapper.

    Allows callers to use:

        analyze(sensor_data)

    or:

        analyze_sensor_data(sensor_data)
    """

    return analyze_sensor_data(
        sensor_data
    )


# ============================================================
# MODEL INFO
# ============================================================

def get_sensor_model_info() -> dict[str, Any]:
    """
    Return static information about the frozen SensorAgent
    model and feature contract.
    """

    return {

        "agent": "SensorAgent",

        "domain": DOMAIN,

        "model_version": MODEL_VERSION,

        "model_type": (
            "IsolationForest"
        ),

        "model_path": str(
            MODEL_PATH
        ),

        "features_path": str(
            FEATURES_PATH
        ),

        "features": list(
            sensor_features
        ),

        "base_features": list(
            BASE_FEATURES
        ),

        "derived_features": list(
            DERIVED_FEATURES
        ),

        "v2_features": list(
            V2_FEATURES
        ),

        "risk_score_definition": (
            "clip(0.5 - "
            "IsolationForest.decision_function, "
            "0, 1)"
        ),

        "risk_score_is_probability": False,
    }


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    import json

    print("=" * 70)
    print("TRUTHCHAIN SENSOR AGENT V2 TEST")
    print("=" * 70)

    print()

    print(
        "Model:",
        MODEL_PATH,
    )

    print(
        "Feature artifact:",
        FEATURES_PATH,
    )

    print(
        "Model version:",
        MODEL_VERSION,
    )

    print()

    print(
        "Raw input features:"
    )

    for index, feature in enumerate(
        BASE_FEATURES,
        start=1,
    ):

        print(
            f"  {index:02d}. {feature}"
        )

    print()

    print(
        "Derived features:"
    )

    for index, feature in enumerate(
        DERIVED_FEATURES,
        start=1,
    ):

        print(
            f"  {index:02d}. {feature}"
        )

    print()

    print(
        "Frozen model features:"
    )

    for index, feature in enumerate(
        sensor_features,
        start=1,
    ):

        print(
            f"  {index:02d}. {feature}"
        )

    print()

    # --------------------------------------------------------
    # Normal-ish telemetry example.
    #
    # This is only a smoke test.
    # It is NOT a claim fraud example.
    #
    # acceleration_magnitude is intentionally omitted because
    # SensorAgent must derive it internally.
    # --------------------------------------------------------

    test_sensor_data = {

        "speed": 38.0,

        "accel_x": 2.0,

        "accel_y": 3.0,

        "accel_z": 9.2,

        "speed_change": 4.0,

        "acceleration_change": 1.5,

        "gps_distance": 42.86,

        "gps_speed": 42.86,
    }

    print("=" * 70)
    print("TEST INPUT")
    print("=" * 70)

    print(
        json.dumps(
            test_sensor_data,
            indent=2,
        )
    )

    print()

    result = analyze_sensor_data(
        test_sensor_data
    )

    print("=" * 70)
    print("SENSOR AGENT RESULT")
    print("=" * 70)

    print(
        json.dumps(
            result,
            indent=2,
        )
    )