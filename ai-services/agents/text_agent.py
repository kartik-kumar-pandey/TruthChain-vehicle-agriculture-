"""
TruthChain 2.0 - TextAgent

LLM-backed motor insurance claim-description analysis.

Provider:
    Groq

Model:
    openai/gpt-oss-120b

Purpose:
    Analyze claimant-provided text and produce structured evidence
    for the TruthChain multimodal fraud-verification pipeline.

IMPORTANT:
    TextAgent does NOT make the final claim fraud decision.

    It produces textual evidence that will later be consumed by:

        - CrossModalAgent
        - Risk Engine
        - InvestigationAgent
        - AdversarialVerifier
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from groq import Groq


# ============================================================
# PATHS / ENVIRONMENT
# ============================================================

# Consolidated production structure:
#
# ai-services/
# ├── .env
# ├── agents/
# │   └── text_agent.py
# ├── graph/
# ├── vision/
# └── ml/

BASE_DIR = Path(
    __file__
).resolve().parent.parent

ENV_FILE = (
    BASE_DIR
    / ".env"
)

load_dotenv(
    dotenv_path=ENV_FILE
)


# ============================================================
# CONSTANTS
# ============================================================

MODEL_VERSION = "text-agent-v2.0"

GROQ_MODEL = (
    "openai/gpt-oss-120b"
)

MIN_TEXT_LENGTH = 10


# ============================================================
# TEXT AGENT
# ============================================================

class TextAgent:
    """
    TruthChain TextAgent.

    Uses an LLM to analyze a motor-insurance claim narrative.

    The LLM is responsible for semantic understanding.

    The agent converts the LLM response into a stable,
    machine-readable TruthChain structure.

    IMPORTANT:

        The LLM's assessment is evidence only.

        It is NOT the final fraud determination.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = GROQ_MODEL,
    ):
        self.model = model

        self.model_version = (
            MODEL_VERSION
        )

        # ----------------------------------------------------
        # API KEY
        # ----------------------------------------------------

        self.api_key = (
            api_key
            or os.getenv(
                "GROQ_API_KEY"
            )
        )

        if not self.api_key:

            raise RuntimeError(
                "GROQ_API_KEY was not found. "
                f"Add GROQ_API_KEY to {ENV_FILE}"
            )

        # ----------------------------------------------------
        # GROQ CLIENT
        # ----------------------------------------------------

        self.client = Groq(
            api_key=self.api_key
        )


    # ========================================================
    # SYSTEM PROMPT
    # ========================================================

    def _build_system_prompt(
        self,
    ) -> str:
        """
        Build the system prompt used by the LLM.
        """

        return """
You are the TextAgent in TruthChain 2.0, a motor-insurance
claim verification system.

Your job is to analyze the claimant's written incident narrative.

You are NOT the final fraud decision-maker.

Do NOT automatically label a claim fraudulent simply because
the claimant reports vehicle damage.

Your task is to extract and assess textual evidence.

Analyze:

1. Incident type
   Examples:
   collision, theft, fire, vandalism, weather_damage,
   unknown

2. Damage described by the claimant
   Use only these canonical labels when applicable:
   dent
   scratch
   crack
   glass_shatter
   lamp_broken
   tire_flat

3. Timeline information
   Extract stated times, dates, or relative time descriptions.

4. Location information
   Extract locations if explicitly mentioned.

5. Vehicle activity
   Examples:
   driving, parked, stopped, turning, reversing,
   braking, overtaking

6. Narrative consistency
   Determine whether the narrative contains internal
   contradictions or ambiguity.

7. Investigation signals
   Identify statements that deserve later verification.

IMPORTANT RULES:

- Do not invent facts.
- Do not assume fraud.
- Do not treat uncertainty as proof of fraud.
- Do not treat damage as proof of fraud.
- Do not infer information that is not present.
- If information is missing, use null or an empty list.
- Contradictions must be based on statements actually present
  in the narrative.
- Keep the reasoning concise and evidence-based.

Return ONLY valid JSON.
"""


    # ========================================================
    # USER PROMPT
    # ========================================================

    def _build_user_prompt(
        self,
        text: str,
    ) -> str:
        """
        Build the user prompt containing the claim narrative.
        """

        return f"""
Analyze the following motor-insurance claim narrative.

CLAIM NARRATIVE:
{text}

Return JSON using exactly this structure:

{{
  "incident_type": "collision | theft | fire | vandalism | weather_damage | unknown",
  "damage_types": [],
  "time_mentions": [],
  "location_mentions": [],
  "vehicle_mentions": [],
  "action_mentions": [],
  "summary": "",
  "contradictions": [],
  "signals": [],
  "assessment": "CONSISTENT | AMBIGUOUS | INCONSISTENT"
}}

Requirements:

- damage_types must contain only canonical TruthChain labels.
- time_mentions must contain only times/dates actually stated.
- location_mentions must contain only locations actually stated.
- vehicle_mentions must contain only vehicle types actually stated.
- action_mentions must contain only actions actually stated.
- contradictions must contain only genuine internal contradictions.
- signals are possible investigation points, not fraud findings.
- assessment must reflect the narrative itself.
- Do not calculate a final fraud score.
"""


    # ========================================================
    # JSON EXTRACTION
    # ========================================================

    def _parse_json(
        self,
        content: str,
    ) -> Dict[str, Any]:
        """
        Parse JSON returned by the LLM.

        Handles:
            - pure JSON
            - markdown code fences
            - JSON embedded in surrounding text
        """

        if not content:

            raise ValueError(
                "LLM returned an empty response."
            )

        content = content.strip()


        # ----------------------------------------------------
        # Remove markdown code fences.
        # ----------------------------------------------------

        if content.startswith("```"):

            lines = content.splitlines()

            if lines:
                lines = lines[1:]

            if (
                lines
                and lines[-1].strip()
                == "```"
            ):

                lines = lines[:-1]

            content = "\n".join(
                lines
            ).strip()


        # ----------------------------------------------------
        # Direct JSON parse.
        # ----------------------------------------------------

        try:

            parsed = json.loads(
                content
            )

        except json.JSONDecodeError:

            # ------------------------------------------------
            # Try extracting the outer JSON object.
            # ------------------------------------------------

            start = content.find(
                "{"
            )

            end = content.rfind(
                "}"
            )

            if (
                start == -1
                or end == -1
                or end <= start
            ):

                raise ValueError(
                    "LLM response did not contain valid JSON."
                )

            json_text = content[
                start : end + 1
            ]

            try:

                parsed = json.loads(
                    json_text
                )

            except json.JSONDecodeError as exc:

                raise ValueError(
                    "LLM response contained malformed JSON."
                ) from exc


        if not isinstance(
            parsed,
            dict,
        ):

            raise ValueError(
                "LLM JSON response must be an object."
            )

        return parsed


    # ========================================================
    # NORMALIZATION
    # ========================================================

    def _normalize_result(
        self,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Normalize the LLM output into a predictable structure.

        Invalid or missing assessment values are treated as
        AMBIGUOUS rather than CONSISTENT.

        This is intentionally fail-closed.
        """

        allowed_damage_types = {
            "dent",
            "scratch",
            "crack",
            "glass_shatter",
            "lamp_broken",
            "tire_flat",
        }


        # ----------------------------------------------------
        # Incident type
        # ----------------------------------------------------

        incident_type = result.get(
            "incident_type"
        )

        allowed_incidents = {
            "collision",
            "theft",
            "fire",
            "vandalism",
            "weather_damage",
            "unknown",
        }

        if (
            incident_type
            not in allowed_incidents
        ):

            incident_type = "unknown"


        # ----------------------------------------------------
        # Damage types
        # ----------------------------------------------------

        damage_types = result.get(
            "damage_types",
            [],
        )

        if not isinstance(
            damage_types,
            list,
        ):

            damage_types = []


        damage_types = [

            str(item)

            for item in damage_types

            if str(item)
            in allowed_damage_types

        ]


        # Remove duplicates while preserving order.
        damage_types = list(
            dict.fromkeys(
                damage_types
            )
        )


        # ----------------------------------------------------
        # List fields
        # ----------------------------------------------------

        def clean_list(
            value: Any,
        ) -> list[str]:
            """
            Normalize a generic string-list field.
            """

            if not isinstance(
                value,
                list,
            ):

                return []

            cleaned: list[str] = []

            for item in value:

                if item is None:
                    continue

                text = str(
                    item
                ).strip()

                if text:
                    cleaned.append(
                        text
                    )

            return cleaned


        time_mentions = clean_list(
            result.get(
                "time_mentions",
                [],
            )
        )


        location_mentions = clean_list(
            result.get(
                "location_mentions",
                [],
            )
        )


        vehicle_mentions = clean_list(
            result.get(
                "vehicle_mentions",
                [],
            )
        )


        action_mentions = clean_list(
            result.get(
                "action_mentions",
                [],
            )
        )


        contradictions = clean_list(
            result.get(
                "contradictions",
                [],
            )
        )


        signals = clean_list(
            result.get(
                "signals",
                [],
            )
        )


        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        summary = result.get(
            "summary",
            "",
        )

        if not isinstance(
            summary,
            str,
        ):

            summary = str(
                summary
            )

        summary = summary.strip()


        # ----------------------------------------------------
        # Assessment
        # ----------------------------------------------------

        assessment = result.get(
            "assessment"
        )

        allowed_assessments = {
            "CONSISTENT",
            "AMBIGUOUS",
            "INCONSISTENT",
        }

        # IMPORTANT:
        #
        # Missing/invalid assessment must NOT become
        # CONSISTENT.
        #
        # Otherwise malformed LLM output could accidentally
        # produce a positive textual assessment.

        if (
            assessment
            not in allowed_assessments
        ):

            assessment = "AMBIGUOUS"


        return {

            "incident_type":
                incident_type,

            "damage_types":
                damage_types,

            "time_mentions":
                time_mentions,

            "location_mentions":
                location_mentions,

            "vehicle_mentions":
                vehicle_mentions,

            "action_mentions":
                action_mentions,

            "summary":
                summary,

            "contradictions":
                contradictions,

            "signals":
                signals,

            "assessment":
                assessment,
        }


    # ========================================================
    # EVIDENCE
    # ========================================================

    def _build_evidence(
        self,
        information: Dict[str, Any],
    ) -> list[str]:
        """
        Convert structured LLM findings into TruthChain evidence.
        """

        evidence: list[str] = []


        # ----------------------------------------------------
        # Incident
        # ----------------------------------------------------

        incident_type = information.get(
            "incident_type"
        )

        if (
            incident_type
            and incident_type != "unknown"
        ):

            evidence.append(
                "Claim narrative indicates "
                f"incident type: {incident_type}."
            )


        # ----------------------------------------------------
        # Damage
        # ----------------------------------------------------

        damage_types = information.get(
            "damage_types",
            [],
        )

        if damage_types:

            readable_damage = [

                damage.replace(
                    "_",
                    " ",
                )

                for damage
                in damage_types

            ]

            evidence.append(
                "Claimant-described damage: "
                + ", ".join(
                    readable_damage
                )
                + "."
            )


        # ----------------------------------------------------
        # Time
        # ----------------------------------------------------

        if information.get(
            "time_mentions"
        ):

            evidence.append(
                "Time information is mentioned "
                "in the claim narrative."
            )


        # ----------------------------------------------------
        # Location
        # ----------------------------------------------------

        if information.get(
            "location_mentions"
        ):

            evidence.append(
                "Location information is mentioned "
                "in the claim narrative."
            )


        # ----------------------------------------------------
        # Vehicle activity
        # ----------------------------------------------------

        if information.get(
            "action_mentions"
        ):

            evidence.append(
                "Vehicle activity is described "
                "in the claim narrative."
            )


        # ----------------------------------------------------
        # Summary
        # ----------------------------------------------------

        summary = information.get(
            "summary"
        )

        if summary:

            evidence.append(
                f"LLM narrative summary: {summary}"
            )


        if not evidence:

            evidence.append(
                "Claim narrative contains limited "
                "structured incident information."
            )


        return evidence


    # ========================================================
    # TEXT RISK SIGNAL
    # ========================================================

    def _calculate_risk_score(
        self,
        contradictions: list[str],
        signals: list[str],
    ) -> float:
        """
        Calculate a TextAgent evidence signal.

        IMPORTANT:

            This is NOT a probability of fraud.

            It only represents textual ambiguity or
            inconsistency detected by the TextAgent.

        Final claim risk is calculated later by the
        centralized TruthChain risk engine.
        """

        score = 0.0


        # Explicit contradictions receive greater weight.
        score += (
            0.25
            * len(
                contradictions
            )
        )


        # Investigation signals receive lower weight.
        score += (
            0.10
            * len(
                signals
            )
        )


        return float(
            min(
                1.0,
                score,
            )
        )


    # ========================================================
    # CONFIDENCE
    # ========================================================

    def _calculate_confidence(
        self,
        assessment: str,
        contradictions: list[str],
        signals: list[str],
    ) -> float:
        """
        Calculate confidence in the textual assessment.

        This is NOT fraud confidence.
        """

        if assessment == "INCONSISTENT":

            return min(
                0.99,
                0.80
                + (
                    0.05
                    * len(
                        contradictions
                    )
                ),
            )


        if assessment == "AMBIGUOUS":

            return 0.75


        return 0.85


    # ========================================================
    # PUBLIC ANALYZE API
    # ========================================================

    def analyze(
        self,
        text: str,
    ) -> Dict[str, Any]:
        """
        Analyze one motor-insurance claim narrative.

        Returns a standardized TruthChain TextAgent response.

        States:

            CONSISTENT
            AMBIGUOUS
            INCONSISTENT
            INSUFFICIENT_DATA
            ERROR
        """

        start_time = (
            time.perf_counter()
        )


        # ----------------------------------------------------
        # Input type validation
        # ----------------------------------------------------

        if not isinstance(
            text,
            str,
        ):

            return self._error_result(
                "Claim description must be a string.",
                start_time,
                error_type="INVALID_INPUT",
            )


        text = text.strip()


        # ----------------------------------------------------
        # Minimum text validation
        # ----------------------------------------------------

        if len(text) < MIN_TEXT_LENGTH:

            return self._insufficient_data_result(
                "Missing or insufficient claim description.",
                start_time,
            )


        try:

            # ------------------------------------------------
            # Build prompts
            # ------------------------------------------------

            system_prompt = (
                self._build_system_prompt()
            )

            user_prompt = (
                self._build_user_prompt(
                    text
                )
            )


            # ------------------------------------------------
            # Groq request
            # ------------------------------------------------

            response = (
                self.client
                .chat
                .completions
                .create(

                    model=self.model,

                    messages=[

                        {
                            "role": "system",
                            "content": system_prompt,
                        },

                        {
                            "role": "user",
                            "content": user_prompt,
                        },

                    ],

                    temperature=0.0,

                    max_tokens=2000,

                    response_format={
                        "type": "json_object"
                    },
                )
            )


            # ------------------------------------------------
            # Validate response structure
            # ------------------------------------------------

            if not response.choices:

                raise RuntimeError(
                    "Groq returned no choices."
                )


            message = (
                response.choices[0]
                .message
            )


            if message is None:

                raise RuntimeError(
                    "Groq returned an empty message."
                )


            content = (
                message.content
            )


            if not content:

                raise RuntimeError(
                    "Groq returned empty content."
                )


            # ------------------------------------------------
            # Parse JSON
            # ------------------------------------------------

            raw_result = (
                self._parse_json(
                    content
                )
            )


            # ------------------------------------------------
            # Normalize
            # ------------------------------------------------

            information = (
                self._normalize_result(
                    raw_result
                )
            )


            # ------------------------------------------------
            # Evidence
            # ------------------------------------------------

            evidence = (
                self._build_evidence(
                    information
                )
            )


            # ------------------------------------------------
            # Contradictions / signals
            # ------------------------------------------------

            contradictions = (
                information[
                    "contradictions"
                ]
            )

            signals = (
                information[
                    "signals"
                ]
            )


            # ------------------------------------------------
            # Text evidence signal
            # ------------------------------------------------

            risk_score = (
                self._calculate_risk_score(
                    contradictions,
                    signals,
                )
            )


            # ------------------------------------------------
            # Assessment
            # ------------------------------------------------

            assessment = (
                information[
                    "assessment"
                ]
            )


            # ------------------------------------------------
            # Confidence
            # ------------------------------------------------

            confidence = (
                self._calculate_confidence(
                    assessment,
                    contradictions,
                    signals,
                )
            )


            # ------------------------------------------------
            # Processing time
            # ------------------------------------------------

            processing_time_ms = int(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000
            )


            # ------------------------------------------------
            # Final TruthChain result
            # ------------------------------------------------

            return {

                "agent":
                    "TextAgent",

                "domain":
                    "motor",

                # Confidence in textual assessment.
                # NOT fraud probability.
                "confidence": round(
                    confidence,
                    4,
                ),

                # Textual evidence signal.
                # NOT final fraud probability.
                "risk_score": round(
                    risk_score,
                    4,
                ),

                "decision":
                    assessment,

                "evidence":
                    evidence,

                "contradictions":
                    contradictions,

                "model_version":
                    self.model_version,

                "processing_time_ms":
                    processing_time_ms,

                "extracted_information": {

                    "incident_type":
                        information[
                            "incident_type"
                        ],

                    "damage_types":
                        information[
                            "damage_types"
                        ],

                    "time_mentions":
                        information[
                            "time_mentions"
                        ],

                    "location_mentions":
                        information[
                            "location_mentions"
                        ],

                    "vehicle_mentions":
                        information[
                            "vehicle_mentions"
                        ],

                    "action_mentions":
                        information[
                            "action_mentions"
                        ],
                },

                "summary":
                    information[
                        "summary"
                    ],

                "signals":
                    signals,

                "text_length":
                    len(text),
            }


        except Exception as exc:

            return self._error_result(
                f"Text analysis failed: {exc}",
                start_time,
                error_type=type(exc).__name__,
                text_length=len(text),
            )


    # ========================================================
    # INSUFFICIENT DATA RESULT
    # ========================================================

    def _insufficient_data_result(
        self,
        message: str,
        start_time: float,
    ) -> Dict[str, Any]:
        """
        Return a standardized INSUFFICIENT_DATA response.

        This is reserved for genuinely missing/insufficient
        input, not model or provider failures.
        """

        processing_time_ms = int(
            (
                time.perf_counter()
                - start_time
            )
            * 1000
        )

        return {

            "agent":
                "TextAgent",

            "domain":
                "motor",

            "confidence":
                0.0,

            "risk_score":
                0.0,

            "decision":
                "INSUFFICIENT_DATA",

            "evidence": [
                message
            ],

            "contradictions": [],

            "model_version":
                self.model_version,

            "processing_time_ms":
                processing_time_ms,

            "extracted_information":
                {},

            "summary":
                "",

            "signals":
                [],

            "text_length":
                0,
        }


    # ========================================================
    # ERROR RESULT
    # ========================================================

    def _error_result(
        self,
        message: str,
        start_time: float,
        error_type: str = "TEXT_AGENT_ERROR",
        text_length: int = 0,
    ) -> Dict[str, Any]:
        """
        Return a standardized ERROR response.

        IMPORTANT:

        Runtime/provider/LLM/JSON failures are ERROR.

        They must NOT be represented as CONSISTENT,
        PASS, or INSUFFICIENT_DATA.

        This allows the graph and RiskEngine to fail closed.
        """

        processing_time_ms = int(
            (
                time.perf_counter()
                - start_time
            )
            * 1000
        )


        return {

            "agent":
                "TextAgent",

            "domain":
                "motor",

            "confidence":
                0.0,

            "risk_score":
                0.0,

            "decision":
                "ERROR",

            "evidence": [
                message
            ],

            "contradictions":
                [],

            "model_version":
                self.model_version,

            "processing_time_ms":
                processing_time_ms,

            "extracted_information":
                {},

            "summary":
                "",

            "signals":
                [],

            "text_length":
                text_length,

            "error_type":
                error_type,

            "error":
                message,
        }


# ============================================================
# SINGLETON
# ============================================================

_text_agent: TextAgent | None = None


def get_text_agent() -> TextAgent:
    """
    Lazily initialize the TextAgent.
    """

    global _text_agent

    if _text_agent is None:

        _text_agent = TextAgent()

    return _text_agent


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def analyze_text(
    text: str,
) -> Dict[str, Any]:
    """
    Convenience function for API and LangGraph nodes.
    """

    agent = get_text_agent()

    return agent.analyze(
        text
    )


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print(
        "TRUTHCHAIN TEXT AGENT - GROQ LLM TEST"
    )
    print("=" * 70)

    print()

    print(
        f"Model: {GROQ_MODEL}"
    )

    print(
        "Provider: Groq"
    )

    print(
        f"Environment file: {ENV_FILE}"
    )

    print()

    try:

        agent = get_text_agent()

    except Exception as exc:

        print(
            "Failed to initialize TextAgent:"
        )

        print(
            str(exc)
        )

        raise SystemExit(1)


    # --------------------------------------------------------
    # Test claim
    # --------------------------------------------------------

    example_text = (
        "I was driving my car on the highway at around "
        "6:30 PM when another vehicle hit the rear side of "
        "my car. The accident caused a dent and scratches "
        "on the rear door and the left lamp was broken."
    )


    print(
        "TEST CLAIM:"
    )

    print(
        example_text
    )

    print()


    # --------------------------------------------------------
    # Run LLM-backed analysis
    # --------------------------------------------------------

    result = agent.analyze(
        example_text
    )


    print("=" * 70)
    print(
        "TEXT AGENT RESULT"
    )
    print("=" * 70)

    print(
        json.dumps(
            result,
            indent=2,
        )
    )