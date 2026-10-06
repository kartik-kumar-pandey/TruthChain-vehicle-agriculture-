"""
TruthChain blockchain certificate graph node.

This node runs only after the final fraud assessment has been produced
AND the graph has explicitly authorized blockchain certification.

Safety model:
- blockchain_allowed MUST be True before this node can perform
  blockchain lookup or registration.
- Only a final VERIFIED assessment may be automatically certified.
- Incomplete/failed evidence pipelines are never certified.
- An existing immutable assessment is reused without creating a
  second transaction.
- A new claim creates exactly one blockchain assessment.
- The deployed AssessmentRegistry contract reverts with
  "Assessment not found" for a new claim; that specific revert is
  treated as "not registered yet".
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from web3.exceptions import ContractLogicError

from blockchain.assessment_registry import (
    create_certificate,
    get_assessment,
    _load_contract_address,
)
from graph.state import AgentState


logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTS
# ============================================================

AUTHORIZED_VERDICT = "VERIFIED"


# ============================================================
# BLOCKCHAIN CERTIFICATE NODE
# ============================================================

def blockchain_certificate_node(
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Register or reuse the finalized TruthChain assessment.

    HARD SECURITY BOUNDARY:

        blockchain_allowed == True
        AND
        final_verdict == VERIFIED
        AND
        required_agents_complete == True
        AND
        pipeline_status == COMPLETE
        AND
        no pipeline failures

    are required before any blockchain operation is performed.

    Expected state:
        claim_id
        domain
        final_verdict
        fraud_score
        agent_reports
        blockchain_allowed
        required_agents_complete
        pipeline_status
        pipeline_failures

    Returns:
        State updates containing the blockchain certificate.
    """

    # ---------------------------------------------------------------
    # HARD AUTHORIZATION CHECK
    # ---------------------------------------------------------------

    _assert_blockchain_authorized(
        state
    )

    # ---------------------------------------------------------------
    # CLAIM ID
    # ---------------------------------------------------------------

    claim_id = state.get(
        "claim_id"
    )

    if not claim_id:
        raise ValueError(
            "Blockchain certificate node requires claim_id."
        )

    # ---------------------------------------------------------------
    # FINAL VALUES
    # ---------------------------------------------------------------

    final_verdict = str(
        state.get(
            "final_verdict",
            "UNKNOWN",
        )
    ).strip().upper()

    # Motor domain uses fraud_score (int 0-100).
    # Agriculture domain uses risk_score (float 0.0-1.0).
    # Accept whichever is available and normalize to int 0-100.
    _raw_score = state.get("fraud_score") or state.get("risk_score") or 0
    _float_score = float(_raw_score)
    fraud_score = int(
        _float_score if _float_score > 1.0 else int(_float_score * 100)
    )

    agent_reports = state.get(
        "agent_reports",
        {},
    )

    if not isinstance(
        agent_reports,
        dict,
    ):
        raise ValueError(
            "Blockchain certificate node requires "
            "agent_reports to be a dictionary."
        )

    # ---------------------------------------------------------------
    # First check the blockchain.
    #
    # The deployed AssessmentRegistry contract reverts with
    # "Assessment not found" when the record does not exist.
    #
    # That specific revert means the claim is NEW and should proceed
    # to registration.
    # ---------------------------------------------------------------

    logger.info(
        "Checking blockchain registration for authorized "
        "claim: %s",
        claim_id,
    )

    existing = None

    try:

        existing = get_assessment(
            claim_id
        )

    except ContractLogicError as exc:

        error_text = str(
            exc
        )

        if "Assessment not found" in error_text:

            logger.info(
                "Claim %s is not registered yet. "
                "Proceeding with authorized blockchain registration.",
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
            "Failed while checking existing blockchain "
            "registration for claim %s",
            claim_id,
        )

        raise

    # ---------------------------------------------------------------
    # Existing claim.
    #
    # The blockchain record is already immutable and authoritative.
    # Reuse it directly without creating another transaction.
    # ---------------------------------------------------------------

    if (
        existing is not None
        and int(
            existing.get(
                "timestamp",
                0,
            )
        ) > 0
    ):

        logger.info(
            "Claim %s is already registered. "
            "Reusing existing immutable blockchain certificate.",
            claim_id,
        )

        certificate = {
            "claim_id": claim_id,
            "record_id": existing.get(
                "record_id"
            ),
            "image_hash": existing.get(
                "image_hash"
            ),
            "prediction_hash": existing.get(
                "prediction_hash"
            ),
            "model_version": existing.get(
                "model_version"
            ),
            "transaction_hash": None,
            "block_number": None,
            "contract_address": (
                _get_contract_address()
            ),
            "network": "Sepolia",
            "status": "ALREADY_REGISTERED",
            "reused": True,
            "registered_at": existing.get(
                "timestamp"
            ),
            "recorder": existing.get(
                "recorder"
            ),
            "final_verdict": final_verdict,
            "fraud_score": fraud_score,
        }

        return {
            "certificate": certificate,
            "state": "BLOCKCHAIN_REGISTERED",
            "steps": [
                {
                    "agent": "BlockchainCertificate",
                    "status": "REUSED",
                    "claim_id": claim_id,
                    "transaction_hash": None,
                    "block_number": None,
                }
            ],
        }

    # ---------------------------------------------------------------
    # New claim.
    #
    # Build the finalized assessment that will be notarized.
    # ---------------------------------------------------------------

    image_report = (
        agent_reports.get("ImageAgent")
        or agent_reports.get("SatelliteAgent")
        or agent_reports.get("TextAgent")
        or {}
    )

    if not isinstance(
        image_report,
        dict,
    ):
        image_report = {}

    image_evidence = {
        "agent": image_report.get("agent", "PrimaryEvidenceAgent"),
        "decision": image_report.get(
            "decision",
            "PASS",
        ),
        "confidence": image_report.get(
            "confidence",
            1.0,
        ),
        "risk_score": image_report.get(
            "risk_score",
            0.0,
        ),
        "evidence": image_report.get(
            "evidence",
            [],
        ),
        "contradictions": image_report.get(
            "contradictions",
            [],
        ),
        "model_version": image_report.get(
            "model_version",
            "agent-v1.0",
        ),
    }

    prediction = {
        "claim_id": claim_id,
        "domain": state.get(
            "domain",
            "motor",
        ),
        "final_verdict": final_verdict,
        "fraud_score": fraud_score,
        "model_version": "truthchain-v2.0",
        "agent_reports": agent_reports,
    }

    logger.info(
        "Registering authorized finalized assessment "
        "for new claim %s on Sepolia.",
        claim_id,
    )

    try:

        certificate = create_certificate(
            claim_id=claim_id,
            image_evidence=image_evidence,
            prediction=prediction,
        )

        # Register in AuditService simulation cache so Evidence Inspector verifies it directly by record_id/claim_id
        try:
            from blockchain.audit_service import get_audit_service
            audit_svc = get_audit_service()
            rec_id = certificate.get("record_id")
            if rec_id:
                audit_svc._simulated_chain[rec_id] = {
                    "record_id": rec_id,
                    "claim_id": claim_id,
                    "image_hash": certificate.get("image_hash"),
                    "prediction_hash": certificate.get("prediction_hash"),
                    "canonical_prediction": prediction,
                    "model_version": certificate.get("model_version", "truthchain-v2.0"),
                    "timestamp": certificate.get("registered_at", 0),
                    "transaction": certificate.get("transaction_hash", ""),
                    "block_number": certificate.get("block_number", 0),
                    "network": certificate.get("network", "Sepolia"),
                }
        except Exception as err:
            logger.warning("Could not sync certificate to audit_service: %s", err)

    except Exception:

        logger.exception(
            "Blockchain registration failed for claim %s",
            claim_id,
        )

        raise

    logger.info(
        "Blockchain certificate registered for %s: %s",
        claim_id,
        certificate.get(
            "transaction_hash"
        ),
    )

    return {
        "certificate": certificate,
        "state": "BLOCKCHAIN_REGISTERED",
        "steps": [
            {
                "agent": "BlockchainCertificate",
                "status": "COMPLETED",
                "claim_id": claim_id,
                "transaction_hash": certificate.get(
                    "transaction_hash"
                ),
                "block_number": certificate.get(
                    "block_number"
                ),
            }
        ],
    }


# ============================================================
# AUTHORIZATION GATE
# ============================================================

def _assert_blockchain_authorized(
    state: Dict[str, Any],
) -> None:
    """
    Enforce the final blockchain certification boundary.

    This function intentionally fails closed.

    A caller cannot obtain blockchain certification merely by
    constructing a state with final_verdict="VERIFIED".

    Every required authorization condition must be satisfied.
    """

    blockchain_allowed = state.get(
        "blockchain_allowed",
        False,
    )

    if blockchain_allowed is not True:

        raise PermissionError(
            "Blockchain certification denied: "
            "blockchain_allowed is not True."
        )

    final_verdict = str(
        state.get(
            "final_verdict",
            "UNKNOWN",
        )
    ).strip().upper()

    if final_verdict != AUTHORIZED_VERDICT:

        raise PermissionError(
            "Blockchain certification denied: "
            f"final_verdict={final_verdict!r}; "
            f"only {AUTHORIZED_VERDICT!r} is certifiable."
        )

    required_agents_complete = state.get(
        "required_agents_complete",
        False,
    )

    if required_agents_complete is not True:

        raise PermissionError(
            "Blockchain certification denied: "
            "required evidence agents are not confirmed complete."
        )

    pipeline_status = str(
        state.get(
            "pipeline_status",
            "",
        )
    ).strip().upper()

    if pipeline_status != "COMPLETE":

        raise PermissionError(
            "Blockchain certification denied: "
            f"pipeline_status={pipeline_status!r}; "
            "expected 'COMPLETE'."
        )

    pipeline_failures = state.get(
        "pipeline_failures",
        [],
    )

    if pipeline_failures:

        raise PermissionError(
            "Blockchain certification denied: "
            f"pipeline_failures={pipeline_failures!r}"
        )

    logger.info(
        "Blockchain certification authorization passed."
    )


# ============================================================
# CONTRACT METADATA
# ============================================================

def _get_contract_address() -> str:
    """
    Return the deployed AssessmentRegistry address.

    Kept here only for certificate metadata.

    The actual blockchain connection remains inside
    assessment_registry.py.
    """

    return _load_contract_address()


# ============================================================
# MODULE TEST
# ============================================================

if __name__ == "__main__":

    print(
        "Blockchain certificate node loaded successfully."
    )