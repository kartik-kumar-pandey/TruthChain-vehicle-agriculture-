"""
TruthChain 2.0 - Adversarial Verification Agent
------------------------------------------------

Performs the final audit after the preliminary RiskEngine result.

Responsibilities:
    1. Validate evidence-pipeline completeness.
    2. Inspect contradictions across evidence agents.
    3. Inspect preliminary risk.
    4. Escalate risk when contradictions materially affect
       claim consistency.
    5. Produce the FINAL automated risk and verdict.

Important:
    - This is the final automated verification authority.
    - It does NOT determine policy coverage, payout, or legal liability.
    - Missing/failed evidence fails closed to NEEDS_REVIEW.
    - Invalid preliminary risk fails closed to NEEDS_REVIEW.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Dict, Any, List, Tuple


logger = logging.getLogger(__name__)


MODEL_VERSION = "adversarial-verifier-v3.1"


# ======================================================================
# Required evidence pipeline
# ======================================================================

REQUIRED_AGENTS = (
    "ImageAgent",
    "SensorAgent",
    "TextAgent",
    "CrossModalAgent",
)


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


class AdversarialVerifier:
    """
    Final adversarial audit agent.

    This agent runs after RiskEngine and has final decision
    authority for the automated verification stage.

    It must never convert incomplete evidence into VERIFIED.
    """

    def __init__(
        self,
        model_version: str = MODEL_VERSION,
    ) -> None:
        self.model_version = model_version

    # ==================================================================
    # FINAL VERIFICATION
    # ==================================================================

    def verify(
        self,
        agent_reports: Dict[str, Any],
        preliminary_risk: float,
    ) -> Dict[str, Any]:
        """
        Audit the active evidence agents and produce the final
        adversarial risk/verdict.

        Parameters
        ----------
        agent_reports:
            Reports produced by the active evidence agents.

        preliminary_risk:
            Risk produced by RiskEngine before adversarial verification.

        Returns
        -------
        dict
            Final structured adversarial verification result.

        Fail-closed behavior
        --------------------
        Missing, invalid, failed, or insufficient evidence produces
        NEEDS_REVIEW rather than VERIFIED.
        """

        start = time.perf_counter()

        try:
            # ==========================================================
            # VALIDATE INPUT CONTAINER
            # ==========================================================

            if not isinstance(agent_reports, dict):
                return self._needs_review_result(
                    start=start,
                    failures=[
                        "agent_reports is not a dictionary."
                    ],
                )

            # ==========================================================
            # VALIDATE PRELIMINARY RISK
            # ==========================================================

            normalized_preliminary_risk = self._safe_risk(
                preliminary_risk
            )

            if normalized_preliminary_risk is None:
                return self._needs_review_result(
                    start=start,
                    failures=[
                        "RiskEngine preliminary_risk is invalid."
                    ],
                )

            preliminary_risk = normalized_preliminary_risk

            # ==========================================================
            # VALIDATE REQUIRED EVIDENCE PIPELINE
            # ==========================================================

            pipeline_valid, pipeline_failures = (
                self._validate_required_agents(
                    agent_reports
                )
            )

            if not pipeline_valid:
                logger.warning(
                    "AdversarialVerifier fail-closed: %s",
                    pipeline_failures,
                )

                return self._needs_review_result(
                    start=start,
                    failures=pipeline_failures,
                    preliminary_risk=preliminary_risk,
                )

            # ==========================================================
            # ACTIVE EVIDENCE AGENTS
            # ==========================================================

            audited_agents = list(REQUIRED_AGENTS)

            # ==========================================================
            # COLLECT EVIDENCE + CONTRADICTIONS
            # ==========================================================

            all_contradictions: List[str] = []
            all_evidence: List[str] = []

            for agent_name in audited_agents:

                report = agent_reports.get(
                    agent_name
                )

                contradictions = report.get(
                    "contradictions",
                    [],
                )

                evidence = report.get(
                    "evidence",
                    [],
                )

                if isinstance(contradictions, list):
                    for contradiction in contradictions:

                        if contradiction is None:
                            continue

                        text = str(
                            contradiction
                        ).strip()

                        if text:
                            all_contradictions.append(
                                f"[{agent_name}] {text}"
                            )

                if isinstance(evidence, list):
                    for item in evidence:

                        if item is None:
                            continue

                        text = str(
                            item
                        ).strip()

                        if text:
                            all_evidence.append(
                                f"[{agent_name}] {text}"
                            )

            # ==========================================================
            # ADVERSARIAL CONTRADICTION ANALYSIS
            # ==========================================================

            contradiction_count = len(
                all_contradictions
            )

            adversarial_flagged = (
                contradiction_count > 0
            )

            # Start final risk at preliminary consensus risk.
            final_risk = preliminary_risk

            # ----------------------------------------------------------
            # Multiple contradictions
            # ----------------------------------------------------------

            if contradiction_count >= 2:

                final_risk = max(
                    final_risk,
                    0.85,
                )

            # ----------------------------------------------------------
            # Single contradiction
            # ----------------------------------------------------------

            elif contradiction_count == 1:

                final_risk = max(
                    final_risk,
                    0.70,
                )

            final_risk = min(
                max(
                    final_risk,
                    0.0,
                ),
                1.0,
            )

            # ==========================================================
            # FINAL DECISION
            # ==========================================================

            if final_risk >= 0.76:

                decision = "FAIL"
                final_verdict = "REJECTED"

            elif final_risk >= 0.51:

                decision = "SUSPICIOUS"
                final_verdict = "SUSPICIOUS"

            elif final_risk >= 0.21:

                decision = "REVIEW_REQUIRED"
                final_verdict = "REVIEW_REQUIRED"

            else:

                decision = "PASS"
                final_verdict = "VERIFIED"

            # ==========================================================
            # CONFIDENCE
            # ==========================================================

            if contradiction_count >= 2:

                confidence = 0.96

            elif contradiction_count == 1:

                confidence = 0.90

            else:

                confidence = 0.96

            # ==========================================================
            # FRAUD SCORE
            # ==========================================================

            fraud_score = int(
                round(
                    final_risk * 100
                )
            )

            fraud_score = min(
                max(
                    fraud_score,
                    0,
                ),
                100,
            )

            # ==========================================================
            # AUDIT EVIDENCE
            # ==========================================================

            evidence = [
                (
                    "Adversarial verification completed across "
                    f"{len(audited_agents)} evidence agents."
                ),
                (
                    "Total contradictions evaluated: "
                    f"{contradiction_count}."
                ),
                (
                    "Preliminary risk before adversarial review: "
                    f"{preliminary_risk:.4f}."
                ),
                (
                    "Final adversarial risk after verification: "
                    f"{final_risk:.4f}."
                ),
            ]

            if contradiction_count >= 2:

                evidence.append(
                    "Multiple cross-modal contradictions detected; "
                    "final risk escalated to at least 0.85."
                )

            elif contradiction_count == 1:

                evidence.append(
                    "A cross-modal contradiction was detected; "
                    "final risk escalated to at least 0.70."
                )

            else:

                evidence.append(
                    "No contradictions were detected across the "
                    "active evidence agents."
                )

            # ==========================================================
            # PROCESSING TIME
            # ==========================================================

            processing_time_ms = (
                time.perf_counter() - start
            ) * 1000.0

            # ==========================================================
            # FINAL STRUCTURED RESULT
            # ==========================================================

            return {
                "agent": "AdversarialVerifier",
                "domain": "motor",

                # Final automated decision.
                "decision": decision,

                # Explicit final verdict.
                "final_verdict": final_verdict,

                # Confidence in the adversarial assessment.
                "confidence": confidence,

                # Final normalized risk [0, 1].
                "risk_score": round(
                    final_risk,
                    4,
                ),

                # Same final risk represented as [0, 100].
                "fraud_score": fraud_score,

                # Preserve RiskEngine result.
                "preliminary_risk": round(
                    preliminary_risk,
                    4,
                ),

                # Whether any contradiction was found.
                "adversarial_flagged": adversarial_flagged,

                # Human-readable audit evidence.
                "evidence": evidence,

                # Exact contradictions collected from agents.
                "contradictions": all_contradictions,

                # Collected evidence for explanation/audit layers.
                "audited_evidence": all_evidence,

                "model_version": self.model_version,

                # Pipeline status is explicitly recorded.
                "pipeline_status": "COMPLETE",

                "pipeline_failures": [],

                "audited_agents": audited_agents,

                "processing_time_ms": round(
                    processing_time_ms,
                    2,
                ),
            }

        except Exception as exc:

            processing_time_ms = (
                time.perf_counter() - start
            ) * 1000.0

            logger.exception(
                "AdversarialVerifier unexpected failure"
            )

            return {
                "agent": "AdversarialVerifier",
                "domain": "motor",
                "decision": "NEEDS_REVIEW",
                "final_verdict": "NEEDS_REVIEW",
                "confidence": 0.0,
                "risk_score": 0.0,
                "fraud_score": 0,
                "preliminary_risk": 0.0,
                "adversarial_flagged": False,
                "evidence": [
                    "AdversarialVerifier encountered an internal error."
                ],
                "contradictions": [],
                "audited_evidence": [],
                "model_version": self.model_version,
                "pipeline_status": "ERROR",
                "pipeline_failures": [
                    "AdversarialVerifier internal error."
                ],
                "error_type": type(exc).__name__,
                "error": str(exc),
                "processing_time_ms": round(
                    processing_time_ms,
                    2,
                ),
            }

    # ==================================================================
    # REQUIRED-AGENT VALIDATION
    # ==================================================================

    @classmethod
    def _validate_required_agents(
        cls,
        agent_reports: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        Validate every required evidence agent.

        This independently enforces the pipeline boundary even though
        RiskEngine already performs validation.

        We require:

            - report exists
            - report is a dictionary
            - report identity matches its key
            - decision exists
            - decision is not a failure/insufficient state
            - no explicit error field
        """

        failures: List[str] = []

        for agent_name in REQUIRED_AGENTS:

            # ----------------------------------------------------------
            # Missing report
            # ----------------------------------------------------------

            if agent_name not in agent_reports:

                failures.append(
                    f"{agent_name} report is missing."
                )

                continue

            report = agent_reports.get(
                agent_name
            )

            # ----------------------------------------------------------
            # Invalid report object
            # ----------------------------------------------------------

            if not isinstance(report, dict):

                failures.append(
                    f"{agent_name} report is invalid."
                )

                continue

            # ----------------------------------------------------------
            # Agent identity
            # ----------------------------------------------------------

            reported_agent = str(
                report.get(
                    "agent",
                    "",
                )
            ).strip()

            if reported_agent != agent_name:

                failures.append(
                    f"{agent_name} report identity mismatch: "
                    f"received "
                    f"{reported_agent or 'UNKNOWN'}."
                )

                continue

            # ----------------------------------------------------------
            # Decision
            # ----------------------------------------------------------

            decision = str(
                report.get(
                    "decision",
                    "",
                )
            ).strip().upper()

            if not decision:

                failures.append(
                    f"{agent_name} report has no decision."
                )

                continue

            # ----------------------------------------------------------
            # Failure state
            # ----------------------------------------------------------

            if cls._report_failed(report):

                failures.append(
                    f"{agent_name} returned unusable state "
                    f"{decision}."
                )

                continue

            # ----------------------------------------------------------
            # Explicit error field
            # ----------------------------------------------------------

            if report.get("error"):

                failures.append(
                    f"{agent_name} contains an error."
                )

        return (
            len(failures) == 0,
            failures,
        )

    @staticmethod
    def _report_failed(
        report: Dict[str, Any],
    ) -> bool:
        """Return True when an upstream report is unusable."""

        decision = str(
            report.get(
                "decision",
                "",
            )
        ).strip().upper()

        status = str(
            report.get(
                "status",
                "",
            )
        ).strip().upper()

        state = str(
            report.get(
                "state",
                "",
            )
        ).strip().upper()

        if decision in FAILURE_STATES:
            return True

        if status in FAILURE_STATES:
            return True

        if state in FAILURE_STATES:
            return True

        if report.get("error"):
            return True

        return False

    # ==================================================================
    # SAFE RISK NORMALIZATION
    # ==================================================================

    @staticmethod
    def _safe_risk(
        value: Any,
    ) -> float | None:
        """
        Safely normalize a risk value to [0, 1].

        Unlike the old implementation, invalid values return None
        rather than silently becoming 0.0.

        This prevents:

            invalid risk
                ↓
              0.0
                ↓
             VERIFIED
        """

        try:
            risk = float(value)

        except (
            TypeError,
            ValueError,
        ):
            return None

        if not math.isfinite(risk):
            return None

        if risk < 0.0:
            return 0.0

        if risk > 1.0:
            return 1.0

        return risk

    # ==================================================================
    # FAIL-CLOSED RESULT
    # ==================================================================

    def _needs_review_result(
        self,
        *,
        start: float,
        failures: List[str],
        preliminary_risk: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Produce a fail-closed final verification result.

        This can NEVER return VERIFIED.
        """

        processing_time_ms = (
            time.perf_counter() - start
        ) * 1000.0

        safe_preliminary = (
            self._safe_risk(
                preliminary_risk
            )
        )

        if safe_preliminary is None:
            safe_preliminary = 0.0

        return {
            "agent": "AdversarialVerifier",
            "domain": "motor",

            "decision": "NEEDS_REVIEW",

            "final_verdict": "NEEDS_REVIEW",

            "confidence": 0.0,

            "risk_score": 0.0,

            "fraud_score": 0,

            "preliminary_risk": round(
                safe_preliminary,
                4,
            ),

            "adversarial_flagged": False,

            "evidence": [
                "Adversarial verification could not be completed "
                "because the evidence pipeline is incomplete or invalid."
            ],

            "contradictions": [],

            "audited_evidence": [],

            "model_version": self.model_version,

            "pipeline_status": "INCOMPLETE",

            "pipeline_failures": failures,

            "audited_agents": list(
                REQUIRED_AGENTS
            ),

            "processing_time_ms": round(
                processing_time_ms,
                2,
            ),
        }


# ======================================================================
# Singleton
# ======================================================================

_adversarial_verifier: AdversarialVerifier | None = None


def get_adversarial_verifier() -> AdversarialVerifier:
    """Return the shared AdversarialVerifier instance."""

    global _adversarial_verifier

    if _adversarial_verifier is None:
        _adversarial_verifier = AdversarialVerifier()

    return _adversarial_verifier


# ======================================================================
# Convenience function
# ======================================================================

def verify_adversarial(
    agent_reports: Dict[str, Any],
    preliminary_risk: float,
) -> Dict[str, Any]:
    """Convenience wrapper for AdversarialVerifier."""

    return get_adversarial_verifier().verify(
        agent_reports=agent_reports,
        preliminary_risk=preliminary_risk,
    )


# ======================================================================
# Local tests
# ======================================================================

if __name__ == "__main__":

    import json

    print("=" * 70)
    print("TRUTHCHAIN ADVERSARIAL VERIFIER TEST")
    print("=" * 70)

    # --------------------------------------------------------------
    # TEST 1: Clean evidence
    # --------------------------------------------------------------

    valid_reports = {
        "ImageAgent": {
            "agent": "ImageAgent",
            "decision": "DAMAGE_DETECTED",
            "confidence": 0.9746,
            "risk_score": 0.9746,
            "detected_damage": [
                "dent",
                "scratch",
                "crack",
                "lamp_broken",
            ],
            "contradictions": [],
            "evidence": [
                "Vehicle damage detected."
            ],
        },

        "SensorAgent": {
            "agent": "SensorAgent",
            "decision": "PASS",
            "confidence": 0.8492,
            "risk_score": 0.4855,
            "anomaly": False,
            "contradictions": [],
            "evidence": [
                "Telemetry within learned normal range."
            ],
        },

        "TextAgent": {
            "agent": "TextAgent",
            "decision": "CONSISTENT",
            "confidence": 0.85,
            "risk_score": 0.30,
            "contradictions": [],
            "evidence": [
                "Claim narrative is internally consistent."
            ],
        },

        "CrossModalAgent": {
            "agent": "CrossModalAgent",
            "decision": "PARTIAL_AGREEMENT",
            "agreement_state": "PARTIAL_AGREEMENT",
            "confidence": 0.80,
            "risk_score": 0.15,
            "contradictions": [],
            "evidence": [
                "Image and text partially agree."
            ],
        },
    }

    result = verify_adversarial(
        valid_reports,
        0.0,
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )

    assert result["decision"] == "PASS"
    assert result["final_verdict"] == "VERIFIED"
    assert result["pipeline_status"] == "COMPLETE"

    # --------------------------------------------------------------
    # TEST 2: Single contradiction
    #
    # Must escalate to at least 0.70.
    # --------------------------------------------------------------

    print()
    print("=" * 70)
    print("CONTRADICTION TEST: SINGLE CONTRADICTION")
    print("=" * 70)

    contradiction_reports = dict(
        valid_reports
    )

    contradiction_reports["CrossModalAgent"] = {
        "agent": "CrossModalAgent",
        "decision": "REVIEW_REQUIRED",
        "agreement_state": "REVIEW_REQUIRED",
        "confidence": 0.75,
        "risk_score": 0.55,
        "contradictions": [
            "ImageAgent and claim text report different damage types."
        ],
        "evidence": [
            "Cross-modal inconsistency detected."
        ],
    }

    contradiction_result = verify_adversarial(
        contradiction_reports,
        0.10,
    )

    print(
        json.dumps(
            contradiction_result,
            indent=2,
        )
    )

    assert contradiction_result["decision"] == "SUSPICIOUS"
    assert contradiction_result["final_verdict"] == "SUSPICIOUS"
    assert contradiction_result["fraud_score"] >= 70

    # --------------------------------------------------------------
    # TEST 3: Multiple contradictions
    #
    # Must escalate to at least 0.85.
    # --------------------------------------------------------------

    print()
    print("=" * 70)
    print("CONTRADICTION TEST: MULTIPLE CONTRADICTIONS")
    print("=" * 70)

    multi_reports = dict(
        valid_reports
    )

    multi_reports["CrossModalAgent"] = {
        "agent": "CrossModalAgent",
        "decision": "CONTRADICTORY",
        "agreement_state": "REVIEW_REQUIRED",
        "confidence": 0.85,
        "risk_score": 0.80,
        "contradictions": [
            "Damage categories disagree.",
            "Incident evidence is inconsistent.",
        ],
        "evidence": [
            "Multiple contradictions detected."
        ],
    }

    multi_result = verify_adversarial(
        multi_reports,
        0.10,
    )

    print(
        json.dumps(
            multi_result,
            indent=2,
        )
    )

    assert multi_result["decision"] == "FAIL"
    assert multi_result["final_verdict"] == "REJECTED"
    assert multi_result["fraud_score"] >= 85

    # --------------------------------------------------------------
    # TEST 4: Missing agent
    #
    # MUST NOT become VERIFIED.
    # --------------------------------------------------------------

    print()
    print("=" * 70)
    print("FAIL-CLOSED TEST: MISSING AGENT")
    print("=" * 70)

    missing_reports = dict(
        valid_reports
    )

    del missing_reports[
        "TextAgent"
    ]

    missing_result = verify_adversarial(
        missing_reports,
        0.0,
    )

    print(
        json.dumps(
            missing_result,
            indent=2,
        )
    )

    assert missing_result["decision"] == "NEEDS_REVIEW"
    assert missing_result["final_verdict"] == "NEEDS_REVIEW"
    assert missing_result["pipeline_status"] == "INCOMPLETE"

    # --------------------------------------------------------------
    # TEST 5: Failed agent
    #
    # MUST NOT become VERIFIED.
    # --------------------------------------------------------------

    print()
    print("=" * 70)
    print("FAIL-CLOSED TEST: AGENT FAILURE")
    print("=" * 70)

    failed_reports = dict(
        valid_reports
    )

    failed_reports["TextAgent"] = {
        "agent": "TextAgent",
        "decision": "ERROR",
        "error": "Text model unavailable",
    }

    failed_result = verify_adversarial(
        failed_reports,
        0.0,
    )

    print(
        json.dumps(
            failed_result,
            indent=2,
        )
    )

    assert failed_result["decision"] == "NEEDS_REVIEW"
    assert failed_result["final_verdict"] == "NEEDS_REVIEW"
    assert failed_result["pipeline_status"] == "INCOMPLETE"

    # --------------------------------------------------------------
    # TEST 6: Agent identity mismatch
    #
    # MUST NOT be accepted.
    # --------------------------------------------------------------

    print()
    print("=" * 70)
    print("FAIL-CLOSED TEST: AGENT IDENTITY MISMATCH")
    print("=" * 70)

    mismatch_reports = dict(
        valid_reports
    )

    mismatch_reports["TextAgent"] = {
        "agent": "ImageAgent",
        "decision": "CONSISTENT",
        "confidence": 0.85,
        "risk_score": 0.30,
    }

    mismatch_result = verify_adversarial(
        mismatch_reports,
        0.0,
    )

    print(
        json.dumps(
            mismatch_result,
            indent=2,
        )
    )

    assert mismatch_result["decision"] == "NEEDS_REVIEW"
    assert mismatch_result["final_verdict"] == "NEEDS_REVIEW"

    # --------------------------------------------------------------
    # TEST 7: Invalid preliminary risk
    #
    # MUST NOT silently become 0 -> VERIFIED.
    # --------------------------------------------------------------

    print()
    print("=" * 70)
    print("FAIL-CLOSED TEST: INVALID PRELIMINARY RISK")
    print("=" * 70)

    invalid_risk_result = verify_adversarial(
        valid_reports,
        "not-a-number",
    )

    print(
        json.dumps(
            invalid_risk_result,
            indent=2,
        )
    )

    assert invalid_risk_result["decision"] == "NEEDS_REVIEW"
    assert invalid_risk_result["final_verdict"] == "NEEDS_REVIEW"

    # --------------------------------------------------------------
    # TEST 8: Insufficient upstream evidence
    #
    # MUST NOT become VERIFIED.
    # --------------------------------------------------------------

    print()
    print("=" * 70)
    print("FAIL-CLOSED TEST: INSUFFICIENT EVIDENCE")
    print("=" * 70)

    insufficient_reports = dict(
        valid_reports
    )

    insufficient_reports["TextAgent"] = {
        "agent": "TextAgent",
        "decision": "INSUFFICIENT_DATA",
        "confidence": 0.0,
        "risk_score": 0.0,
    }

    insufficient_result = verify_adversarial(
        insufficient_reports,
        0.0,
    )

    print(
        json.dumps(
            insufficient_result,
            indent=2,
        )
    )

    assert insufficient_result["decision"] == "NEEDS_REVIEW"
    assert insufficient_result["final_verdict"] == "NEEDS_REVIEW"

    print()
    print("=" * 70)
    print("ALL ADVERSARIAL VERIFIER TESTS PASSED")
    print("=" * 70)