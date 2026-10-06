"""
TruthChain Agriculture - Sensor Agent

Deterministic environmental/weather evidence agent.

This agent evaluates structured sensor/weather observations against an
agriculture insurance claim narrative.

It is intentionally NOT a trained weather model and does NOT determine
fraud. Its risk_score represents evidence uncertainty, not final fraud risk.

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


MODEL_VERSION = "agriculture-sensor-agent-v0.1"
DOMAIN = "agriculture"
AGENT_NAME = "SensorAgent"


# ---------------------------------------------------------------------------
# Event thresholds
# ---------------------------------------------------------------------------
#
# These are screening thresholds for the deterministic evidence layer.
# They are NOT insurance policy thresholds and must be calibrated against
# real historical agricultural/weather data before production use.
#

DEFAULT_THRESHOLDS = {
    "heavy_rain_mm_24h": 64.5,
    "extreme_rain_mm_24h": 115.6,
    "flood_rain_mm_24h": 204.5,
    "high_wind_kmh": 50.0,
    "extreme_wind_kmh": 80.0,
    "heatwave_temp_c": 40.0,
    "frost_temp_c": 2.0,
    "waterlogging_soil_moisture": 0.85,
    "drought_soil_moisture": 0.20,
}


# ---------------------------------------------------------------------------
# Sensor Agent
# ---------------------------------------------------------------------------

class SensorAgent:
    """
    Deterministic agriculture environmental evidence agent.

    Supported observations include:
        - rainfall_mm_24h
        - rainfall_mm_7d
        - temperature_c
        - max_temperature_c
        - min_temperature_c
        - wind_speed_kmh
        - soil_moisture
        - relative_humidity
        - flood_detected
        - drought_detected
        - waterlogging_detected

    The agent compares observed conditions with the claimed damage/event
    type supplied by the caller.
    """

    def __init__(
        self,
        thresholds: Optional[Dict[str, float]] = None,
    ) -> None:

        self.model_version = MODEL_VERSION
        self.domain = DOMAIN
        self.agent_name = AGENT_NAME

        self.thresholds = dict(DEFAULT_THRESHOLDS)

        if thresholds:
            self.thresholds.update(thresholds)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        observations: Dict[str, Any],
        claimed_event: Optional[str] = None,
        event_date: Optional[str] = None,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze structured environmental observations.

        Parameters
        ----------
        observations:
            Dictionary containing sensor/weather observations.

        claimed_event:
            Claimed damage/event type, for example:
                "heavy rain"
                "flood"
                "drought"
                "hail"
                "storm"
                "waterlogging"

        event_date:
            Optional claim event date.

        location:
            Optional observation location.

        Returns
        -------
        dict
            Standardized SensorAgent result.
        """

        start_time = time.perf_counter()

        try:
            if not isinstance(observations, dict):
                raise TypeError("observations must be a dictionary")

            cleaned = self._clean_observations(observations)

            if not cleaned:
                return self._error_result(
                    "No valid sensor observations were supplied.",
                    start_time,
                )

            evidence: List[str] = []
            contradictions: List[str] = []

            detected_events = self._detect_environmental_events(
                cleaned
            )

            # ----------------------------------------------------------
            # Observation evidence
            # ----------------------------------------------------------

            self._build_observation_evidence(
                cleaned,
                evidence,
            )

            if event_date:
                evidence.append(
                    f"Sensor evidence is associated with claim event date "
                    f"'{event_date}'."
                )

            if location:
                evidence.append(
                    f"Sensor evidence location/context: '{location}'."
                )

            # ----------------------------------------------------------
            # Event comparison
            # ----------------------------------------------------------

            normalized_event = self._normalize_event(
                claimed_event
            )

            evidence_decision = "UNCERTAIN"

            if normalized_event:
                evidence.append(
                    f"Claimed environmental event: '{normalized_event}'."
                )

                matching_events = self._matching_events(
                    normalized_event,
                    detected_events,
                )

                if matching_events:
                    evidence.append(
                        "Sensor observations provide evidence consistent "
                        "with the claimed environmental event: "
                        + ", ".join(matching_events)
                        + "."
                    )

                    evidence_decision = "SUPPORT"

                else:
                    contradiction = self._event_contradiction(
                        normalized_event,
                        detected_events,
                    )

                    if contradiction:
                        contradictions.append(contradiction)

                    if detected_events:
                        evidence.append(
                            "Sensor observations detected environmental "
                            "conditions, but they do not directly support "
                            f"the claimed event '{normalized_event}'."
                        )
                        evidence_decision = "CONTRADICTION"
                    else:
                        evidence.append(
                            "Available sensor observations do not provide "
                            f"clear evidence for claimed event "
                            f"'{normalized_event}'."
                        )
                        evidence_decision = "UNCERTAIN"

            else:
                if detected_events:
                    evidence.append(
                        "Detected environmental condition(s): "
                        + ", ".join(detected_events)
                        + "."
                    )
                    evidence_decision = "SUPPORT"
                else:
                    evidence.append(
                        "No threshold-level environmental event was "
                        "detected from the supplied observations."
                    )
                    evidence_decision = "UNCERTAIN"

            # ----------------------------------------------------------
            # Confidence
            # ----------------------------------------------------------

            confidence = self._calculate_confidence(
                observations=cleaned,
                detected_events=detected_events,
                claimed_event=normalized_event,
                evidence_decision=evidence_decision,
            )

            # This is evidence uncertainty, NOT fraud probability.
            risk_score = 1.0 - confidence

            if evidence_decision == "CONTRADICTION":
                decision = "SUSPICIOUS"
            elif evidence_decision == "UNCERTAIN":
                decision = "INSUFFICIENT_DATA"
            else:
                decision = "PASS"

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

                # Agriculture-specific evidence fields.
                "claimed_event": normalized_event,
                "detected_events": detected_events,
                "evidence_decision": evidence_decision,
                "event_date": event_date,
                "location": location,
                "observations": cleaned,
                "thresholds": dict(self.thresholds),

                # Explicit semantic clarification.
                "risk_score_meaning": "environmental_evidence_uncertainty",
                "agent_version": MODEL_VERSION,
            }

        except Exception as exc:
            return self._error_result(
                str(exc),
                start_time,
            )

    # ------------------------------------------------------------------
    # Observation cleaning
    # ------------------------------------------------------------------

    def _clean_observations(
        self,
        observations: Dict[str, Any],
    ) -> Dict[str, float | bool | str]:

        cleaned: Dict[str, float | bool | str] = {}

        numeric_fields = {
            "rainfall_mm_24h",
            "rainfall_mm_7d",
            "temperature_c",
            "max_temperature_c",
            "min_temperature_c",
            "wind_speed_kmh",
            "soil_moisture",
            "relative_humidity",
        }

        boolean_fields = {
            "flood_detected",
            "drought_detected",
            "waterlogging_detected",
        }

        for key in numeric_fields:
            if key not in observations:
                continue

            value = observations[key]

            try:
                value = float(value)
            except (TypeError, ValueError):
                continue

            if value != value:
                continue

            cleaned[key] = value

        for key in boolean_fields:
            if key not in observations:
                continue

            value = observations[key]

            if isinstance(value, bool):
                cleaned[key] = value
            elif isinstance(value, str):
                normalized = value.strip().lower()

                if normalized in {"true", "yes", "1"}:
                    cleaned[key] = True
                elif normalized in {"false", "no", "0"}:
                    cleaned[key] = False

        return cleaned

    # ------------------------------------------------------------------
    # Environmental event detection
    # ------------------------------------------------------------------

    def _detect_environmental_events(
        self,
        observations: Dict[str, Any],
    ) -> List[str]:

        events = set()

        rainfall_24h = observations.get("rainfall_mm_24h")
        rainfall_7d = observations.get("rainfall_mm_7d")

        temperature = observations.get("temperature_c")
        max_temperature = observations.get("max_temperature_c")
        min_temperature = observations.get("min_temperature_c")

        wind_speed = observations.get("wind_speed_kmh")
        soil_moisture = observations.get("soil_moisture")

        # Explicit sensor flags.
        if observations.get("flood_detected") is True:
            events.add("Flood")

        if observations.get("drought_detected") is True:
            events.add("Drought")

        if observations.get("waterlogging_detected") is True:
            events.add("Waterlogging")

        # Rainfall thresholds.
        if (
            rainfall_24h is not None
            and rainfall_24h >= self.thresholds["flood_rain_mm_24h"]
        ):
            events.add("Flood")

        elif (
            rainfall_24h is not None
            and rainfall_24h >= self.thresholds["extreme_rain_mm_24h"]
        ):
            events.add("Excess rainfall")

        elif (
            rainfall_24h is not None
            and rainfall_24h >= self.thresholds["heavy_rain_mm_24h"]
        ):
            events.add("Heavy rain")

        # Seven-day rainfall can support waterlogging conditions.
        if (
            rainfall_7d is not None
            and rainfall_7d >= self.thresholds["flood_rain_mm_24h"] * 2
        ):
            events.add("Excess rainfall")

        # Soil moisture.
        if (
            soil_moisture is not None
            and soil_moisture >= self.thresholds["waterlogging_soil_moisture"]
        ):
            events.add("Waterlogging")

        elif (
            soil_moisture is not None
            and soil_moisture <= self.thresholds["drought_soil_moisture"]
        ):
            events.add("Drought")

        # Temperature.
        highest_temperature = max(
            value
            for value in [
                temperature,
                max_temperature,
            ]
            if value is not None
        ) if any(
            value is not None
            for value in [temperature, max_temperature]
        ) else None

        lowest_temperature = min(
            value
            for value in [
                temperature,
                min_temperature,
            ]
            if value is not None
        ) if any(
            value is not None
            for value in [temperature, min_temperature]
        ) else None

        if (
            highest_temperature is not None
            and highest_temperature >= self.thresholds["heatwave_temp_c"]
        ):
            events.add("Heatwave")

        if (
            lowest_temperature is not None
            and lowest_temperature <= self.thresholds["frost_temp_c"]
        ):
            events.add("Frost")

        # Wind.
        if (
            wind_speed is not None
            and wind_speed >= self.thresholds["extreme_wind_kmh"]
        ):
            events.add("Storm")

        elif (
            wind_speed is not None
            and wind_speed >= self.thresholds["high_wind_kmh"]
        ):
            events.add("High wind")

        return sorted(events)

    # ------------------------------------------------------------------
    # Event normalization
    # ------------------------------------------------------------------

    def _normalize_event(
        self,
        event: Optional[str],
    ) -> Optional[str]:

        if event is None:
            return None

        normalized = str(event).strip().lower()

        if not normalized:
            return None

        aliases = {
            "rain": "Heavy rain",
            "heavy rainfall": "Heavy rain",
            "heavy rain": "Heavy rain",
            "excess rain": "Excess rainfall",
            "excess rainfall": "Excess rainfall",
            "flood": "Flood",
            "flooding": "Flood",
            "water logging": "Waterlogging",
            "waterlogging": "Waterlogging",
            "drought": "Drought",
            "storm": "Storm",
            "cyclone": "Storm",
            "high wind": "High wind",
            "heat wave": "Heatwave",
            "heatwave": "Heatwave",
            "frost": "Frost",
        }

        return aliases.get(
            normalized,
            str(event).strip(),
        )

    # ------------------------------------------------------------------
    # Event matching
    # ------------------------------------------------------------------

    def _matching_events(
        self,
        claimed_event: str,
        detected_events: List[str],
    ) -> List[str]:

        matches = []

        for detected in detected_events:
            if detected == claimed_event:
                matches.append(detected)
                continue

            # Related conditions.
            if claimed_event == "Heavy rain" and detected in {
                "Excess rainfall",
                "Flood",
            }:
                matches.append(detected)

            elif claimed_event == "Excess rainfall" and detected in {
                "Flood",
            }:
                matches.append(detected)

            elif claimed_event == "Flood" and detected in {
                "Waterlogging",
                "Excess rainfall",
            }:
                matches.append(detected)

            elif claimed_event == "Waterlogging" and detected in {
                "Flood",
                "Excess rainfall",
            }:
                matches.append(detected)

            elif claimed_event == "Storm" and detected in {
                "High wind",
            }:
                matches.append(detected)

        return matches

    def _event_contradiction(
        self,
        claimed_event: str,
        detected_events: List[str],
    ) -> Optional[str]:

        if not detected_events:
            return (
                f"No threshold-level sensor evidence supports the "
                f"claimed event '{claimed_event}'."
            )

        return (
            f"Sensor observations detected {', '.join(detected_events)}, "
            f"but did not detect conditions directly supporting the "
            f"claimed event '{claimed_event}'."
        )

    # ------------------------------------------------------------------
    # Evidence text
    # ------------------------------------------------------------------

    def _build_observation_evidence(
        self,
        observations: Dict[str, Any],
        evidence: List[str],
    ) -> None:

        if "rainfall_mm_24h" in observations:
            evidence.append(
                f"Observed 24-hour rainfall: "
                f"{observations['rainfall_mm_24h']:.2f} mm."
            )

        if "rainfall_mm_7d" in observations:
            evidence.append(
                f"Observed 7-day rainfall: "
                f"{observations['rainfall_mm_7d']:.2f} mm."
            )

        if "temperature_c" in observations:
            evidence.append(
                f"Observed temperature: "
                f"{observations['temperature_c']:.2f} °C."
            )

        if "max_temperature_c" in observations:
            evidence.append(
                f"Observed maximum temperature: "
                f"{observations['max_temperature_c']:.2f} °C."
            )

        if "min_temperature_c" in observations:
            evidence.append(
                f"Observed minimum temperature: "
                f"{observations['min_temperature_c']:.2f} °C."
            )

        if "wind_speed_kmh" in observations:
            evidence.append(
                f"Observed wind speed: "
                f"{observations['wind_speed_kmh']:.2f} km/h."
            )

        if "soil_moisture" in observations:
            evidence.append(
                f"Observed soil moisture: "
                f"{observations['soil_moisture']:.3f}."
            )

        if "relative_humidity" in observations:
            evidence.append(
                f"Observed relative humidity: "
                f"{observations['relative_humidity']:.2f}%."
            )

        if observations.get("flood_detected") is True:
            evidence.append(
                "Sensor input explicitly reports flood conditions."
            )

        if observations.get("drought_detected") is True:
            evidence.append(
                "Sensor input explicitly reports drought conditions."
            )

        if observations.get("waterlogging_detected") is True:
            evidence.append(
                "Sensor input explicitly reports waterlogging conditions."
            )

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self,
        observations: Dict[str, Any],
        detected_events: List[str],
        claimed_event: Optional[str],
        evidence_decision: str,
    ) -> float:

        observation_count = len(observations)

        # More independent observations provide more evidence.
        observation_score = min(
            observation_count / 5.0,
            1.0,
        )

        event_score = 0.0

        if detected_events:
            event_score = 0.25

        if claimed_event and evidence_decision == "SUPPORT":
            event_score = 0.45

        elif (
            claimed_event
            and evidence_decision == "CONTRADICTION"
        ):
            event_score = 0.35

        confidence = (
            0.55 * observation_score
            + event_score
        )

        # A single explicit event flag is still useful evidence.
        if observation_count == 1 and detected_events:
            confidence = max(confidence, 0.55)

        return max(
            0.0,
            min(1.0, confidence),
        )

    # ------------------------------------------------------------------
    # Error handling
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
            "claimed_event": None,
            "detected_events": [],
            "evidence_decision": "ERROR",
            "event_date": None,
            "location": None,
            "observations": {},
            "thresholds": dict(self.thresholds),
            "risk_score_meaning": "environmental_evidence_uncertainty",
            "agent_version": MODEL_VERSION,
        }


# ---------------------------------------------------------------------------
# Singleton / convenience API
# ---------------------------------------------------------------------------

_sensor_agent: Optional[SensorAgent] = None


def get_sensor_agent() -> SensorAgent:
    global _sensor_agent

    if _sensor_agent is None:
        _sensor_agent = SensorAgent()

    return _sensor_agent


def analyze_sensor_evidence(
    observations: Dict[str, Any],
    claimed_event: Optional[str] = None,
    event_date: Optional[str] = None,
    location: Optional[str] = None,
) -> Dict[str, Any]:

    return get_sensor_agent().analyze(
        observations=observations,
        claimed_event=claimed_event,
        event_date=event_date,
        location=location,
    )


# ---------------------------------------------------------------------------
# Local test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    print("=" * 72)
    print("TRUTHCHAIN AGRICULTURE SENSOR AGENT TEST")
    print("=" * 72)

    sample_observations = {
        "rainfall_mm_24h": 82.4,
        "rainfall_mm_7d": 146.7,
        "temperature_c": 27.3,
        "wind_speed_kmh": 18.5,
        "soil_moisture": 0.91,
        "relative_humidity": 94.0,
    }

    print("\nSAMPLE SENSOR OBSERVATIONS")
    print("-" * 72)

    print(
        json.dumps(
            sample_observations,
            indent=2,
        )
    )

    result = analyze_sensor_evidence(
        observations=sample_observations,
        claimed_event="heavy rain",
        event_date="2026-09-17",
        location="Rampur",
    )

    print("\nAGRICULTURE SENSOR AGENT RESULT")
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
        print("SENSOR AGENT TEST: PASS")
    else:
        print("SENSOR AGENT TEST: FAIL")