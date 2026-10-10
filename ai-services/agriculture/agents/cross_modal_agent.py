"""
TruthChain Agriculture - Cross-Modal Agent (LLM-Powered)

Cross-modal consistency layer for agriculture claims.

Uses Groq LLM (openai/gpt-oss-120b) for semantic multi-evidence fusion,
exactly mirroring the motor pipeline's CrossModalAgent architecture.

This agent compares evidence produced by:
    - ImageAgent
    - SatelliteAgent
    - TextAgent
    - SensorAgent

It does NOT independently determine insurance fraud.

Its purpose is to:
    1. Normalize crop names across modalities using deterministic pre-processing.
    2. Feed all agent evidence to Groq LLM for semantic cross-modal reasoning.
    3. Detect contradictions via LLM reasoning (not just dict lookup).
    4. Measure cross-modal agreement with LLM explanation.
    5. Produce a structured result for downstream investigation/risk/consensus.

Important:
    risk_score is a cross-modal inconsistency score.
    It is NOT a final fraud probability.

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
import re
import time
from typing import Any, Dict, List, Optional, Set

import config  # noqa: F401
from groq import Groq


MODEL_VERSION = "agriculture-cross-modal-agent-llm-v1.0"
DOMAIN = "agriculture"
AGENT_NAME = "CrossModalAgent"

GROQ_MODEL = "openai/gpt-oss-120b"
REASONING_EFFORT = "low"
MAX_COMPLETION_TOKENS = 1800


# ---------------------------------------------------------------------------
# Crop taxonomy normalization (deterministic pre-processing)
# ---------------------------------------------------------------------------

CROP_GROUPS = {
    "wheat": "Wheat",
    "wheat plant": "Wheat",

    "mustard": "Mustard",
    "sarson": "Mustard",
    "rapeseed": "Mustard",
    "canola": "Mustard",
    "rapeseed canola": "Mustard",
    "rapeseed (canola)": "Mustard",
    "rapeseed (canola) plant": "Mustard",
    "mustard plant": "Mustard",

    "lentil": "Lentil",
    "masoor": "Lentil",
    "lentil plant": "Lentil",

    "fallow": "Fallow",

    "green pea": "Green pea",
    "green peas": "Green pea",
    "pea": "Green pea",
    "peas": "Green pea",
    "matar": "Green pea",
    "green pea plant": "Green pea",

    "sugarcane": "Sugarcane",
    "sugar cane": "Sugarcane",
    "ganna": "Sugarcane",
    "sugar cane plant": "Sugarcane",
    "sugarcane plant": "Sugarcane",

    "garlic": "Garlic",
    "lahsun": "Garlic",
    "garlic plant": "Garlic",

    "maize": "Maize",
    "corn": "Maize",
    "makka": "Maize",
    "maize corn": "Maize",
    "maize (corn)": "Maize",
    "maize (corn) plant": "Maize",
    "corn plant": "Maize",
    "maize plant": "Maize",

    "gram": "Gram",
    "chickpea": "Gram",
    "chick peas": "Gram",
    "chana": "Gram",
    "gram plant": "Gram",

    "coriander": "Coriander",
    "dhaniya": "Coriander",
    "coriander plant": "Coriander",

    "potato": "Potato",
    "potatoes": "Potato",
    "aloo": "Potato",
    "potato plant": "Potato",

    "bersem": "Bersem",
    "berseem": "Bersem",
    "bersem plant": "Bersem",
    "berseem plant": "Bersem",

    "rice": "Rice",
    "paddy": "Rice",
    "dhan": "Rice",
    "rice plant": "Rice",
    "paddy plant": "Rice",
}


# ---------------------------------------------------------------------------
# Event normalization (deterministic pre-processing)
# ---------------------------------------------------------------------------

EVENT_GROUPS = {
    "rain": "Heavy rain",
    "heavy rain": "Heavy rain",
    "heavy rainfall": "Heavy rain",

    "excess rain": "Excess rainfall",
    "excess rainfall": "Excess rainfall",

    "flood": "Flood",
    "flooding": "Flood",

    "waterlogging": "Waterlogging",
    "water logging": "Waterlogging",

    "drought": "Drought",

    "storm": "Storm",
    "cyclone": "Storm",

    "high wind": "High wind",

    "hail": "Hail",
    "hailstorm": "Hail",

    "pest": "Pest",
    "pest attack": "Pest",

    "disease": "Disease",

    "fire": "Fire",

    "heatwave": "Heatwave",
    "heat wave": "Heatwave",

    "frost": "Frost",

    "cold wave": "Cold wave",
    "coldwave": "Cold wave",

    "lodging": "Lodging",
}


# ---------------------------------------------------------------------------
# System prompt for Groq LLM cross-modal fusion
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are the cross-modal evidence fusion component of an agriculture insurance
claim verification system.

You receive structured outputs from multiple evidence agents:
  - TextAgent: extracted crop, event, area, loss% from claim narrative
  - ImageAgent: crop classification from field photo (CNN model)
  - SatelliteAgent: crop classification from Sentinel-2 imagery (CropAgent v0.2, NDVI)
  - SensorAgent: weather/soil sensor analysis (rainfall, temperature, soil moisture)

Your task is to:
1. Detect semantic agreements and contradictions across all evidence modalities.
2. Explain each contradiction clearly with specific field values.
3. Assess cross-modal consistency as a numerical score.
4. Output a structured JSON analysis.

Do NOT:
- Determine final fraud or claim validity
- Invent information not present in the inputs
- Estimate loss amounts

Return ONLY valid JSON with exactly these fields:

{
  "cross_modal_score": number (0.0-1.0, where 0=perfect agreement, 1=maximum inconsistency),
  "agreement_level": "HIGH" | "MODERATE" | "LOW" | "CONTRADICTORY",
  "decision": "PASS" | "SUSPICIOUS" | "INSUFFICIENT_DATA",
  "crop_consistency": {
    "status": "CONSISTENT" | "INCONSISTENT" | "UNAVAILABLE",
    "claimed": string or null,
    "image_detected": string or null,
    "satellite_detected": string or null,
    "explanation": string
  },
  "event_consistency": {
    "status": "CONSISTENT" | "INCONSISTENT" | "UNAVAILABLE",
    "claimed": string or null,
    "sensor_evidence": string or null,
    "explanation": string
  },
  "satellite_ndvi_analysis": {
    "ndvi_value": number or null,
    "ndvi_interpretation": string,
    "supports_damage_claim": boolean or null
  },
  "contradictions": [string],
  "supporting_evidence": [string],
  "llm_reasoning": string
}

Decision rules:
- PASS: No contradictions found, modalities agree or have no conflicting evidence
- SUSPICIOUS: One or more clear contradictions detected between modalities
- INSUFFICIENT_DATA: Too few modalities available to make a determination

cross_modal_score: 0.0-0.3 = low inconsistency, 0.3-0.6 = moderate, 0.6-1.0 = high inconsistency
"""


# ---------------------------------------------------------------------------
# Cross-Modal Agent (LLM-Powered)
# ---------------------------------------------------------------------------

class CrossModalAgent:
    """
    LLM-powered agriculture cross-modal consistency engine.

    Uses Groq LLM (openai/gpt-oss-120b) for semantic multi-evidence fusion.

    Deterministic pre-processing normalizes crop and event names.
    The LLM then reasons over the normalized evidence to detect
    contradictions and produce a structured cross-modal assessment.

    This matches the motor pipeline's CrossModalAgent architecture.
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
        text_result: Optional[Dict[str, Any]] = None,
        image_result: Optional[Dict[str, Any]] = None,
        satellite_result: Optional[Dict[str, Any]] = None,
        sensor_result: Optional[Dict[str, Any]] = None,
        claim: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Compare agriculture evidence across modalities using Groq LLM.

        Parameters
        ----------
        text_result:
            Output from TextAgent.

        image_result:
            Output from ImageAgent.

        satellite_result:
            Output from SatelliteAgent.

        sensor_result:
            Output from SensorAgent.

        claim:
            Optional structured claim fields as fallback context.

        Returns
        -------
        dict
            Standardized cross-modal result.
        """

        start_time = time.perf_counter()

        try:
            text_result = text_result or {}
            image_result = image_result or {}
            satellite_result = satellite_result or {}
            sensor_result = sensor_result or {}
            claim = claim or {}

            available_modalities = self._available_modalities(
                text_result,
                image_result,
                satellite_result,
                sensor_result,
            )

            if not available_modalities and not claim:
                return self._error_result(
                    "No claim or agent evidence was supplied.",
                    start_time,
                )

            # ----------------------------------------------------------
            # Deterministic pre-processing: normalize crop/event names
            # ----------------------------------------------------------

            claimed_crop = self._resolve_claimed_crop(
                claim=claim,
                text_result=text_result,
                image_result=image_result,
                satellite_result=satellite_result,
            )

            claimed_event = self._resolve_claimed_event(
                claim=claim,
                text_result=text_result,
                sensor_result=sensor_result,
            )

            claimed_loss = self._resolve_claimed_loss(
                claim=claim,
                text_result=text_result,
            )

            event_date = self._resolve_value(
                claim.get("event_date"),
                text_result.get("event_date"),
                sensor_result.get("event_date"),
            )

            location = self._resolve_value(
                claim.get("location"),
                text_result.get("location"),
                sensor_result.get("location"),
            )

            # ----------------------------------------------------------
            # Build evidence context for LLM
            # ----------------------------------------------------------

            evidence_context = self._build_evidence_context(
                text_result=text_result,
                image_result=image_result,
                satellite_result=satellite_result,
                sensor_result=sensor_result,
                claimed_crop=claimed_crop,
                claimed_event=claimed_event,
                claimed_loss=claimed_loss,
                event_date=event_date,
                location=location,
            )

            # ----------------------------------------------------------
            # LLM semantic fusion
            # ----------------------------------------------------------

            llm_result = self._llm_analyze(evidence_context)

            # ----------------------------------------------------------
            # Extract and validate LLM output
            # ----------------------------------------------------------

            cross_modal_score = float(
                llm_result.get("cross_modal_score", 0.5)
            )
            cross_modal_score = max(0.0, min(1.0, cross_modal_score))

            agreement_level = str(
                llm_result.get("agreement_level", "MODERATE")
            ).upper()

            decision = str(
                llm_result.get("decision", "INSUFFICIENT_DATA")
            ).upper()

            if decision not in {"PASS", "SUSPICIOUS", "INSUFFICIENT_DATA"}:
                decision = "INSUFFICIENT_DATA"

            contradictions: List[str] = [
                str(c) for c in llm_result.get("contradictions", [])
                if c and str(c).strip()
            ]

            supporting_evidence: List[str] = [
                str(e) for e in llm_result.get("supporting_evidence", [])
                if e and str(e).strip()
            ]

            llm_reasoning = str(
                llm_result.get("llm_reasoning", "")
            ).strip()

            # ----------------------------------------------------------
            # Build evidence list
            # ----------------------------------------------------------

            evidence: List[str] = []

            if claimed_crop:
                evidence.append(
                    f"Normalized claimed crop: '{claimed_crop}'."
                )

            if claimed_event:
                evidence.append(
                    f"Normalized claimed event: '{claimed_event}'."
                )

            if claimed_loss is not None:
                evidence.append(
                    f"Normalized claimed crop loss: "
                    f"{claimed_loss:.2f}%."
                )

            if event_date:
                evidence.append(
                    f"Claim event date: '{event_date}'."
                )

            if location:
                evidence.append(
                    f"Claim location/context: '{location}'."
                )

            evidence.extend(supporting_evidence)

            evidence.append(
                f"Cross-modal LLM agreement level: {agreement_level}. "
                f"Inconsistency score: {cross_modal_score:.3f}."
            )

            if llm_reasoning:
                evidence.append(
                    f"LLM reasoning: {llm_reasoning}"
                )

            evidence.append(
                f"Evidence modalities available: "
                + ", ".join(available_modalities)
                + f" ({len(available_modalities)})."
            )

            # ----------------------------------------------------------
            # Satellite NDVI info
            # ----------------------------------------------------------

            ndvi_analysis = llm_result.get("satellite_ndvi_analysis", {})
            ndvi_value = None
            if isinstance(ndvi_analysis, dict):
                ndvi_raw = ndvi_analysis.get("ndvi_value")
                if ndvi_raw is not None:
                    try:
                        ndvi_value = float(ndvi_raw)
                    except (TypeError, ValueError):
                        ndvi_value = None

                ndvi_interp = ndvi_analysis.get("ndvi_interpretation", "")
                if ndvi_interp:
                    evidence.append(
                        f"Satellite NDVI analysis: {ndvi_interp}"
                    )

            # ----------------------------------------------------------
            # Confidence
            # ----------------------------------------------------------

            confidence = self._calculate_confidence(
                cross_modal_score=cross_modal_score,
                modality_count=len(available_modalities),
                contradiction_count=len(contradictions),
            )

            processing_time_ms = round(
                (time.perf_counter() - start_time) * 1000,
                3,
            )

            return {
                "agent": self.agent_name,
                "domain": self.domain,
                "confidence": round(confidence, 6),
                "risk_score": round(cross_modal_score, 6),
                "decision": decision,
                "evidence": evidence,
                "contradictions": contradictions,
                "model_version": self.model_version,
                "processing_time_ms": processing_time_ms,

                # Agriculture cross-modal specific fields.
                "claimed_crop": claimed_crop,
                "claimed_event": claimed_event,
                "claimed_loss_percent": claimed_loss,
                "event_date": event_date,
                "location": location,
                "agreement_level": agreement_level,
                "cross_modal_score": round(cross_modal_score, 6),
                "agreement_score": round(1.0 - cross_modal_score, 6),
                "contradiction_count": len(contradictions),
                "available_modalities": available_modalities,
                "ndvi_value": ndvi_value,
                "crop_consistency": llm_result.get("crop_consistency", {}),
                "event_consistency": llm_result.get("event_consistency", {}),
                "llm_reasoning": llm_reasoning,

                # LLM audit information.
                "llm_provider": "groq",
                "llm_model": self.model,

                # Semantic clarification.
                "risk_score_meaning": "cross_modal_inconsistency",
                "agent_version": MODEL_VERSION,
            }

        except Exception as exc:
            return self._error_result(
                str(exc),
                start_time,
            )

    # ------------------------------------------------------------------
    # Evidence context builder
    # ------------------------------------------------------------------

    def _build_evidence_context(
        self,
        text_result: Dict[str, Any],
        image_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
        claimed_crop: Optional[str],
        claimed_event: Optional[str],
        claimed_loss: Optional[float],
        event_date: Optional[str],
        location: Optional[str],
    ) -> str:
        """Build a structured evidence context string for the LLM."""

        lines = []

        lines.append("=== CLAIM SUMMARY (normalized) ===")
        lines.append(f"Claimed crop: {claimed_crop or 'not specified'}")
        lines.append(f"Claimed event: {claimed_event or 'not specified'}")
        lines.append(f"Claimed loss: {f'{claimed_loss:.1f}%' if claimed_loss is not None else 'not specified'}")
        lines.append(f"Event date: {event_date or 'not specified'}")
        lines.append(f"Location: {location or 'not specified'}")

        lines.append("\n=== TEXT AGENT OUTPUT ===")
        if text_result:
            lines.append(f"Decision: {text_result.get('decision', 'N/A')}")
            lines.append(f"Extracted crop: {text_result.get('extracted_crop', 'N/A')}")
            lines.append(f"Damage types: {text_result.get('damage_types', [])}")
            lines.append(f"Confidence: {text_result.get('confidence', 0):.3f}")
            ev = text_result.get('evidence', [])
            if ev:
                lines.append(f"Key evidence: {'; '.join(ev[:3])}")
        else:
            lines.append("Not available.")

        lines.append("\n=== IMAGE AGENT OUTPUT (Crop CNN) ===")
        if image_result and image_result.get('decision') not in ('INSUFFICIENT_DATA', None, ''):
            lines.append(f"Decision: {image_result.get('decision', 'N/A')}")
            lines.append(f"Crop classification: {image_result.get('crop_classification', image_result.get('predicted_crop', 'N/A'))}")
            lines.append(f"Damage level: {image_result.get('damage_level', 'N/A')}")
            lines.append(f"Confidence: {image_result.get('confidence', 0):.3f}")
            ev = image_result.get('evidence', [])
            if ev:
                lines.append(f"Key evidence: {'; '.join(str(e) for e in ev[:3])}")
        else:
            lines.append("Not available or insufficient data.")

        lines.append("\n=== SATELLITE AGENT OUTPUT (Sentinel-2 / CropAgent v0.2) ===")
        if satellite_result and satellite_result.get('decision') not in ('INSUFFICIENT_DATA', None, ''):
            lines.append(f"Decision: {satellite_result.get('decision', 'N/A')}")
            lines.append(f"Predicted crop: {satellite_result.get('predicted_crop', 'N/A')}")
            lines.append(f"NDVI: {satellite_result.get('ndvi', satellite_result.get('ndvi_mean', 'N/A'))}")
            lines.append(f"Evidence decision: {satellite_result.get('evidence_decision', 'N/A')}")
            lines.append(f"Confidence: {satellite_result.get('confidence', 0):.3f}")
            ev = satellite_result.get('evidence', [])
            if ev:
                lines.append(f"Key evidence: {'; '.join(str(e) for e in ev[:3])}")
        else:
            lines.append("Not available or insufficient data.")

        lines.append("\n=== SENSOR AGENT OUTPUT (Weather/Soil) ===")
        if sensor_result and sensor_result.get('decision') not in ('INSUFFICIENT_DATA', None, ''):
            lines.append(f"Decision: {sensor_result.get('decision', 'N/A')}")
            lines.append(f"Detected events: {sensor_result.get('detected_events', [])}")
            lines.append(f"Evidence decision: {sensor_result.get('evidence_decision', 'N/A')}")
            lines.append(f"Confidence: {sensor_result.get('confidence', 0):.3f}")
            obs = sensor_result.get('observations', {})
            if obs:
                obs_str = ", ".join(
                    f"{k}={v}" for k, v in list(obs.items())[:6]
                )
                lines.append(f"Observations: {obs_str}")
            ev = sensor_result.get('evidence', [])
            if ev:
                lines.append(f"Key evidence: {'; '.join(str(e) for e in ev[:3])}")
        else:
            lines.append("Not available or insufficient data.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # LLM analysis
    # ------------------------------------------------------------------

    def _llm_analyze(
        self,
        evidence_context: str,
    ) -> Dict[str, Any]:
        """
        Use Groq LLM to perform semantic cross-modal fusion.
        Falls back to deterministic analysis if LLM is unavailable.
        """

        if self.client is None:
            return self._deterministic_fallback(evidence_context)

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
                            "Analyze the cross-modal consistency of this "
                            "agriculture claim evidence:\n\n"
                            f"{evidence_context}"
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
                    "Groq returned an empty cross-modal response."
                )

            parsed = json.loads(content)

            if not isinstance(parsed, dict):
                raise RuntimeError(
                    "Groq cross-modal response must be a JSON object."
                )

            return parsed

        except Exception:
            return self._deterministic_fallback(evidence_context)

    def _deterministic_fallback(
        self,
        evidence_context: str,
    ) -> Dict[str, Any]:
        """Deterministic fallback when Groq LLM is unavailable."""

        has_data = "Not available" not in evidence_context

        return {
            "cross_modal_score": 0.5,
            "agreement_level": "MODERATE",
            "decision": "INSUFFICIENT_DATA" if not has_data else "PASS",
            "crop_consistency": {
                "status": "UNAVAILABLE",
                "claimed": None,
                "image_detected": None,
                "satellite_detected": None,
                "explanation": "LLM unavailable — deterministic fallback."
            },
            "event_consistency": {
                "status": "UNAVAILABLE",
                "claimed": None,
                "sensor_evidence": None,
                "explanation": "LLM unavailable — deterministic fallback."
            },
            "satellite_ndvi_analysis": {
                "ndvi_value": None,
                "ndvi_interpretation": "LLM unavailable.",
                "supports_damage_claim": None,
            },
            "contradictions": [],
            "supporting_evidence": [
                "LLM cross-modal fusion unavailable. Deterministic fallback used."
            ],
            "llm_reasoning": "Groq LLM client not available. Using deterministic fallback.",
        }

    # ------------------------------------------------------------------
    # Claim field resolvers (deterministic pre-processing)
    # ------------------------------------------------------------------

    def _resolve_claimed_crop(
        self,
        claim: Dict[str, Any],
        text_result: Dict[str, Any],
        image_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
    ) -> Optional[str]:
        """Resolve normalized claimed crop from all sources."""

        for value in [
            claim.get("crop"),
            claim.get("claimed_crop"),
            text_result.get("extracted_crop"),
        ]:
            normalized = self._normalize_crop(value)
            if normalized:
                return normalized

        return None

    def _resolve_claimed_event(
        self,
        claim: Dict[str, Any],
        text_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
    ) -> Optional[str]:
        """Resolve normalized claimed event from all sources."""

        for value in [
            claim.get("event"),
            claim.get("damage_type"),
        ]:
            normalized = self._normalize_event(value)
            if normalized:
                return normalized

        damage_types = text_result.get("damage_types", [])
        if isinstance(damage_types, list) and damage_types:
            return damage_types[0]

        return None

    def _resolve_claimed_loss(
        self,
        claim: Dict[str, Any],
        text_result: Dict[str, Any],
    ) -> Optional[float]:
        """Resolve claimed loss percentage."""

        for value in [
            claim.get("claimed_loss_percent"),
            text_result.get("claimed_loss_percent"),
        ]:
            if value is not None:
                try:
                    f = float(value)
                    if 0 <= f <= 100:
                        return f
                except (TypeError, ValueError):
                    pass

        return None

    def _resolve_value(
        self,
        *values: Any,
    ) -> Optional[str]:
        """Return the first non-empty string value."""

        for value in values:
            if value is not None:
                s = str(value).strip()
                if s:
                    return s

        return None

    def _normalize_crop(
        self,
        value: Any,
    ) -> Optional[str]:
        """Normalize crop name using CROP_GROUPS lookup."""

        if value is None:
            return None

        value = str(value).strip()
        if not value:
            return None

        normalized = value.lower()

        if normalized in CROP_GROUPS:
            return CROP_GROUPS[normalized]

        for canonical in set(CROP_GROUPS.values()):
            if normalized == canonical.lower():
                return canonical

        return value

    def _normalize_event(
        self,
        value: Any,
    ) -> Optional[str]:
        """Normalize event name using EVENT_GROUPS lookup."""

        if value is None:
            return None

        value = str(value).strip()
        if not value:
            return None

        normalized = value.lower()

        if normalized in EVENT_GROUPS:
            return EVENT_GROUPS[normalized]

        return value

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
        """Return list of available (non-empty) evidence modalities."""

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
        cross_modal_score: float,
        modality_count: int,
        contradiction_count: int,
    ) -> float:
        """Calculate confidence based on LLM-produced cross-modal score."""

        if modality_count == 0:
            return 0.0

        modality_factor = min(modality_count / 4.0, 1.0)
        consistency_factor = 1.0 - cross_modal_score
        contradiction_penalty = min(0.30, contradiction_count * 0.08)

        confidence = (
            0.50 * modality_factor
            + 0.40 * consistency_factor
            - contradiction_penalty
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
            "claimed_crop": None,
            "claimed_event": None,
            "claimed_loss_percent": None,
            "event_date": None,
            "location": None,
            "agreement_level": "CONTRADICTORY",
            "cross_modal_score": 1.0,
            "agreement_score": 0.0,
            "contradiction_count": 1,
            "available_modalities": [],
            "ndvi_value": None,
            "crop_consistency": {},
            "event_consistency": {},
            "llm_reasoning": "",
            "llm_provider": "groq",
            "llm_model": self.model,
            "risk_score_meaning": "cross_modal_inconsistency",
            "agent_version": MODEL_VERSION,
        }


# ---------------------------------------------------------------------------
# Singleton / convenience API
# ---------------------------------------------------------------------------

_cross_modal_agent: Optional[CrossModalAgent] = None


def get_cross_modal_agent() -> CrossModalAgent:
    global _cross_modal_agent

    if _cross_modal_agent is None:
        _cross_modal_agent = CrossModalAgent()

    return _cross_modal_agent