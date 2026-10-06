"""
TruthChain Agriculture
Core Hashing Utilities
======================

Deterministic hashing helpers used for:

- claim evidence
- uploaded files
- satellite metadata
- agent outputs
- evidence certificates
- blockchain anchoring

SHA-256 is used throughout this standalone Agriculture service.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


# ============================================================
# Constants
# ============================================================

HASH_ALGORITHM = "sha256"

CHUNK_SIZE = 1024 * 1024  # 1 MiB


# ============================================================
# Byte hashing
# ============================================================

def sha256_bytes(data: bytes) -> str:
    """
    Calculate SHA-256 for raw bytes.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """

    if not isinstance(data, bytes):
        raise TypeError(
            "sha256_bytes() expects bytes."
        )

    digest = hashlib.sha256()
    digest.update(data)

    return digest.hexdigest()


# ============================================================
# Text hashing
# ============================================================

def sha256_text(
    text: str,
    *,
    encoding: str = "utf-8",
) -> str:
    """
    Calculate SHA-256 for text.

    UTF-8 is used by default.
    """

    if not isinstance(text, str):
        raise TypeError(
            "sha256_text() expects a string."
        )

    return sha256_bytes(
        text.encode(encoding)
    )


# ============================================================
# File hashing
# ============================================================

def sha256_file(
    path: str | Path,
) -> str:
    """
    Calculate SHA-256 for a file.

    The file is streamed in chunks so large satellite files,
    images, videos, or evidence bundles do not need to be
    loaded entirely into memory.
    """

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"Evidence file does not exist: {file_path}"
        )

    if not file_path.is_file():
        raise ValueError(
            f"Evidence path is not a file: {file_path}"
        )

    digest = hashlib.sha256()

    with file_path.open("rb") as file:
        while True:
            chunk = file.read(CHUNK_SIZE)

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


# ============================================================
# Canonical JSON
# ============================================================

def canonicalize_json(value: Any) -> str:
    """
    Convert a Python value into deterministic JSON.

    The resulting representation is designed for hashing:

    - dictionary keys are sorted
    - unnecessary whitespace is removed
    - UTF-8 characters are preserved
    - separators are deterministic

    This is important because two logically identical JSON
    objects should produce the same evidence hash even when
    their original key ordering differs.
    """

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


# ============================================================
# Canonical JSON hashing
# ============================================================

def sha256_json(value: Any) -> str:
    """
    Calculate SHA-256 of a canonical JSON representation.
    """

    canonical = canonicalize_json(value)

    return sha256_text(canonical)


# ============================================================
# JSON file hashing
# ============================================================

def sha256_json_file(
    path: str | Path,
) -> str:
    """
    Load a JSON file, canonicalize its contents, and calculate
    its SHA-256 hash.

    This means formatting differences in the JSON file do not
    change the resulting logical evidence hash.
    """

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(
            f"JSON file does not exist: {file_path}"
        )

    if not file_path.is_file():
        raise ValueError(
            f"JSON path is not a file: {file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        value = json.load(file)

    return sha256_json(value)


# ============================================================
# Evidence object hashing
# ============================================================

def hash_evidence(
    evidence: Any,
) -> str:
    """
    Hash a structured evidence object.

    This is intentionally an alias with semantic meaning:
    callers can use hash_evidence() when hashing an evidence
    payload instead of directly calling sha256_json().
    """

    return sha256_json(evidence)


# ============================================================
# Agent result hashing
# ============================================================

def hash_agent_result(
    agent_result: Any,
) -> str:
    """
    Hash a structured agent result.

    The function accepts either:
        - a normal Python dictionary
        - a Pydantic model exposing model_dump()

    The exact object representation is hashed canonically.
    """

    if hasattr(agent_result, "model_dump"):
        payload = agent_result.model_dump()

    elif isinstance(agent_result, dict):
        payload = agent_result

    else:
        raise TypeError(
            "hash_agent_result() expects a dict or a "
            "Pydantic model with model_dump()."
        )

    return sha256_json(payload)


# ============================================================
# Claim hashing
# ============================================================

def hash_claim(
    claim: Any,
) -> str:
    """
    Hash an agriculture claim.

    Supports:
        - Pydantic models with model_dump()
        - dictionaries
    """

    if hasattr(claim, "model_dump"):
        payload = claim.model_dump()

    elif isinstance(claim, dict):
        payload = claim

    else:
        raise TypeError(
            "hash_claim() expects a dict or a "
            "Pydantic model with model_dump()."
        )

    return sha256_json(payload)


# ============================================================
# Multiple hashes
# ============================================================

def combine_hashes(
    hashes: list[str],
) -> str:
    """
    Deterministically combine multiple SHA-256 hashes into
    one SHA-256 digest.

    The input order is preserved intentionally.

    Example:

        claim_hash
        image_hash
        satellite_hash
        agent_hash

    are combined into one evidence bundle hash.
    """

    if not isinstance(hashes, list):
        raise TypeError(
            "combine_hashes() expects a list of hashes."
        )

    if not hashes:
        raise ValueError(
            "Cannot combine an empty list of hashes."
        )

    for item in hashes:
        if not isinstance(item, str):
            raise TypeError(
                "Every hash must be a string."
            )

        if not item:
            raise ValueError(
                "Hashes must not be empty."
            )

    combined = "|".join(hashes)

    return sha256_text(combined)


# ============================================================
# Evidence bundle hash
# ============================================================

def hash_evidence_bundle(
    *,
    claim_hash: str,
    evidence_hashes: list[str],
    agent_hashes: list[str] | None = None,
) -> str:
    """
    Create the deterministic top-level evidence-bundle hash.

    The structure is:

        claim hash
        +
        evidence hashes
        +
        optional agent hashes

    The resulting digest is what we can later anchor on-chain.
    """

    payload = {
        "claim_hash": claim_hash,
        "evidence_hashes": evidence_hashes,
        "agent_hashes": agent_hashes or [],
    }

    return sha256_json(payload)


# ============================================================
# Hash metadata
# ============================================================

def hash_metadata(
    *,
    value: Any,
) -> dict[str, str]:
    """
    Return hash metadata for audit records.
    """

    return {
        "algorithm": HASH_ALGORITHM,
        "hash": sha256_json(value),
    }


# ============================================================
# Validation
# ============================================================

def is_sha256(value: str) -> bool:
    """
    Check whether a string has the expected SHA-256 hexadecimal
    representation.
    """

    if not isinstance(value, str):
        return False

    if len(value) != 64:
        return False

    try:
        int(value, 16)
    except ValueError:
        return False

    return True


# ============================================================
# Public exports
# ============================================================

__all__ = [
    "HASH_ALGORITHM",
    "CHUNK_SIZE",
    "sha256_bytes",
    "sha256_text",
    "sha256_file",
    "canonicalize_json",
    "sha256_json",
    "sha256_json_file",
    "hash_evidence",
    "hash_agent_result",
    "hash_claim",
    "combine_hashes",
    "hash_evidence_bundle",
    "hash_metadata",
    "is_sha256",
]