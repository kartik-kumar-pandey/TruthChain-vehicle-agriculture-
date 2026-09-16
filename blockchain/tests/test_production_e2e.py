"""
TruthChain 2.0 production E2E regression tests.

Validates the blockchain side of a previously successful production claim:
- claim exists on Sepolia
- on-chain image hash matches expected evidence hash
- on-chain prediction hash matches expected prediction hash
- contract verification succeeds
- individual hash comparisons succeed

This test intentionally uses an existing immutable testnet record.
It does NOT submit a new blockchain transaction.
"""

from blockchain.assessment_registry import (
    get_assessment,
    verify_assessment,
)


CLAIM_ID = "TC-PRODUCTION-E2E-002"

EXPECTED_IMAGE_HASH = (
    "68d2d86e8241fb213cf9de01d98bfa650903b1022cea458e05ddbae544b60cb6"
)

EXPECTED_PREDICTION_HASH = (
    "a7a9ea2c8fa21a459fa613ec0f0f16226d631ae9362a53673cc21e4282fbb80c"
)


def test_production_e2e_blockchain_record_exists():
    """Verify the production E2E claim exists on Sepolia."""

    assessment = get_assessment(CLAIM_ID)

    assert assessment["claim_id"] == CLAIM_ID
    assert assessment["record_id"].startswith("0x")
    assert assessment["image_hash"].lower() == (
        "0x" + EXPECTED_IMAGE_HASH
    ).lower()
    assert assessment["prediction_hash"].lower() == (
        "0x" + EXPECTED_PREDICTION_HASH
    ).lower()

    assert assessment["model_version"] == "truthchain-v2.0"
    assert int(assessment["timestamp"]) > 0
    assert assessment["recorder"]


def test_production_e2e_hash_verification():
    """Verify the exact evidence hashes against the deployed contract."""

    result = verify_assessment(
        CLAIM_ID,
        bytes.fromhex(EXPECTED_IMAGE_HASH),
        bytes.fromhex(EXPECTED_PREDICTION_HASH),
    )

    assert result["claim_id"] == CLAIM_ID
    assert result["is_match"] is True
    assert result["image_hash_match"] is True
    assert result["prediction_hash_match"] is True

    assert result["on_chain_image_hash"].lower() == (
        "0x" + EXPECTED_IMAGE_HASH
    ).lower()

    assert result["on_chain_prediction_hash"].lower() == (
        "0x" + EXPECTED_PREDICTION_HASH
    ).lower()

    assert result["model_version"] == "truthchain-v2.0"
    assert int(result["registered_at"]) > 0