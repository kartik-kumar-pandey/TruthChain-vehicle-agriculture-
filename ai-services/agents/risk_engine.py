"""
TruthChain 2.0 - Consensus Risk Engine
---------------------------------------

Calculates PRELIMINARY fraud risk from the active evidence agents.

Important semantic distinction:

    Evidence confidence != fraud probability.

Production agents provide different kinds of scores:

    ImageAgent
        risk_score represents confidence/severity of detected
        vehicle damage. Damage itself is NOT fraud.

    SensorAgent
        risk_score represents telemetry/anomaly-related signal.
        A PASS/normal telemetry result is not treated as fraud.

    TextAgent
        risk_score represents narrative risk/consistency signal.
        A CONSISTENT narrative is not treated as fraud.

    CrossModalAgent
        risk_score represents cross-modal contradiction risk.
        A CONSISTENT result is not treated as fraud.

Therefore this engine converts agent outputs into explicit
fraud-risk signals before applying the configured weights.

The AdversarialVerifier remains the FINAL decision authority.

Production safety:
    - Missing required evidence does not become VERIFIED.
    - Agent execution failures do not become VERIFIED.
    - Insufficient data produces NEEDS_REVIEW.
    - Invalid/mismatched agent reports do not become VERIFIED.
    - This engine only produces a PRELIMINARY risk assessment.
    - Final fraud authority remains downstream.
"""

from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, List, Tuple


logger = logging.getLogger(__name__)


MODEL_VERSION = "consensus-risk-v3.3"


# ======================================================================
# Production constants
# ======================================================================

WEIGHT_IMAGE = 0.20
WEIGHT_SENSOR = 0.20
WEIGHT_TEXT = 0.15
WEIGHT_CROSS_MODAL = 0.25


REQUIRED_AGENTS = (
    "ImageAgent",
    "SensorAgent",
    "TextAgent",
    "CrossModalAgent",
)


# These states mean the upstream agent did not produce usable
# evidence for consensus calculation.
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


class RiskEngine:
    """
    Calculates preliminary multi-agent fraud risk.

    This agent does NOT produce the final fraud decision.

    Final decision authority:
        AdversarialVerifier

    Important:
        The preliminary score is only meaningful when all required
        evidence agents have successfully produced usable reports.
    """

    def __init__(
        self,
        model_version: str = MODEL_VERSION,
    ) -> None:
        self.model_version = model_version

    # ==================================================================
    # MAIN CONSENSUS CALCULATION
    # ==================================================================

    def calculate_consensus(
        self,
        agent_reports: Dict[str, Any],
    ) -> Dict[str, Any]:

        start = time.perf_counter()

        try:
            if not isinstance(agent_reports, dict):
                return self._insufficient_data_result(
                    start=start,
                    failures=[
                        "agent_reports is not a dictionary."
                    ],
                )

            # ----------------------------------------------------------
            # Validate required evidence agents BEFORE calculating risk.
            #
            # This is the most important production safety boundary.
            #
            # We must never do:
            #
            #     failed agent -> risk 0 -> VERIFIED
            #
            # Instead:
            #
            #     missing/failed/invalid evidence -> NEEDS_REVIEW
            # ----------------------------------------------------------

            pipeline_valid, failures = self._validate_required_agents(
                agent_reports
            )

            if not pipeline_valid:
                logger.warning(
                    "RiskEngine fail-closed: %s",
                    failures,
                )

                return self._insufficient_data_result(
                    start=start,
                    failures=failures,
                )

            # ----------------------------------------------------------
            # Retrieve active agent reports
            # ----------------------------------------------------------

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

            # ----------------------------------------------------------
            # Convert evidence-agent outputs into FRAUD signals.
            #
            # This is intentionally different from blindly using
            # each agent's raw risk_score.
            # ----------------------------------------------------------

            image_fraud_signal = self._image_fraud_signal(
                image_report
            )

            sensor_fraud_signal = self._sensor_fraud_signal(
                sensor_report
            )

            text_fraud_signal = self._text_fraud_signal(
                text_report
            )

            cross_modal_fraud_signal = self._cross_modal_fraud_signal(
                cross_modal_report
            )

            # ----------------------------------------------------------
            # Active evidence weights
            #
            # Image       = 0.20
            # Sensor      = 0.20
            # Text        = 0.15
            # CrossModal  = 0.25
            #
            # These sum to 0.80 because investigation/verifier stages
            # belong to later parts of the pipeline.
            #
            # Normalize to 1.0.
            # ----------------------------------------------------------

            active_weight = (
                WEIGHT_IMAGE
                + WEIGHT_SENSOR
                + WEIGHT_TEXT
                + WEIGHT_CROSS_MODAL
            )

            # ----------------------------------------------------------
            # Weighted preliminary fraud risk
            # ----------------------------------------------------------

            weighted_risk_raw = (
                WEIGHT_IMAGE * image_fraud_signal
                + WEIGHT_SENSOR * sensor_fraud_signal
                + WEIGHT_TEXT * text_fraud_signal
                + WEIGHT_CROSS_MODAL * cross_modal_fraud_signal
            )

            if active_weight > 0:
                weighted_risk = (
                    weighted_risk_raw / active_weight
                )
            else:
                weighted_risk = 0.0

            weighted_risk = self._safe_risk(
                weighted_risk
            )

            # ----------------------------------------------------------
            # Deterministic 0-100 fraud score
            # ----------------------------------------------------------

            fraud_score = self._risk_to_score(
                weighted_risk
            )

            # ----------------------------------------------------------
            # Preliminary decision bands
            #
            # These are preliminary only.
            # AdversarialVerifier has final authority.
            # ----------------------------------------------------------

            preliminary_verdict = self._verdict_from_score(
                fraud_score
            )

            processing_time_ms = (
                time.perf_counter() - start
            ) * 1000.0

            # ----------------------------------------------------------
            # Structured result
            # ----------------------------------------------------------

            return {
                "agent": "RiskEngine",
                "domain": "motor",

                "decision": preliminary_verdict,

                "fraud_score": fraud_score,

                "weighted_risk": round(
                    weighted_risk,
                    4,
                ),

                # This is intentionally the preliminary result.
                "final_verdict": preliminary_verdict,

                "model_version": self.model_version,

                # ------------------------------------------------------
                # Explicit FRAUD signals
                # ------------------------------------------------------

                "formula_components": {
                    "image_fraud_signal": round(
                        image_fraud_signal,
                        4,
                    ),
                    "sensor_fraud_signal": round(
                        sensor_fraud_signal,
                        4,
                    ),
                    "text_fraud_signal": round(
                        text_fraud_signal,
                        4,
                    ),
                    "cross_modal_fraud_signal": round(
                        cross_modal_fraud_signal,
                        4,
                    ),
                },

                # ------------------------------------------------------
                # Preserve original agent-level raw scores for auditability
                # ------------------------------------------------------

                "raw_agent_scores": {
                    "image_risk_score": round(
                        self._safe_risk(
                            image_report.get(
                                "risk_score",
                                0.0,
                            )
                        ),
                        4,
                    ),
                    "sensor_risk_score": round(
                        self._safe_risk(
                            sensor_report.get(
                                "risk_score",
                                0.0,
                            )
                        ),
                        4,
                    ),
                    "text_risk_score": round(
                        self._safe_risk(
                            text_report.get(
                                "risk_score",
                                0.0,
                            )
                        ),
                        4,
                    ),
                    "cross_modal_risk_score": round(
                        self._safe_risk(
                            cross_modal_report.get(
                                "risk_score",
                                0.0,
                            )
                        ),
                        4,
                    ),
                },

                # ------------------------------------------------------
                # Configuration
                # ------------------------------------------------------

                "weights": {
                    "image": WEIGHT_IMAGE,
                    "sensor": WEIGHT_SENSOR,
                    "text": WEIGHT_TEXT,
                    "cross_modal": WEIGHT_CROSS_MODAL,
                },

                "active_weight_total": round(
                    active_weight,
                    4,
                ),

                # ------------------------------------------------------
                # Pipeline metadata
                # ------------------------------------------------------

                "risk_stage": "PRELIMINARY",

                "pipeline_status": "COMPLETE",

                "pipeline_failures": [],

                "evidence_status": "COMPLETE",

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
                "RiskEngine unexpected failure"
            )

            return {
                "agent": "RiskEngine",
                "domain": "motor",
                "decision": "NEEDS_REVIEW",
                "fraud_score": 0,
                "weighted_risk": 0.0,
                "final_verdict": "NEEDS_REVIEW",
                "model_version": self.model_version,
                "formula_components": {
                    "image_fraud_signal": 0.0,
                    "sensor_fraud_signal": 0.0,
                    "text_fraud_signal": 0.0,
                    "cross_modal_fraud_signal": 0.0,
                },
                "raw_agent_scores": {
                    "image_risk_score": 0.0,
                    "sensor_risk_score": 0.0,
                    "text_risk_score": 0.0,
                    "cross_modal_risk_score": 0.0,
                },
                "weights": {
                    "image": WEIGHT_IMAGE,
                    "sensor": WEIGHT_SENSOR,
                    "text": WEIGHT_TEXT,
                    "cross_modal": WEIGHT_CROSS_MODAL,
                },
                "active_weight_total": 0.0,
                "risk_stage": "PRELIMINARY",
                "pipeline_status": "ERROR",
                "pipeline_failures": [
                    "RiskEngine internal error."
                ],
                "evidence_status": "INSUFFICIENT_DATA",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "processing_time_ms": round(
                    processing_time_ms,
                    2,
                ),
            }

    # ==================================================================
    # PIPELINE VALIDATION
    # ==================================================================

    @classmethod
    def _validate_required_agents(
        cls,
        agent_reports: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        Validate that all required evidence agents completed successfully.

        Validation includes:

            1. Required key exists.
            2. Report is a dictionary.
            3. Internal agent identity matches the expected key.
            4. Decision is present.
            5. Decision/state is not a failure state.
            6. Explicit error field is absent.

        This prevents:

            missing/failed evidence
                    ↓
                signal = 0
                    ↓
                 VERIFIED

        Instead:

            missing/failed/invalid evidence
                    ↓
                NEEDS_REVIEW
        """

        failures: List[str] = []

        for agent_name in REQUIRED_AGENTS:

            if agent_name not in agent_reports:
                failures.append(
                    f"{agent_name} report is missing."
                )
                continue

            report = agent_reports.get(
                agent_name
            )

            if not isinstance(report, dict):
                failures.append(
                    f"{agent_name} report is invalid."
                )
                continue

            # ----------------------------------------------------------
            # Evidence identity validation
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
                    f"received {reported_agent or 'UNKNOWN'}."
                )
                continue

            # ----------------------------------------------------------
            # Decision validation
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
            # Explicit failure state
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
        """Return True when an agent report represents failure."""

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

        return (
            report
            if isinstance(report, dict)
            else {}
        )

    def _insufficient_data_result(
        self,
        start: float,
        failures: List[str],
    ) -> Dict[str, Any]:
        """
        Return a fail-closed result.

        IMPORTANT:
            This must never return VERIFIED.
        """

        processing_time_ms = (
            time.perf_counter() - start
        ) * 1000.0

        return {
            "agent": "RiskEngine",
            "domain": "motor",

            "decision": "NEEDS_REVIEW",

            "fraud_score": 0,

            "weighted_risk": 0.0,

            "final_verdict": "NEEDS_REVIEW",

            "model_version": self.model_version,

            "formula_components": {
                "image_fraud_signal": 0.0,
                "sensor_fraud_signal": 0.0,
                "text_fraud_signal": 0.0,
                "cross_modal_fraud_signal": 0.0,
            },

            "raw_agent_scores": {
                "image_risk_score": 0.0,
                "sensor_risk_score": 0.0,
                "text_risk_score": 0.0,
                "cross_modal_risk_score": 0.0,
            },

            "weights": {
                "image": WEIGHT_IMAGE,
                "sensor": WEIGHT_SENSOR,
                "text": WEIGHT_TEXT,
                "cross_modal": WEIGHT_CROSS_MODAL,
            },

            "active_weight_total": 0.0,

            "risk_stage": "PRELIMINARY",

            "pipeline_status": "INCOMPLETE",

            "pipeline_failures": failures,

            "evidence_status": "INSUFFICIENT_DATA",

            "processing_time_ms": round(
                processing_time_ms,
                2,
            ),
        }

    # ==================================================================
    # IMAGE FRAUD SIGNAL
    # ==================================================================

    @classmethod
    def _image_fraud_signal(
        cls,
        report: Dict[str, Any],
    ) -> float:
        """
        Convert ImageAgent output into a fraud signal.

        A damage detection is NOT inherently fraudulent.

        Example:

            DAMAGE_DETECTED
                -> 0.0 fraud signal

        An image-related fraud signal can arise through explicit
        contradictions.

        Agent failure is handled by pipeline validation before this
        function is called.
        """

        decision = str(
            report.get(
                "decision",
                "",
            )
        ).strip().upper()

        contradictions = report.get(
            "contradictions",
            [],
        )

        if not isinstance(
            contradictions,
            list,
        ):
            contradictions = []

        # Explicit image contradictions are genuine fraud
        # signals. Do not manufacture risk from damage alone.
        if contradictions:
            return cls._safe_risk(
                min(
                    0.25 * len(contradictions),
                    1.0,
                )
            )

        if decision == "DAMAGE_DETECTED":
            return 0.0

        return 0.0

    # ==================================================================
    # SENSOR FRAUD SIGNAL
    # ==================================================================

    @classmethod
    def _sensor_fraud_signal(
        cls,
        report: Dict[str, Any],
    ) -> float:
        """
        Convert SensorAgent output into a fraud signal.

        A normal telemetry result must not be treated as fraud.

        Only an explicit anomaly/suspicious result contributes
        the agent's risk score.
        """

        decision = str(
            report.get(
                "decision",
                "",
            )
        ).strip().upper()

        anomaly = bool(
            report.get(
                "anomaly",
                False,
            )
        )

        raw_risk = cls._safe_risk(
            report.get(
                "risk_score",
                0.0,
            )
        )

        # Normal telemetry.
        if (
            decision in {
                "PASS",
                "CONSISTENT",
                "NORMAL",
            }
            and not anomaly
        ):
            return 0.0

        # Explicit anomaly.
        if anomaly:
            return raw_risk

        # Explicit suspicious result.
        if decision in {
            "SUSPICIOUS",
            "FAIL",
            "ANOMALY",
            "REVIEW_REQUIRED",
            "CONTRADICTORY",
        }:
            return raw_risk

        return 0.0

    # ==================================================================
    # TEXT FRAUD SIGNAL
    # ==================================================================

    @classmethod
    def _text_fraud_signal(
        cls,
        report: Dict[str, Any],
    ) -> float:
        """
        Convert TextAgent output into a fraud signal.

        A CONSISTENT narrative is not suspicious.
        """

        decision = str(
            report.get(
                "decision",
                "",
            )
        ).strip().upper()

        raw_risk = cls._safe_risk(
            report.get(
                "risk_score",
                0.0,
            )
        )

        if decision in {
            "CONSISTENT",
            "PASS",
            "VERIFIED",
        }:
            return 0.0

        if decision in {
            "SUSPICIOUS",
            "FAIL",
            "REVIEW_REQUIRED",
            "CONTRADICTORY",
        }:
            return raw_risk

        return 0.0

    # ==================================================================
    # CROSS-MODAL FRAUD SIGNAL
    # ==================================================================

    @classmethod
    def _cross_modal_fraud_signal(
        cls,
        report: Dict[str, Any],
    ) -> float:
        """
        Convert CrossModalAgent output into a fraud signal.

        Cross-modal contradiction is the strongest direct evidence
        signal because this agent explicitly compares independent
        image, sensor and text evidence.
        """

        decision = str(
            report.get(
                "decision",
                "",
            )
        ).strip().upper()

        raw_risk = cls._safe_risk(
            report.get(
                "risk_score",
                0.0,
            )
        )

        contradictions = report.get(
            "contradictions",
            [],
        )

        if not isinstance(
            contradictions,
            list,
        ):
            contradictions = []

        # Strongest signal: explicit contradiction.
        if contradictions:

            if decision == "CONTRADICTORY":
                return max(
                    raw_risk,
                    0.75,
                )

            if decision == "REVIEW_REQUIRED":
                return max(
                    raw_risk,
                    0.50,
                )

            return raw_risk

        # Agreement is not fraud.
        if decision in {
            "CONSISTENT",
            "PARTIAL_AGREEMENT",
            "PASS",
            "VERIFIED",
        }:
            return 0.0

        if decision in {
            "SUSPICIOUS",
            "FAIL",
            "REVIEW_REQUIRED",
        }:
            return raw_risk

        return 0.0

    # ==================================================================
    # SCORE CONVERSION
    # ==================================================================

    @staticmethod
    def _risk_to_score(
        risk: float,
    ) -> int:
        """
        Canonical conversion from [0, 1] risk to [0, 100].
        """

        normalized = min(
            max(
                float(risk),
                0.0,
            ),
            1.0,
        )

        return int(
            normalized * 100 + 0.5
        )

    # ==================================================================
    # PRELIMINARY VERDICT
    # ==================================================================

    @staticmethod
    def _verdict_from_score(
        fraud_score: int,
    ) -> str:
        """
        Convert a 0-100 score into TruthChain preliminary
        decision bands.

        These are preliminary only.
        AdversarialVerifier has final authority.
        """

        if fraud_score <= 20:
            return "VERIFIED"

        if fraud_score <= 50:
            return "REVIEW_REQUIRED"

        if fraud_score <= 75:
            return "SUSPICIOUS"

        return "REJECTED"

    # ==================================================================
    # RISK VALIDATION
    # ==================================================================

    @staticmethod
    def _safe_risk(
        value: Any,
    ) -> float:
        """
        Safely normalize a risk score to [0, 1].

        Invalid, NaN, or infinite values are handled deterministically.
        """

        try:
            risk = float(value)

        except (
            TypeError,
            ValueError,
        ):
            return 0.0

        if not math.isfinite(risk):
            if risk == float("inf"):
                return 1.0

            return 0.0

        return min(
            max(
                risk,
                0.0,
            ),
            1.0,
        )


# ======================================================================
# Singleton
# ======================================================================

_risk_engine: RiskEngine | None = None


def get_risk_engine() -> RiskEngine:
    """Return the shared RiskEngine instance."""
    global _risk_engine

    if _risk_engine is None:
        _risk_engine = RiskEngine()

    return _risk_engine


# ======================================================================
# Convenience function
# ======================================================================

def calculate_consensus(
    agent_reports: Dict[str, Any],
) -> Dict[str, Any]:
    """Convenience wrapper for RiskEngine."""
    return get_risk_engine().calculate_consensus(
        agent_reports=agent_reports
    )


# ======================================================================
# Local tests
# ======================================================================

if __name__ == "__main__":

    import json

    print("=" * 70)
    print("TRUTHCHAIN RISK ENGINE TEST")
    print("=" * 70)

    # --------------------------------------------------------------
    # TEST 1: Normal evidence
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
            "contradictions": [],
        },

        "CrossModalAgent": {
            "agent": "CrossModalAgent",
            "decision": "PARTIAL_AGREEMENT",
            "agreement_state": "PARTIAL_AGREEMENT",
            "confidence": 0.80,
            "risk_score": 0.15,
            "contradictions": [],
        },
    }

    result = calculate_consensus(
        valid_reports
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )

    assert result["pipeline_status"] == "COMPLETE"
    assert result["decision"] == "VERIFIED"
    assert result["formula_components"]["image_fraud_signal"] == 0.0
    assert result["formula_components"]["sensor_fraud_signal"] == 0.0
    assert result["formula_components"]["text_fraud_signal"] == 0.0
    assert result["formula_components"]["cross_modal_fraud_signal"] == 0.0

    # --------------------------------------------------------------
    # TEST 2: Failed TextAgent
    #
    # This MUST NOT produce VERIFIED.
    # --------------------------------------------------------------

    print()
    print("=" * 70)
    print("FAIL-CLOSED TEST: TEXT AGENT FAILURE")
    print("=" * 70)

    failed_reports = dict(
        valid_reports
    )

    failed_reports["TextAgent"] = {
        "agent": "TextAgent",
        "decision": "ERROR",
        "error": "Text model unavailable",
    }

    failed_result = calculate_consensus(
        failed_reports
    )

    print(
        json.dumps(
            failed_result,
            indent=2,
        )
    )

    assert failed_result["decision"] == "NEEDS_REVIEW"
    assert failed_result["pipeline_status"] == "INCOMPLETE"

    # --------------------------------------------------------------
    # TEST 3: Missing CrossModalAgent
    #
    # This MUST NOT produce VERIFIED.
    # --------------------------------------------------------------

    print()
    print("=" * 70)
    print("FAIL-CLOSED TEST: MISSING CROSS-MODAL RESULT")
    print("=" * 70)

    missing_reports = dict(
        valid_reports
    )

    del missing_reports[
        "CrossModalAgent"
    ]

    missing_result = calculate_consensus(
        missing_reports
    )

    print(
        json.dumps(
            missing_result,
            indent=2,
        )
    )

    assert missing_result["decision"] == "NEEDS_REVIEW"
    assert missing_result["pipeline_status"] == "INCOMPLETE"

    # --------------------------------------------------------------
    # TEST 4: Agent identity mismatch
    #
    # This MUST NOT be accepted.
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

    mismatch_result = calculate_consensus(
        mismatch_reports
    )

    print(
        json.dumps(
            mismatch_result,
            indent=2,
        )
    )

    assert mismatch_result["decision"] == "NEEDS_REVIEW"
    assert mismatch_result["pipeline_status"] == "INCOMPLETE"

    # --------------------------------------------------------------
    # TEST 5: Insufficient TextAgent
    #
    # This MUST NOT become VERIFIED.
    # --------------------------------------------------------------

    print()
    print("=" * 70)
    print("FAIL-CLOSED TEST: INSUFFICIENT TEXT EVIDENCE")
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

    insufficient_result = calculate_consensus(
        insufficient_reports
    )

    print(
        json.dumps(
            insufficient_result,
            indent=2,
        )
    )

    assert insufficient_result["decision"] == "NEEDS_REVIEW"
    assert insufficient_result["pipeline_status"] == "INCOMPLETE"

    print()
    print("=" * 70)
    print("ALL RISK ENGINE TESTS PASSED")
    print("=" * 70)