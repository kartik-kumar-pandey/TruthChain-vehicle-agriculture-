"""
TruthChain Agriculture - Investigation Agent

Investigation / verification-planning layer for agriculture claims.

This agent does NOT independently determine fraud.

Its purpose is to examine the outputs of the evidence and cross-modal
layers and determine:

    1. What evidence is already available.
    2. What contradictions require investigation.
    3. What additional verification should be performed.
    4. Whether human review should be considered.
    5. Whether the claim can proceed to the risk/consensus layer.

The actual external investigation integrations can be added later for:
    - Weather/IMD verification
    - Field boundary/cadastral verification
    - Additional satellite scenes
    - Claimant/location verification
    - Historical crop evidence
    - Policy/claim records
    - Other authorized external sources

This version is a deterministic investigation planner.

Standardized agent contract:
{
    "agent": "...",
    "domain": "...",
    "confidence": 0.0-1.0,
    "risk_score": 0.0-1.0,
    "decision": "PASS | SUSPICIOUS | INSUFFICIENT_DATA | ERROR",
    "evidence": [...],
    "contradictions": [...],
    "model_version": "...",
    "processing_time_ms": ...
}
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


MODEL_VERSION = "agriculture-investigation-agent-v0.1"
DOMAIN = "agriculture"
AGENT_NAME = "InvestigationAgent"


# ---------------------------------------------------------------------------
# Investigation priority levels
# ---------------------------------------------------------------------------

PRIORITY_HIGH = "HIGH"
PRIORITY_MEDIUM = "MEDIUM"
PRIORITY_LOW = "LOW"


# ---------------------------------------------------------------------------
# Investigation Agent
# ---------------------------------------------------------------------------

class InvestigationAgent:
    """
    Deterministic investigation-planning agent.

    The agent consumes evidence from:
        - TextAgent
        - ImageAgent
        - SatelliteAgent
        - SensorAgent
        - CrossModalAgent

    It creates an auditable investigation plan.

    Important:
        investigation_score is NOT a fraud probability.
        risk_score is NOT a final insurance risk score.

        They represent the amount of additional verification warranted
        by the currently available evidence.
    """

    def __init__(self) -> None:
        self.model_version = MODEL_VERSION
        self.domain = DOMAIN
        self.agent_name = AGENT_NAME

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        cross_modal_result: Optional[Dict[str, Any]] = None,
        text_result: Optional[Dict[str, Any]] = None,
        image_result: Optional[Dict[str, Any]] = None,
        satellite_result: Optional[Dict[str, Any]] = None,
        sensor_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Build an investigation plan from available evidence.

        Parameters
        ----------
        cross_modal_result:
            Output from CrossModalAgent.

        text_result:
            Output from TextAgent.

        image_result:
            Output from ImageAgent.

        satellite_result:
            Output from SatelliteAgent.

        sensor_result:
            Output from SensorAgent.

        Returns
        -------
        dict
            Standardized InvestigationAgent result.
        """

        start_time = time.perf_counter()

        try:
            cross_modal_result = cross_modal_result or {}
            text_result = text_result or {}
            image_result = image_result or {}
            satellite_result = satellite_result or {}
            sensor_result = sensor_result or {}

            evidence: List[str] = []
            contradictions: List[str] = []
            investigation_tasks: List[Dict[str, Any]] = []

            # ----------------------------------------------------------
            # Basic validation
            # ----------------------------------------------------------

            available_modalities = self._available_modalities(
                text_result=text_result,
                image_result=image_result,
                satellite_result=satellite_result,
                sensor_result=sensor_result,
            )

            if not cross_modal_result and not available_modalities:
                return self._error_result(
                    "No evidence was supplied to the InvestigationAgent.",
                    start_time,
                )

            # ----------------------------------------------------------
            # Cross-modal status
            # ----------------------------------------------------------

            cross_modal_decision = cross_modal_result.get(
                "decision"
            )

            agreement_score = self._safe_float(
                cross_modal_result.get(
                    "agreement_score"
                )
            )

            cross_modal_risk = self._safe_float(
                cross_modal_result.get(
                    "risk_score"
                )
            )

            contradiction_count = self._safe_int(
                cross_modal_result.get(
                    "contradiction_count"
                )
            )

            if cross_modal_decision:
                evidence.append(
                    f"Cross-modal decision is '{cross_modal_decision}'."
                )

            if agreement_score is not None:
                evidence.append(
                    f"Cross-modal agreement score is "
                    f"{agreement_score:.3f}."
                )

            if contradiction_count is not None:
                evidence.append(
                    f"Cross-modal contradiction count is "
                    f"{contradiction_count}."
                )

            # ----------------------------------------------------------
            # Identify investigation needs
            # ----------------------------------------------------------

            self._investigate_crop_consistency(
                cross_modal_result=cross_modal_result,
                image_result=image_result,
                satellite_result=satellite_result,
                investigation_tasks=investigation_tasks,
                evidence=evidence,
                contradictions=contradictions,
            )

            self._investigate_environmental_event(
                cross_modal_result=cross_modal_result,
                sensor_result=sensor_result,
                text_result=text_result,
                investigation_tasks=investigation_tasks,
                evidence=evidence,
                contradictions=contradictions,
            )

            self._investigate_satellite_context(
                cross_modal_result=cross_modal_result,
                satellite_result=satellite_result,
                investigation_tasks=investigation_tasks,
                evidence=evidence,
                contradictions=contradictions,
            )

            self._investigate_loss_claim(
                cross_modal_result=cross_modal_result,
                text_result=text_result,
                image_result=image_result,
                satellite_result=satellite_result,
                sensor_result=sensor_result,
                investigation_tasks=investigation_tasks,
                evidence=evidence,
                contradictions=contradictions,
            )

            self._investigate_temporal_context(
                cross_modal_result=cross_modal_result,
                satellite_result=satellite_result,
                sensor_result=sensor_result,
                investigation_tasks=investigation_tasks,
                evidence=evidence,
                contradictions=contradictions,
            )

            self._investigate_missing_evidence(
                cross_modal_result=cross_modal_result,
                text_result=text_result,
                image_result=image_result,
                satellite_result=satellite_result,
                sensor_result=sensor_result,
                investigation_tasks=investigation_tasks,
                evidence=evidence,
                contradictions=contradictions,
            )

            # ----------------------------------------------------------
            # Determine investigation priority
            # ----------------------------------------------------------

            priority = self._calculate_priority(
                cross_modal_decision=cross_modal_decision,
                agreement_score=agreement_score,
                contradiction_count=contradiction_count,
                task_count=len(investigation_tasks),
            )

            evidence.append(
                f"Investigation priority is '{priority}'."
            )

            # ----------------------------------------------------------
            # Determine investigation decision
            # ----------------------------------------------------------

            if cross_modal_decision == "SUSPICIOUS":
                decision = "SUSPICIOUS"

            elif contradiction_count is not None and contradiction_count > 0:
                decision = "SUSPICIOUS"

            elif not available_modalities:
                decision = "INSUFFICIENT_DATA"

            elif priority == PRIORITY_HIGH:
                decision = "SUSPICIOUS"

            elif priority == PRIORITY_MEDIUM:
                decision = "INSUFFICIENT_DATA"

            else:
                decision = "PASS"

            # ----------------------------------------------------------
            # Investigation score
            # ----------------------------------------------------------

            investigation_score = self._calculate_investigation_score(
                cross_modal_decision=cross_modal_decision,
                agreement_score=agreement_score,
                contradiction_count=contradiction_count,
                task_count=len(investigation_tasks),
                available_modalities=len(available_modalities),
            )

            # This is additional-verification need, not fraud probability.
            risk_score = investigation_score

            confidence = self._calculate_confidence(
                available_modalities=len(available_modalities),
                task_count=len(investigation_tasks),
                contradiction_count=contradiction_count,
                agreement_score=agreement_score,
            )

            # ----------------------------------------------------------
            # Human review recommendation
            # ----------------------------------------------------------

            human_review_recommended = self._human_review_recommendation(
                decision=decision,
                priority=priority,
                investigation_tasks=investigation_tasks,
            )

            if human_review_recommended:
                evidence.append(
                    "Human review is recommended before final claim "
                    "resolution."
                )

            # ----------------------------------------------------------
            # Processing time
            # ----------------------------------------------------------

            processing_time_ms = round(
                (time.perf_counter() - start_time) * 1000,
                3,
            )

            return {
                "agent": self.agent_name,
                "domain": self.domain,
                "confidence": round(confidence, 6),
                "risk_score": round(risk_score, 6),
                "decision": decision,
                "evidence": evidence,
                "contradictions": contradictions,
                "model_version": self.model_version,
                "processing_time_ms": processing_time_ms,

                # Investigation information.
                "investigation_score": round(
                    investigation_score,
                    6,
                ),
                "investigation_priority": priority,
                "investigation_tasks": investigation_tasks,
                "available_modalities": available_modalities,
                "human_review_recommended": human_review_recommended,

                # Context passed downstream.
                "claimed_crop": cross_modal_result.get(
                    "claimed_crop"
                ),
                "claimed_event": cross_modal_result.get(
                    "claimed_event"
                ),
                "claimed_loss_percent": cross_modal_result.get(
                    "claimed_loss_percent"
                ),
                "event_date": cross_modal_result.get(
                    "event_date"
                ),
                "location": cross_modal_result.get(
                    "location"
                ),

                # Semantic clarification.
                "risk_score_meaning": (
                    "additional_verification_need"
                ),
                "agent_version": MODEL_VERSION,
            }

        except Exception as exc:
            return self._error_result(
                str(exc),
                start_time,
            )

    # ------------------------------------------------------------------
    # Crop investigation
    # ------------------------------------------------------------------

    def _investigate_crop_consistency(
        self,
        cross_modal_result: Dict[str, Any],
        image_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
        investigation_tasks: List[Dict[str, Any]],
        evidence: List[str],
        contradictions: List[str],
    ) -> None:

        crop_check = self._find_check(
            cross_modal_result,
            "crop_consistency",
        )

        if not crop_check:
            return

        status = crop_check.get("status")

        if status == "PASS":
            evidence.append(
                "Image and satellite crop evidence are currently "
                "consistent with the normalized claim crop."
            )

            return

        if status == "CONTRADICTION":
            contradictions.extend(
                crop_check.get(
                    "contradictions",
                    [],
                )
            )

            investigation_tasks.append(
                {
                    "task_id": "CROP-001",
                    "priority": PRIORITY_HIGH,
                    "type": "crop_verification",
                    "description": (
                        "Verify the claimed crop against additional "
                        "field imagery and/or additional satellite "
                        "observations near the claim event period."
                    ),
                    "sources": [
                        "additional_satellite_scene",
                        "additional_field_image",
                    ],
                    "reason": (
                        "Cross-modal crop evidence contains a "
                        "contradiction."
                    ),
                }
            )

    # ------------------------------------------------------------------
    # Environmental event investigation
    # ------------------------------------------------------------------

    def _investigate_environmental_event(
        self,
        cross_modal_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
        text_result: Dict[str, Any],
        investigation_tasks: List[Dict[str, Any]],
        evidence: List[str],
        contradictions: List[str],
    ) -> None:

        event_check = self._find_check(
            cross_modal_result,
            "event_consistency",
        )

        if not event_check:
            return

        status = event_check.get("status")

        if status == "PASS":
            evidence.append(
                "Narrative and environmental evidence currently "
                "support the claimed event."
            )
            return

        if status == "CONTRADICTION":
            contradictions.extend(
                event_check.get(
                    "contradictions",
                    [],
                )
            )

            investigation_tasks.append(
                {
                    "task_id": "EVENT-001",
                    "priority": PRIORITY_HIGH,
                    "type": "environmental_event_verification",
                    "description": (
                        "Verify the claimed environmental event using "
                        "independent weather/environmental observations "
                        "for the relevant field and event period."
                    ),
                    "sources": [
                        "weather_station",
                        "authorized_weather_api",
                        "rainfall_records",
                    ],
                    "reason": (
                        "Claimed event is inconsistent with available "
                        "environmental evidence."
                    ),
                }
            )

    # ------------------------------------------------------------------
    # Satellite investigation
    # ------------------------------------------------------------------

    def _investigate_satellite_context(
        self,
        cross_modal_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
        investigation_tasks: List[Dict[str, Any]],
        evidence: List[str],
        contradictions: List[str],
    ) -> None:

        if not satellite_result:
            investigation_tasks.append(
                {
                    "task_id": "SAT-001",
                    "priority": PRIORITY_MEDIUM,
                    "type": "satellite_verification",
                    "description": (
                        "Obtain a suitable satellite observation for "
                        "the claim field and event period."
                    ),
                    "sources": [
                        "authorized_stac_catalog",
                    ],
                    "reason": (
                        "No satellite evidence was supplied."
                    ),
                }
            )
            return

        scene_id = satellite_result.get(
            "scene_id"
        )

        scene_datetime = satellite_result.get(
            "scene_datetime"
        )

        evidence_decision = satellite_result.get(
            "evidence_decision"
        )

        if scene_id:
            evidence.append(
                f"Satellite scene '{scene_id}' is available for "
                "investigation."
            )

        if scene_datetime:
            evidence.append(
                f"Satellite scene acquisition time is "
                f"'{scene_datetime}'."
            )

        if evidence_decision == "CONTRADICTION":
            investigation_tasks.append(
                {
                    "task_id": "SAT-002",
                    "priority": PRIORITY_HIGH,
                    "type": "satellite_reverification",
                    "description": (
                        "Review additional satellite scenes before "
                        "drawing conclusions from the contradictory "
                        "crop evidence."
                    ),
                    "sources": [
                        "authorized_stac_catalog",
                        "additional_satellite_scene",
                    ],
                    "reason": (
                        "Current satellite evidence contradicts the "
                        "claimed crop/event context."
                    ),
                }
            )

    # ------------------------------------------------------------------
    # Loss investigation
    # ------------------------------------------------------------------

    def _investigate_loss_claim(
        self,
        cross_modal_result: Dict[str, Any],
        text_result: Dict[str, Any],
        image_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
        investigation_tasks: List[Dict[str, Any]],
        evidence: List[str],
        contradictions: List[str],
    ) -> None:

        claimed_loss = cross_modal_result.get(
            "claimed_loss_percent"
        )

        if claimed_loss is None:
            investigation_tasks.append(
                {
                    "task_id": "LOSS-001",
                    "priority": PRIORITY_MEDIUM,
                    "type": "loss_quantification",
                    "description": (
                        "Obtain or calculate an independently supported "
                        "estimate of crop damage/loss before final "
                        "claim resolution."
                    ),
                    "sources": [
                        "field_damage_assessment",
                        "validated_damage_model",
                        "additional_imagery",
                    ],
                    "reason": (
                        "No explicit quantified loss claim was "
                        "available."
                    ),
                }
            )
            return

        evidence.append(
            f"Claimed crop loss is {float(claimed_loss):.2f}%."
        )

        # IMPORTANT:
        # Do not derive crop loss from model confidence.
        #
        # Current ImageAgent and SatelliteAgent predict crop identity,
        # not validated percentage crop damage.
        #
        # Therefore any loss percentage must remain a claim until a
        # dedicated damage-estimation source is available.

        investigation_tasks.append(
            {
                "task_id": "LOSS-002",
                "priority": PRIORITY_MEDIUM,
                "type": "loss_quantification",
                "description": (
                    "Independently validate the claimed crop-loss "
                    "percentage using a dedicated damage assessment "
                    "source."
                ),
                "sources": [
                    "field_damage_assessment",
                    "validated_damage_model",
                    "multi_temporal_satellite_imagery",
                ],
                "reason": (
                    "Current crop-classification evidence does not "
                    "measure percentage crop loss."
                ),
                "claimed_loss_percent": float(
                    claimed_loss
                ),
            }
        )

    # ------------------------------------------------------------------
    # Temporal investigation
    # ------------------------------------------------------------------

    def _investigate_temporal_context(
        self,
        cross_modal_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
        investigation_tasks: List[Dict[str, Any]],
        evidence: List[str],
        contradictions: List[str],
    ) -> None:

        event_date = cross_modal_result.get(
            "event_date"
        )

        if not event_date:
            investigation_tasks.append(
                {
                    "task_id": "TIME-001",
                    "priority": PRIORITY_MEDIUM,
                    "type": "event_date_verification",
                    "description": (
                        "Verify the claim event date before using "
                        "temporal evidence for final resolution."
                    ),
                    "sources": [
                        "claim_record",
                        "weather_records",
                        "satellite_acquisition_metadata",
                    ],
                    "reason": (
                        "No normalized claim event date was available."
                    ),
                }
            )
            return

        satellite_datetime = satellite_result.get(
            "scene_datetime"
        )

        sensor_date = sensor_result.get(
            "event_date"
        )

        if satellite_datetime:
            satellite_date = str(
                satellite_datetime
            )[:10]

            if satellite_date != str(event_date)[:10]:
                contradictions.append(
                    f"Satellite scene date '{satellite_date}' "
                    f"does not match claim event date "
                    f"'{event_date}'."
                )

                investigation_tasks.append(
                    {
                        "task_id": "TIME-002",
                        "priority": PRIORITY_HIGH,
                        "type": "temporal_satellite_verification",
                        "description": (
                            "Obtain satellite observations closer to "
                            "the actual claimed event date."
                        ),
                        "sources": [
                            "authorized_stac_catalog",
                        ],
                        "reason": (
                            "Current satellite acquisition date does "
                            "not match the claim event date."
                        ),
                    }
                )

        if sensor_date:
            if str(sensor_date)[:10] != str(event_date)[:10]:
                contradictions.append(
                    f"Sensor evidence date '{sensor_date}' "
                    f"does not match claim event date "
                    f"'{event_date}'."
                )

                investigation_tasks.append(
                    {
                        "task_id": "TIME-003",
                        "priority": PRIORITY_HIGH,
                        "type": "temporal_sensor_verification",
                        "description": (
                            "Verify environmental observations for "
                            "the actual claimed event date."
                        ),
                        "sources": [
                            "weather_station",
                            "authorized_weather_api",
                        ],
                        "reason": (
                            "Sensor evidence date does not match "
                            "the claim event date."
                        ),
                    }
                )

    # ------------------------------------------------------------------
    # Missing evidence
    # ------------------------------------------------------------------

    def _investigate_missing_evidence(
        self,
        cross_modal_result: Dict[str, Any],
        text_result: Dict[str, Any],
        image_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
        investigation_tasks: List[Dict[str, Any]],
        evidence: List[str],
        contradictions: List[str],
    ) -> None:

        expected = {
            "TextAgent": text_result,
            "ImageAgent": image_result,
            "SatelliteAgent": satellite_result,
            "SensorAgent": sensor_result,
        }

        missing = [
            name
            for name, result in expected.items()
            if not result
        ]

        if missing:
            evidence.append(
                "Missing evidence modalities: "
                + ", ".join(missing)
                + "."
            )

            investigation_tasks.append(
                {
                    "task_id": "DATA-001",
                    "priority": PRIORITY_MEDIUM,
                    "type": "evidence_completion",
                    "description": (
                        "Obtain the missing evidence modalities before "
                        "making a final automated determination."
                    ),
                    "sources": missing,
                    "reason": (
                        "Cross-modal analysis has incomplete evidence."
                    ),
                }
            )

    # ------------------------------------------------------------------
    # Priority
    # ------------------------------------------------------------------

    def _calculate_priority(
        self,
        cross_modal_decision: Optional[str],
        agreement_score: Optional[float],
        contradiction_count: Optional[int],
        task_count: int,
    ) -> str:

        if (
            cross_modal_decision == "SUSPICIOUS"
            or (
                contradiction_count is not None
                and contradiction_count > 0
            )
        ):
            return PRIORITY_HIGH

        if (
            agreement_score is not None
            and agreement_score < 0.60
        ):
            return PRIORITY_HIGH

        if task_count >= 3:
            return PRIORITY_MEDIUM

        if task_count > 0:
            return PRIORITY_LOW

        return PRIORITY_LOW

    # ------------------------------------------------------------------
    # Investigation score
    # ------------------------------------------------------------------

    def _calculate_investigation_score(
        self,
        cross_modal_decision: Optional[str],
        agreement_score: Optional[float],
        contradiction_count: Optional[int],
        task_count: int,
        available_modalities: int,
    ) -> float:

        score = 0.0

        if cross_modal_decision == "SUSPICIOUS":
            score += 0.40

        if contradiction_count:
            score += min(
                contradiction_count * 0.20,
                0.60,
            )

        if agreement_score is not None:
            score += (
                max(0.0, 1.0 - agreement_score)
                * 0.30
            )

        if task_count:
            score += min(
                task_count * 0.05,
                0.25,
            )

        if available_modalities < 4:
            score += (
                4 - available_modalities
            ) * 0.05

        return max(
            0.0,
            min(1.0, score),
        )

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self,
        available_modalities: int,
        task_count: int,
        contradiction_count: Optional[int],
        agreement_score: Optional[float],
    ) -> float:

        coverage = min(
            available_modalities / 4.0,
            1.0,
        )

        agreement = (
            agreement_score
            if agreement_score is not None
            else 0.0
        )

        contradiction_penalty = min(
            (contradiction_count or 0) * 0.15,
            0.60,
        )

        # Investigation confidence means confidence in the assessment
        # of what verification is needed, not confidence in fraud.
        confidence = (
            0.45 * coverage
            + 0.45 * agreement
            + 0.10 * min(task_count / 5.0, 1.0)
            - contradiction_penalty
        )

        return max(
            0.0,
            min(1.0, confidence),
        )

    # ------------------------------------------------------------------
    # Human review
    # ------------------------------------------------------------------

    def _human_review_recommendation(
        self,
        decision: str,
        priority: str,
        investigation_tasks: List[Dict[str, Any]],
    ) -> bool:

        if decision == "SUSPICIOUS":
            return True

        if priority == PRIORITY_HIGH:
            return True

        high_priority_tasks = sum(
            1
            for task in investigation_tasks
            if task.get("priority") == PRIORITY_HIGH
        )

        return high_priority_tasks > 0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _available_modalities(
        text_result: Dict[str, Any],
        image_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
    ) -> List[str]:

        results = [
            ("TextAgent", text_result),
            ("ImageAgent", image_result),
            ("SatelliteAgent", satellite_result),
            ("SensorAgent", sensor_result),
        ]

        available = []

        for name, result in results:
            if not result:
                continue

            if result.get("decision") == "ERROR":
                continue

            available.append(name)

        return available

    @staticmethod
    def _find_check(
        cross_modal_result: Dict[str, Any],
        name: str,
    ) -> Optional[Dict[str, Any]]:

        checks = cross_modal_result.get(
            "cross_modal_checks",
            [],
        )

        if not isinstance(checks, list):
            return None

        for check in checks:
            if check.get("name") == name:
                return check

        return None

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> Optional[float]:

        if value is None:
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(
        value: Any,
    ) -> Optional[int]:

        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Error result
    # ------------------------------------------------------------------

    def _error_result(
        self,
        message: str,
        start_time: float,
    ) -> Dict[str, Any]:

        processing_time_ms = round(
            (time.perf_counter() - start_time) * 1000,
            3,
        )

        return {
            "agent": self.agent_name,
            "domain": self.domain,
            "confidence": 0.0,
            "risk_score": 1.0,
            "decision": "ERROR",
            "evidence": [],
            "contradictions": [message],
            "model_version": self.model_version,
            "processing_time_ms": processing_time_ms,
            "investigation_score": 1.0,
            "investigation_priority": PRIORITY_HIGH,
            "investigation_tasks": [],
            "available_modalities": [],
            "human_review_recommended": True,
            "claimed_crop": None,
            "claimed_event": None,
            "claimed_loss_percent": None,
            "event_date": None,
            "location": None,
            "risk_score_meaning": "additional_verification_need",
            "agent_version": MODEL_VERSION,
        }


# ---------------------------------------------------------------------------
# Singleton / convenience API
# ---------------------------------------------------------------------------

_investigation_agent: Optional[InvestigationAgent] = None


def get_investigation_agent() -> InvestigationAgent:
    global _investigation_agent

    if _investigation_agent is None:
        _investigation_agent = InvestigationAgent()

    return _investigation_agent


def analyze_investigation(
    cross_modal_result: Optional[Dict[str, Any]] = None,
    text_result: Optional[Dict[str, Any]] = None,
    image_result: Optional[Dict[str, Any]] = None,
    satellite_result: Optional[Dict[str, Any]] = None,
    sensor_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    return get_investigation_agent().analyze(
        cross_modal_result=cross_modal_result,
        text_result=text_result,
        image_result=image_result,
        satellite_result=satellite_result,
        sensor_result=sensor_result,
    )


# ---------------------------------------------------------------------------
# Local test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    print("=" * 72)
    print("TRUTHCHAIN AGRICULTURE INVESTIGATION AGENT TEST")
    print("=" * 72)

    # Representative successful CrossModal result.
    # These values correspond to the contract already tested by
    # CrossModalAgent.

    cross_modal_result = {
        "agent": "CrossModalAgent",
        "domain": "agriculture",
        "confidence": 0.960714,
        "risk_score": 0.025,
        "decision": "PASS",
        "evidence": [
            "ImageAgent crop evidence matches claimed crop 'Wheat'.",
            "SatelliteAgent crop evidence matches claimed crop 'Wheat'.",
            "Environmental/narrative evidence supports claimed event "
            "'Heavy rain'.",
        ],
        "contradictions": [],
        "model_version": "agriculture-cross-modal-agent-v0.1",
        "processing_time_ms": 1.0,
        "claimed_crop": "Wheat",
        "claimed_event": "Heavy rain",
        "claimed_loss_percent": 65.0,
        "event_date": "2026-09-17",
        "location": "Rampur",
        "agreement_score": 0.928571,
        "contradiction_count": 0,
        "cross_modal_checks": [
            {
                "name": "crop_consistency",
                "status": "PASS",
                "score": 1.0,
                "evidence": [
                    "ImageAgent crop evidence matches claimed crop "
                    "'Wheat'.",
                    "SatelliteAgent crop evidence matches claimed crop "
                    "'Wheat'.",
                ],
                "contradictions": [],
            },
            {
                "name": "event_consistency",
                "status": "PASS",
                "score": 1.0,
                "evidence": [
                    "Environmental/narrative evidence supports claimed "
                    "event 'Heavy rain'.",
                ],
                "contradictions": [],
            },
            {
                "name": "loss_consistency",
                "status": "PASS",
                "score": 0.5,
                "evidence": [
                    "Claimed crop loss is 65.00%; available evidence "
                    "modalities for contextual review: ImageAgent, "
                    "SatelliteAgent, SensorAgent.",
                ],
                "contradictions": [],
            },
            {
                "name": "context_consistency",
                "status": "PASS",
                "score": 1.0,
                "evidence": [
                    "Satellite scene acquisition date matches the "
                    "claim event date.",
                    "Sensor evidence date matches the claim event date.",
                ],
                "contradictions": [],
            },
            {
                "name": "modality_health",
                "status": "PASS",
                "score": 1.0,
                "evidence": [],
                "contradictions": [],
            },
        ],
    }

    text_result = {
        "agent": "TextAgent",
        "decision": "PASS",
        "event_date": "2026-09-17",
        "location": "Rampur",
        "extracted_crop": "Wheat",
        "claimed_loss_percent": 65.0,
        "damage_types": [
            "Heavy rain",
            "Waterlogging",
        ],
    }

    image_result = {
        "agent": "ImageAgent",
        "decision": "PASS",
        "predicted_crop": "Wheat",
        "claimed_crop": "Wheat",
    }

    satellite_result = {
        "agent": "SatelliteAgent",
        "decision": "PASS",
        "predicted_crop": "Wheat",
        "claimed_crop": "Wheat",
        "evidence_decision": "SUPPORT",
        "scene_id": (
            "S2C_MSIL2A_20260917T051651_N0512_R062_"
            "T44RMQ_20260917T101515"
        ),
        "scene_datetime": "2026-09-17T05:16:51.025000Z",
    }

    sensor_result = {
        "agent": "SensorAgent",
        "decision": "PASS",
        "claimed_event": "Heavy rain",
        "detected_events": [
            "Heavy rain",
            "Waterlogging",
        ],
        "event_date": "2026-09-17",
        "location": "Rampur",
    }

    print("\nINVESTIGATION INPUT")
    print("-" * 72)

    print(
        json.dumps(
            {
                "cross_modal": cross_modal_result,
                "text": text_result,
                "image": image_result,
                "satellite": satellite_result,
                "sensor": sensor_result,
            },
            indent=2,
        )
    )

    result = analyze_investigation(
        cross_modal_result=cross_modal_result,
        text_result=text_result,
        image_result=image_result,
        satellite_result=satellite_result,
        sensor_result=sensor_result,
    )

    print("\nINVESTIGATION RESULT")
    print("-" * 72)

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )

    print("-" * 72)

    if result["decision"] != "ERROR":
        print("INVESTIGATION AGENT TEST: PASS")
    else:
        print("INVESTIGATION AGENT TEST: FAIL")