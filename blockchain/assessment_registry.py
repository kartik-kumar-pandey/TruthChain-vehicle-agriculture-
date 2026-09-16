"""
TruthChain AssessmentRegistry blockchain integration.

Connects the TruthChain backend to the deployed AssessmentRegistry
contract on Sepolia.

Important:
- The Solidity contract uses bytes32 recordId.
- Human-readable claim IDs such as "TC-TEST-001" are deterministically
  converted to bytes32 using Ethereum keccak256.
- Image/prediction evidence is hashed with SHA-256 before being stored.
- Blockchain registration is idempotent: an already-registered claim
  is read from the blockchain instead of being registered again.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import ContractLogicError

# ---------------------------------------------------------------------------
# Paths / environment
# ---------------------------------------------------------------------------

# blockchain/assessment_registry.py -> .parent = blockchain/, .parent.parent = project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
BLOCKCHAIN_DIR = Path(__file__).resolve().parent
BLOCKCHAIN_ENV = BLOCKCHAIN_DIR / ".env"
CONTRACT_INFO_PATH = BLOCKCHAIN_DIR / "contract_info.json"

if BLOCKCHAIN_ENV.exists():
    load_dotenv(BLOCKCHAIN_ENV)

ROOT_ENV = PROJECT_ROOT / ".env"

if ROOT_ENV.exists():
    load_dotenv(ROOT_ENV, override=False)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)


# ---------------------------------------------------------------------------
# Contract ABI
# ---------------------------------------------------------------------------

ASSESSMENT_REGISTRY_ABI = [
    {
        "inputs": [
            {
                "internalType": "bytes32",
                "name": "recordId",
                "type": "bytes32",
            },
            {
                "internalType": "bytes32",
                "name": "imageHash",
                "type": "bytes32",
            },
            {
                "internalType": "bytes32",
                "name": "predictionHash",
                "type": "bytes32",
            },
            {
                "internalType": "string",
                "name": "modelVersion",
                "type": "string",
            },
        ],
        "name": "registerAssessment",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {
                "internalType": "bytes32",
                "name": "recordId",
                "type": "bytes32",
            }
        ],
        "name": "getAssessment",
        "outputs": [
            {
                "internalType": "bytes32",
                "name": "imageHash",
                "type": "bytes32",
            },
            {
                "internalType": "bytes32",
                "name": "predictionHash",
                "type": "bytes32",
            },
            {
                "internalType": "string",
                "name": "modelVersion",
                "type": "string",
            },
            {
                "internalType": "uint256",
                "name": "timestamp",
                "type": "uint256",
            },
            {
                "internalType": "address",
                "name": "recorder",
                "type": "address",
            },
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {
                "internalType": "bytes32",
                "name": "recordId",
                "type": "bytes32",
            },
            {
                "internalType": "bytes32",
                "name": "imageHash",
                "type": "bytes32",
            },
            {
                "internalType": "bytes32",
                "name": "predictionHash",
                "type": "bytes32",
            },
        ],
        "name": "verifyAssessment",
        "outputs": [
            {
                "internalType": "bool",
                "name": "isMatch",
                "type": "bool",
            },
            {
                "internalType": "uint256",
                "name": "registeredAt",
                "type": "uint256",
            },
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_contract_address() -> str:
    """Load the deployed AssessmentRegistry address."""

    env_address = os.getenv("ASSESSMENT_CONTRACT_ADDRESS")

    if env_address:
        return Web3.to_checksum_address(env_address)

    if not CONTRACT_INFO_PATH.exists():
        raise FileNotFoundError(
            f"Contract address not found. Missing {CONTRACT_INFO_PATH}"
        )

    with CONTRACT_INFO_PATH.open("r", encoding="utf-8") as f:
        contract_info = json.load(f)

    address = contract_info.get("address")

    if not address:
        raise ValueError(
            f"No 'address' field found in {CONTRACT_INFO_PATH}"
        )

    return Web3.to_checksum_address(address)


def _get_rpc_url() -> str:
    """Load the Sepolia RPC URL."""

    rpc_url = (
        os.getenv("SEPOLIA_RPC_URL")
        or os.getenv("BLOCKCHAIN_PROVIDER")
    )

    if not rpc_url:
        raise RuntimeError(
            "Missing SEPOLIA_RPC_URL or BLOCKCHAIN_PROVIDER."
        )

    return rpc_url


def _get_private_key() -> str:
    """Load the signing private key.

    Never print this value.
    """

    private_key = os.getenv("PRIVATE_KEY")

    if not private_key:
        raise RuntimeError(
            "Missing PRIVATE_KEY in blockchain/.env."
        )

    return private_key


def claim_id_to_bytes32(claim_id: str) -> bytes:
    """
    Convert a human-readable TruthChain claim ID into bytes32.

    Example:
        TC-TEST-001
        ->
        keccak256("TC-TEST-001")
    """

    if not claim_id:
        raise ValueError("claim_id cannot be empty.")

    return Web3.keccak(text=str(claim_id))


def sha256_bytes32(value: Any) -> bytes:
    """
    SHA-256 hash arbitrary canonicalized data into exactly 32 bytes.
    """

    if isinstance(value, bytes):
        payload = value

    elif isinstance(value, str):
        payload = value.encode("utf-8")

    else:
        payload = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    return hashlib.sha256(payload).digest()


def _bytes32_to_hex(value: bytes) -> str:
    """Convert bytes32 to a readable 0x-prefixed hex string."""

    return Web3.to_hex(value)


def _get_web3() -> Web3:
    """Create and validate a Web3 connection."""

    w3 = Web3(Web3.HTTPProvider(_get_rpc_url()))

    if not w3.is_connected():
        raise ConnectionError(
            "Unable to connect to the blockchain RPC."
        )

    return w3


def _get_contract(w3: Web3):
    """Return the deployed AssessmentRegistry contract."""

    address = _load_contract_address()

    contract = w3.eth.contract(
        address=address,
        abi=ASSESSMENT_REGISTRY_ABI,
    )

    logger.info(
        "AssessmentRegistry connected: %s",
        address,
    )

    return contract


# ---------------------------------------------------------------------------
# Connection test
# ---------------------------------------------------------------------------

def connection_info() -> Dict[str, Any]:
    """
    Return blockchain connection information without exposing secrets.
    """

    w3 = _get_web3()
    contract = _get_contract(w3)

    account = w3.eth.account.from_key(_get_private_key())

    balance = w3.eth.get_balance(account.address)

    chain_id = w3.eth.chain_id

    network = {
        11155111: "Sepolia",
        1: "Ethereum Mainnet",
        31337: "Hardhat Local",
    }.get(chain_id, f"Chain {chain_id}")

    return {
        "connected": True,
        "chain_id": chain_id,
        "network": network,
        "contract_address": contract.address,
        "recorder_address": account.address,
        "balance_wei": balance,
        "balance_eth": float(
            w3.from_wei(balance, "ether")
        ),
    }


# ---------------------------------------------------------------------------
# Register assessment
# ---------------------------------------------------------------------------

def register_assessment(
    claim_id: str,
    image_hash: bytes,
    prediction_hash: bytes,
    model_version: str,
) -> Dict[str, Any]:
    """
    Register an assessment on-chain.

    This function performs the actual blockchain transaction.
    """

    if len(image_hash) != 32:
        raise ValueError(
            "image_hash must be exactly 32 bytes."
        )

    if len(prediction_hash) != 32:
        raise ValueError(
            "prediction_hash must be exactly 32 bytes."
        )

    w3 = _get_web3()
    contract = _get_contract(w3)

    private_key = _get_private_key()
    account = w3.eth.account.from_key(private_key)

    record_id = claim_id_to_bytes32(claim_id)

    nonce = w3.eth.get_transaction_count(
        account.address,
        "pending",
    )

    transaction = contract.functions.registerAssessment(
        record_id,
        image_hash,
        prediction_hash,
        model_version,
    ).build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "chainId": w3.eth.chain_id,
        }
    )

    gas_estimate = w3.eth.estimate_gas(transaction)

    transaction["gas"] = int(
        gas_estimate * 1.20
    )

    latest_block = w3.eth.get_block("latest")

    base_fee = latest_block.get("baseFeePerGas")

    if base_fee is not None:
        priority_fee = w3.to_wei(
            1.5,
            "gwei",
        )

        transaction["maxPriorityFeePerGas"] = priority_fee

        transaction["maxFeePerGas"] = (
            int(base_fee * 2)
            + priority_fee
        )

    else:
        transaction["gasPrice"] = w3.eth.gas_price

    signed_transaction = w3.eth.account.sign_transaction(
        transaction,
        private_key=private_key,
    )

    raw_transaction = getattr(
        signed_transaction,
        "raw_transaction",
        getattr(
            signed_transaction,
            "rawTransaction",
            None,
        ),
    )

    if raw_transaction is None:
        raise RuntimeError(
            "Unable to obtain signed transaction bytes."
        )

    tx_hash = w3.eth.send_raw_transaction(
        raw_transaction
    )

    logger.info(
        "Assessment transaction submitted: %s",
        tx_hash.hex(),
    )

    receipt = w3.eth.wait_for_transaction_receipt(
        tx_hash
    )

    if receipt.status != 1:
        raise RuntimeError(
            f"Assessment transaction failed: {tx_hash.hex()}"
        )

    return {
        "success": True,
        "claim_id": claim_id,
        "record_id": _bytes32_to_hex(record_id),
        "transaction_hash": tx_hash.hex(),
        "block_number": receipt.blockNumber,
        "gas_used": receipt.gasUsed,
        "contract_address": contract.address,
        "model_version": model_version,
    }


# ---------------------------------------------------------------------------
# Read assessment
# ---------------------------------------------------------------------------

def get_assessment(claim_id: str) -> Dict[str, Any]:
    """
    Read an assessment from the blockchain.
    """

    w3 = _get_web3()
    contract = _get_contract(w3)

    record_id = claim_id_to_bytes32(claim_id)

    (
        image_hash,
        prediction_hash,
        model_version,
        timestamp,
        recorder,
    ) = contract.functions.getAssessment(
        record_id
    ).call()

    return {
        "claim_id": claim_id,
        "record_id": _bytes32_to_hex(record_id),
        "image_hash": _bytes32_to_hex(image_hash),
        "prediction_hash": _bytes32_to_hex(prediction_hash),
        "model_version": model_version,
        "timestamp": timestamp,
        "recorder": recorder,
    }


# ---------------------------------------------------------------------------
# Registration existence check
# ---------------------------------------------------------------------------

def is_assessment_registered(
    claim_id: str,
) -> bool:
    """
    Return True when the claim already has an on-chain assessment.

    The deployed Solidity contract initializes an unregistered record with
    timestamp == 0. A successful registration stores block timestamp,
    therefore timestamp > 0 means the assessment exists.
    """

    assessment = get_assessment(claim_id)

    return int(assessment["timestamp"]) > 0


# ---------------------------------------------------------------------------
# Verify assessment
# ---------------------------------------------------------------------------

def verify_assessment(
    claim_id: str,
    image_hash: bytes,
    prediction_hash: bytes,
) -> Dict[str, Any]:
    """
    Verify supplied evidence against the on-chain assessment.

    Returns both the contract verification result and the individual
    hash comparisons so callers can independently inspect image and
    prediction integrity.
    """

    if len(image_hash) != 32:
        raise ValueError(
            "image_hash must be exactly 32 bytes."
        )

    if len(prediction_hash) != 32:
        raise ValueError(
            "prediction_hash must be exactly 32 bytes."
        )

    w3 = _get_web3()
    contract = _get_contract(w3)

    record_id = claim_id_to_bytes32(claim_id)

    # Ask the deployed contract to perform its native verification.
    is_match, registered_at = (
        contract.functions.verifyAssessment(
            record_id,
            image_hash,
            prediction_hash,
        ).call()
    )

    # Read the complete immutable assessment back from chain so the
    # caller can see exactly what was stored and independently compare
    # each evidence hash.
    on_chain = get_assessment(claim_id)

    supplied_image_hash = _bytes32_to_hex(image_hash)
    supplied_prediction_hash = _bytes32_to_hex(prediction_hash)

    on_chain_image_hash = on_chain["image_hash"]
    on_chain_prediction_hash = on_chain["prediction_hash"]

    image_hash_match = (
        supplied_image_hash.lower()
        == on_chain_image_hash.lower()
    )

    prediction_hash_match = (
        supplied_prediction_hash.lower()
        == on_chain_prediction_hash.lower()
    )

    # The contract result remains authoritative. The individual
    # comparisons provide transparent diagnostic/audit information.
    return {
        "claim_id": claim_id,
        "record_id": _bytes32_to_hex(record_id),
        "is_match": bool(is_match),
        "image_hash_match": image_hash_match,
        "prediction_hash_match": prediction_hash_match,
        "supplied_image_hash": supplied_image_hash,
        "supplied_prediction_hash": supplied_prediction_hash,
        "on_chain_image_hash": on_chain_image_hash,
        "on_chain_prediction_hash": on_chain_prediction_hash,
        "model_version": on_chain["model_version"],
        "registered_at": registered_at,
        "on_chain_timestamp": on_chain["timestamp"],
        "recorder": on_chain["recorder"],
    }

# ---------------------------------------------------------------------------
# Certificate creation
# ---------------------------------------------------------------------------
def create_certificate(
    claim_id: str,
    image_evidence: Any,
    prediction: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Create and register a TruthChain blockchain certificate.

    Registration is idempotent.

    If claim_id has already been registered on-chain, this function
    does NOT submit another transaction. Instead it retrieves and
    returns the existing immutable blockchain assessment.

    If the deployed contract reports "Assessment not found", the claim
    is treated as new and a registration transaction is submitted.

    The actual raw image is NOT placed on-chain.
    Only cryptographic hashes are stored.
    """

    if not claim_id:
        raise ValueError(
            "claim_id cannot be empty."
        )

    if not isinstance(prediction, dict):
        raise TypeError(
            "prediction must be a dictionary."
        )

    model_version = str(
        prediction.get(
            "model_version",
            "truthchain-v2.0",
        )
    )

    # ---------------------------------------------------------------
    # Step 1: Build deterministic hashes for this assessment
    # ---------------------------------------------------------------

    image_hash = sha256_bytes32(
        image_evidence
    )

    canonical_prediction = {
        "claim_id": claim_id,
        "prediction": prediction,
    }

    prediction_hash = sha256_bytes32(
        canonical_prediction
    )

    # ---------------------------------------------------------------
    # Step 2: Check whether the claim already exists
    #
    # IMPORTANT:
    # The deployed AssessmentRegistry contract reverts with:
    #
    #     "Assessment not found"
    #
    # when the claim does not exist.
    #
    # That is expected for a new claim, so we must continue to the
    # registration step instead of treating it as an error.
    # ---------------------------------------------------------------

    existing = None

    try:
        existing = get_assessment(
            claim_id
        )

    except ContractLogicError as exc:
        error_text = str(exc)

        if "Assessment not found" in error_text:
            logger.info(
                "No existing assessment found for %s. "
                "Proceeding with new blockchain registration.",
                claim_id,
            )
            existing = None

        else:
            logger.exception(
                "Blockchain lookup reverted unexpectedly "
                "for claim %s",
                claim_id,
            )
            raise

    except Exception:
        logger.exception(
            "Failed while checking existing assessment "
            "for claim %s",
            claim_id,
        )
        raise

    # ---------------------------------------------------------------
    # Step 3: Existing assessment
    #
    # Never overwrite an immutable on-chain assessment.
    # ---------------------------------------------------------------

    if existing is not None and int(
        existing.get(
            "timestamp",
            0,
        )
    ) > 0:

        logger.info(
            "Assessment already registered for %s. "
            "Reusing existing blockchain certificate.",
            claim_id,
        )

        # -----------------------------------------------------------
        # Integrity check
        # -----------------------------------------------------------

        existing_image_hash = existing[
            "image_hash"
        ]

        existing_prediction_hash = existing[
            "prediction_hash"
        ]

        current_image_hash = _bytes32_to_hex(
            image_hash
        )

        current_prediction_hash = _bytes32_to_hex(
            prediction_hash
        )

        if existing_image_hash != current_image_hash:
            raise ValueError(
                "Blockchain integrity conflict: "
                f"claim '{claim_id}' is already registered, "
                "but the supplied image evidence produces a "
                "different image hash."
            )

        if existing_prediction_hash != current_prediction_hash:
            raise ValueError(
                "Blockchain integrity conflict: "
                f"claim '{claim_id}' is already registered, "
                "but the supplied prediction produces a "
                "different prediction hash."
            )

        return {
            "claim_id": claim_id,
            "record_id": existing[
                "record_id"
            ],
            "image_hash": existing[
                "image_hash"
            ],
            "prediction_hash": existing[
                "prediction_hash"
            ],
            "model_version": existing[
                "model_version"
            ],
            "transaction_hash": None,
            "block_number": None,
            "contract_address": _load_contract_address(),
            "network": "Sepolia",
            "status": "ALREADY_REGISTERED",
            "reused": True,
            "registered_at": existing[
                "timestamp"
            ],
            "recorder": existing[
                "recorder"
            ],
        }

    # ---------------------------------------------------------------
    # Step 4: New assessment
    #
    # The claim does not exist, so create its deterministic record ID
    # and submit the real blockchain transaction.
    # ---------------------------------------------------------------

    record_id = claim_id_to_bytes32(
        claim_id
    )

    logger.info(
        "Registering new assessment for %s on Sepolia.",
        claim_id,
    )

    # ---------------------------------------------------------------
    # Step 5: Connect to deployed contract
    # ---------------------------------------------------------------

    w3 = _get_web3()
    contract = _get_contract(w3)

    # ---------------------------------------------------------------
    # Step 6: Build transaction
    # ---------------------------------------------------------------

    account = w3.eth.account.from_key(
        _get_private_key()
    )

    nonce = w3.eth.get_transaction_count(
        account.address,
        "pending",
    )

    chain_id = w3.eth.chain_id

    gas_price = w3.eth.gas_price

    transaction = contract.functions.registerAssessment(
        record_id,
        image_hash,
        prediction_hash,
        model_version,
    ).build_transaction(
        {
            "from": account.address,
            "nonce": nonce,
            "chainId": chain_id,
            "gas": 300000,
            "maxPriorityFeePerGas": (
                w3.to_wei(
                    1,
                    "gwei",
                )
            ),
            "maxFeePerGas": (
                gas_price * 2
            ),
        }
    )

    # ---------------------------------------------------------------
    # Step 7: Sign transaction
    # ---------------------------------------------------------------

    signed = account.sign_transaction(
        transaction
    )

    raw_transaction = getattr(
        signed,
        "raw_transaction",
        None,
    )

    if raw_transaction is None:
        raw_transaction = getattr(
            signed,
            "rawTransaction",
            None,
        )

    if raw_transaction is None:
        raise RuntimeError(
            "Unable to obtain signed raw transaction."
        )

    # ---------------------------------------------------------------
    # Step 8: Submit transaction
    # ---------------------------------------------------------------

    tx_hash = w3.eth.send_raw_transaction(
        raw_transaction
    )

    tx_hash_hex = tx_hash.hex()

    logger.info(
        "Assessment registration transaction submitted "
        "for %s: %s",
        claim_id,
        tx_hash_hex,
    )

    # ---------------------------------------------------------------
    # Step 9: Wait for blockchain confirmation
    # ---------------------------------------------------------------

    receipt = w3.eth.wait_for_transaction_receipt(
        tx_hash
    )

    if receipt["status"] != 1:
        raise RuntimeError(
            "Blockchain assessment registration transaction "
            f"failed for claim '{claim_id}'. "
            f"Transaction: {tx_hash_hex}"
        )

    block_number = receipt[
        "blockNumber"
    ]

    # ---------------------------------------------------------------
    # Step 10: Return immutable certificate metadata
    # ---------------------------------------------------------------

    logger.info(
        "Assessment registered successfully for %s "
        "in block %s.",
        claim_id,
        block_number,
    )

    return {
        "claim_id": claim_id,
        "record_id": _bytes32_to_hex(
            record_id
        ),
        "image_hash": _bytes32_to_hex(
            image_hash
        ),
        "prediction_hash": _bytes32_to_hex(
            prediction_hash
        ),
        "model_version": model_version,
        "transaction_hash": tx_hash_hex,
        "block_number": block_number,
        "contract_address": _load_contract_address(),
        "network": "Sepolia",
        "status": "REGISTERED",
        "reused": False,
        "registered_at": int(
            receipt.get(
                "blockNumber",
                0,
            )
        ),
        "recorder": account.address,
    }
# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    print("=" * 72)
    print("TRUTHCHAIN ASSESSMENT REGISTRY CONNECTION TEST")
    print("=" * 72)

    try:
        info = connection_info()

        print(
            json.dumps(
                info,
                indent=2,
            )
        )

        print(
            "\nBlockchain connection successful."
        )

    except Exception as exc:

        print(
            "\nBlockchain connection failed."
        )

        print(
            f"{type(exc).__name__}: {exc}"
        )

        raise
