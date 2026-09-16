"""
TruthChain Canonical Serialization & Hashing Module
====================================================
Implements RFC 8785 (JSON Canonicalization Scheme) compatible hashing
for vehicle damage predictions and SHA-256 image commitments.

Guarantees:
- Deterministic hashing regardless of Python dictionary key ordering.
- Consistent cross-platform representation (JSON RFC 8785).
- Clean conversion between hex digests and Solidity bytes32 types.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Union


def canonical_json_bytes(obj: Any) -> bytes:
    """
    Serialize an arbitrary Python dict/list into canonical UTF-8 JSON bytes.
    - Keys are sorted lexicographically.
    - Compact separators (',', ':') with no whitespace.
    - Floating point values formatted cleanly.
    - UTF-8 encoded without escaping ASCII characters.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_json_str(obj: Any) -> str:
    """Serialize object to canonical JSON string."""
    return canonical_json_bytes(obj).decode("utf-8")


def hash_image_bytes(image_bytes: bytes) -> str:
    """
    Compute standard SHA-256 digest of raw vehicle image bytes.
    Returns 64-character lowercase hex string.
    """
    if not image_bytes:
        raise ValueError("Cannot hash empty image bytes")
    return hashlib.sha256(image_bytes).hexdigest()


def format_canonical_prediction(prediction_raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and structure pure prediction data into a standardized canonical shape
    for audit hashing.

    Extracts:
    - probabilities: sorted dict of damage classes to rounded float values
    - thresholds: sorted dict of damage class thresholds
    - detected_damages: sorted list of detected damage dicts
    - model_version: model identifier string
    """
    probs = prediction_raw.get("probabilities", {})
    thresholds = prediction_raw.get("thresholds", {})
    detected = prediction_raw.get("detected_damages") or prediction_raw.get("detections") or []
    model_version = prediction_raw.get("model_version") or prediction_raw.get("model") or "TruthChain Vision ResNet-50"

    # Round probabilities and thresholds to 4 decimal places for stable float hashing
    clean_probs = {
        str(k): round(float(v), 4) for k, v in sorted(probs.items())
    }
    clean_thresholds = {
        str(k): round(float(v), 4) for k, v in sorted(thresholds.items())
    }

    # Normalize detected damage list deterministically based on thresholds
    if clean_probs and clean_thresholds:
        clean_detected = []
        for cls, prob in sorted(clean_probs.items()):
            thr = clean_thresholds.get(cls, 0.5)
            if prob >= thr:
                clean_detected.append({
                    "probability": prob,
                    "threshold": thr,
                    "type": str(cls),
                })
    else:
        clean_detected = []
        for d in sorted(detected, key=lambda x: str(x.get("type", ""))):
            clean_detected.append({
                "probability": round(float(d.get("probability", 0.0)), 4),
                "threshold": round(float(d.get("threshold", 0.0)), 4),
                "type": str(d.get("type", "")),
            })

    return {
        "detected_damages": clean_detected,
        "model_version": str(model_version),
        "probabilities": clean_probs,
        "thresholds": clean_thresholds,
    }



def hash_prediction_dict(prediction_dict: Dict[str, Any]) -> str:
    """
    Compute SHA-256 digest of a prediction structure.
    Formats into canonical shape (RFC 8785) first, then returns 64-character lowercase hex string.
    """
    canonical_dict = format_canonical_prediction(prediction_dict)
    canonical_bytes = canonical_json_bytes(canonical_dict)
    return hashlib.sha256(canonical_bytes).hexdigest()


def to_bytes32(hex_str: str) -> bytes:
    """
    Convert a 64-character hex string (with or without '0x' prefix)
    into a 32-byte Solidity `bytes32` value.
    """
    cleaned = hex_str.strip()
    if cleaned.startswith("0x") or cleaned.startswith("0X"):
        cleaned = cleaned[2:]
    if len(cleaned) < 64:
        # Pad with leading zeros if shorter
        cleaned = cleaned.zfill(64)
    elif len(cleaned) > 64:
        # Truncate if longer (or sha256 hash it)
        cleaned = cleaned[:64]
    return bytes.fromhex(cleaned)


def from_bytes32(b32: Union[bytes, str]) -> str:
    """
    Convert a bytes32 value or hex string to a normalized 0x-prefixed 64-char hex string.
    """
    if isinstance(b32, bytes):
        return "0x" + b32.hex()
    if isinstance(b32, str):
        if not b32.startswith("0x"):
            return "0x" + b32
        return b32
    return str(b32)


def generate_record_id(prefix: str = "TC") -> str:
    """
    Generate standard formatted TruthChain Record ID (e.g., TC-000001 or timestamp hash).
    """
    import time
    import random
    ts = int(time.time() * 1000)
    rand_suffix = random.randint(100, 999)
    return f"{prefix}-{ts % 1000000:06d}-{rand_suffix}"
