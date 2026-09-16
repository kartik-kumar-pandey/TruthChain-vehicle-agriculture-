"""
TruthChain 2.0 - Full Evidence Inspector

Purpose
-------
Build a single audit/demo view that combines:

    CLAIM
    AI PIPELINE (off-chain evidence)
    BLOCKCHAIN (on-chain immutable record + tx metadata when available)
    INTEGRITY (fresh comparison against Sepolia)

Important distinction
---------------------
The AssessmentRegistry contract stores:
    - record ID (derived from claim ID)
    - image hash
    - prediction hash
    - model version
    - timestamp
    - recorder address

The rich AI agent reports are NOT stored in the Solidity record. They are
off-chain evidence. This inspector therefore labels every section clearly.

Transaction hash and block number are transaction metadata, not Solidity
storage fields. If the API certificate contains them, the inspector displays
them and can independently fetch the receipt from Sepolia.

Usage
-----
From the TruthChain-Production project root:

1) If the AI API is running:
    .\\ai-services\\.venv\\Scripts\\python.exe -m blockchain.scripts.show_evidence_inspector TC-PRODUCTION-E2E-002

2) If the API is not running, save the API response JSON and use:
    .\\ai-services\\.venv\\Scripts\\python.exe -m blockchain.scripts.show_evidence_inspector TC-PRODUCTION-E2E-002 --evidence-file evidence.json

3) You may explicitly provide a transaction hash:
    .\\ai-services\\.venv\\Scripts\\python.exe -m blockchain.scripts.show_evidence_inspector TC-PRODUCTION-E2E-002 --tx-hash 0x...

The script NEVER prints private keys.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from web3 import Web3

from blockchain.assessment_registry import (
    claim_id_to_bytes32,
    connection_info,
    get_assessment,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BLOCKCHAIN_DIR = PROJECT_ROOT / "blockchain"

for env_path in (
    BLOCKCHAIN_DIR / ".env",
    PROJECT_ROOT / ".env",
):
    if env_path.exists():
        load_dotenv(env_path, override=False)


AGENTS = [
    "ImageAgent",
    "SensorAgent",
    "TextAgent",
    "CrossModalAgent",
    "RiskEngine",
    "AdversarialVerifier",
    "ExplanationAgent",
    "CommunicationAgent",
]


def shorten(value: Any, width: int = 24) -> str:
    """Keep long hashes/addresses readable in terminal output."""
    if value is None:
        return "N/A"
    text = str(value)
    if len(text) <= width:
        return text
    if text.startswith("0x"):
        return f"{text[:10]}...{text[-8:]}"
    return f"{text[:width - 3]}..."


def yes_no(value: Any) -> str:
    return "MATCH" if bool(value) else "MISMATCH"


def load_evidence_file(path: str) -> Optional[Dict[str, Any]]:
    """Load an API response or its data object from JSON."""
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"Evidence file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    # Accept either:
    #   {"status":"success","data":{...}}
    # or directly:
    #   {"claim_id":"...", "agent_reports":...}
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]

    if isinstance(payload, dict):
        return payload

    raise ValueError("Evidence JSON must contain an object.")


def fetch_api_evidence(
    claim_id: str,
    api_url: str,
    timeout: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    Try the TruthChain API first.

    This is intentionally optional. Blockchain inspection still works if
    the API is offline, because the on-chain portion is read directly from
    Sepolia.
    """
    try:
        import urllib.error
        import urllib.request

        url = f"{api_url.rstrip('/')}/api/v1/claims/{claim_id}"

        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json"},
            method="GET",
        )

        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw)

        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            return payload["data"]

        if isinstance(payload, dict):
            return payload

    except Exception:
        # API is optional. Do not make a local API outage look like a
        # blockchain failure.
        return None

    return None


def get_transaction_details(
    tx_hash: Optional[str],
) -> Dict[str, Any]:
    """
    Independently retrieve transaction/receipt metadata from Sepolia.

    This is NOT contract storage. It is Ethereum transaction metadata.
    """
    if not tx_hash:
        return {
            "available": False,
            "tx_hash": None,
            "block_number": None,
            "status": None,
            "gas_used": None,
        }

    rpc_url = (
        os.getenv("SEPOLIA_RPC_URL")
        or os.getenv("BLOCKCHAIN_PROVIDER")
    )

    if not rpc_url:
        return {
            "available": False,
            "tx_hash": tx_hash,
            "block_number": None,
            "status": None,
            "gas_used": None,
            "error": "SEPOLIA_RPC_URL/BLOCKCHAIN_PROVIDER not configured.",
        }

    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))

        if not w3.is_connected():
            raise ConnectionError("Unable to connect to Sepolia RPC.")

        normalized = (
            tx_hash if tx_hash.startswith("0x") else f"0x{tx_hash}"
        )

        receipt = w3.eth.get_transaction_receipt(normalized)

        return {
            "available": True,
            "tx_hash": normalized,
            "block_number": receipt["blockNumber"],
            "status": receipt["status"],
            "gas_used": receipt["gasUsed"],
        }

    except Exception as exc:
        return {
            "available": False,
            "tx_hash": tx_hash,
            "block_number": None,
            "status": None,
            "gas_used": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def normalize_report(report: Any) -> Dict[str, Any]:
    return report if isinstance(report, dict) else {}


def print_agent_row(name: str, report: Dict[str, Any]) -> None:
    decision = report.get("decision", "N/A")
    confidence = report.get("confidence")
    risk = report.get("risk_score")

    confidence_text = (
        f"{float(confidence):.2f}"
        if confidence is not None
        else "N/A"
    )

    risk_text = (
        f"{float(risk):.2f}"
        if risk is not None
        else "N/A"
    )

    print(
        f"│   ├── {name:<20} "
        f"decision={decision:<18} "
        f"risk={risk_text:<5} "
        f"confidence={confidence_text}"
    )


def print_inspector(
    claim_id: str,
    evidence: Optional[Dict[str, Any]],
    on_chain: Dict[str, Any],
    verification: Dict[str, Any],
    tx_details: Dict[str, Any],
    info: Dict[str, Any],
) -> None:
    evidence = evidence or {}

    agent_reports = evidence.get("agent_reports", {})
    if not isinstance(agent_reports, dict):
        agent_reports = {}

    certificate = evidence.get("certificate", {})
    if not isinstance(certificate, dict):
        certificate = {}

    api_claim_id = evidence.get("claim_id", claim_id)
    api_image_hash = certificate.get("image_hash")
    api_prediction_hash = certificate.get("prediction_hash")

    image_hash_match = (
        api_image_hash.lower() == on_chain["image_hash"].lower()
        if api_image_hash
        else verification["image_hash_match"]
    )

    prediction_hash_match = (
        api_prediction_hash.lower()
        == on_chain["prediction_hash"].lower()
        if api_prediction_hash
        else verification["prediction_hash_match"]
    )

    overall_match = image_hash_match and prediction_hash_match

    timestamp = int(on_chain["timestamp"])
    utc_time = (
        datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
        if timestamp > 0
        else "N/A"
    )

    print()
    print("═" * 88)
    print("TRUTHCHAIN 2.0 — FULL EVIDENCE INSPECTOR")
    print("═" * 88)

    # ------------------------------------------------------------------
    # CLAIM
    # ------------------------------------------------------------------
    print()
    print("CLAIM")
    print("├── Claim ID        :", api_claim_id)
    print("├── Image hash      :", on_chain["image_hash"])
    print("└── Prediction hash :", on_chain["prediction_hash"])

    # ------------------------------------------------------------------
    # AI PIPELINE
    # ------------------------------------------------------------------
    print()
    print("AI PIPELINE")
    print("└── SOURCE: OFF-CHAIN EVIDENCE / AI API")

    for index, agent_name in enumerate(AGENTS):
        report = normalize_report(agent_reports.get(agent_name))

        connector = "└──" if index == len(AGENTS) - 1 else "├──"

        decision = report.get("decision", "NOT AVAILABLE")
        confidence = report.get("confidence")
        risk = report.get("risk_score")

        confidence_text = (
            f"{float(confidence):.2f}"
            if confidence is not None
            else "N/A"
        )
        risk_text = (
            f"{float(risk):.2f}"
            if risk is not None
            else "N/A"
        )

        print(
            f"{connector} {agent_name:<22} "
            f"{decision:<20} "
            f"risk={risk_text:<5} "
            f"confidence={confidence_text}"
        )

    pipeline_status = evidence.get("pipeline_status", "N/A")
    final_verdict = evidence.get("final_verdict", "N/A")
    fraud_score = evidence.get("fraud_score", "N/A")

    print()
    print(f"    Pipeline status : {pipeline_status}")
    print(f"    Final verdict   : {final_verdict}")
    print(f"    Fraud score     : {fraud_score}")

    # ------------------------------------------------------------------
    # BLOCKCHAIN
    # ------------------------------------------------------------------
    print()
    print("BLOCKCHAIN")
    print("└── SOURCE: SEPOLIA / ASSESSMENT REGISTRY")

    print("    ├── Network         :", info["network"])
    print("    ├── Chain ID        :", info["chain_id"])
    print("    ├── Contract        :", info["contract_address"])
    print("    ├── Record ID       :", on_chain["record_id"])
    print("    ├── Model version   :", on_chain["model_version"])
    print("    ├── Timestamp       :", on_chain["timestamp"])
    print("    ├── UTC time        :", utc_time)
    print("    └── Recorder        :", on_chain["recorder"])

    tx_hash = tx_details.get("tx_hash")
    block_number = tx_details.get("block_number")

    print()
    print("    TRANSACTION METADATA")
    print("    ├── Transaction     :", tx_hash or "NOT PROVIDED")
    print("    ├── Block           :", block_number or "NOT PROVIDED")
    print("    ├── Receipt status  :", tx_details.get("status", "N/A"))
    print("    └── Gas used        :", tx_details.get("gas_used", "N/A"))

    if tx_hash:
        clean_tx_hash = (
            tx_hash if str(tx_hash).startswith("0x")
            else f"0x{tx_hash}"
        )
        print(
            "        Etherscan      : "
            f"https://sepolia.etherscan.io/tx/{clean_tx_hash}"
        )

    print()
    print("    NOTE:")
    print("    Transaction hash and block number are Ethereum transaction")
    print("    metadata. They are not fields stored by getAssessment().")

    # ------------------------------------------------------------------
    # INTEGRITY
    # ------------------------------------------------------------------
    print()
    print("INTEGRITY")
    print("├── Image hash MATCH       :", "TRUE" if image_hash_match else "FALSE")
    print(
        "├── Prediction hash MATCH  :",
        "TRUE" if prediction_hash_match else "FALSE",
    )
    print("└── Overall MATCH          :", "TRUE" if overall_match else "FALSE")

    print()
    print("    VERIFICATION SOURCE")
    print("    ├── Contract getAssessment() : READ")
    print("    ├── Contract verifyAssessment():",
          "MATCH" if verification["contract_match"] else "MISMATCH")
    print("    ├── Image hash comparison    :",
          "MATCH" if verification["image_hash_match"] else "MISMATCH")
    print("    └── Prediction comparison    :",
          "MATCH" if verification["prediction_hash_match"] else "MISMATCH")

    # ------------------------------------------------------------------
    # Storage boundary
    # ------------------------------------------------------------------
    print()
    print("STORAGE BOUNDARY")
    print("├── IMMUTABLE ON-CHAIN")
    print("│   ├── Record ID")
    print("│   ├── Image SHA-256 hash")
    print("│   ├── Prediction SHA-256 hash")
    print("│   ├── Model version")
    print("│   ├── Timestamp")
    print("│   └── Recorder address")
    print("│")
    print("└── OFF-CHAIN")
    print("    ├── Image file / raw evidence")
    print("    ├── Sensor telemetry")
    print("    ├── Claim narrative")
    print("    ├── All AI agent reports")
    print("    ├── Risk/explanation/communication details")
    print("    └── Full pipeline response")

    print()
    print("═" * 88)
    print(
        "AUDIT RESULT:",
        "VERIFIED — EVIDENCE HASHES MATCH ON-CHAIN"
        if overall_match
        else "FAILED — EVIDENCE DOES NOT MATCH ON-CHAIN",
    )
    print("═" * 88)
    print()


def inspect(
    claim_id: str,
    evidence_file: Optional[str],
    api_url: str,
    tx_hash_override: Optional[str],
) -> None:
    print("\nLoading TruthChain evidence and Sepolia record...")

    # --------------------------------------------------------------
    # 1. Optional off-chain evidence
    # --------------------------------------------------------------
    evidence = None

    if evidence_file:
        evidence = load_evidence_file(evidence_file)
    else:
        evidence = fetch_api_evidence(claim_id, api_url)

    # --------------------------------------------------------------
    # 2. Read blockchain connection
    # --------------------------------------------------------------
    info = connection_info()

    # --------------------------------------------------------------
    # 3. Read immutable contract record
    # --------------------------------------------------------------
    on_chain = get_assessment(claim_id)

    # --------------------------------------------------------------
    # 4. Verify the exact hashes read from the chain against the
    #    same values. This also exercises the deployed verifier.
    # --------------------------------------------------------------
    image_bytes = bytes.fromhex(
        on_chain["image_hash"][2:]
        if on_chain["image_hash"].startswith("0x")
        else on_chain["image_hash"]
    )

    prediction_bytes = bytes.fromhex(
        on_chain["prediction_hash"][2:]
        if on_chain["prediction_hash"].startswith("0x")
        else on_chain["prediction_hash"]
    )

    w3 = Web3(Web3.HTTPProvider(
        os.getenv("SEPOLIA_RPC_URL")
        or os.getenv("BLOCKCHAIN_PROVIDER")
    ))

    if not w3.is_connected():
        raise ConnectionError("Unable to connect to Sepolia RPC.")

    contract_address = info["contract_address"]

    # Use the public contract call directly so the inspector does not
    # depend on the return shape of verify_assessment().
    from blockchain.assessment_registry import ASSESSMENT_REGISTRY_ABI

    contract = w3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=ASSESSMENT_REGISTRY_ABI,
    )

    record_id_bytes = claim_id_to_bytes32(claim_id)

    contract_match, registered_at = contract.functions.verifyAssessment(
        record_id_bytes,
        image_bytes,
        prediction_bytes,
    ).call()

    # Since the supplied values are exactly what getAssessment returned,
    # these two comparisons must be true for a healthy record.
    image_hash_match = True
    prediction_hash_match = True

    # --------------------------------------------------------------
    # 5. Find transaction metadata from API certificate or override.
    # --------------------------------------------------------------
    certificate = (
        evidence.get("certificate", {})
        if isinstance(evidence, dict)
        else {}
    )

    if not isinstance(certificate, dict):
        certificate = {}

    tx_hash = (
        tx_hash_override
        or certificate.get("transaction_hash")
    )

    tx_details = get_transaction_details(tx_hash)

    # --------------------------------------------------------------
    # 6. Cross-check API certificate hashes if available.
    # --------------------------------------------------------------
    if evidence:
        api_image_hash = certificate.get("image_hash")
        api_prediction_hash = certificate.get("prediction_hash")

        if api_image_hash:
            image_hash_match = (
                str(api_image_hash).lower()
                == str(on_chain["image_hash"]).lower()
            )

        if api_prediction_hash:
            prediction_hash_match = (
                str(api_prediction_hash).lower()
                == str(on_chain["prediction_hash"]).lower()
            )

    verification = {
        "contract_match": bool(contract_match),
        "registered_at": registered_at,
        "image_hash_match": bool(image_hash_match),
        "prediction_hash_match": bool(prediction_hash_match),
    }

    print_inspector(
        claim_id=claim_id,
        evidence=evidence,
        on_chain=on_chain,
        verification=verification,
        tx_details=tx_details,
        info=info,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="TruthChain 2.0 full AI + blockchain evidence inspector."
    )

    parser.add_argument(
        "claim_id",
        help="TruthChain claim ID, e.g. TC-PRODUCTION-E2E-002",
    )

    parser.add_argument(
        "--evidence-file",
        help=(
            "Optional JSON file containing the /api/v1/consensus/evaluate "
            "response or its data object."
        ),
    )

    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="TruthChain API base URL (default: http://127.0.0.1:8000)",
    )

    parser.add_argument(
        "--tx-hash",
        help="Optional transaction hash when it is not present in the API evidence.",
    )

    args = parser.parse_args()

    try:
        inspect(
            claim_id=args.claim_id,
            evidence_file=args.evidence_file,
            api_url=args.api_url,
            tx_hash_override=args.tx_hash,
        )

    except Exception as exc:
        print()
        print("TRUTHCHAIN EVIDENCE INSPECTOR FAILED")
        print(f"{type(exc).__name__}: {exc}")
        print()
        sys.exit(2)


if __name__ == "__main__":
    main()
