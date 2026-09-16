"""
TruthChain CrossModalAgent
--------------------------
Compares evidence from:
    - ImageAgent
    - SensorAgent
    - TextAgent

Purpose:
    Detect cross-modal agreement, partial agreement, and genuine
    contradictions.

This agent does NOT decide final fraud.
It produces a structured cross-modal risk assessment
for the downstream risk engine.

Production principles:
    - Missing agent results are treated as insufficient data.
    - Agent execution failures are never treated as consistency.
    - Agent identity is validated before using its evidence.
    - Additional/unseen damage is not automatically fraud.
    - Partial image/text disagreement is lower-risk than
      explicit contradiction.
    - Sensor anomalies are supporting evidence, not proof of fraud.
    - Unexpected exceptions fail closed as ERROR.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List


MODEL_VERSION = "cross-modal-agent-v1.2"


# ------------------------------------------------------------------
# Canonical TruthChain motor-damage classes
# ------------------------------------------------------------------

CANONICAL_DAMAGE_TYPES = {
    "dent",
    "scratch",
    "crack",
    "glass_shatter",
    "lamp_broken",
    "tire_flat",
}


# ------------------------------------------------------------------
# Agent decisions that indicate execution failure
# ------------------------------------------------------------------

FAILURE_DECISIONS = {
    "ERROR",
    "FAILED",
    "AGENT_ERROR",
    "PROCESSING_ERROR",
    "MODEL_ERROR",
}


# A required upstream agent can also legitimately report that it
# could not collect enough evidence. That is not a successful
# evidence collection state.
INSUFFICIENT_DECISIONS = {
    "INSUFFICIENT_DATA",
    "NEEDS_REVIEW",
    "PENDING",
    "UNKNOWN",
}


EXPECTED_AGENTS = {
    "ImageAgent",
    "SensorAgent",
    "TextAgent",
}


class CrossModalAgent:
    """
    Cross-modal evidence verification agent.

    Compares independently generated outputs from the
    ImageAgent, SensorAgent, and TextAgent.

    It does NOT make the final fraud decision.
    """

    def __init__(self) -> None:
        self.model_version = MODEL_VERSION

    # ==============================================================
    # Utility helpers
    # ==============================================================

    @staticmethod
    def _normalise_damage_types(values: Any) -> set[str]:
        """
        Convert damage-type input into a normalized canonical set.

        Unknown values are ignored rather than being allowed to
        influence cross-modal comparisons.
        """
        if not isinstance(values, list):
            return set()

        normalized: set[str] = set()

        for value in values:
            value_normalized = str(value).strip().lower()

            if value_normalized in CANONICAL_DAMAGE_TYPES:
                normalized.add(value_normalized)

        return normalized

    @staticmethod
    def _normalise_decision(result: Dict[str, Any]) -> str:
        """Return a normalized upstream decision."""
        return str(result.get("decision", "")).strip().upper()

    @classmethod
    def _agent_failed(cls, result: Dict[str, Any]) -> bool:
        """
        Determine whether an agent result represents execution failure.

        A dictionary existing by itself is not sufficient evidence
        that an agent successfully completed its work.
        """
        decision = cls._normalise_decision(result)

        if decision in FAILURE_DECISIONS:
            return True

        status = str(result.get("status", "")).strip().upper()

        if status in FAILURE_DECISIONS:
            return True

        if result.get("error"):
            return True

        return False

    @classmethod
    def _agent_insufficient(cls, result: Dict[str, Any]) -> bool:
        """
        Determine whether an upstream agent completed without enough
        evidence for reliable cross-modal comparison.
        """
        decision = cls._normalise_decision(result)

        return decision in INSUFFICIENT_DECISIONS

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        """Safely convert a value to float."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _validate_agent_result(
        cls,
        result: Any,
        expected_agent: str,
    ) -> tuple[bool, str]:
        """
        Validate an upstream agent result.

        Returns:
            (valid, reason)
        """
        if not isinstance(result, dict):
            return False, f"{expected_agent} result is not a dictionary."

        actual_agent = str(result.get("agent", "")).strip()

        if actual_agent and actual_agent != expected_agent:
            return (
                False,
                f"Expected {expected_agent}, received {actual_agent}.",
            )

        # Missing agent field is tolerated for backwards compatibility,
        # but a completely empty decision is not.
        decision = cls._normalise_decision(result)

        if not decision:
            return (
                False,
                f"{expected_agent} result does not contain a decision.",
            )

        return True, ""

    # ==============================================================
    # Standard result helpers
    # ==============================================================

    def _base_result(
        self,
        *,
        confidence: float,
        risk_score: float,
        decision: str,
        agreement_state: str,
        evidence: List[str],
        contradictions: List[str],
        processing_time_ms: int,
    ) -> Dict[str, Any]:
        """Build the standard CrossModalAgent response."""
        return {
            "agent": "CrossModalAgent",
            "domain": "motor",
            "confidence": float(
                min(0.99, max(0.0, confidence))
            ),
            "risk_score": float(
                min(1.0, max(0.0, risk_score))
            ),
            "decision": decision,
            "agreement_state": agreement_state,
            "evidence": evidence,
            "contradictions": contradictions,
            "model_version": self.model_version,
            "processing_time_ms": processing_time_ms,
        }

    def _insufficient_result(
        self,
        *,
        evidence: List[str],
        missing_agents: List[str] | None = None,
        failed_agents: List[str] | None = None,
        processing_time_ms: int,
    ) -> Dict[str, Any]:
        """Return a fail-closed insufficient-data result."""
        result = self._base_result(
            confidence=0.0,
            risk_score=0.0,
            decision="INSUFFICIENT_DATA",
            agreement_state="INSUFFICIENT_DATA",
            evidence=evidence,
            contradictions=[],
            processing_time_ms=processing_time_ms,
        )

        if missing_agents:
            result["missing_agents"] = missing_agents

        if failed_agents:
            result["failed_agents"] = failed_agents

        return result

    def _error_result(
        self,
        *,
        error: Exception,
        processing_time_ms: int,
    ) -> Dict[str, Any]:
        """Return a structured runtime-error result."""
        return self._base_result(
            confidence=0.0,
            risk_score=0.0,
            decision="ERROR",
            agreement_state="ERROR",
            evidence=[
                "CrossModalAgent failed while comparing upstream evidence."
            ],
            contradictions=[],
            processing_time_ms=processing_time_ms,
        ) | {
            "error_type": type(error).__name__,
            "error": str(error),
        }

    # ==============================================================
    # Image ↔ Text comparison
    # ==============================================================

    def _compare_image_text(
        self,
        image_result: Dict[str, Any],
        text_result: Dict[str, Any],
    ) -> tuple[List[str], List[str], float, str]:
        """
        Compare visual damage detected by ImageAgent against
        damage described by TextAgent.

        Important:
            A difference between image and text is NOT automatically
            treated as fraud. Insurance narratives are often partial,
            and photographs may not expose every damaged component.

        Returns:
            evidence,
            contradictions,
            risk_score,
            agreement_state
        """
        evidence: List[str] = []
        contradictions: List[str] = []

        image_damage = self._normalise_damage_types(
            image_result.get("detected_damage", [])
        )

        text_info = text_result.get("extracted_information", {})

        if not isinstance(text_info, dict):
            text_info = {}

        text_damage = self._normalise_damage_types(
            text_info.get("damage_types", [])
        )

        # ----------------------------------------------------------
        # Neither modality reports damage
        # ----------------------------------------------------------

        if not image_damage and not text_damage:
            evidence.append(
                "Image and text evidence contain no reported vehicle damage."
            )

            return (
                evidence,
                contradictions,
                0.0,
                "NO_DAMAGE_REPORTED",
            )

        # ----------------------------------------------------------
        # Both modalities contain damage information
        # ----------------------------------------------------------

        if image_damage and text_damage:
            overlap = image_damage.intersection(text_damage)

            image_only = image_damage - text_damage
            text_only = text_damage - image_damage

            if overlap:
                evidence.append(
                    "Image and text evidence agree on damage: "
                    + ", ".join(sorted(overlap))
                    + "."
                )

            if image_only:
                evidence.append(
                    "ImageAgent detected additional damage not explicitly "
                    "described in the claim text: "
                    + ", ".join(sorted(image_only))
                    + "."
                )

            if text_only:
                evidence.append(
                    "Claim text describes additional damage not detected "
                    "by ImageAgent: "
                    + ", ".join(sorted(text_only))
                    + "."
                )

            # Strong overlap = consistent evidence.
            if overlap and not image_only and not text_only:
                return (
                    evidence,
                    contradictions,
                    0.0,
                    "CONSISTENT",
                )

            # Partial overlap = partial agreement, not contradiction.
            if overlap and (image_only or text_only):
                return (
                    evidence,
                    contradictions,
                    0.15,
                    "PARTIAL_AGREEMENT",
                )

            # No overlap at all means the two modalities describe
            # completely different damage.
            contradictions.append(
                "ImageAgent and claim text report different damage types "
                "with no overlapping damage category."
            )

            return (
                evidence,
                contradictions,
                0.55,
                "REVIEW_REQUIRED",
            )

        # ----------------------------------------------------------
        # Image detects damage, text has no specific damage
        # ----------------------------------------------------------

        if image_damage and not text_damage:
            evidence.append(
                "ImageAgent detected vehicle damage, but the claim text "
                "does not specify individual damage types."
            )

            return (
                evidence,
                contradictions,
                0.10,
                "PARTIAL_AGREEMENT",
            )

        # ----------------------------------------------------------
        # Text describes damage, image detects none
        # ----------------------------------------------------------

        evidence.append(
            "Claim text describes vehicle damage, but ImageAgent "
            "detected no supported damage category in the supplied image."
        )

        return (
            evidence,
            contradictions,
            0.20,
            "PARTIAL_AGREEMENT",
        )

    # ==============================================================
    # Sensor context comparison
    # ==============================================================

    def _compare_sensor_context(
        self,
        image_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
        text_result: Dict[str, Any],
    ) -> tuple[List[str], List[str], float]:
        """
        Compare sensor anomaly state against incident evidence.

        Sensor anomalies are treated as supporting evidence,
        not direct proof of fraud.
        """
        evidence: List[str] = []
        contradictions: List[str] = []

        sensor_anomaly = bool(
            sensor_result.get("anomaly", False)
        )

        sensor_risk = self._safe_float(
            sensor_result.get("risk_score", 0.0),
            0.0,
        )

        sensor_risk = max(0.0, min(1.0, sensor_risk))

        text_info = text_result.get(
            "extracted_information",
            {},
        )

        if not isinstance(text_info, dict):
            text_info = {}

        incident_type = text_info.get("incident_type")

        image_damage = self._normalise_damage_types(
            image_result.get("detected_damage", [])
        )

        # ----------------------------------------------------------
        # Sensor anomaly
        # ----------------------------------------------------------

        if sensor_anomaly:
            evidence.append(
                "SensorAgent identified an anomalous telemetry pattern."
            )

            if incident_type:
                evidence.append(
                    "Telemetry anomaly is associated with a claim "
                    f"describing a {incident_type}."
                )

            # Cap the cross-modal contribution.
            return (
                evidence,
                contradictions,
                min(0.75, sensor_risk),
            )

        # ----------------------------------------------------------
        # Normal telemetry + visual damage
        # ----------------------------------------------------------

        if image_damage:
            evidence.append(
                "Sensor telemetry is not classified as anomalous while "
                "visual evidence indicates vehicle damage."
            )

            return (
                evidence,
                contradictions,
                0.0,
            )

        # ----------------------------------------------------------
        # Normal telemetry + no image damage
        # ----------------------------------------------------------

        evidence.append(
            "Sensor telemetry is not classified as anomalous."
        )

        return (
            evidence,
            contradictions,
            0.0,
        )

    # ==============================================================
    # Main analysis
    # ==============================================================

    def analyze(
        self,
        image_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
        text_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Analyze the three agent outputs together.

        The function is deliberately fail-closed:
            - missing evidence -> INSUFFICIENT_DATA
            - upstream failure -> INSUFFICIENT_DATA
            - unexpected CrossModal exception -> ERROR
        """
        start_time = time.perf_counter()

        try:
            # ------------------------------------------------------
            # Validate result objects
            # ------------------------------------------------------

            supplied_results = {
                "ImageAgent": image_result,
                "SensorAgent": sensor_result,
                "TextAgent": text_result,
            }

            missing_agents: List[str] = []
            invalid_agents: List[str] = []

            for agent_name, result in supplied_results.items():
                if result is None:
                    missing_agents.append(agent_name)
                    continue

                valid, reason = self._validate_agent_result(
                    result,
                    agent_name,
                )

                if not valid:
                    invalid_agents.append(
                        f"{agent_name}: {reason}"
                    )

            if missing_agents or invalid_agents:
                processing_time_ms = int(
                    (time.perf_counter() - start_time) * 1000
                )

                evidence = []

                if missing_agents:
                    evidence.append(
                        "Missing required agent results: "
                        + ", ".join(missing_agents)
                        + "."
                    )

                if invalid_agents:
                    evidence.append(
                        "Invalid upstream agent results were supplied."
                    )

                result = self._insufficient_result(
                    evidence=evidence,
                    missing_agents=missing_agents or None,
                    processing_time_ms=processing_time_ms,
                )

                if invalid_agents:
                    result["invalid_agents"] = invalid_agents

                return result

            # ------------------------------------------------------
            # Detect upstream execution failures
            # ------------------------------------------------------

            failed_agents: List[str] = []

            for agent_name, result in supplied_results.items():
                if self._agent_failed(result):
                    failed_agents.append(agent_name)

            if failed_agents:
                processing_time_ms = int(
                    (time.perf_counter() - start_time) * 1000
                )

                return self._insufficient_result(
                    evidence=[
                        "One or more upstream agents failed: "
                        + ", ".join(failed_agents)
                        + "."
                    ],
                    failed_agents=failed_agents,
                    processing_time_ms=processing_time_ms,
                )

            # ------------------------------------------------------
            # Detect insufficient upstream evidence
            # ------------------------------------------------------

            insufficient_agents: List[str] = []

            for agent_name, result in supplied_results.items():
                if self._agent_insufficient(result):
                    insufficient_agents.append(agent_name)

            if insufficient_agents:
                processing_time_ms = int(
                    (time.perf_counter() - start_time) * 1000
                )

                return self._insufficient_result(
                    evidence=[
                        "One or more required upstream agents did not "
                        "produce sufficient evidence: "
                        + ", ".join(insufficient_agents)
                        + "."
                    ],
                    missing_agents=insufficient_agents,
                    processing_time_ms=processing_time_ms,
                )

            # ------------------------------------------------------
            # Image ↔ Text
            # ------------------------------------------------------

            (
                image_text_evidence,
                image_text_contradictions,
                image_text_risk,
                agreement_state,
            ) = self._compare_image_text(
                image_result=image_result,
                text_result=text_result,
            )

            evidence: List[str] = []
            contradictions: List[str] = []

            evidence.extend(image_text_evidence)
            contradictions.extend(image_text_contradictions)

            # ------------------------------------------------------
            # Sensor context
            # ------------------------------------------------------

            (
                sensor_evidence,
                sensor_contradictions,
                sensor_context_risk,
            ) = self._compare_sensor_context(
                image_result=image_result,
                sensor_result=sensor_result,
                text_result=text_result,
            )

            evidence.extend(sensor_evidence)
            contradictions.extend(sensor_contradictions)

            # ------------------------------------------------------
            # Overall cross-modal risk
            # ------------------------------------------------------

            contradiction_count = len(contradictions)

            # Genuine contradictions receive additional weight.
            contradiction_risk = min(
                1.0,
                contradiction_count * 0.30,
            )

            risk_score = max(
                image_text_risk,
                sensor_context_risk,
                contradiction_risk,
            )

            risk_score = float(
                min(
                    1.0,
                    max(
                        0.0,
                        risk_score,
                    ),
                )
            )

            # ------------------------------------------------------
            # Decision
            # ------------------------------------------------------

            if contradiction_count >= 2:
                decision = "CONTRADICTORY"

            elif contradiction_count == 1:
                decision = "REVIEW_REQUIRED"

            elif agreement_state == "PARTIAL_AGREEMENT":
                decision = "PARTIAL_AGREEMENT"

            elif agreement_state == "NO_DAMAGE_REPORTED":
                decision = "CONSISTENT"

            else:
                decision = "CONSISTENT"

            # ------------------------------------------------------
            # Confidence
            # ------------------------------------------------------

            if decision == "CONSISTENT":
                confidence = 0.90

            elif decision == "PARTIAL_AGREEMENT":
                confidence = 0.80

            elif decision == "REVIEW_REQUIRED":
                confidence = 0.75

            elif decision == "CONTRADICTORY":
                confidence = 0.85

            else:
                confidence = 0.0

            processing_time_ms = int(
                (time.perf_counter() - start_time) * 1000
            )

            # ------------------------------------------------------
            # Final result
            # ------------------------------------------------------

            result = self._base_result(
                confidence=confidence,
                risk_score=risk_score,
                decision=decision,
                agreement_state=agreement_state,
                evidence=evidence,
                contradictions=contradictions,
                processing_time_ms=processing_time_ms,
            )

            result["modal_results"] = {
                "image_decision": image_result.get("decision"),
                "sensor_decision": sensor_result.get("decision"),
                "text_decision": text_result.get("decision"),
            }

            return result

        except Exception as exc:
            processing_time_ms = int(
                (time.perf_counter() - start_time) * 1000
            )

            return self._error_result(
                error=exc,
                processing_time_ms=processing_time_ms,
            )


# ==============================================================
# Singleton
# ==============================================================

_cross_modal_agent: CrossModalAgent | None = None


def get_cross_modal_agent() -> CrossModalAgent:
    """Return the shared CrossModalAgent instance."""
    global _cross_modal_agent

    if _cross_modal_agent is None:
        _cross_modal_agent = CrossModalAgent()

    return _cross_modal_agent


# ==============================================================
# Convenience function
# ==============================================================

def analyze_cross_modal(
    image_result: Dict[str, Any],
    sensor_result: Dict[str, Any],
    text_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Convenience wrapper for CrossModalAgent."""
    return get_cross_modal_agent().analyze(
        image_result=image_result,
        sensor_result=sensor_result,
        text_result=text_result,
    )


# ==============================================================
# Local test
# ==============================================================

if __name__ == "__main__":
    import json

    image_result = {
        "agent": "ImageAgent",
        "domain": "motor",
        "confidence": 0.9746,
        "risk_score": 0.9746,
        "decision": "DAMAGE_DETECTED",
        "damage_detected": True,
        "detected_damage": [
            "dent",
            "scratch",
            "crack",
            "lamp_broken",
        ],
    }

    sensor_result = {
        "agent": "SensorAgent",
        "domain": "motor",
        "confidence": 0.8492,
        "risk_score": 0.4855,
        "decision": "PASS",
        "anomaly": False,
    }

    text_result = {
        "agent": "TextAgent",
        "domain": "motor",
        "confidence": 0.85,
        "risk_score": 0.30,
        "decision": "CONSISTENT",
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
            "vehicle_mentions": [
                "car",
                "vehicle",
            ],
            "action_mentions": [
                "driving",
                "hit",
            ],
        },
    }

    print("=" * 70)
    print("TRUTHCHAIN CROSS-MODAL AGENT TEST")
    print("=" * 70)

    result = analyze_cross_modal(
        image_result,
        sensor_result,
        text_result,
    )

    print(json.dumps(result, indent=2))

    print()
    print("=" * 70)
    print("FAIL-CLOSED TEST")
    print("=" * 70)

    failed_text = dict(text_result)
    failed_text["decision"] = "ERROR"
    failed_text["error"] = "Simulated TextAgent failure"

    failure_result = analyze_cross_modal(
        image_result,
        sensor_result,
        failed_text,
    )

    print(json.dumps(failure_result, indent=2))

    assert failure_result["decision"] == "INSUFFICIENT_DATA"
    assert failure_result["agreement_state"] == "INSUFFICIENT_DATA"

    print()
    print("CrossModalAgent tests passed.")