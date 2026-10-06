"""
TruthChain Agriculture - Cross-Modal Agent

Cross-modal consistency layer for agriculture claims.

This agent compares evidence produced by:
    - ImageAgent
    - SatelliteAgent
    - TextAgent
    - SensorAgent

It does NOT independently determine insurance fraud.

Its purpose is to:
    1. Normalize crop names across modalities.
    2. Compare claimed crop vs image/satellite crop evidence.
    3. Compare claimed damage event vs sensor evidence.
    4. Compare narrative loss vs available evidence.
    5. Detect explicit contradictions.
    6. Measure cross-modal agreement.
    7. Produce a structured result for downstream investigation/risk/consensus.

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

import re
import time
from typing import Any, Dict, List, Optional, Set


MODEL_VERSION = "agriculture-cross-modal-agent-v0.1"
DOMAIN = "agriculture"
AGENT_NAME = "CrossModalAgent"


# ---------------------------------------------------------------------------
# Crop taxonomy normalization
# ---------------------------------------------------------------------------
#
# CrossModal owns the broad normalization layer.
#
# This is important because different models may use labels such as:
#   "Maize"
#   "Maize (Corn) plant"
#   "Corn"
#
# and:
#   "Mustard"
#   "Rapeseed (Canola) plant"
#   "Canola"
#
# Those should not automatically be treated as contradictions.
#

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
# Event normalization
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
# Cross-modal agent
# ---------------------------------------------------------------------------

class CrossModalAgent:
    """
    Agriculture cross-modal consistency engine.

    Expected inputs are already-produced agent dictionaries.

    Example:

        image_result = ImageAgent.analyze(...)
        satellite_result = SatelliteAgent.analyze(...)
        text_result = TextAgent.analyze(...)
        sensor_result = SensorAgent.analyze(...)

        result = CrossModalAgent().analyze(
            text_result=text_result,
            image_result=image_result,
            satellite_result=satellite_result,
            sensor_result=sensor_result,
        )
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
        text_result: Optional[Dict[str, Any]] = None,
        image_result: Optional[Dict[str, Any]] = None,
        satellite_result: Optional[Dict[str, Any]] = None,
        sensor_result: Optional[Dict[str, Any]] = None,
        claim: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Compare agriculture evidence across available modalities.

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
            Optional structured claim fields. This can provide fallback
            information such as crop, claimed event, loss percentage,
            event date, and location.

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

            evidence: List[str] = []
            contradictions: List[str] = []
            checks: List[Dict[str, Any]] = []

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
            # Claim extraction / normalization
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
            # Crop consistency
            # ----------------------------------------------------------

            crop_check = self._check_crop_consistency(
                claimed_crop=claimed_crop,
                image_result=image_result,
                satellite_result=satellite_result,
            )

            if crop_check["status"] != "UNAVAILABLE":
                checks.append(crop_check)

                if crop_check["status"] == "PASS":
                    evidence.extend(crop_check["evidence"])

                elif crop_check["status"] == "CONTRADICTION":
                    contradictions.extend(crop_check["contradictions"])

            # ----------------------------------------------------------
            # Event consistency
            # ----------------------------------------------------------

            event_check = self._check_event_consistency(
                claimed_event=claimed_event,
                sensor_result=sensor_result,
                text_result=text_result,
            )

            if event_check["status"] != "UNAVAILABLE":
                checks.append(event_check)

                if event_check["status"] == "PASS":
                    evidence.extend(event_check["evidence"])

                elif event_check["status"] == "CONTRADICTION":
                    contradictions.extend(event_check["contradictions"])

            # ----------------------------------------------------------
            # Loss consistency
            # ----------------------------------------------------------

            loss_check = self._check_loss_consistency(
                claimed_loss=claimed_loss,
                image_result=image_result,
                satellite_result=satellite_result,
                sensor_result=sensor_result,
            )

            if loss_check["status"] != "UNAVAILABLE":
                checks.append(loss_check)

                if loss_check["status"] == "PASS":
                    evidence.extend(loss_check["evidence"])

                elif loss_check["status"] == "CONTRADICTION":
                    contradictions.extend(loss_check["contradictions"])

            # ----------------------------------------------------------
            # Date / location consistency
            # ----------------------------------------------------------

            context_check = self._check_context_consistency(
                event_date=event_date,
                location=location,
                text_result=text_result,
                sensor_result=sensor_result,
                satellite_result=satellite_result,
            )

            if context_check["status"] != "UNAVAILABLE":
                checks.append(context_check)

                if context_check["status"] == "PASS":
                    evidence.extend(context_check["evidence"])

                elif context_check["status"] == "CONTRADICTION":
                    contradictions.extend(context_check["contradictions"])

            # ----------------------------------------------------------
            # Modality-level decisions
            # ----------------------------------------------------------

            modality_check = self._check_modality_health(
                text_result=text_result,
                image_result=image_result,
                satellite_result=satellite_result,
                sensor_result=sensor_result,
            )

            if modality_check["status"] != "UNAVAILABLE":
                checks.append(modality_check)

                evidence.extend(modality_check["evidence"])
                contradictions.extend(
                    modality_check["contradictions"]
                )

            # ----------------------------------------------------------
            # Agreement calculation
            # ----------------------------------------------------------

            agreement = self._calculate_agreement(
                checks=checks,
                available_modalities=available_modalities,
            )

            # ----------------------------------------------------------
            # Final cross-modal decision
            # ----------------------------------------------------------

            contradiction_count = len(contradictions)
            usable_check_count = sum(
                1
                for check in checks
                if check["status"] != "UNAVAILABLE"
            )

            if usable_check_count == 0:
                decision = "INSUFFICIENT_DATA"

            elif contradiction_count > 0:
                decision = "SUSPICIOUS"

            elif agreement >= 0.60:
                decision = "PASS"

            else:
                decision = "INSUFFICIENT_DATA"

            # Cross-modal confidence reflects agreement and evidence
            # availability. It is deliberately not called fraud probability.
            confidence = self._calculate_confidence(
                agreement=agreement,
                usable_check_count=usable_check_count,
                modality_count=len(available_modalities),
                contradiction_count=contradiction_count,
            )

            # Inconsistency score is distinct from final fraud risk.
            risk_score = self._calculate_risk_score(
                agreement=agreement,
                contradiction_count=contradiction_count,
                usable_check_count=usable_check_count,
            )

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

            evidence.append(
                "Cross-modal agreement score: "
                f"{agreement:.3f}."
            )

            evidence.append(
                "Cross-modal evidence modalities available: "
                + ", ".join(available_modalities)
                + "."
            )

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

                # Normalized claim information.
                "claimed_crop": claimed_crop,
                "claimed_event": claimed_event,
                "claimed_loss_percent": claimed_loss,
                "event_date": event_date,
                "location": location,

                # Cross-modal analysis.
                "agreement_score": round(agreement, 6),
                "cross_modal_checks": checks,
                "available_modalities": available_modalities,
                "contradiction_count": contradiction_count,

                # Explicit semantic clarification.
                "risk_score_meaning": "cross_modal_inconsistency_score",
                "agent_version": MODEL_VERSION,
            }

        except Exception as exc:
            return self._error_result(
                str(exc),
                start_time,
            )

    # ------------------------------------------------------------------
    # Claim resolution
    # ------------------------------------------------------------------

    def _resolve_claimed_crop(
        self,
        claim: Dict[str, Any],
        text_result: Dict[str, Any],
        image_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
    ) -> Optional[str]:

        candidates = [
            claim.get("crop"),
            claim.get("claimed_crop"),
            text_result.get("extracted_crop"),
            text_result.get("claimed_crop"),
            image_result.get("claimed_crop"),
            satellite_result.get("claimed_crop"),
        ]

        for value in candidates:
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

        candidates = [
            claim.get("event"),
            claim.get("claimed_event"),
            claim.get("damage_type"),
            text_result.get("claimed_event"),
            sensor_result.get("claimed_event"),
        ]

        # TextAgent currently exposes damage_types rather than
        # claimed_event, so use the first narrative event if needed.
        damage_types = text_result.get("damage_types")

        if isinstance(damage_types, list) and damage_types:
            candidates.append(damage_types[0])

        for value in candidates:
            normalized = self._normalize_event(value)

            if normalized:
                return normalized

        return None

    def _resolve_claimed_loss(
        self,
        claim: Dict[str, Any],
        text_result: Dict[str, Any],
    ) -> Optional[float]:

        candidates = [
            claim.get("claimed_loss_percent"),
            claim.get("loss_percent"),
            text_result.get("claimed_loss_percent"),
        ]

        for value in candidates:
            if value is None:
                continue

            try:
                value = float(value)
            except (TypeError, ValueError):
                continue

            if 0.0 <= value <= 100.0:
                return value

        return None

    @staticmethod
    def _resolve_value(*values: Any) -> Optional[Any]:

        for value in values:
            if value is None:
                continue

            if isinstance(value, str) and not value.strip():
                continue

            return value

        return None

    # ------------------------------------------------------------------
    # Crop normalization
    # ------------------------------------------------------------------

    def _normalize_crop(
        self,
        value: Any,
    ) -> Optional[str]:

        if value is None:
            return None

        text = str(value).strip()

        if not text:
            return None

        normalized = re.sub(
            r"\s+",
            " ",
            text.lower(),
        )

        normalized = normalized.strip(" .-_")

        # Direct alias.
        if normalized in CROP_GROUPS:
            return CROP_GROUPS[normalized]

        # Remove common model suffix.
        without_plant = re.sub(
            r"\s+plant$",
            "",
            normalized,
        ).strip()

        if without_plant in CROP_GROUPS:
            return CROP_GROUPS[without_plant]

        # Fallback substring handling for labels such as:
        # "Maize (Corn) plant".
        if "maize" in normalized or "corn" in normalized:
            return "Maize"

        if (
            "rapeseed" in normalized
            or "canola" in normalized
            or "mustard" in normalized
        ):
            return "Mustard"

        if "sugarcane" in normalized or "sugar cane" in normalized:
            return "Sugarcane"

        if "wheat" in normalized:
            return "Wheat"

        if "rice" in normalized or "paddy" in normalized:
            return "Rice"

        if "lentil" in normalized or "masoor" in normalized:
            return "Lentil"

        if "potato" in normalized:
            return "Potato"

        if "garlic" in normalized:
            return "Garlic"

        if "coriander" in normalized:
            return "Coriander"

        if "chickpea" in normalized or "chick pea" in normalized:
            return "Gram"

        if "gram" in normalized:
            return "Gram"

        if "pea" in normalized:
            return "Green pea"

        if "bersem" in normalized or "berseem" in normalized:
            return "Bersem"

        return text

    # ------------------------------------------------------------------
    # Event normalization
    # ------------------------------------------------------------------

    def _normalize_event(
        self,
        value: Any,
    ) -> Optional[str]:

        if value is None:
            return None

        text = str(value).strip().lower()

        if not text:
            return None

        text = re.sub(r"\s+", " ", text)

        if text in EVENT_GROUPS:
            return EVENT_GROUPS[text]

        # Handle simple embedded phrases.
        if "heavy rain" in text or "heavy rainfall" in text:
            return "Heavy rain"

        if "excess rain" in text or "excess rainfall" in text:
            return "Excess rainfall"

        if "flood" in text:
            return "Flood"

        if "waterlog" in text:
            return "Waterlogging"

        if "drought" in text:
            return "Drought"

        if "cyclone" in text or "storm" in text:
            return "Storm"

        if "hail" in text:
            return "Hail"

        if "pest" in text or "insect" in text:
            return "Pest"

        if "disease" in text:
            return "Disease"

        if "fire" in text:
            return "Fire"

        if "heat wave" in text or "heatwave" in text:
            return "Heatwave"

        if "frost" in text:
            return "Frost"

        return str(value).strip()

    # ------------------------------------------------------------------
    # Crop consistency
    # ------------------------------------------------------------------

    def _check_crop_consistency(
        self,
        claimed_crop: Optional[str],
        image_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not claimed_crop:
            return self._unavailable_check(
                "crop_consistency"
            )

        observations = []

        image_crop = self._normalize_crop(
            image_result.get("predicted_crop")
        )

        satellite_crop = self._normalize_crop(
            satellite_result.get("predicted_crop")
        )

        if image_crop:
            observations.append(
                ("ImageAgent", image_crop)
            )

        if satellite_crop:
            observations.append(
                ("SatelliteAgent", satellite_crop)
            )

        if not observations:
            return self._unavailable_check(
                "crop_consistency"
            )

        evidence = []
        contradictions = []

        for agent_name, predicted_crop in observations:
            if predicted_crop == claimed_crop:
                evidence.append(
                    f"{agent_name} crop evidence matches claimed "
                    f"crop '{claimed_crop}'."
                )
            else:
                contradictions.append(
                    f"{agent_name} predicted crop '{predicted_crop}', "
                    f"which differs from claimed crop '{claimed_crop}'."
                )

        if contradictions:
            return {
                "name": "crop_consistency",
                "status": "CONTRADICTION",
                "score": 0.0,
                "evidence": evidence,
                "contradictions": contradictions,
            }

        return {
            "name": "crop_consistency",
            "status": "PASS",
            "score": 1.0,
            "evidence": evidence,
            "contradictions": [],
        }

    # ------------------------------------------------------------------
    # Event consistency
    # ------------------------------------------------------------------

    def _check_event_consistency(
        self,
        claimed_event: Optional[str],
        sensor_result: Dict[str, Any],
        text_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        if not claimed_event:
            return self._unavailable_check(
                "event_consistency"
            )

        evidence = []
        contradictions = []

        detected_events: Set[str] = set()

        sensor_events = sensor_result.get("detected_events", [])

        if isinstance(sensor_events, list):
            for event in sensor_events:
                normalized = self._normalize_event(event)

                if normalized:
                    detected_events.add(normalized)

        text_events = text_result.get("damage_types", [])

        if isinstance(text_events, list):
            for event in text_events:
                normalized = self._normalize_event(event)

                if normalized:
                    detected_events.add(normalized)

        if not detected_events:
            return self._unavailable_check(
                "event_consistency"
            )

        matches = self._event_matches(
            claimed_event,
            detected_events,
        )

        if matches:
            evidence.append(
                f"Environmental/narrative evidence supports claimed "
                f"event '{claimed_event}' through: "
                + ", ".join(sorted(matches))
                + "."
            )

            return {
                "name": "event_consistency",
                "status": "PASS",
                "score": 1.0,
                "evidence": evidence,
                "contradictions": [],
            }

        contradictions.append(
            f"Claimed event '{claimed_event}' is not supported by "
            f"available event evidence: "
            + ", ".join(sorted(detected_events))
            + "."
        )

        return {
            "name": "event_consistency",
            "status": "CONTRADICTION",
            "score": 0.0,
            "evidence": [],
            "contradictions": contradictions,
        }

    def _event_matches(
        self,
        claimed_event: str,
        detected_events: Set[str],
    ) -> Set[str]:

        matches: Set[str] = set()

        if claimed_event in detected_events:
            matches.add(claimed_event)

        related = {
            "Heavy rain": {
                "Excess rainfall",
                "Flood",
            },
            "Excess rainfall": {
                "Heavy rain",
                "Flood",
            },
            "Flood": {
                "Excess rainfall",
                "Waterlogging",
                "Heavy rain",
            },
            "Waterlogging": {
                "Flood",
                "Excess rainfall",
                "Heavy rain",
            },
            "Storm": {
                "High wind",
            },
            "High wind": {
                "Storm",
            },
        }

        for event in related.get(claimed_event, set()):
            if event in detected_events:
                matches.add(event)

        return matches

    # ------------------------------------------------------------------
    # Loss consistency
    # ------------------------------------------------------------------

    def _check_loss_consistency(
        self,
        claimed_loss: Optional[float],
        image_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        if claimed_loss is None:
            return self._unavailable_check(
                "loss_consistency"
            )

        evidence = []
        contradictions = []

        # At this stage the ImageAgent/SatelliteAgent do not produce a
        # validated crop-loss percentage. Therefore we must NOT invent
        # one from their confidence scores.
        #
        # We only record whether environmental/image evidence exists.
        supporting_modalities = []

        if image_result.get("decision") not in {
            None,
            "",
            "ERROR",
        }:
            supporting_modalities.append("ImageAgent")

        if satellite_result.get("decision") not in {
            None,
            "",
            "ERROR",
        }:
            supporting_modalities.append("SatelliteAgent")

        if sensor_result.get("decision") not in {
            None,
            "",
            "ERROR",
        }:
            supporting_modalities.append("SensorAgent")

        if supporting_modalities:
            evidence.append(
                f"Claimed crop loss is {claimed_loss:.2f}%; "
                f"available evidence modalities for contextual review: "
                + ", ".join(supporting_modalities)
                + "."
            )

            return {
                "name": "loss_consistency",
                "status": "PASS",
                "score": 0.5,
                "evidence": evidence,
                "contradictions": contradictions,
            }

        return self._unavailable_check(
            "loss_consistency"
        )

    # ------------------------------------------------------------------
    # Date / location consistency
    # ------------------------------------------------------------------

    def _check_context_consistency(
        self,
        event_date: Optional[str],
        location: Optional[str],
        text_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        evidence = []
        contradictions = []

        if not event_date and not location:
            return self._unavailable_check(
                "context_consistency"
            )

        if event_date:
            evidence.append(
                f"Cross-modal claim event date is '{event_date}'."
            )

        if location:
            evidence.append(
                f"Cross-modal claim location/context is '{location}'."
            )

        # Satellite has a scene acquisition timestamp.
        scene_datetime = satellite_result.get("scene_datetime")

        if event_date and scene_datetime:
            satellite_date = str(scene_datetime)[:10]

            if satellite_date == str(event_date)[:10]:
                evidence.append(
                    "Satellite scene acquisition date matches the "
                    "claim event date."
                )
            else:
                contradictions.append(
                    "Satellite scene acquisition date "
                    f"'{satellite_date}' differs from claim event date "
                    f"'{event_date}'."
                )

        # Sensor event date.
        sensor_date = sensor_result.get("event_date")

        if event_date and sensor_date:
            if str(sensor_date)[:10] == str(event_date)[:10]:
                evidence.append(
                    "Sensor evidence date matches the claim event date."
                )
            else:
                contradictions.append(
                    f"Sensor evidence date '{sensor_date}' differs from "
                    f"claim event date '{event_date}'."
                )

        if contradictions:
            return {
                "name": "context_consistency",
                "status": "CONTRADICTION",
                "score": 0.0,
                "evidence": evidence,
                "contradictions": contradictions,
            }

        return {
            "name": "context_consistency",
            "status": "PASS",
            "score": 1.0,
            "evidence": evidence,
            "contradictions": [],
        }

    # ------------------------------------------------------------------
    # Modality health
    # ------------------------------------------------------------------

    def _check_modality_health(
        self,
        text_result: Dict[str, Any],
        image_result: Dict[str, Any],
        satellite_result: Dict[str, Any],
        sensor_result: Dict[str, Any],
    ) -> Dict[str, Any]:

        results = {
            "TextAgent": text_result,
            "ImageAgent": image_result,
            "SatelliteAgent": satellite_result,
            "SensorAgent": sensor_result,
        }

        evidence = []
        contradictions = []

        usable = 0

        for name, result in results.items():
            if not result:
                continue

            decision = result.get("decision")

            if decision == "ERROR":
                contradictions.append(
                    f"{name} returned an ERROR result."
                )
                continue

            if decision:
                usable += 1

                evidence.append(
                    f"{name} supplied usable evidence with decision "
                    f"'{decision}'."
                )

        if usable == 0:
            return self._unavailable_check(
                "modality_health"
            )

        return {
            "name": "modality_health",
            "status": "PASS",
            "score": min(1.0, usable / 4.0),
            "evidence": evidence,
            "contradictions": contradictions,
        }

    # ------------------------------------------------------------------
    # Agreement
    # ------------------------------------------------------------------

    def _calculate_agreement(
        self,
        checks: List[Dict[str, Any]],
        available_modalities: List[str],
    ) -> float:

        usable = [
            check
            for check in checks
            if check.get("status") != "UNAVAILABLE"
        ]

        if not usable:
            return 0.0

        weighted_scores = []
        weights = []

        for check in usable:
            status = check.get("status")

            if status == "PASS":
                score = float(
                    check.get("score", 1.0)
                )

            elif status == "CONTRADICTION":
                score = 0.0

            else:
                score = 0.5

            # Crop/event consistency are more meaningful than modality
            # health for cross-modal agreement.
            if check["name"] in {
                "crop_consistency",
                "event_consistency",
            }:
                weight = 2.0
            else:
                weight = 1.0

            weighted_scores.append(score * weight)
            weights.append(weight)

        if not weights:
            return 0.0

        return max(
            0.0,
            min(
                1.0,
                sum(weighted_scores) / sum(weights),
            ),
        )

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self,
        agreement: float,
        usable_check_count: int,
        modality_count: int,
        contradiction_count: int,
    ) -> float:

        coverage = min(
            modality_count / 4.0,
            1.0,
        )

        check_coverage = min(
            usable_check_count / 5.0,
            1.0,
        )

        contradiction_penalty = min(
            contradiction_count * 0.20,
            0.80,
        )

        confidence = (
            0.55 * agreement
            + 0.25 * coverage
            + 0.20 * check_coverage
            - contradiction_penalty
        )

        return max(
            0.0,
            min(1.0, confidence),
        )

    # ------------------------------------------------------------------
    # Risk / inconsistency
    # ------------------------------------------------------------------

    def _calculate_risk_score(
        self,
        agreement: float,
        contradiction_count: int,
        usable_check_count: int,
    ) -> float:

        if usable_check_count == 0:
            return 1.0

        contradiction_component = min(
            contradiction_count / 3.0,
            1.0,
        )

        disagreement_component = 1.0 - agreement

        risk = (
            0.65 * contradiction_component
            + 0.35 * disagreement_component
        )

        return max(
            0.0,
            min(1.0, risk),
        )

    # ------------------------------------------------------------------
    # Utilities
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

            if result:
                available.append(name)

        return available

    @staticmethod
    def _unavailable_check(
        name: str,
    ) -> Dict[str, Any]:

        return {
            "name": name,
            "status": "UNAVAILABLE",
            "score": 0.0,
            "evidence": [],
            "contradictions": [],
        }

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
            "agreement_score": 0.0,
            "cross_modal_checks": [],
            "available_modalities": [],
            "contradiction_count": 1,
            "risk_score_meaning": "cross_modal_inconsistency_score",
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


def analyze_cross_modal(
    text_result: Optional[Dict[str, Any]] = None,
    image_result: Optional[Dict[str, Any]] = None,
    satellite_result: Optional[Dict[str, Any]] = None,
    sensor_result: Optional[Dict[str, Any]] = None,
    claim: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    return get_cross_modal_agent().analyze(
        text_result=text_result,
        image_result=image_result,
        satellite_result=satellite_result,
        sensor_result=sensor_result,
        claim=claim,
    )


# ---------------------------------------------------------------------------
# Local test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    print("=" * 72)
    print("TRUTHCHAIN AGRICULTURE CROSS-MODAL AGENT TEST")
    print("=" * 72)

    # --------------------------------------------------------------
    # Simulated outputs from the already-tested agents.
    #
    # These are representative agent-contract results, not new model
    # predictions.
    # --------------------------------------------------------------

    text_result = {
        "agent": "TextAgent",
        "domain": "agriculture",
        "confidence": 1.0,
        "risk_score": 0.0,
        "decision": "PASS",
        "evidence": [
            "Claim narrative identifies crop as 'Wheat'.",
            "Claimed crop loss is 65.00%.",
        ],
        "contradictions": [],
        "model_version": "agriculture-text-agent-v0.1",
        "processing_time_ms": 1.0,
        "extracted_crop": "Wheat",
        "claimed_loss_percent": 65.0,
        "event_date": "2026-09-17",
        "damage_types": [
            "Heavy rain",
            "Waterlogging",
        ],
        "location": "Rampur",
    }

    image_result = {
        "agent": "ImageAgent",
        "domain": "agriculture",
        "confidence": 0.65,
        "risk_score": 0.35,
        "decision": "PASS",
        "evidence": [
            "Image model predicted Wheat.",
        ],
        "contradictions": [],
        "model_version": "TruthChain-Agriculture-Crop-v0.2",
        "processing_time_ms": 10.0,
        "predicted_crop": "Wheat",
        "image_confidence": 0.65,
        "claimed_crop": "Wheat",
        "claim_crop_match": True,
    }

    satellite_result = {
        "agent": "SatelliteAgent",
        "domain": "agriculture",
        "confidence": 0.70,
        "risk_score": 0.30,
        "decision": "PASS",
        "evidence": [
            "Satellite model predicted Wheat.",
        ],
        "contradictions": [],
        "model_version": "Satellite-CropAgent-v0.2",
        "processing_time_ms": 20.0,
        "claimed_crop": "Wheat",
        "predicted_crop": "Wheat",
        "evidence_decision": "SUPPORT",
        "scene_datetime": "2026-09-17T05:16:51.025000Z",
    }

    sensor_result = {
        "agent": "SensorAgent",
        "domain": "agriculture",
        "confidence": 1.0,
        "risk_score": 0.0,
        "decision": "PASS",
        "evidence": [
            "Heavy rain detected.",
            "Waterlogging detected.",
        ],
        "contradictions": [],
        "model_version": "agriculture-sensor-agent-v0.1",
        "processing_time_ms": 1.0,
        "claimed_event": "Heavy rain",
        "detected_events": [
            "Heavy rain",
            "Waterlogging",
        ],
        "evidence_decision": "SUPPORT",
        "event_date": "2026-09-17",
        "location": "Rampur",
    }

    print("\nCROSS-MODAL INPUT")
    print("-" * 72)

    print(
        json.dumps(
            {
                "text": text_result,
                "image": image_result,
                "satellite": satellite_result,
                "sensor": sensor_result,
            },
            indent=2,
        )
    )

    result = analyze_cross_modal(
        text_result=text_result,
        image_result=image_result,
        satellite_result=satellite_result,
        sensor_result=sensor_result,
    )

    print("\nCROSS-MODAL RESULT")
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
        print("CROSS-MODAL AGENT TEST: PASS")
    else:
        print("CROSS-MODAL AGENT TEST: FAIL")