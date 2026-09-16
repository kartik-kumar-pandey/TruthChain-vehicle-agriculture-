"""
TruthChain 2.0 - Communication Agent
------------------------------------

Generates customer-facing communication from the automated evidence
verification result.

Important boundaries:
    - VERIFIED does not mean insurance coverage is approved.
    - VERIFIED does not determine a payout amount.
    - VERIFIED does not promise payment timing.
    - REJECTED does not independently establish contractual coverage denial.
    - REVIEW_REQUIRED and SUSPICIOUS are routed toward human review.
    - Policy/coverage decisions are outside this agent unless an explicit
      downstream policy decision is supplied.

This agent communicates the authoritative ExplanationAgent result.
It does not independently make insurance, legal, coverage, fraud, or
settlement decisions.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Tuple


logger = logging.getLogger(__name__)


MODEL_VERSION = "comm-v2.1"


FAILURE_STATES = {
    "ERROR",
    "FAILED",
    "AGENT_ERROR",
    "PROCESSING_ERROR",
    "MODEL_ERROR",
    "INSUFFICIENT_DATA",
    "NEEDS_REVIEW",
    "PENDING",
    "UNKNOWN",
}


class CommunicationAgent:
    """
    Generates professional, evidence-based claim communications.

    Authority chain:

        AdversarialVerifier
                ↓
        ExplanationAgent
                ↓
        CommunicationAgent

    CommunicationAgent must never upgrade a lower-confidence or
    incomplete pipeline into VERIFIED.
    """

    def __init__(
        self,
        model_version: str = MODEL_VERSION,
    ):
        self.model_version = model_version

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_verdict(
        verdict: Any,
    ) -> str:
        """Normalize supported TruthChain verdict aliases."""

        value = str(
            verdict or ""
        ).strip().upper()

        aliases = {
            "PASS": "VERIFIED",
            "VERIFIED": "VERIFIED",

            "REVIEW": "REVIEW_REQUIRED",
            "REVIEW_REQUIRED": "REVIEW_REQUIRED",

            "SUSPICIOUS": "SUSPICIOUS",

            "FAIL": "REJECTED",
            "REJECTED": "REJECTED",
        }

        if value in FAILURE_STATES:
            return "REVIEW_REQUIRED"

        return aliases.get(
            value,
            "REVIEW_REQUIRED",
        )

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:
        """Safely convert a value to finite float."""

        try:
            result = float(value)

            if not math.isfinite(result):
                return default

            return result

        except (TypeError, ValueError):
            return default

    @staticmethod
    def _collect_missing_evidence(
        explanation: Dict[str, Any],
    ) -> List[str]:
        """
        Use explicit missing-evidence information if supplied.

        We intentionally do not invent required documents.
        """

        candidates = explanation.get(
            "missing_evidence",
            [],
        )

        if not isinstance(candidates, list):
            return []

        return [
            str(item).strip()
            for item in candidates
            if str(item).strip()
        ]

    @staticmethod
    def _pipeline_failed(
        explanation: Dict[str, Any],
    ) -> bool:
        """
        Determine whether ExplanationAgent indicates an incomplete
        or failed pipeline.
        """

        if not isinstance(explanation, dict):
            return True

        pipeline_status = str(
            explanation.get(
                "pipeline_status",
                "",
            )
        ).strip().upper()

        if pipeline_status != "COMPLETE":
            return True

        failures = explanation.get(
            "pipeline_failures",
            [],
        )

        if failures:
            return True

        decision = str(
            explanation.get(
                "decision",
                "",
            )
        ).strip().upper()

        if decision in FAILURE_STATES:
            return True

        if explanation.get("error"):
            return True

        return False

    def _resolve_authoritative_verdict(
        self,
        supplied_verdict: Any,
        explanation: Dict[str, Any],
    ) -> Tuple[str, List[str]]:
        """
        Resolve the verdict that CommunicationAgent is permitted to
        communicate.

        ExplanationAgent is the immediate authority.

        For a complete pipeline, its final_verdict must agree with
        verifier_final_verdict.

        Any disagreement is converted to REVIEW_REQUIRED.
        """

        warnings: List[str] = []

        if not isinstance(explanation, dict):
            return (
                "REVIEW_REQUIRED",
                [
                    "ExplanationAgent output is missing or invalid."
                ],
            )

        if self._pipeline_failed(explanation):

            warnings.append(
                "ExplanationAgent reports an incomplete or failed "
                "verification pipeline."
            )

            return (
                "REVIEW_REQUIRED",
                warnings,
            )

        explanation_verdict = self._normalise_verdict(
            explanation.get(
                "final_verdict",
                explanation.get("decision"),
            )
        )

        verifier_verdict_raw = explanation.get(
            "verifier_final_verdict"
        )

        if verifier_verdict_raw is not None:

            verifier_verdict = self._normalise_verdict(
                verifier_verdict_raw
            )

            if explanation_verdict != verifier_verdict:

                warnings.append(
                    "ExplanationAgent final verdict disagrees with "
                    "AdversarialVerifier final verdict."
                )

                logger.error(
                    "Communication verdict mismatch: "
                    "explanation=%s verifier=%s",
                    explanation_verdict,
                    verifier_verdict,
                )

                return (
                    "REVIEW_REQUIRED",
                    warnings,
                )

        supplied = self._normalise_verdict(
            supplied_verdict
        )

        if supplied != explanation_verdict:

            warnings.append(
                "Supplied communication verdict disagrees with the "
                "authoritative ExplanationAgent verdict."
            )

            logger.error(
                "Communication supplied verdict mismatch: "
                "supplied=%s explanation=%s",
                supplied,
                explanation_verdict,
            )

            # Never communicate a conflicting positive result.
            return (
                "REVIEW_REQUIRED",
                warnings,
            )

        return (
            explanation_verdict,
            warnings,
        )

    # ------------------------------------------------------------------
    # Main communication generator
    # ------------------------------------------------------------------

    def generate_message(
        self,
        claim_id: str,
        domain: str,
        verdict: str,
        policy_info: Dict[str, Any],
        explanation: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a customer-facing communication.

        Parameters
        ----------
        claim_id:
            Unique claim identifier.

        domain:
            Claim domain, normally "motor".

        verdict:
            Graph-supplied final TruthChain verdict.

        policy_info:
            Optional downstream policy information.

            This is intentionally not used to invent:
                - payment amounts
                - coverage decisions
                - deadlines

        explanation:
            Output from ExplanationAgent.

        Security behavior:
            Any mismatch or incomplete pipeline becomes
            REVIEW_REQUIRED.
        """

        if not isinstance(policy_info, dict):
            policy_info = {}

        if not isinstance(explanation, dict):
            explanation = {}

        normalized_verdict, warnings = (
            self._resolve_authoritative_verdict(
                supplied_verdict=verdict,
                explanation=explanation,
            )
        )

        claimant_name = (
            policy_info.get("claimant_name")
            or "Policyholder"
        )

        claimant_name = str(
            claimant_name
        ).strip()

        if not claimant_name:
            claimant_name = "Policyholder"

        final_score = self._safe_float(
            explanation.get(
                "risk_score",
                0.0,
            ),
            0.0,
        )

        final_score = max(
            0.0,
            min(
                100.0,
                final_score,
            ),
        )

        contradiction_count = int(
            max(
                0.0,
                self._safe_float(
                    explanation.get(
                        "contradiction_count",
                        0,
                    ),
                    0,
                ),
            )
        )

        summary = str(
            explanation.get(
                "executive_summary",
                "",
            )
        ).strip()

        highlights = explanation.get(
            "key_highlights",
            [],
        )

        if not isinstance(highlights, list):
            highlights = []

        missing_evidence = (
            self._collect_missing_evidence(
                explanation
            )
        )

        # --------------------------------------------------------------
        # Pipeline warning
        # --------------------------------------------------------------

        if warnings:

            # Communication metadata records the warnings.
            # Customer-facing body remains conservative.
            logger.warning(
                "CommunicationAgent warnings for claim %s: %s",
                claim_id,
                warnings,
            )

        # --------------------------------------------------------------
        # VERIFIED
        # --------------------------------------------------------------

        if normalized_verdict == "VERIFIED":

            subject = (
                "Automated Claim Verification Completed — "
                f"Claim #{claim_id}"
            )

            body = (
                f"Dear {claimant_name},\n\n"
                f"Automated evidence verification for claim "
                f"#{claim_id} has been completed successfully.\n\n"
                f"The submitted claim evidence passed the current "
                f"TruthChain verification checks. The final automated "
                f"fraud score was {final_score:.0f}/100, with "
                f"{contradiction_count} recorded evidence "
                f"contradiction(s).\n\n"
                f"This verification result supports the next stage "
                f"of claim processing. It does not by itself determine "
                f"policy coverage, settlement eligibility, or the "
                f"amount or timing of any payment.\n\n"
                f"Your claim can now continue through the applicable "
                f"coverage and settlement process.\n\n"
                f"Regards,\n"
                f"TruthChain Claims Verification"
            )

        # --------------------------------------------------------------
        # REVIEW REQUIRED
        # --------------------------------------------------------------

        elif normalized_verdict == "REVIEW_REQUIRED":

            subject = (
                "Claim Under Additional Review — "
                f"Claim #{claim_id}"
            )

            body = (
                f"Dear {claimant_name},\n\n"
                f"Claim #{claim_id} requires additional review "
                f"following automated evidence verification.\n\n"
                f"The current automated fraud score is "
                f"{final_score:.0f}/100. The verification system "
                f"identified evidence or pipeline conditions that "
                f"should be reviewed before the claim proceeds to a "
                f"final processing decision.\n"
            )

            if contradiction_count > 0:

                body += (
                    f"\nThe automated assessment recorded "
                    f"{contradiction_count} evidence contradiction(s) "
                    f"for further examination.\n"
                )

            if missing_evidence:

                body += (
                    "\nAdditional evidence currently identified as "
                    "needed:\n"
                )

                for item in missing_evidence:
                    body += f"- {item}\n"

            body += (
                "\nA claims reviewer may contact you if additional "
                "information or documentation is required.\n\n"
                "Regards,\n"
                "TruthChain Claims Verification"
            )

        # --------------------------------------------------------------
        # SUSPICIOUS
        # --------------------------------------------------------------

        elif normalized_verdict == "SUSPICIOUS":

            subject = (
                "Claim Requires Further Verification — "
                f"Claim #{claim_id}"
            )

            body = (
                f"Dear {claimant_name},\n\n"
                f"Claim #{claim_id} requires further verification "
                f"following the automated evidence assessment.\n\n"
                f"The current automated fraud score is "
                f"{final_score:.0f}/100. The result has therefore "
                f"been routed for enhanced human review.\n\n"
                f"This automated assessment is not, by itself, a "
                f"final determination of coverage, liability, or "
                f"payment.\n\n"
                f"A claims or fraud reviewer will determine the "
                f"appropriate next step based on the available evidence.\n\n"
                f"Regards,\n"
                f"TruthChain Claims Verification"
            )

        # --------------------------------------------------------------
        # REJECTED
        # --------------------------------------------------------------

        else:

            subject = (
                "Automated Verification Result — "
                f"Claim #{claim_id}"
            )

            body = (
                f"Dear {claimant_name},\n\n"
                f"The automated TruthChain evidence-verification "
                f"pipeline has completed its assessment of claim "
                f"#{claim_id}.\n\n"
                f"The claim received a REJECTED verification outcome "
                f"with a final automated fraud score of "
                f"{final_score:.0f}/100.\n\n"
                f"The available evidence should be reviewed through "
                f"the applicable claims process before any final "
                f"coverage or settlement decision is communicated.\n\n"
                f"This automated result does not by itself constitute "
                f"a contractual or legal denial of insurance coverage.\n\n"
                f"If required, a claims reviewer will provide the "
                f"appropriate next steps.\n\n"
                f"Regards,\n"
                f"TruthChain Claims Verification"
            )

        # --------------------------------------------------------------
        # Internal metadata
        # --------------------------------------------------------------

        return {
            "agent": "CommunicationAgent",

            "claim_id": claim_id,

            "domain": domain,

            "decision": normalized_verdict,

            "final_verdict": normalized_verdict,

            "subject": subject,

            "message_body": body,

            "recipient": claimant_name,

            "fraud_score": round(
                final_score,
                2,
            ),

            "contradiction_count": contradiction_count,

            "explanation_summary": summary,

            "evidence_highlight_count": len(
                highlights
            ),

            "pipeline_status": (
                "COMPLETE"
                if not warnings
                else "INCOMPLETE"
            ),

            "pipeline_warnings": warnings,

            "model_version": self.model_version,
        }


# ======================================================================
# Singleton
# ======================================================================

_communication_agent: CommunicationAgent | None = None


def get_communication_agent() -> CommunicationAgent:
    """Return the shared CommunicationAgent instance."""

    global _communication_agent

    if _communication_agent is None:
        _communication_agent = CommunicationAgent()

    return _communication_agent


# ======================================================================
# Convenience function
# ======================================================================

def generate_message(
    claim_id: str,
    domain: str,
    verdict: str,
    policy_info: Dict[str, Any],
    explanation: Dict[str, Any],
) -> Dict[str, Any]:
    """Convenience wrapper for CommunicationAgent."""

    return get_communication_agent().generate_message(
        claim_id=claim_id,
        domain=domain,
        verdict=verdict,
        policy_info=policy_info,
        explanation=explanation,
    )


# ======================================================================
# Local regression tests
# ======================================================================

if __name__ == "__main__":

    import json

    explanation = {
        "agent": "ExplanationAgent",
        "domain": "motor",
        "decision": "VERIFIED",
        "final_verdict": "VERIFIED",
        "risk_score": 0,
        "confidence": 0.96,
        "executive_summary": (
            "Automated evidence verification completed successfully."
        ),
        "key_highlights": [
            "Image evidence verified.",
            "Sensor evidence within normal range.",
            "Text evidence consistent.",
            "Cross-modal evidence compatible.",
            "Adversarial verification completed.",
        ],
        "recommended_actions": [
            "Continue downstream processing."
        ],
        "contradiction_count": 0,
        "contradictions": [],
        "verifier_decision": "PASS",
        "verifier_final_verdict": "VERIFIED",
        "pipeline_status": "COMPLETE",
        "pipeline_failures": [],
    }

    policy_info = {
        "claimant_name": "Policyholder"
    }

    print("=" * 70)
    print("TRUTHCHAIN COMMUNICATION AGENT TEST")
    print("=" * 70)

    # --------------------------------------------------------------
    # Normal VERIFIED
    # --------------------------------------------------------------

    result = generate_message(
        claim_id="TC-COMM-001",
        domain="motor",
        verdict="VERIFIED",
        policy_info=policy_info,
        explanation=explanation,
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )

    assert result["decision"] == "VERIFIED"
    assert result["final_verdict"] == "VERIFIED"
    assert result["pipeline_status"] == "COMPLETE"

    print("\nPASS: NORMAL VERIFIED COMMUNICATION")

    # --------------------------------------------------------------
    # SUSPICIOUS
    # --------------------------------------------------------------

    suspicious = dict(explanation)

    suspicious["decision"] = "SUSPICIOUS"
    suspicious["final_verdict"] = "SUSPICIOUS"
    suspicious["verifier_final_verdict"] = "SUSPICIOUS"
    suspicious["verifier_decision"] = "SUSPICIOUS"
    suspicious["risk_score"] = 70
    suspicious["contradiction_count"] = 1
    suspicious["contradictions"] = [
        "Image and text evidence disagree."
    ]

    result = generate_message(
        claim_id="TC-COMM-002",
        domain="motor",
        verdict="SUSPICIOUS",
        policy_info=policy_info,
        explanation=suspicious,
    )

    assert result["decision"] == "SUSPICIOUS"
    assert result["pipeline_status"] == "COMPLETE"

    print("PASS: SUSPICIOUS COMMUNICATION")

    # --------------------------------------------------------------
    # REJECTED
    # --------------------------------------------------------------

    rejected = dict(explanation)

    rejected["decision"] = "REJECTED"
    rejected["final_verdict"] = "REJECTED"
    rejected["verifier_final_verdict"] = "REJECTED"
    rejected["verifier_decision"] = "FAIL"
    rejected["risk_score"] = 85

    result = generate_message(
        claim_id="TC-COMM-003",
        domain="motor",
        verdict="REJECTED",
        policy_info=policy_info,
        explanation=rejected,
    )

    assert result["decision"] == "REJECTED"

    print("PASS: REJECTED COMMUNICATION")

    # --------------------------------------------------------------
    # Incomplete ExplanationAgent
    # --------------------------------------------------------------

    incomplete = dict(explanation)

    incomplete["pipeline_status"] = "INCOMPLETE"
    incomplete["pipeline_failures"] = [
        "TextAgent returned ERROR."
    ]

    result = generate_message(
        claim_id="TC-COMM-004",
        domain="motor",
        verdict="VERIFIED",
        policy_info=policy_info,
        explanation=incomplete,
    )

    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["pipeline_status"] == "INCOMPLETE"

    print("PASS: INCOMPLETE PIPELINE FAIL-CLOSED")

    # --------------------------------------------------------------
    # Verifier disagreement
    # --------------------------------------------------------------

    disagreement = dict(explanation)

    disagreement["final_verdict"] = "VERIFIED"
    disagreement["decision"] = "VERIFIED"
    disagreement["verifier_final_verdict"] = "SUSPICIOUS"

    result = generate_message(
        claim_id="TC-COMM-005",
        domain="motor",
        verdict="VERIFIED",
        policy_info=policy_info,
        explanation=disagreement,
    )

    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["pipeline_status"] == "INCOMPLETE"

    print("PASS: VERIFIER DISAGREEMENT FAIL-CLOSED")

    # --------------------------------------------------------------
    # Supplied verdict disagreement
    # --------------------------------------------------------------

    result = generate_message(
        claim_id="TC-COMM-006",
        domain="motor",
        verdict="SUSPICIOUS",
        policy_info=policy_info,
        explanation=explanation,
    )

    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["pipeline_status"] == "INCOMPLETE"

    print("PASS: SUPPLIED VERDICT MISMATCH FAIL-CLOSED")

    # --------------------------------------------------------------
    # Missing ExplanationAgent output
    # --------------------------------------------------------------

    result = generate_message(
        claim_id="TC-COMM-007",
        domain="motor",
        verdict="VERIFIED",
        policy_info=policy_info,
        explanation={},
    )

    assert result["decision"] == "REVIEW_REQUIRED"

    print("PASS: MISSING EXPLANATION FAIL-CLOSED")

    print()
    print("=" * 70)
    print("ALL COMMUNICATION AGENT TESTS PASSED")
    print("=" * 70)