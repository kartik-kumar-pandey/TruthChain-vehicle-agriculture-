"""
TruthChain 2.0 - Explanation Agent
----------------------------------

Converts the active multi-agent evidence pipeline into a clear,
auditable explanation.

Active evidence sources:
    - ImageAgent
    - SensorAgent
    - TextAgent
    - CrossModalAgent
    - RiskEngine
    - AdversarialVerifier

Important boundaries:
    - VERIFIED does not mean insurance coverage is approved.
    - VERIFIED does not determine a payout amount.
    - VERIFIED does not promise payment timing.
    - REJECTED does not independently establish contractual coverage denial.
    - REVIEW_REQUIRED and SUSPICIOUS are routed toward human review.
    - Pipeline failures are never silently converted into VERIFIED.
    - Policy/coverage decisions are outside this agent unless an explicit
      downstream policy decision is supplied.

This agent explains the authoritative graph result.
It does NOT independently determine the final fraud verdict.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Tuple


logger = logging.getLogger(__name__)


MODEL_VERSION = "explainer-v2.2"


# ----------------------------------------------------------------------
# Verdict constants
# ----------------------------------------------------------------------

VERIFIED = "VERIFIED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
SUSPICIOUS = "SUSPICIOUS"
REJECTED = "REJECTED"

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

REQUIRED_AGENTS = (
    "ImageAgent",
    "SensorAgent",
    "TextAgent",
    "CrossModalAgent",
    "RiskEngine",
    "AdversarialVerifier",
)


class ExplanationAgent:
    """
    Produces an executive-level explanation from the TruthChain
    evidence pipeline.

    The ExplanationAgent is NOT a decision-maker.

    Authority:
        AdversarialVerifier.final_verdict

    Responsibilities:
        - explain evidence
        - summarize model findings
        - expose contradictions
        - expose pipeline failures
        - provide operational recommendations

    It must never manufacture evidence or upgrade an incomplete
    pipeline into VERIFIED.
    """

    def __init__(
        self,
        model_version: str = MODEL_VERSION,
    ) -> None:
        self.model_version = model_version

    # ==================================================================
    # Safe helpers
    # ==================================================================

    @staticmethod
    def _safe_float(
        value: Any,
        default: float = 0.0,
    ) -> float:
        """Safely convert a value to a finite float."""

        try:
            result = float(value)

            if not math.isfinite(result):
                return default

            return result

        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalise_verdict(
        verdict: Any,
    ) -> str:
        """
        Normalize externally supplied verdicts.

        Unknown or failure states become REVIEW_REQUIRED.
        """

        value = str(
            verdict or ""
        ).strip().upper()

        aliases = {
            "PASS": VERIFIED,
            "VERIFIED": VERIFIED,

            "REVIEW": REVIEW_REQUIRED,
            "REVIEW_REQUIRED": REVIEW_REQUIRED,

            "SUSPICIOUS": SUSPICIOUS,

            "FAIL": REJECTED,
            "REJECTED": REJECTED,
        }

        if value in FAILURE_STATES:
            return REVIEW_REQUIRED

        return aliases.get(
            value,
            REVIEW_REQUIRED,
        )

    @staticmethod
    def _is_failure_state(
        value: Any,
    ) -> bool:
        """Return True when a value represents an unusable pipeline state."""

        return str(
            value or ""
        ).strip().upper() in FAILURE_STATES

    @staticmethod
    def _get_report(
        agent_reports: Dict[str, Any],
        name: str,
    ) -> Dict[str, Any]:
        """Safely retrieve an agent report."""

        report = agent_reports.get(
            name,
            {},
        )

        return report if isinstance(report, dict) else {}

    @classmethod
    def _is_pipeline_failure(
        cls,
        report: Dict[str, Any],
    ) -> bool:
        """
        Determine whether an upstream report represents execution
        failure or insufficient evidence.
        """

        if not isinstance(report, dict):
            return True

        decision = str(
            report.get("decision", "")
        ).strip().upper()

        status = str(
            report.get("status", "")
        ).strip().upper()

        state = str(
            report.get("state", "")
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
    # Pipeline integrity
    # ==================================================================

    def _validate_pipeline(
        self,
        agent_reports: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        Validate all required upstream reports.

        Validation includes:
            - report exists
            - report is a dictionary
            - report identity matches dictionary key
            - decision is present
            - report is not in a failure state
            - report does not contain an error

        Returns:
            (pipeline_valid, failure_reasons)
        """

        failures: List[str] = []

        if not isinstance(agent_reports, dict):
            return (
                False,
                ["agent_reports is not a dictionary."],
            )

        for agent_name in REQUIRED_AGENTS:

            if agent_name not in agent_reports:
                failures.append(
                    f"{agent_name} report is missing."
                )
                continue

            report = agent_reports.get(agent_name)

            if not isinstance(report, dict):
                failures.append(
                    f"{agent_name} report is not a dictionary."
                )
                continue

            # ----------------------------------------------------------
            # Identity validation
            # ----------------------------------------------------------

            reported_agent = str(
                report.get("agent", "")
            ).strip()

            if reported_agent != agent_name:
                failures.append(
                    f"{agent_name} report identity mismatch: "
                    f"received {reported_agent or 'UNKNOWN'}."
                )
                continue

            # ----------------------------------------------------------
            # Decision validation
            # ----------------------------------------------------------

            decision = str(
                report.get(
                    "decision",
                    report.get(
                        "status",
                        "",
                    ),
                )
            ).strip().upper()

            if not decision:
                failures.append(
                    f"{agent_name} report has no decision."
                )
                continue

            # ----------------------------------------------------------
            # Failure-state validation
            # ----------------------------------------------------------

            if self._is_pipeline_failure(report):
                failures.append(
                    f"{agent_name} returned pipeline state "
                    f"{decision or 'UNKNOWN'}."
                )

        return (
            len(failures) == 0,
            failures,
        )

    # ==================================================================
    # Verifier authority
    # ==================================================================

    def _resolve_authoritative_verdict(
        self,
        requested_verdict: Any,
        verifier_report: Dict[str, Any],
        pipeline_valid: bool,
    ) -> Tuple[str, List[str]]:
        """
        Resolve the final explanation verdict.

        AdversarialVerifier is authoritative.

        The graph-provided verdict is only accepted when:
            - the pipeline is valid
            - the verifier is valid
            - verifier final verdict agrees with it

        Otherwise the result is fail-closed.
        """

        warnings: List[str] = []

        requested = self._normalise_verdict(
            requested_verdict
        )

        if not pipeline_valid:
            warnings.append(
                "The evidence pipeline is incomplete or invalid; "
                "the explanation cannot be treated as VERIFIED."
            )
            return REVIEW_REQUIRED, warnings

        if not verifier_report:
            warnings.append(
                "AdversarialVerifier report is missing."
            )
            return REVIEW_REQUIRED, warnings

        if self._is_pipeline_failure(
            verifier_report
        ):
            warnings.append(
                "AdversarialVerifier did not complete successfully."
            )
            return REVIEW_REQUIRED, warnings

        verifier_raw = verifier_report.get(
            "final_verdict"
        )

        if not verifier_raw:
            verifier_raw = verifier_report.get(
                "decision"
            )

        verifier_verdict = self._normalise_verdict(
            verifier_raw
        )

        # --------------------------------------------------------------
        # Never allow an invalid/unknown verifier state to become
        # VERIFIED.
        # --------------------------------------------------------------

        if verifier_verdict == REVIEW_REQUIRED:
            raw_upper = str(
                verifier_raw or ""
            ).strip().upper()

            if raw_upper not in {
                REVIEW_REQUIRED,
                "REVIEW",
            }:
                warnings.append(
                    "AdversarialVerifier supplied an unknown final "
                    "verdict; explanation forced to REVIEW_REQUIRED."
                )

                return REVIEW_REQUIRED, warnings

        # --------------------------------------------------------------
        # The verifier is authoritative.
        # --------------------------------------------------------------

        if requested != verifier_verdict:

            warnings.append(
                "Graph verdict and AdversarialVerifier verdict "
                "disagreed; AdversarialVerifier was treated as "
                "authoritative."
            )

            logger.error(
                "Explanation verdict mismatch: graph=%s verifier=%s",
                requested,
                verifier_verdict,
            )

        return verifier_verdict, warnings

    # ==================================================================
    # Missing evidence
    # ==================================================================

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

    # ==================================================================
    # Evidence extraction
    # ==================================================================

    def _image_highlights(
        self,
        report: Dict[str, Any],
        highlights: List[str],
    ) -> None:
        """Explain ImageAgent output."""

        if not report:
            highlights.append(
                "ImageAgent did not provide a usable visual assessment."
            )
            return

        decision = str(
            report.get("decision", "")
        ).upper()

        damages = report.get(
            "detected_damage",
            [],
        )

        if isinstance(damages, str):
            damages = [damages]

        if isinstance(damages, list):

            readable = [
                self._damage_label(str(item))
                for item in damages
                if str(item).strip()
            ]

            if readable:
                highlights.append(
                    "Image analysis detected vehicle damage: "
                    + ", ".join(readable)
                    + "."
                )

        confidence = self._safe_float(
            report.get("confidence"),
            0.0,
        )

        confidence = max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )

        if decision == "DAMAGE_DETECTED":

            highlights.append(
                "ImageAgent classified the supplied image as "
                f"damage detected with confidence {confidence:.3f}."
            )

        elif decision:

            highlights.append(
                f"ImageAgent decision: {decision}."
            )

        contradictions = report.get(
            "contradictions",
            [],
        )

        if isinstance(contradictions, list):

            for contradiction in contradictions:

                if str(contradiction).strip():

                    highlights.append(
                        f"ImageAgent contradiction: {contradiction}"
                    )

    def _sensor_highlights(
        self,
        report: Dict[str, Any],
        highlights: List[str],
    ) -> None:
        """Explain learned sensor anomaly detection."""

        if not report:
            highlights.append(
                "SensorAgent did not provide a usable telemetry assessment."
            )
            return

        decision = str(
            report.get("decision", "")
        ).upper()

        anomaly = bool(
            report.get("anomaly", False)
        )

        if anomaly:

            highlights.append(
                "SensorAgent identified an anomalous telemetry pattern "
                "relative to the learned normal distribution."
            )

        elif decision == "PASS":

            highlights.append(
                "SensorAgent found the supplied telemetry consistent "
                "with the learned normal distribution."
            )

        elif decision:

            highlights.append(
                f"SensorAgent decision: {decision}."
            )

        contradictions = report.get(
            "contradictions",
            [],
        )

        if isinstance(contradictions, list):

            for contradiction in contradictions:

                if str(contradiction).strip():

                    highlights.append(
                        f"SensorAgent contradiction: {contradiction}"
                    )

    def _text_highlights(
        self,
        report: Dict[str, Any],
        highlights: List[str],
    ) -> None:
        """Explain structured information extracted from the claim narrative."""

        if not report:
            highlights.append(
                "TextAgent did not provide a usable narrative assessment."
            )
            return

        decision = str(
            report.get("decision", "")
        ).upper()

        extracted = report.get(
            "extracted_information",
            {},
        )

        if not isinstance(extracted, dict):
            extracted = {}

        incident_type = extracted.get(
            "incident_type"
        )

        if incident_type:

            highlights.append(
                "Claim narrative indicates incident type: "
                f"{str(incident_type).replace('_', ' ')}."
            )

        damage_types = extracted.get(
            "damage_types",
            [],
        )

        if isinstance(damage_types, str):
            damage_types = [damage_types]

        if isinstance(damage_types, list) and damage_types:

            readable = [
                self._damage_label(str(item))
                for item in damage_types
                if str(item).strip()
            ]

            if readable:

                highlights.append(
                    "Claim narrative describes damage: "
                    + ", ".join(readable)
                    + "."
                )

        if decision:

            highlights.append(
                f"TextAgent decision: {decision}."
            )

        contradictions = report.get(
            "contradictions",
            [],
        )

        if isinstance(contradictions, list):

            for contradiction in contradictions:

                if str(contradiction).strip():

                    highlights.append(
                        f"TextAgent contradiction: {contradiction}"
                    )

    def _cross_modal_highlights(
        self,
        report: Dict[str, Any],
        highlights: List[str],
    ) -> None:
        """Explain agreement or contradiction between modalities."""

        if not report:
            highlights.append(
                "CrossModalAgent did not provide a multimodal "
                "consistency assessment."
            )
            return

        decision = str(
            report.get("decision", "")
        ).upper()

        agreement_state = str(
            report.get("agreement_state", "")
        ).upper()

        evidence = report.get(
            "evidence",
            [],
        )

        if isinstance(evidence, list):

            for item in evidence:

                if str(item).strip():

                    highlights.append(
                        f"Cross-modal evidence: {item}"
                    )

        contradictions = report.get(
            "contradictions",
            [],
        )

        if isinstance(contradictions, list):

            for item in contradictions:

                if str(item).strip():

                    highlights.append(
                        f"Cross-modal contradiction: {item}"
                    )

        if agreement_state:

            highlights.append(
                f"CrossModalAgent agreement state: {agreement_state}."
            )

        elif decision:

            highlights.append(
                f"CrossModalAgent decision: {decision}."
            )

    def _risk_highlights(
        self,
        risk_report: Dict[str, Any],
        highlights: List[str],
    ) -> None:
        """Explain RiskEngine without confusing raw model scores."""

        if not risk_report:
            highlights.append(
                "RiskEngine did not provide a consensus risk assessment."
            )
            return

        decision = str(
            risk_report.get("decision", "")
        ).upper()

        fraud_score = self._safe_float(
            risk_report.get("fraud_score"),
            0.0,
        )

        fraud_score = max(
            0.0,
            min(
                100.0,
                fraud_score,
            ),
        )

        weighted_risk = self._safe_float(
            risk_report.get("weighted_risk"),
            0.0,
        )

        weighted_risk = max(
            0.0,
            min(
                1.0,
                weighted_risk,
            ),
        )

        highlights.append(
            "RiskEngine produced a preliminary decision of "
            f"{decision or 'UNSPECIFIED'} with fraud score "
            f"{fraud_score:.0f}/100."
        )

        formula = risk_report.get(
            "formula_components",
            {},
        )

        if isinstance(formula, dict):

            active_signals: List[str] = []

            for name, value in formula.items():

                numeric_value = self._safe_float(
                    value,
                    0.0,
                )

                if numeric_value > 0:

                    active_signals.append(
                        f"{name}={numeric_value:.3f}"
                    )

            if active_signals:

                highlights.append(
                    "Explicit fraud signals contributing to consensus: "
                    + ", ".join(active_signals)
                    + "."
                )

            else:

                highlights.append(
                    "No explicit fraud signal was activated by the "
                    "current evidence agents."
                )

        if weighted_risk > 0:

            highlights.append(
                "Consensus weighted fraud risk before adversarial "
                f"review: {weighted_risk:.3f}."
            )

    def _adversarial_highlights(
        self,
        report: Dict[str, Any],
        highlights: List[str],
    ) -> None:
        """Explain the final adversarial verification stage."""

        if not report:
            highlights.append(
                "AdversarialVerifier did not provide a final "
                "verification assessment."
            )
            return

        contradictions = report.get(
            "contradictions",
            [],
        )

        if not isinstance(contradictions, list):
            contradictions = []

        flagged = bool(
            report.get(
                "adversarial_flagged",
                False,
            )
        )

        if contradictions:

            highlights.append(
                "AdversarialVerifier identified "
                f"{len(contradictions)} contradiction(s) across "
                "the active evidence agents."
            )

            for contradiction in contradictions:

                if str(contradiction).strip():

                    highlights.append(
                        f"Verification contradiction: {contradiction}"
                    )

        elif not flagged:

            highlights.append(
                "AdversarialVerifier found no contradictions across "
                "the active evidence agents."
            )

        else:

            highlights.append(
                "AdversarialVerifier flagged the claim for "
                "additional review."
            )

    # ==================================================================
    # Damage labels
    # ==================================================================

    @staticmethod
    def _damage_label(
        value: str,
    ) -> str:
        """Convert model class names into readable labels."""

        labels = {
            "dent": "dent",
            "scratch": "scratch",
            "crack": "crack",
            "glass_shatter": "glass shatter",
            "lamp_broken": "broken lamp",
            "tire_flat": "flat tire",
        }

        return labels.get(
            value,
            value.replace("_", " "),
        )

    # ==================================================================
    # Contradiction handling
    # ==================================================================

    @staticmethod
    def _collect_unique_contradictions(
        reports: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Collect unique contradictions.

        CrossModalAgent and AdversarialVerifier can describe the same
        underlying contradiction. Counting each copy would inflate
        the explanation's contradiction count.
        """

        unique: List[str] = []
        seen: set[str] = set()

        for report in reports:

            if not isinstance(report, dict):
                continue

            contradictions = report.get(
                "contradictions",
                [],
            )

            if not isinstance(contradictions, list):
                continue

            for contradiction in contradictions:

                normalized = str(
                    contradiction
                ).strip()

                if not normalized:
                    continue

                key = normalized.lower()

                if key not in seen:

                    seen.add(key)
                    unique.append(normalized)

        return unique

    # ==================================================================
    # Main explanation
    # ==================================================================

    def generate_explanation(
        self,
        domain: str,
        overall_verdict: str,
        risk_score: float,
        agent_reports: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a transparent explanation.

        The AdversarialVerifier is the authoritative source for the
        final verdict.

        This agent fails closed when:
            - required reports are missing
            - report identity is incorrect
            - upstream reports fail
            - verifier output is invalid
            - graph and verifier verdicts disagree
        """

        if not isinstance(agent_reports, dict):
            agent_reports = {}

        # --------------------------------------------------------------
        # Retrieve reports
        # --------------------------------------------------------------

        image_report = self._get_report(
            agent_reports,
            "ImageAgent",
        )

        sensor_report = self._get_report(
            agent_reports,
            "SensorAgent",
        )

        text_report = self._get_report(
            agent_reports,
            "TextAgent",
        )

        cross_modal_report = self._get_report(
            agent_reports,
            "CrossModalAgent",
        )

        risk_report = self._get_report(
            agent_reports,
            "RiskEngine",
        )

        verifier_report = self._get_report(
            agent_reports,
            "AdversarialVerifier",
        )

        # --------------------------------------------------------------
        # Validate pipeline
        # --------------------------------------------------------------

        pipeline_valid, pipeline_failures = (
            self._validate_pipeline(
                agent_reports
            )
        )

        # --------------------------------------------------------------
        # Resolve authoritative verdict
        # --------------------------------------------------------------

        normalized_verdict, verdict_warnings = (
            self._resolve_authoritative_verdict(
                requested_verdict=overall_verdict,
                verifier_report=verifier_report,
                pipeline_valid=pipeline_valid,
            )
        )

        if verdict_warnings:
            pipeline_failures = (
                list(pipeline_failures)
                + verdict_warnings
            )

        # --------------------------------------------------------------
        # Normalize final fraud score
        # --------------------------------------------------------------

        final_score = self._safe_float(
            risk_score,
            0.0,
        )

        final_score = max(
            0.0,
            min(
                100.0,
                final_score,
            ),
        )

        # --------------------------------------------------------------
        # Collect evidence highlights
        # --------------------------------------------------------------

        highlights: List[str] = []

        self._image_highlights(
            image_report,
            highlights,
        )

        self._sensor_highlights(
            sensor_report,
            highlights,
        )

        self._text_highlights(
            text_report,
            highlights,
        )

        self._cross_modal_highlights(
            cross_modal_report,
            highlights,
        )

        self._risk_highlights(
            risk_report,
            highlights,
        )

        self._adversarial_highlights(
            verifier_report,
            highlights,
        )

        # --------------------------------------------------------------
        # Pipeline warnings
        # --------------------------------------------------------------

        if pipeline_failures:

            highlights.append(
                "Pipeline integrity warning: automated verification "
                "could not be treated as fully complete."
            )

            for failure in pipeline_failures:

                highlights.append(
                    f"Pipeline issue: {failure}"
                )

        # --------------------------------------------------------------
        # Unique contradictions
        # --------------------------------------------------------------

        contradiction_sources = [
            image_report,
            sensor_report,
            text_report,
            cross_modal_report,
            verifier_report,
        ]

        unique_contradictions = (
            self._collect_unique_contradictions(
                contradiction_sources
            )
        )

        contradiction_count = len(
            unique_contradictions
        )

        # --------------------------------------------------------------
        # Verifier consistency
        # --------------------------------------------------------------

        verifier_decision = str(
            verifier_report.get(
                "decision",
                "",
            )
        ).upper()

        raw_verifier_final = verifier_report.get(
            "final_verdict"
        )

        if raw_verifier_final is None:
            raw_verifier_final = verifier_report.get(
                "decision"
            )

        verifier_final_verdict = self._normalise_verdict(
            raw_verifier_final
        )

        if (
            not verifier_report
            or self._is_pipeline_failure(verifier_report)
        ):
            verifier_final_verdict = REVIEW_REQUIRED

        # --------------------------------------------------------------
        # Executive summary
        # --------------------------------------------------------------

        actionable_steps: List[str] = []

        if normalized_verdict == VERIFIED:

            summary = (
                f"Automated evidence verification for this "
                f"{domain.upper()} claim completed successfully. "
                f"The active image, sensor, text, cross-modal, "
                f"and adversarial checks found no recorded "
                f"contradictions. The final fraud score is "
                f"{final_score:.0f}/100. This result supports "
                f"downstream claim processing but does not by itself "
                f"determine policy coverage or payment."
            )

            actionable_steps.extend(
                [
                    "Continue the claim through downstream coverage "
                    "and settlement checks.",
                    "Preserve the generated evidence report for audit "
                    "and provenance.",
                ]
            )

        elif normalized_verdict == REVIEW_REQUIRED:

            summary = (
                f"The {domain.upper()} claim requires human review. "
                f"The automated evidence pipeline produced a final "
                f"fraud score of {final_score:.0f}/100 and identified "
                f"evidence or pipeline conditions that should be "
                f"examined before a final claim processing decision."
            )

            if pipeline_failures:

                summary += (
                    " One or more required automated verification "
                    "components did not complete successfully."
                )

            actionable_steps.extend(
                [
                    "Route the claim to a human claims or fraud reviewer.",
                    "Review the recorded evidence contradictions and "
                    "model findings.",
                    "Request additional evidence if the reviewer "
                    "determines it is necessary.",
                ]
            )

        elif normalized_verdict == SUSPICIOUS:

            summary = (
                f"The {domain.upper()} claim was classified as "
                f"SUSPICIOUS by the automated verification pipeline. "
                f"The final fraud score is {final_score:.0f}/100. "
                f"The result should be investigated before downstream "
                f"claim processing is completed."
            )

            actionable_steps.extend(
                [
                    "Route the claim for enhanced human fraud review.",
                    "Examine the model evidence and any detected "
                    "contradictions.",
                    "Obtain additional supporting evidence where "
                    "appropriate.",
                ]
            )

        else:

            summary = (
                f"The {domain.upper()} claim reached a REJECTED "
                f"automated verification outcome with a final fraud "
                f"score of {final_score:.0f}/100. This is an "
                f"evidence-verification result and should not be "
                f"treated as a standalone legal, contractual, or "
                f"payment decision."
            )

            actionable_steps.extend(
                [
                    "Route the claim for human review before any "
                    "final denial or settlement action.",
                    "Document the specific evidence and contradictions "
                    "supporting the outcome.",
                ]
            )

        # --------------------------------------------------------------
        # Final result
        # --------------------------------------------------------------

        pipeline_status = (
            "COMPLETE"
            if pipeline_valid and not verdict_warnings
            else "INCOMPLETE"
        )

        return {
            "agent": "ExplanationAgent",
            "domain": domain,
            "decision": normalized_verdict,
            "final_verdict": normalized_verdict,

            "risk_score": round(
                final_score,
                2,
            ),

            "confidence": self._safe_float(
                verifier_report.get(
                    "confidence",
                    0.0,
                ),
                0.0,
            ),

            "executive_summary": summary,

            "key_highlights": highlights,

            "recommended_actions": actionable_steps,

            "contradiction_count": contradiction_count,

            "contradictions": unique_contradictions,

            "verifier_decision": verifier_decision,

            "verifier_final_verdict": verifier_final_verdict,

            "pipeline_status": pipeline_status,

            "pipeline_failures": pipeline_failures,

            "model_version": self.model_version,
        }


# ======================================================================
# Singleton
# ======================================================================

_explanation_agent: ExplanationAgent | None = None


def get_explanation_agent() -> ExplanationAgent:
    """Return the shared ExplanationAgent instance."""

    global _explanation_agent

    if _explanation_agent is None:
        _explanation_agent = ExplanationAgent()

    return _explanation_agent


# ======================================================================
# Convenience function
# ======================================================================

def generate_explanation(
    domain: str,
    overall_verdict: str,
    risk_score: float,
    agent_reports: Dict[str, Any],
) -> Dict[str, Any]:
    """Convenience wrapper for ExplanationAgent."""

    return get_explanation_agent().generate_explanation(
        domain=domain,
        overall_verdict=overall_verdict,
        risk_score=risk_score,
        agent_reports=agent_reports,
    )


# ======================================================================
# Local regression tests
# ======================================================================

if __name__ == "__main__":

    import json

    test_reports = {
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
        },

        "SensorAgent": {
            "agent": "SensorAgent",
            "decision": "PASS",
            "confidence": 0.8492,
            "risk_score": 0.4855,
            "anomaly": False,
            "contradictions": [],
        },

        "TextAgent": {
            "agent": "TextAgent",
            "decision": "CONSISTENT",
            "confidence": 0.85,
            "risk_score": 0.30,
            "extracted_information": {
                "incident_type": "collision",
                "damage_types": [
                    "dent",
                    "scratch",
                    "lamp_broken",
                ],
                "time_mentions": [
                    "6:30 PM",
                ],
                "location_mentions": [
                    "highway",
                ],
            },
            "contradictions": [],
        },

        "CrossModalAgent": {
            "agent": "CrossModalAgent",
            "decision": "PARTIAL_AGREEMENT",
            "agreement_state": "PARTIAL_AGREEMENT",
            "confidence": 0.80,
            "risk_score": 0.15,
            "evidence": [
                "Image and text evidence agree on damage: "
                "dent, lamp_broken, scratch."
            ],
            "contradictions": [],
        },

        "RiskEngine": {
            "agent": "RiskEngine",
            "decision": "VERIFIED",
            "fraud_score": 16,
            "weighted_risk": 0.1562,
            "formula_components": {},
        },

        "AdversarialVerifier": {
            "agent": "AdversarialVerifier",
            "decision": "PASS",
            "final_verdict": "VERIFIED",
            "confidence": 0.96,
            "risk_score": 0.0,
            "fraud_score": 0,
            "adversarial_flagged": False,
            "contradictions": [],
        },
    }

    print("=" * 70)
    print("TRUTHCHAIN EXPLANATION AGENT TEST")
    print("=" * 70)

    result = generate_explanation(
        domain="motor",
        overall_verdict="VERIFIED",
        risk_score=0,
        agent_reports=test_reports,
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )

    assert result["agent"] == "ExplanationAgent"
    assert result["decision"] == "VERIFIED"
    assert result["final_verdict"] == "VERIFIED"
    assert result["verifier_final_verdict"] == "VERIFIED"
    assert result["pipeline_status"] == "COMPLETE"

    print("\nPASS: NORMAL VERIFIED PIPELINE")

    # --------------------------------------------------------------
    # Missing agent
    # --------------------------------------------------------------

    missing_reports = dict(test_reports)
    del missing_reports["TextAgent"]

    result = generate_explanation(
        domain="motor",
        overall_verdict="VERIFIED",
        risk_score=0,
        agent_reports=missing_reports,
    )

    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["final_verdict"] == "REVIEW_REQUIRED"
    assert result["pipeline_status"] == "INCOMPLETE"

    print("PASS: MISSING AGENT FAIL-CLOSED")

    # --------------------------------------------------------------
    # Failed agent
    # --------------------------------------------------------------

    failed_reports = dict(test_reports)

    failed_reports["TextAgent"] = {
        "agent": "TextAgent",
        "decision": "ERROR",
        "error": "Text extraction failed",
    }

    result = generate_explanation(
        domain="motor",
        overall_verdict="VERIFIED",
        risk_score=0,
        agent_reports=failed_reports,
    )

    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["pipeline_status"] == "INCOMPLETE"

    print("PASS: FAILED AGENT FAIL-CLOSED")

    # --------------------------------------------------------------
    # Identity mismatch
    # --------------------------------------------------------------

    identity_reports = dict(test_reports)

    identity_reports["TextAgent"] = {
        "agent": "ImageAgent",
        "decision": "CONSISTENT",
    }

    result = generate_explanation(
        domain="motor",
        overall_verdict="VERIFIED",
        risk_score=0,
        agent_reports=identity_reports,
    )

    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["pipeline_status"] == "INCOMPLETE"

    print("PASS: AGENT IDENTITY MISMATCH FAIL-CLOSED")

    # --------------------------------------------------------------
    # Verifier disagreement
    # --------------------------------------------------------------

    mismatch_reports = dict(test_reports)

    mismatch_reports["AdversarialVerifier"] = {
        "agent": "AdversarialVerifier",
        "decision": "SUSPICIOUS",
        "final_verdict": "SUSPICIOUS",
        "confidence": 0.90,
        "adversarial_flagged": True,
        "contradictions": [
            "Image and text evidence disagree."
        ],
    }

    result = generate_explanation(
        domain="motor",
        overall_verdict="VERIFIED",
        risk_score=70,
        agent_reports=mismatch_reports,
    )

    assert result["decision"] == "SUSPICIOUS"
    assert result["final_verdict"] == "SUSPICIOUS"
    assert result["verifier_final_verdict"] == "SUSPICIOUS"

    print("PASS: VERIFIER OVERRIDES GRAPH VERDICT")

    # --------------------------------------------------------------
    # Unknown verifier verdict
    # --------------------------------------------------------------

    unknown_reports = dict(test_reports)

    unknown_reports["AdversarialVerifier"] = {
        "agent": "AdversarialVerifier",
        "decision": "SOMETHING_UNKNOWN",
        "final_verdict": "SOMETHING_UNKNOWN",
        "confidence": 0.0,
        "contradictions": [],
    }

    result = generate_explanation(
        domain="motor",
        overall_verdict="VERIFIED",
        risk_score=0,
        agent_reports=unknown_reports,
    )

    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["pipeline_status"] == "INCOMPLETE"

    print("PASS: UNKNOWN VERIFIER STATE FAIL-CLOSED")

    print()
    print("=" * 70)
    print("ALL EXPLANATION AGENT TESTS PASSED")
    print("=" * 70)