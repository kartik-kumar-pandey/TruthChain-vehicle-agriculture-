"""
TruthChain Agriculture - Graph State Definitions
-------------------------------------------------

Shared LangGraph state for the Agriculture evidence-verification
workflow.

The structure intentionally follows the first TruthChain domain while
using Agriculture-specific evidence and risk semantics.

Production principles:

    1. Agent failures are explicitly represented.
    2. Missing evidence cannot silently become VERIFIED.
    3. Cross-modal consistency is separated from final risk consensus.
    4. Investigation requirements remain auditable.
    5. Adversarial verification is explicitly represented.
    6. Blockchain registration requires explicit authorization.
    7. Pipeline execution remains auditable through `steps`.
"""

from __future__ import annotations

from typing import Annotated, TypedDict, List, Dict, Any
import operator


# ======================================================================
# Constants
# ======================================================================

PIPELINE_STATES = {
    "START",
    "RUNNING",
    "EVIDENCE_COLLECTION",
    "CROSS_MODAL_ANALYSIS",
    "INVESTIGATION",
    "ADVERSARIAL_REVIEW",
    "RISK_CONSENSUS",
    "DECISION",
    "BLOCKCHAIN_PENDING",
    "BLOCKCHAIN_REGISTERED",
    "COMPLETED",
    "NEEDS_REVIEW",
    "ERROR",
}


FINAL_VERDICTS = {
    "PENDING",
    "VERIFIED",
    "REVIEW_REQUIRED",
    "REJECTED",
    "UNCERTAIN",
    "ERROR",
}


# ======================================================================
# Agent State
# ======================================================================

class AgricultureAgentState(TypedDict, total=False):

    # ------------------------------------------------------------------
    # Claim information
    # ------------------------------------------------------------------

    claim_id: str

    domain: str

    # ------------------------------------------------------------------
    # Input claim data
    # ------------------------------------------------------------------

    data: Dict[str, Any]

    # ------------------------------------------------------------------
    # Pipeline state
    # ------------------------------------------------------------------

    state: str

    # ------------------------------------------------------------------
    # Final assessment
    #
    # `final_verdict` becomes authoritative only after the
    # DecisionEngine/finalization stage.
    # ------------------------------------------------------------------

    final_verdict: str

    risk_score: float

    confidence: float

    # ------------------------------------------------------------------
    # Preliminary assessment
    # ------------------------------------------------------------------

    preliminary_verdict: str

    preliminary_risk_score: float

    # ------------------------------------------------------------------
    # Individual agent reports
    # ------------------------------------------------------------------

    agent_reports: Dict[str, Any]

    # ------------------------------------------------------------------
    # Dedicated Agriculture verification outputs
    # ------------------------------------------------------------------

    cross_modal_result: Dict[str, Any]

    investigation_result: Dict[str, Any]

    adversarial_verifier_result: Dict[str, Any]

    risk_engine_result: Dict[str, Any]

    decision_engine_result: Dict[str, Any]

    # ------------------------------------------------------------------
    # Pipeline integrity
    #
    # These fields prevent fail-open execution.
    # ------------------------------------------------------------------

    pipeline_status: str

    pipeline_failures: List[str]

    failed_agents: List[str]

    required_agents_complete: bool

    # ------------------------------------------------------------------
    # Evidence completeness
    # ------------------------------------------------------------------

    evidence_complete: bool

    missing_evidence: List[str]

    # ------------------------------------------------------------------
    # Investigation / human review
    # ------------------------------------------------------------------

    investigation_required: bool

    human_review_required: bool

    review_reasons: List[str]

    # ------------------------------------------------------------------
    # Finalization authorization
    #
    # Blockchain registration MUST NOT happen merely because
    # final_verdict == VERIFIED.
    #
    # The workflow must explicitly authorize certification.
    # ------------------------------------------------------------------

    blockchain_allowed: bool

    blockchain_reason: str

    # ------------------------------------------------------------------
    # Evidence integrity
    # ------------------------------------------------------------------

    evidence_hash: str

    # ------------------------------------------------------------------
    # Blockchain certificate
    # ------------------------------------------------------------------

    certificate: Dict[str, Any]

    # ------------------------------------------------------------------
    # Explanation
    # ------------------------------------------------------------------

    explanation: Dict[str, Any]

    # ------------------------------------------------------------------
    # Pipeline execution steps
    #
    # LangGraph accumulates steps returned by each node instead of
    # replacing the previous list.
    # ------------------------------------------------------------------

    steps: Annotated[
        List[Dict[str, Any]],
        operator.add,
    ]