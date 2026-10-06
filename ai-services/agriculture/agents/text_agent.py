"""
TruthChain Agriculture - LLM-Powered Text Agent

Uses Groq's OpenAI-compatible API with:
    model = openai/gpt-oss-120b

The LLM is responsible for semantic extraction from the claim narrative.

Python remains responsible for:
    - validating extracted values
    - normalizing fields
    - detecting deterministic contradictions
    - calculating extraction confidence
    - producing the standardized TruthChain agent contract

This agent does NOT perform fraud detection.

Downstream agents are responsible for cross-modal verification,
investigation, risk assessment, adversarial verification, and final decision.
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import config  # noqa: F401
from groq import Groq


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL_VERSION = "agriculture-text-agent-grok-v0.1"
DOMAIN = "agriculture"
AGENT_NAME = "TextAgent"

GROQ_MODEL = "openai/gpt-oss-120b"

# LLM extraction uses low reasoning because this is a structured extraction
# task rather than a complex reasoning task.
REASONING_EFFORT = "low"

# Maximum output tokens for the structured extraction response.
MAX_COMPLETION_TOKENS = 1200


# ---------------------------------------------------------------------------
# Supported agriculture crop aliases
# ---------------------------------------------------------------------------

CROP_ALIASES = {
    "wheat": "Wheat",
    "gehun": "Wheat",

    "mustard": "Mustard",
    "sarson": "Mustard",
    "rapeseed": "Mustard",
    "canola": "Mustard",

    "lentil": "Lentil",
    "lentils": "Lentil",
    "masoor": "Lentil",

    "fallow": "Fallow",

    "green pea": "Green pea",
    "green peas": "Green pea",
    "pea": "Green pea",
    "peas": "Green pea",
    "matar": "Green pea",

    "sugarcane": "Sugarcane",
    "sugar cane": "Sugarcane",
    "ganna": "Sugarcane",

    "garlic": "Garlic",
    "lahsun": "Garlic",

    "maize": "Maize",
    "corn": "Maize",
    "makka": "Maize",

    "gram": "Gram",
    "chickpea": "Gram",
    "chick peas": "Gram",
    "chickpeas": "Gram",
    "chana": "Gram",

    "coriander": "Coriander",
    "dhaniya": "Coriander",

    "potato": "Potato",
    "potatoes": "Potato",
    "aloo": "Potato",

    "bersem": "Bersem",
    "berseem": "Bersem",

    "rice": "Rice",
    "paddy": "Rice",
    "dhan": "Rice",
}


# ---------------------------------------------------------------------------
# Damage / event normalization
# ---------------------------------------------------------------------------

DAMAGE_ALIASES = {
    "hail": "Hail",
    "hailstorm": "Hail",

    "flood": "Flood",
    "flooding": "Flood",

    "drought": "Drought",

    "storm": "Storm",
    "cyclone": "Cyclone",

    "heavy rain": "Heavy rain",
    "heavy rainfall": "Heavy rain",
    "heavy rains": "Heavy rain",

    "excess rainfall": "Excess rainfall",
    "excess rain": "Excess rainfall",

    "waterlogging": "Waterlogging",
    "water logging": "Waterlogging",
    "water logged": "Waterlogging",
    "waterlogged": "Waterlogging",

    "pest": "Pest",
    "pest attack": "Pest",

    "insect": "Pest",
    "insect attack": "Pest",

    "disease": "Disease",
    "fungal disease": "Disease",

    "fire": "Fire",

    "lodging": "Lodging",

    "heatwave": "Heatwave",
    "heat wave": "Heatwave",

    "cold wave": "Cold wave",
    "coldwave": "Cold wave",

    "frost": "Frost",
}


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are the information extraction component of an agriculture insurance
claim verification system.

Your task is ONLY to extract factual information explicitly stated or
reasonably expressed in the claimant's narrative.

Do NOT:
- determine whether the claim is fraudulent
- decide whether the claim is valid
- estimate fraud probability
- invent missing information
- infer crop loss percentage from descriptions
- infer an event date that is not present
- infer a location that is not present

Return ONLY valid JSON.

Use exactly these fields:

{
  "crop": string or null,
  "field_area_hectares": number or null,
  "claimed_loss_percent": number or null,
  "event_date": "YYYY-MM-DD" or null,
  "damage_types": array of strings,
  "location": string or null
}

Extraction rules:

1. crop
   Extract the explicitly claimed crop.
   Normalize common names where obvious, for example:
   wheat -> Wheat
   gehun -> Wheat
   maize/corn -> Maize
   rice/paddy -> Rice
   mustard/sarson -> Mustard
   sugarcane/sugar cane -> Sugarcane

2. field_area_hectares
   Convert acres to hectares using:
   1 acre = 0.40468564224 hectares.
   Keep hectares as a numeric value.

3. claimed_loss_percent
   Extract the explicitly claimed crop loss/damage percentage.
   Do not calculate it from other information.

4. event_date
   Normalize explicit dates to YYYY-MM-DD.
   If the narrative says something relative such as "last week" and
   there is no explicit reference date supplied, return null.

5. damage_types
   Extract explicitly stated agricultural damage/event types such as:
   Heavy rain, Excess rainfall, Waterlogging, Flood, Drought, Hail,
   Storm, Cyclone, Pest, Disease, Fire, Lodging, Heatwave, Frost.

6. location
   Extract the explicitly stated village, district, location, or other
   useful geographic context.
   Do not invent a location.

If a field is not supported by the narrative, return null or [].
"""


# ---------------------------------------------------------------------------
# Text Agent
# ---------------------------------------------------------------------------


class TextAgent:
    """
    LLM-powered agriculture claim-text extraction agent.

    Groq:
        openai/gpt-oss-120b

    The LLM extracts semantic information from the narrative.

    Python validates and normalizes the result before producing the
    standardized TruthChain contract.

    Confidence represents extraction completeness/quality.

    risk_score represents extraction uncertainty:
        risk_score = 1 - confidence

    It is NOT a fraud probability.
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
        text: str,
        structured_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze an agriculture claim narrative using the Groq LLM.

        Parameters
        ----------
        text:
            Claim narrative supplied by the claimant/operator.

        structured_fields:
            Optional structured information already available outside
            the narrative. These fields supplement LLM extraction when
            the narrative does not contain the value.

        Returns
        -------
        dict
            Standardized TextAgent result.
        """

        start_time = time.perf_counter()

        try:
            if not isinstance(text, str):
                raise TypeError("text must be a string")

            cleaned_text = self._clean_text(text)

            if not cleaned_text:
                return self._error_result(
                    "Claim narrative is empty.",
                    start_time,
                )

            structured_fields = structured_fields or {}

            # ----------------------------------------------------------
            # LLM extraction
            # ----------------------------------------------------------

            extracted = self._llm_extract(cleaned_text)

            if not isinstance(extracted, dict):
                return self._error_result(
                    "LLM extraction did not return a JSON object.",
                    start_time,
                )

            # ----------------------------------------------------------
            # Normalize LLM fields
            # ----------------------------------------------------------

            extracted_crop = self._normalize_crop(
                extracted.get("crop")
            )

            extracted_area = self._normalize_area(
                extracted.get("field_area_hectares")
            )

            extracted_loss = self._normalize_loss(
                extracted.get("claimed_loss_percent")
            )

            extracted_date = self._normalize_date(
                extracted.get("event_date")
            )

            damage_types = self._normalize_damage_types(
                extracted.get("damage_types")
            )

            location = self._normalize_location(
                extracted.get("location")
            )

            # ----------------------------------------------------------
            # Structured fields can supplement LLM extraction.
            # ----------------------------------------------------------

            crop = (
                extracted_crop
                or self._normalize_crop(structured_fields.get("crop"))
            )

            area_hectares = (
                extracted_area
                if extracted_area is not None
                else self._structured_area(structured_fields)
            )

            loss_percent = (
                extracted_loss
                if extracted_loss is not None
                else self._structured_loss(structured_fields)
            )

            event_date = (
                extracted_date
                or self._normalize_date(
                    structured_fields.get("event_date")
                )
            )

            if not damage_types:
                damage_types = self._normalize_damage_types(
                    structured_fields.get("damage_types")
                )

            if not location:
                location = self._structured_location(structured_fields)

            # ----------------------------------------------------------
            # Deterministic validation
            # ----------------------------------------------------------

            contradictions: List[str] = []

            self._detect_contradictions(
                cleaned_text,
                loss_percent,
                area_hectares,
                contradictions,
            )

            # ----------------------------------------------------------
            # Evidence
            # ----------------------------------------------------------

            evidence: List[str] = []

            if crop:
                evidence.append(
                    f"Claim narrative identifies crop as '{crop}'."
                )

            if area_hectares is not None:
                evidence.append(
                    f"Claimed field area is "
                    f"{area_hectares:.4f} hectares."
                )

            if loss_percent is not None:
                evidence.append(
                    f"Claimed crop loss is "
                    f"{loss_percent:.2f}%."
                )

            if event_date:
                evidence.append(
                    f"Claimed event date is {event_date}."
                )

            if damage_types:
                evidence.append(
                    "Claim narrative reports damage/event type(s): "
                    + ", ".join(damage_types)
                    + "."
                )

            if location:
                evidence.append(
                    f"Claim narrative identifies location/context "
                    f"as '{location}'."
                )

            # ----------------------------------------------------------
            # Confidence
            # ----------------------------------------------------------

            fields_found = sum(
                value is not None
                for value in [
                    crop,
                    area_hectares,
                    loss_percent,
                    event_date,
                    location,
                ]
            )

            damage_found = bool(damage_types)

            confidence = self._calculate_confidence(
                fields_found=fields_found,
                damage_found=damage_found,
                text_length=len(cleaned_text),
                contradictions=contradictions,
            )

            # ----------------------------------------------------------
            # Decision
            # ----------------------------------------------------------

            if fields_found == 0 and not damage_found:
                decision = "INSUFFICIENT_DATA"
            elif contradictions:
                decision = "SUSPICIOUS"
            else:
                decision = "PASS"

            processing_time_ms = round(
                (time.perf_counter() - start_time) * 1000,
                3,
            )

            # ----------------------------------------------------------
            # Standardized TruthChain contract
            # ----------------------------------------------------------

            result = {
                "agent": self.agent_name,
                "domain": self.domain,
                "confidence": round(confidence, 6),
                "risk_score": round(1.0 - confidence, 6),
                "decision": decision,
                "evidence": evidence,
                "contradictions": contradictions,
                "model_version": self.model_version,
                "processing_time_ms": processing_time_ms,

                # Agriculture-specific extracted information.
                "extracted_crop": crop,
                "field_area_hectares": area_hectares,
                "claimed_loss_percent": loss_percent,
                "event_date": event_date,
                "damage_types": damage_types,
                "location": location,

                # LLM audit information.
                "llm_provider": "groq",
                "llm_model": self.model,

                # Audit/debug information.
                "text_length": len(cleaned_text),
                "fields_extracted": fields_found,
                "raw_text": text,
            }

            return result

        except Exception as exc:
            return self._error_result(
                str(exc),
                start_time,
            )

    # ------------------------------------------------------------------
    # LLM extraction
    # ------------------------------------------------------------------

    def _llm_extract(self, text: str) -> Dict[str, Any]:
        """
        Ask GPT-OSS to extract structured agriculture claim information.
        Falls back to heuristic regex extraction if LLM client is unavailable.
        """
        if self.client is None:
            return self._heuristic_extract(text)

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
                        "Extract the agriculture claim information from "
                        "the following narrative.\n\n"
                        f"CLAIM NARRATIVE:\n{text}"
                    ),
                },
            ],
            temperature=0,
            max_completion_tokens=MAX_COMPLETION_TOKENS,
            reasoning_effort=REASONING_EFFORT,
            include_reasoning=False,
            response_format={"type": "json_object"},
        )

        message = response.choices[0].message

        content = message.content

        if not content:
            raise RuntimeError(
                "Groq returned an empty extraction response."
            )

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Groq returned invalid JSON: {content}"
            ) from exc

        if not isinstance(parsed, dict):
            raise RuntimeError(
                "Groq extraction response must be a JSON object."
            )

        return parsed

    def _heuristic_extract(self, text: str) -> Dict[str, Any]:
        """Heuristic regex extraction when Groq LLM client is not available."""
        text_lower = text.lower()
        extracted_crop = None
        for alias, canonical in CROP_ALIASES.items():
            if alias in text_lower:
                extracted_crop = canonical
                break

        loss_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
        loss_pct = float(loss_match.group(1)) if loss_match else None

        area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:hectare|ha|acre)", text_lower)
        area = float(area_match.group(1)) if area_match else None

        date_match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        event_date = date_match.group(1) if date_match else None

        damage_types = []
        if "rain" in text_lower or "flood" in text_lower:
            damage_types.append("Heavy rain")
        if "hail" in text_lower:
            damage_types.append("Hailstorm")
        if "drought" in text_lower:
            damage_types.append("Drought")

        return {
            "crop": extracted_crop,
            "field_area_hectares": area,
            "claimed_loss_percent": loss_pct,
            "event_date": event_date,
            "damage_types": damage_types,
            "location": None,
        }

    # ------------------------------------------------------------------
    # Crop normalization
    # ------------------------------------------------------------------

    def _normalize_crop(
        self,
        value: Any,
    ) -> Optional[str]:

        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        normalized = value.lower()

        if normalized in CROP_ALIASES:
            return CROP_ALIASES[normalized]

        # Direct canonical-name matching.
        for canonical in set(CROP_ALIASES.values()):
            if normalized == canonical.lower():
                return canonical

        return value

    # ------------------------------------------------------------------
    # Area normalization
    # ------------------------------------------------------------------

    def _normalize_area(
        self,
        value: Any,
    ) -> Optional[float]:

        if value is None:
            return None

        try:
            area = float(value)
        except (TypeError, ValueError):
            return None

        if area <= 0:
            return None

        return area

    def _structured_area(
        self,
        structured_fields: Dict[str, Any],
    ) -> Optional[float]:

        value = structured_fields.get("area_hectares")

        if value is not None:
            try:
                area = float(value)

                if area > 0:
                    return area

            except (TypeError, ValueError):
                pass

        value = structured_fields.get("area")

        if value is None:
            return None

        try:
            value = float(value)
        except (TypeError, ValueError):
            return None

        if value <= 0:
            return None

        unit = str(
            structured_fields.get(
                "area_unit",
                "hectares",
            )
        ).lower()

        if unit in {"acre", "acres"}:
            return value * 0.40468564224

        return value

    # ------------------------------------------------------------------
    # Loss normalization
    # ------------------------------------------------------------------

    def _normalize_loss(
        self,
        value: Any,
    ) -> Optional[float]:

        if value is None:
            return None

        try:
            loss = float(value)
        except (TypeError, ValueError):
            return None

        if 0.0 <= loss <= 100.0:
            return loss

        return None

    def _structured_loss(
        self,
        structured_fields: Dict[str, Any],
    ) -> Optional[float]:

        value = structured_fields.get("claimed_loss_percent")

        if value is None:
            value = structured_fields.get("loss_percent")

        return self._normalize_loss(value)

    # ------------------------------------------------------------------
    # Date normalization
    # ------------------------------------------------------------------

    def _normalize_date(
        self,
        value: Any,
    ) -> Optional[str]:

        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        # Already ISO-like.
        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            return parsed.strftime("%Y-%m-%d")

        except ValueError:
            pass

        # Common explicit formats.
        patterns = [
            r"\b(?P<day>\d{1,2})[-/.]"
            r"(?P<month>\d{1,2})[-/.]"
            r"(?P<year>\d{4})\b",

            r"\b(?P<year>\d{4})[-/.]"
            r"(?P<month>\d{1,2})[-/.]"
            r"(?P<day>\d{1,2})\b",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                value,
            )

            if not match:
                continue

            try:
                date_value = datetime(
                    year=int(match.group("year")),
                    month=int(match.group("month")),
                    day=int(match.group("day")),
                )

                return date_value.strftime("%Y-%m-%d")

            except ValueError:
                continue

        return None

    # ------------------------------------------------------------------
    # Damage/event normalization
    # ------------------------------------------------------------------

    def _normalize_damage_types(
        self,
        values: Any,
    ) -> List[str]:

        if values is None:
            return []

        if isinstance(values, str):
            values = [values]

        if not isinstance(values, list):
            return []

        normalized_values: List[str] = []

        for value in values:
            if value is None:
                continue

            text = str(value).strip()

            if not text:
                continue

            normalized = text.lower()

            canonical = DAMAGE_ALIASES.get(
                normalized,
                text,
            )

            if canonical not in normalized_values:
                normalized_values.append(canonical)

        return sorted(normalized_values)

    # ------------------------------------------------------------------
    # Location normalization
    # ------------------------------------------------------------------

    def _normalize_location(
        self,
        value: Any,
    ) -> Optional[str]:

        if value is None:
            return None

        if isinstance(value, dict):
            parts: List[str] = []

            for key in (
                "village",
                "district",
                "state",
                "country",
            ):
                item = value.get(key)

                if item:
                    parts.append(str(item).strip())

            return ", ".join(parts) if parts else None

        value = str(value).strip()

        return value or None

    def _structured_location(
        self,
        structured_fields: Dict[str, Any],
    ) -> Optional[str]:

        return self._normalize_location(
            structured_fields.get("location")
        )

    # ------------------------------------------------------------------
    # Deterministic contradiction validation
    # ------------------------------------------------------------------

    def _detect_contradictions(
        self,
        text: str,
        loss_percent: Optional[float],
        area_hectares: Optional[float],
        contradictions: List[str],
    ) -> None:

        if loss_percent is not None:
            if loss_percent > 100.0 or loss_percent < 0.0:
                contradictions.append(
                    "Claimed loss percentage is outside "
                    "the valid 0-100% range."
                )

        if area_hectares is not None and area_hectares <= 0:
            contradictions.append(
                "Claimed field area must be greater than zero."
            )

        # Detect both explicit no-loss and substantial-loss statements.
        no_loss = bool(
            re.search(
                r"\b(?:no loss|zero loss|no damage)\b",
                text,
                flags=re.IGNORECASE,
            )
        )

        substantial_loss = bool(
            re.search(
                r"\b(?:[5-9]\d|100)\s*%\s*(?:loss|damage)\b",
                text,
                flags=re.IGNORECASE,
            )
        )

        if no_loss and substantial_loss:
            contradictions.append(
                "Narrative contains both a no-loss statement "
                "and a substantial-loss statement."
            )

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self,
        fields_found: int,
        damage_found: bool,
        text_length: int,
        contradictions: List[str],
    ) -> float:

        # Five principal claim fields.
        field_score = fields_found / 5.0

        # Damage/event information is useful but not mandatory.
        damage_score = 0.10 if damage_found else 0.0

        # Longer narratives provide more extraction context.
        if text_length < 20:
            length_score = 0.0
        elif text_length < 50:
            length_score = 0.05
        else:
            length_score = 0.10

        confidence = (
            0.80 * field_score
            + damage_score
            + length_score
        )

        # Contradictions reduce extraction confidence.
        if contradictions:
            confidence -= min(
                0.25,
                0.10 * len(contradictions),
            )

        return max(
            0.0,
            min(1.0, confidence),
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_text(text: str) -> str:
        return re.sub(
            r"\s+",
            " ",
            text.strip(),
        )

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

            "extracted_crop": None,
            "field_area_hectares": None,
            "claimed_loss_percent": None,
            "event_date": None,
            "damage_types": [],
            "location": None,

            "llm_provider": "groq",
            "llm_model": self.model,

            "text_length": 0,
            "fields_extracted": 0,
        }


# ---------------------------------------------------------------------------
# Singleton / convenience API
# ---------------------------------------------------------------------------

_text_agent: Optional[TextAgent] = None


def get_text_agent() -> TextAgent:
    global _text_agent

    if _text_agent is None:
        _text_agent = TextAgent()

    return _text_agent


def analyze_claim_text(
    text: str,
    structured_fields: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:

    return get_text_agent().analyze(
        text=text,
        structured_fields=structured_fields,
    )


# ---------------------------------------------------------------------------
# Local test
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    print("=" * 72)
    print("TRUTHCHAIN AGRICULTURE LLM TEXT AGENT TEST")
    print("=" * 72)

    sample_claim = (
        "My wheat crop was damaged by heavy rain and waterlogging in "
        "Village Rampur, District Lucknow. The field area is 2 hectares "
        "and approximately 65% crop loss occurred. The event happened "
        "on 17-09-2026."
    )

    print("\nMODEL")
    print("-" * 72)
    print(GROQ_MODEL)

    print("\nINPUT CLAIM")
    print("-" * 72)
    print(sample_claim)

    result = analyze_claim_text(sample_claim)

    print("\nAGRICULTURE TEXT AGENT RESULT")
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
        print("TEXT AGENT TEST: PASS")
    else:
        print("TEXT AGENT TEST: FAIL")