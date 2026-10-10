"""
TruthChain Agriculture - Investigation Agent (LLM-Powered)

Deep fraud investigation layer for agriculture claims.

Uses Groq LLM (openai/gpt-oss-120b) for deep investigation reasoning,
exactly mirroring the motor pipeline's LLM agent architecture.

Its purpose is to:
    1. Examine outputs from all evidence agents.
    2. Use LLM to reason about fraud indicators and field visit priority.
    3. Generate fraud_indicators[], field_visit_priority, and investigation_narrative.
    4. Produce structured investigation result for downstream risk/consensus.

This agent does NOT independently determine fraud.

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

import json
import os
import time
from typing import Any, Dict, List, Optional

import config  # noqa: F401
from groq import Groq


MODEL_VERSION = "agriculture-investigation-agent-llm-v1.0"
DOMAIN = "agriculture"
AGENT_NAME = "InvestigationAgent"

GROQ_MODEL = "openai/gpt-oss-120b"
REASONING_EFFORT = "default"
MAX_COMPLETION_TOKENS = 2000


# ---------------------------------------------------------------------------
# Investigation priority levels
# ---------------------------------------------------------------------------

PRIORITY_HIGH = "HIGH"
PRIORITY_MEDIUM = "MEDIUM"
PRIORITY_LOW = "LOW"


# ---------------------------------------------------------------------------
# System prompt for Groq LLM investigation
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are the deep investigation component of an agriculture insurance claim
verification system.

You receive structured outputs from all evidence verification agents:
  - TextAgent: extracted claim information from narrative
  - ImageAgent: crop image analysis (CNN classification)
  - SatelliteAgent: Sentinel-2 satellite evidence (NDVI, CropAgent v0.2)
  - SensorAgent: weather/soil sensor analysis
  - CrossModalAgent: cross-modal consistency assessment

Your task is to:
1. Analyze all evidence for potential fraud indicators.
2. Identify specific red flags in the evidence chain.
3. Determine field visit priority based on evidence quality.
4. Recommend specific verification actions.
5. Output a structured JSON investigation report.

Do NOT:
- Make a final insurance fraud determination
- Recommend claim approval or denial
- Invent information not present in the inputs

Return ONLY valid JSON with exactly these fields:

{
  "investigation_score": number (0.0-1.0, higher = more investigation needed),
  "field_visit_priority": "HIGH" | "MEDIUM" | "LOW",
  "fraud_indicators": [string],
  "supporting_factors": [string],
  "verification_actions": [string],
  "satellite_consistency": "CONSISTENT" | "INCONSISTENT" | "UNAVAILABLE",
  "crop_fraud_risk": "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN",
  "event_fraud_risk": "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN",
  "decision": "PASS" | "SUSPICIOUS" | "INSUFFICIENT_DATA",
  "human_review_recommended": boolean,
  "investigation_narrative": string
}

Decision rules:
- PASS: No significant fraud indicators, evidence is consistent
- SUSPICIOUS: One or more fraud indicators detected
- INSUFFICIENT_DATA: Too few modalities or evidence to make determination

investigation_score: 0.0-0.3 = low investigation need, 0.3-0.6 = moderate, 0.6-1.0 = high

Field visit priority:
- HIGH: Significant contradictions, high claimed loss, suspicious patterns
- MEDIUM: Some evidence gaps or moderate risk signals
- LOW: Consistent evidence, low risk signals
"""


# ---------------------------------------------------------------------------
# Investigation Agent (LLM-Powered)
# ---------------------------------------------------------------------------

class InvestigationAgent:
    """
    LLM-powered deep investigation agent for agriculture claims.

    Uses Groq LLM (openai/gpt-oss-120b) to reason over all evidence
    and generate fraud indicators, field visit priority, and investigation
    narrative.

    This matches the motor pipeline's InvestigationAgent architecture.
    """

    def __init__(
        self,
        client: Optional[Groq] = None,
        model: str = GROQ_MODEL,
    ) -> None:
        self.model_version = MODEL_VERSION
        self.domain = DOMAIN
        self.agent_name = AGENT_NAME
        self.model = model

        if client is not None:
            self.client = client
        elif os.getenv("GROQ_API_KEY"):
            try:
                self.client = Groq()
            except Exception:
                self.client = None
        else:
            self.client = None

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
        Build an LLM-powered investigation report from available evidence.

        Parameters
        ----------
        cross_modal_result:
            Output from CrossModalAgent (LLM fusion result).

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
            # Build investigation context for LLM
            # ----------------------------------------------------------

            investigation_context = self._build_investigation_context(
                cross_modal_result=cross_modal_result,
                text_result=text_result,
                image_result=image_result,
                satellite_result=satellite_result,
                sensor_result=sensor_result,
                available_modalities=available_modalities,
            )

            # ----------------------------------------------------------
            # LLM deep investigation
            # ----------------------------------------------------------

            llm_result = self._llm_investigate(investigation_context)

            # ----------------------------------------------------------
            # Extract validated LLM output
            # ----------------------------------------------------------

            investigation_score = float(
                llm_result.get("investigation_score", 0.5)
            )
            investigation_score = max(0.0, min(1.0, investigation_score))

            priority = str(
                llm_result.get("field_visit_priority", PRIORITY_MEDIUM)
            ).upper()
            if priority not in {PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW}:
                priority = PRIORITY_MEDIUM

            fraud_indicators: List[str] = [
                str(f) for f in llm_result.get("fraud_indicators", [])
                if f and str(f).strip()
            ]

            supporting_factors: List[str] = [
                str(f) for f in llm_result.get("supporting_factors", [])
                if f and str(f).strip()
            ]

            verification_actions: List[str] = [
                str(a) for a in llm_result.get("verification_actions", [])
                if a and str(a).strip()
            ]

            decision = str(
                llm_result.get("decision", "INSUFFICIENT_DATA")
            ).upper()
            if decision not in {"PASS", "SUSPICIOUS", "INSUFFICIENT_DATA"}:
                decision = "INSUFFICIENT_DATA"

            human_review_recommended = bool(
                llm_result.get("human_review_recommended", False)
            )

            investigation_narrative = str(
                llm_result.get("investigation_narrative", "")
            ).strip()

            satellite_consistency = str(
                llm_result.get("satellite_consistency", "UNAVAILABLE")
            ).upper()

            crop_fraud_risk = str(
                llm_result.get("crop_fraud_risk", "UNKNOWN")
            ).upper()

            event_fraud_risk = str(
                llm_result.get("event_fraud_risk", "UNKNOWN")
            ).upper()

            # ----------------------------------------------------------
            # Build evidence and contradictions lists
            # ----------------------------------------------------------

            evidence: List[str] = []
            contradictions: List[str] = list(fraud_indicators)

            cross_modal_decision = cross_modal_result.get("decision")
            if cross_modal_decision:
                evidence.append(
                    f"Cross-modal LLM decision: '{cross_modal_decision}'."
                )

            cross_modal_score = cross_modal_result.get("cross_modal_score")
            if cross_modal_score is not None:
                evidence.append(
                    f"Cross-modal inconsistency score: {cross_modal_score:.3f}."
                )

            llm_contradictions = cross_modal_result.get("contradictions", [])
            if llm_contradictions:
                evidence.append(
                    f"CrossModal contradictions: {'; '.join(str(c) for c in llm_contradictions[:3])}."
                )

            evidence.extend(supporting_factors)

            evidence.append(
                f"LLM investigation priority: '{priority}'."
            )
            evidence.append(
                f"LLM investigation score: {investigation_score:.3f}."
            )
            evidence.append(
                f"Fraud indicators identified: {len(fraud_indicators)}."
            )

            if investigation_narrative:
                evidence.append(
                    f"Investigation narrative: {investigation_narrative}"
                )

            if human_review_recommended:
                evidence.append(
                    "Human review is recommended before final claim resolution."
                )

            evidence.append(
                "Evidence modalities available: "
                + ", ".join(available_modalities)
                + f" ({len(available_modalities)})."
            )

            # ----------------------------------------------------------
            # Confidence
            # ----------------------------------------------------------

            confidence = self._calculate_confidence(
                investigation_score=investigation_score,
                available_modality_count=len(available_modalities),
                fraud_indicator_count=len(fraud_indicators),
            )

            processing_time_ms = round(
                (time.perf_counter() - start_time) * 1000,
                3,
            )

            return {
                "agent": self.agent_name,
                "domain": self.domain,
                "confidence": round(confidence, 6),
                "risk_score": round(investigation_score, 6),
                "decision": decision,
                "evidence": evidence,
                "contradictions": contradictions,
                "model_version": self.model_version,
                "processing_time_ms": processing_time_ms,

                # Investigation-specific fields.
                "investigation_score": round(investigation_score, 6),
                "investigation_priority": priority,
                "field_visit_priority": priority,
                "fraud_indicators": fraud_indicators,
                "verification_actions": verification_actions,
                "investigation_tasks": [
                    {"action": a, "priority": priority}
                    for a in verification_actions
                ],
                "available_modalities": available_modalities,
                "human_review_recommended": human_review_recommended,
                "investigation_narrative": investigation_narrative,
                "satellite_consistency": satellite_consistency,
                "crop_fraud_risk": crop_fraud_risk,
                "event_fraud_risk": event_fraud_risk,

                # Context passed downstream.
                "claimed_crop": cross_modal_result.get("claimed_crop"),
                "claimed_event": cross_modal_result.get("claimed_event"),
                "claimed_loss_percent": cross_modal_result.get("claimed_loss_percent"),
                "event_date": cross_modal_result.get("event_date"),
                "location": cross_modal_result.get("location"),

                # LLM audit information.
                "llm_provider": "groq",
                "llm_model": self.model,

                # Semantic clarification.
                "risk_score_meaning": "additional_verification_need",
                "agent_version": MODEL_VERSION,
            }

        except Exception as exc:
            return self._error_result(
                str(exc),
                start_time,
            )

    # ------------------------------------------------------------------
    # Investigation context builder
    # ------------------------------------------------------------------

    def _build_investigation_context(
        self,
        cross_modal_result: Dict[str, Any],
        text_result: Dict[str, Any],
        image_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
        available_modalities: List[str],
    ) -> str:
        """Build structured context for LLM investigation."""

        lines = []

        lines.append("=== CLAIM OVERVIEW (from CrossModalAgent LLM) ===")
        lines.append(f"Claimed crop: {cross_modal_result.get('claimed_crop', 'N/A')}")
        lines.append(f"Claimed event: {cross_modal_result.get('claimed_event', 'N/A')}")
        lines.append(f"Claimed loss: {cross_modal_result.get('claimed_loss_percent', 'N/A')}%")
        lines.append(f"Location: {cross_modal_result.get('location', 'N/A')}")
        lines.append(f"Event date: {cross_modal_result.get('event_date', 'N/A')}")
        lines.append(f"Cross-modal decision: {cross_modal_result.get('decision', 'N/A')}")
        lines.append(f"Cross-modal inconsistency score: {cross_modal_result.get('cross_modal_score', 'N/A')}")
        lines.append(f"Agreement level: {cross_modal_result.get('agreement_level', 'N/A')}")
        lines.append(f"Contradiction count: {cross_modal_result.get('contradiction_count', 0)}")

        llm_contradictions = cross_modal_result.get("contradictions", [])
        if llm_contradictions:
            lines.append(f"Cross-modal contradictions:")
            for c in llm_contradictions[:5]:
                lines.append(f"  - {c}")

        llm_reasoning = cross_modal_result.get("llm_reasoning", "")
        if llm_reasoning:
            lines.append(f"Cross-modal LLM reasoning: {llm_reasoning}")

        crop_consistency = cross_modal_result.get("crop_consistency", {})
        if isinstance(crop_consistency, dict):
            lines.append(f"Crop consistency: {crop_consistency.get('status', 'N/A')}")
            lines.append(f"  Image detected: {crop_consistency.get('image_detected', 'N/A')}")
            lines.append(f"  Satellite detected: {crop_consistency.get('satellite_detected', 'N/A')}")
            expl = crop_consistency.get("explanation", "")
            if expl:
                lines.append(f"  Explanation: {expl}")

        event_consistency = cross_modal_result.get("event_consistency", {})
        if isinstance(event_consistency, dict):
            lines.append(f"Event consistency: {event_consistency.get('status', 'N/A')}")
            expl = event_consistency.get("explanation", "")
            if expl:
                lines.append(f"  Explanation: {expl}")

        lines.append("\n=== TEXT AGENT ===")
        if text_result:
            lines.append(f"Decision: {text_result.get('decision', 'N/A')}")
            lines.append(f"Extracted crop: {text_result.get('extracted_crop', 'N/A')}")
            lines.append(f"Damage types: {text_result.get('damage_types', [])}")
            lines.append(f"Claimed loss%: {text_result.get('claimed_loss_percent', 'N/A')}")
            lines.append(f"Confidence: {text_result.get('confidence', 0):.3f}")

        lines.append("\n=== IMAGE AGENT (Crop CNN) ===")
        if image_result and image_result.get("decision") not in (None, ""):
            lines.append(f"Decision: {image_result.get('decision', 'N/A')}")
            lines.append(f"Crop classification: {image_result.get('crop_classification', image_result.get('predicted_crop', 'N/A'))}")
            lines.append(f"Damage level: {image_result.get('damage_level', 'N/A')}")
            lines.append(f"Confidence: {image_result.get('confidence', 0):.3f}")
        else:
            lines.append("Not available or insufficient.")

        lines.append("\n=== SATELLITE AGENT (Sentinel-2 CropAgent v0.2) ===")
        if satellite_result and satellite_result.get("decision") not in (None, ""):
            lines.append(f"Decision: {satellite_result.get('decision', 'N/A')}")
            lines.append(f"Predicted crop: {satellite_result.get('predicted_crop', 'N/A')}")
            ndvi = satellite_result.get("ndvi") or satellite_result.get("ndvi_mean")
            lines.append(f"NDVI: {ndvi}")
            lines.append(f"Evidence decision: {satellite_result.get('evidence_decision', 'N/A')}")
            lines.append(f"Confidence: {satellite_result.get('confidence', 0):.3f}")
        else:
            lines.append("Not available or insufficient.")

        lines.append("\n=== SENSOR AGENT (Weather/Soil) ===")
        if sensor_result and sensor_result.get("decision") not in (None, ""):
            lines.append(f"Decision: {sensor_result.get('decision', 'N/A')}")
            lines.append(f"Detected events: {sensor_result.get('detected_events', [])}")
            lines.append(f"Evidence decision: {sensor_result.get('evidence_decision', 'N/A')}")
            obs = sensor_result.get("observations", {})
            if obs:
                obs_str = ", ".join(
                    f"{k}={v}" for k, v in list(obs.items())[:6]
                )
                lines.append(f"Observations: {obs_str}")
        else:
            lines.append("Not available or insufficient.")

        lines.append(f"\n=== AVAILABLE MODALITIES ===")
        lines.append(f"{', '.join(available_modalities)} ({len(available_modalities)}/4)")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # LLM investigation
    # ------------------------------------------------------------------

    def _llm_investigate(
        self,
        investigation_context: str,
    ) -> Dict[str, Any]:
        """
        Use Groq LLM for deep investigation reasoning.
        Falls back to heuristic analysis if LLM is unavailable.
        """

        if self.client is None:
            return self._heuristic_fallback(investigation_context)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": (
                            "Perform a deep investigation analysis of this "
                            "agriculture insurance claim:\n\n"
                            f"{investigation_context}"
                        ),
                    },
                ],
                temperature=0,
                max_completion_tokens=MAX_COMPLETION_TOKENS,
                response_format={"type": "json_object"},
            )

            content = response.choices[0].message.content

            if not content:
                raise RuntimeError(
                    "Groq returned an empty investigation response."
                )

            parsed = json.loads(content)

            if not isinstance(parsed, dict):
                raise RuntimeError(
                    "Groq investigation response must be a JSON object."
                )

            return parsed

        except Exception:
            return self._heuristic_fallback(investigation_context)

    def _heuristic_fallback(
        self,
        investigation_context: str,
    ) -> Dict[str, Any]:
        """Heuristic fallback when Groq LLM is unavailable."""

        suspicious = "SUSPICIOUS" in investigation_context
        score = 0.6 if suspicious else 0.3

        return {
            "investigation_score": score,
            "field_visit_priority": PRIORITY_HIGH if suspicious else PRIORITY_LOW,
            "fraud_indicators": [
                "LLM unavailable — heuristic fallback used. Manual review recommended."
            ] if suspicious else [],
            "supporting_factors": [
                "LLM investigation not available. Deterministic fallback activated."
            ],
            "verification_actions": [
                "Manual review of cross-modal contradictions.",
                "Field visit recommended to verify crop and damage claims.",
            ],
            "satellite_consistency": "UNAVAILABLE",
            "crop_fraud_risk": "UNKNOWN",
            "event_fraud_risk": "UNKNOWN",
            "decision": "SUSPICIOUS" if suspicious else "INSUFFICIENT_DATA",
            "human_review_recommended": True,
            "investigation_narrative": (
                "LLM investigation unavailable. Heuristic analysis detected "
                f"{'suspicious signals' if suspicious else 'no clear signals'}. "
                "Human review is recommended."
            ),
        }

    # ------------------------------------------------------------------
    # Available modalities
    # ------------------------------------------------------------------

    def _available_modalities(
        self,
        text_result: Dict[str, Any],
        image_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
    ) -> List[str]:
        """Return list of available evidence modalities."""

        available = []

        if text_result and text_result.get("decision") not in (None, ""):
            available.append("TextAgent")

        if image_result and image_result.get("decision") not in (None, ""):
            available.append("ImageAgent")

        if satellite_result and satellite_result.get("decision") not in (None, ""):
            available.append("SatelliteAgent")

        if sensor_result and sensor_result.get("decision") not in (None, ""):
            available.append("SensorAgent")

        return available

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self,
        investigation_score: float,
        available_modality_count: int,
        fraud_indicator_count: int,
    ) -> float:
        """Calculate investigation confidence."""

        if available_modality_count == 0:
            return 0.0

        modality_factor = min(available_modality_count / 4.0, 1.0)
        indicator_penalty = min(0.30, fraud_indicator_count * 0.06)

        confidence = (
            0.60 * modality_factor
            + 0.30 * (1.0 - investigation_score)
            - indicator_penalty
        )

        return max(0.0, min(1.0, confidence))

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
            "field_visit_priority": PRIORITY_HIGH,
            "fraud_indicators": [],
            "verification_actions": [],
            "investigation_tasks": [],
            "available_modalities": [],
            "human_review_recommended": True,
            "investigation_narrative": f"Investigation failed: {message}",
            "satellite_consistency": "UNAVAILABLE",
            "crop_fraud_risk": "UNKNOWN",
            "event_fraud_risk": "UNKNOWN",
            "claimed_crop": None,
            "claimed_event": None,
            "claimed_loss_percent": None,
            "event_date": None,
            "location": None,
            "llm_provider": "groq",
            "llm_model": self.model,
            "risk_score_meaning": "additional_verification_need",
            "agent_version": MODEL_VERSION,
        }