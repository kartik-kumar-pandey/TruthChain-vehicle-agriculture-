"""
TruthChain 2.0 - On-chain Assessment Inspector

Reads an AssessmentRegistry record directly from Sepolia
and displays everything available from the deployed contract.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from blockchain.assessment_registry import (
    connection_info,
    get_assessment,
    claim_id_to_bytes32,
)


def show_record(claim_id: str) -> None:
    print("=" * 78)
    print("TRUTHCHAIN 2.0 — BLOCKCHAIN RECORD INSPECTOR")
    print("=" * 78)

    # ------------------------------------------------------------------
    # Blockchain connection
    # ------------------------------------------------------------------

    info = connection_info()

    print("\nBLOCKCHAIN CONNECTION")
    print("-" * 78)
    print(f"Connected       : {info['connected']}")
    print(f"Network         : {info['network']}")
    print(f"Chain ID        : {info['chain_id']}")
    print(f"Contract        : {info['contract_address']}")

    # ------------------------------------------------------------------
    # Claim / record identity
    # ------------------------------------------------------------------

    record_id = claim_id_to_bytes32(claim_id).hex()

    print("\nRECORD IDENTITY")
    print("-" * 78)
    print(f"Claim ID        : {claim_id}")
    print(f"Record ID       : 0x{record_id}")

    # ------------------------------------------------------------------
    # Read directly from AssessmentRegistry
    # ------------------------------------------------------------------

    assessment = get_assessment(claim_id)

    print("\nON-CHAIN ASSESSMENT")
    print("-" * 78)
    print(f"Image Hash      : {assessment['image_hash']}")
    print(f"Prediction Hash : {assessment['prediction_hash']}")
    print(f"Model Version   : {assessment['model_version']}")
    print(f"Timestamp       : {assessment['timestamp']}")
    print(f"Recorder        : {assessment['recorder']}")

    # ------------------------------------------------------------------
    # Human-readable timestamp
    # ------------------------------------------------------------------

    timestamp = int(assessment["timestamp"])

    if timestamp > 0:
        dt = datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        )

        print(f"UTC Time        : {dt.isoformat()}")

    # ------------------------------------------------------------------
    # Complete JSON representation
    # ------------------------------------------------------------------

    print("\nRAW RECORD OBJECT")
    print("-" * 78)
    print(
        json.dumps(
            assessment,
            indent=2,
        )
    )

    print("\n" + "=" * 78)
    print("END OF ON-CHAIN RECORD")
    print("=" * 78)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(
            "Usage:\n"
            "  python -m blockchain.scripts.show_onchain_record "
            "<CLAIM_ID>\n\n"
            "Example:\n"
            "  python -m blockchain.scripts.show_onchain_record "
            "TC-PRODUCTION-E2E-002"
        )
        sys.exit(1)

    show_record(sys.argv[1])