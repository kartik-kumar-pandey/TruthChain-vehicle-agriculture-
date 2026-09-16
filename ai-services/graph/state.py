"""
TruthChain 2.0 - Graph State Definitions
----------------------------------------

Shared LangGraph state for the TruthChain evidence-verification
workflow.

Production principles:

    1. Agent failures are explicitly represented.
    2. Missing evidence cannot silently become VERIFIED.
    3. The graph distinguishes preliminary and authoritative verdicts.
    4. Blockchain registration requires explicit authorization.
    5. Pipeline execution remains auditable through `steps`.
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
    "CONSENSUS",
    "ADVERSARIAL_REVIEW",
    "EXPLANATION",
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
    "SUSPICIOUS",
    "REJECTED",
    "NEEDS_REVIEW",
    "ERROR",
}


# ======================================================================
# Agent State
# ======================================================================

class AgentState(TypedDict, total=False):

    # ------------------------------------------------------------------
    # Claim information
    # ------------------------------------------------------------------

    claim_id: str

    domain: str

    # ------------------------------------------------------------------
    # Input data
    # ------------------------------------------------------------------

    data: Dict[str, Any]

    # ------------------------------------------------------------------
    # Pipeline state
    # ------------------------------------------------------------------

    state: str

    # ------------------------------------------------------------------
    # Final assessment
    #
    # `final_verdict` is authoritative ONLY after the graph's
    # finalization stage.
    # ------------------------------------------------------------------

    final_verdict: str

    fraud_score: int

    # ------------------------------------------------------------------
    # Preliminary risk information
    # ------------------------------------------------------------------

    preliminary_verdict: str

    preliminary_fraud_score: int

    # ------------------------------------------------------------------
    # Individual agent reports
    # ------------------------------------------------------------------

    agent_reports: Dict[str, Any]

    # ------------------------------------------------------------------
    # Pipeline integrity
    #
    # These fields are specifically used to prevent fail-open
    # execution.
    # ------------------------------------------------------------------

    pipeline_status: str

    pipeline_failures: List[str]

    failed_agents: List[str]

    required_agents_complete: bool

    # ------------------------------------------------------------------
    # Finalization authorization
    #
    # Blockchain node MUST NOT register a certificate merely because
    # final_verdict happens to equal VERIFIED.
    #
    # The graph must explicitly authorize certification.
    # ------------------------------------------------------------------

    blockchain_allowed: bool

    blockchain_reason: str

    # ------------------------------------------------------------------
    # Blockchain certificate
    # ------------------------------------------------------------------

    certificate: Dict[str, Any]

    # ------------------------------------------------------------------
    # Explanation
    # ------------------------------------------------------------------

    explanation: Dict[str, Any]

    # ------------------------------------------------------------------
    # Communication
    # ------------------------------------------------------------------

    communication: Dict[str, Any]

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