"""
TruthChain Agriculture - Adversarial Verifier (LLM-Powered)

Adversarial challenge layer for agriculture claims.

Uses Groq LLM (openai/gpt-oss-120b) to challenge the evidence chain,
exactly mirroring the motor pipeline's AdversarialVerifier architecture.

Responsibilities:
    1. Independently challenge all evidence produced by Agriculture agents.
    2. Look for weaknesses LLM reasoning can detect beyond deterministic rules.
    3. Generate adversarial challenges and vulnerability analysis.
    4. Produce verification_score and adversarial_result for DecisionEngine.

The verifier does NOT declare insurance fraud by itself.

IMPORTANT
---------
This is an LLM-powered adversarial challenge layer.

It is NOT a trained fraud classifier and its verification_score is NOT
a calibrated fraud probability.

Standardized agent contract:
{
    "agent": "...",
    "domain": "...",
    "confidence": 0.0-1.0,
    "risk_score": 0.0-1.0,
    "decision": "PASS | SUSPICIOUS | NEEDS_REVIEW | ERROR",
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


AGENT_NAME = "AdversarialVerifier"
DOMAIN = "agriculture"
AGENT_VERSION = "agriculture-adversarial-verifier-llm-v1.0"

GROQ_MODEL = "openai/gpt-oss-120b"
REASONING_EFFORT = "default"
MAX_COMPLETION_TOKENS = 2000


# ---------------------------------------------------------------------------
# System prompt for Groq LLM adversarial challenge
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are the adversarial verification component of an agriculture insurance
claim verification system.

Your role is to act as a skeptical auditor who adversarially challenges
the evidence produced by all verification agents.

You receive the complete evidence chain from:
  - TextAgent: claim narrative analysis
  - ImageAgent: crop image CNN analysis
  - SatelliteAgent: Sentinel-2 satellite evidence
  - SensorAgent: weather/soil analysis
  - CrossModalAgent: LLM cross-modal fusion
  - InvestigationAgent: LLM deep investigation
  - RiskEngine: weighted risk consensus

Your task is to:
1. Challenge each piece of evidence — ask "could this be fabricated or mistaken?"
2. Identify specific vulnerabilities in the evidence chain.
3. Find weaknesses that were NOT caught by previous deterministic/rule-based checks.
4. Assess the overall strength of the evidence chain.
5. Output a structured JSON adversarial challenge report.

Do NOT:
- Make a final insurance fraud determination
- Recommend claim approval or denial
- Invent information not present in the inputs

Return ONLY valid JSON with exactly these fields:

{
  "verification_score": number (0.0-1.0, higher = more unresolved challenges),
  "adversarial_result": "PASS" | "FLAGGED" | "NEEDS_REVIEW",
  "challenge_count": integer,
  "challenge_results": [
    {
      "challenge": string,
      "target_agent": string,
      "severity": "HIGH" | "MEDIUM" | "LOW",
      "resolution": "UNRESOLVED" | "RESOLVED" | "PARTIAL"
    }
  ],
  "vulnerabilities": [string],
  "evidence_chain_strength": "STRONG" | "MODERATE" | "WEAK" | "INSUFFICIENT",
  "satellite_evidence_reliability": "HIGH" | "MEDIUM" | "LOW" | "UNAVAILABLE",
  "image_evidence_reliability": "HIGH" | "MEDIUM" | "LOW" | "UNAVAILABLE",
  "decision": "PASS" | "SUSPICIOUS" | "NEEDS_REVIEW",
  "adversarial_narrative": string
}

Decision rules:
- PASS: Evidence chain is strong, challenges are resolved
- SUSPICIOUS: Specific unresolved challenges with strong evidence of inconsistency
- NEEDS_REVIEW: Some challenges unresolved but not definitively suspicious

adversarial_result:
- PASS: All challenges resolved, evidence is reliable
- FLAGGED: Multiple unresolved challenges, evidence reliability is questionable
- NEEDS_REVIEW: Some unresolved challenges requiring human review

verification_score: 0.0-0.3 = strong evidence, 0.3-0.6 = moderate, 0.6-1.0 = weak/challenged

Challenge examples to consider:
- Could the crop photo have been taken elsewhere?
- Does NDVI support the claimed damage severity?
- Is the weather data consistent with the claimed event date and location?
- Are there temporal inconsistencies between claim date and satellite scene?
- Could the claimed loss percentage be exaggerated?
- Is the crop classification consistent across image and satellite?
"""


# ---------------------------------------------------------------------------
# Adversarial Verifier (LLM-Powered)
# ---------------------------------------------------------------------------

class AdversarialVerifier:
    """
    LLM-powered adversarial verification agent for agriculture claims.

    Uses Groq LLM (openai/gpt-oss-120b) to challenge the evidence chain
    and identify weaknesses not caught by deterministic rules.

    This matches the motor pipeline's AdversarialVerifier architecture.
    """

    def __init__(
        self,
        client: Optional[Groq] = None,
        model: str = GROQ_MODEL,
    ) -> None:
        self.agent_name = AGENT_NAME
        self.domain = DOMAIN
        self.agent_version = AGENT_VERSION
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

    def verify(
        self,
        image: Optional[Dict[str, Any]] = None,
        sensor: Optional[Dict[str, Any]] = None,
        text: Optional[Dict[str, Any]] = None,
        cross_modal: Optional[Dict[str, Any]] = None,
        investigation: Optional[Dict[str, Any]] = None,
        risk_engine: Optional[Dict[str, Any]] = None,
        satellite: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Adversarially challenge the agriculture evidence chain using Groq LLM.

        Parameters
        ----------
        image: ImageAgent result
        sensor: SensorAgent result
        text: TextAgent result
        cross_modal: CrossModalAgent result (LLM fusion)
        investigation: InvestigationAgent result (LLM investigation)
        risk_engine: RiskEngine result
        satellite: SatelliteAgent result

        Returns
        -------
        dict
            Standardized AdversarialVerifier result.
        """

        start_time = time.perf_counter()

        try:
            image = image or {}
            sensor = sensor or {}
            text = text or {}
            cross_modal = cross_modal or {}
            investigation = investigation or {}
            risk_engine = risk_engine or {}
            satellite = satellite or {}

            available_count = sum(
                1 for r in [image, sensor, text, cross_modal, satellite]
                if r and r.get("decision") not in (None, "")
            )

            if available_count == 0:
                return self._error_result(
                    "No agent evidence supplied to AdversarialVerifier.",
                    start_time,
                )

            # ----------------------------------------------------------
            # Build adversarial challenge context
            # ----------------------------------------------------------

            challenge_context = self._build_challenge_context(
                image=image,
                sensor=sensor,
                text=text,
                cross_modal=cross_modal,
                investigation=investigation,
                risk_engine=risk_engine,
                satellite=satellite,
            )

            # ----------------------------------------------------------
            # LLM adversarial challenge
            # ----------------------------------------------------------

            llm_result = self._llm_challenge(challenge_context)

            # ----------------------------------------------------------
            # Extract and validate LLM output
            # ----------------------------------------------------------

            verification_score = float(
                llm_result.get("verification_score", 0.5)
            )
            verification_score = max(0.0, min(1.0, verification_score))

            adversarial_result = str(
                llm_result.get("adversarial_result", "NEEDS_REVIEW")
            ).upper()
            if adversarial_result not in {"PASS", "FLAGGED", "NEEDS_REVIEW"}:
                adversarial_result = "NEEDS_REVIEW"

            challenge_count = int(
                llm_result.get("challenge_count", 0)
            )

            challenge_results: List[Dict[str, Any]] = [
                c for c in llm_result.get("challenge_results", [])
                if isinstance(c, dict)
            ]

            vulnerabilities: List[str] = [
                str(v) for v in llm_result.get("vulnerabilities", [])
                if v and str(v).strip()
            ]

            evidence_chain_strength = str(
                llm_result.get("evidence_chain_strength", "MODERATE")
            ).upper()

            satellite_reliability = str(
                llm_result.get("satellite_evidence_reliability", "UNAVAILABLE")
            ).upper()

            image_reliability = str(
                llm_result.get("image_evidence_reliability", "UNAVAILABLE")
            ).upper()

            decision = str(
                llm_result.get("decision", "NEEDS_REVIEW")
            ).upper()
            if decision not in {"PASS", "SUSPICIOUS", "NEEDS_REVIEW"}:
                decision = "NEEDS_REVIEW"

            adversarial_narrative = str(
                llm_result.get("adversarial_narrative", "")
            ).strip()

            # ----------------------------------------------------------
            # Build evidence list
            # ----------------------------------------------------------

            evidence: List[str] = []
            contradictions: List[str] = list(vulnerabilities)

            evidence.append(
                f"LLM adversarial verification score: {verification_score:.3f}."
            )
            evidence.append(
                f"Adversarial result: {adversarial_result}."
            )
            evidence.append(
                f"Evidence chain strength: {evidence_chain_strength}."
            )
            evidence.append(
                f"LLM challenge count: {challenge_count}."
            )
            evidence.append(
                f"Satellite evidence reliability: {satellite_reliability}."
            )
            evidence.append(
                f"Image evidence reliability: {image_reliability}."
            )

            if adversarial_narrative:
                evidence.append(
                    f"Adversarial narrative: {adversarial_narrative}"
                )

            unresolved = [
                c for c in challenge_results
                if c.get("resolution") == "UNRESOLVED"
            ]
            if unresolved:
                evidence.append(
                    f"Unresolved adversarial challenges: {len(unresolved)}."
                )

            # Include cross-modal and investigation context
            if cross_modal.get("cross_modal_score") is not None:
                evidence.append(
                    f"CrossModal inconsistency score: "
                    f"{cross_modal['cross_modal_score']:.3f}."
                )

            if investigation.get("investigation_score") is not None:
                evidence.append(
                    f"Investigation score: "
                    f"{investigation['investigation_score']:.3f}."
                )

            if risk_engine.get("consensus_score") is not None:
                evidence.append(
                    f"RiskEngine consensus score: "
                    f"{risk_engine['consensus_score']:.6f}."
                )

            # ----------------------------------------------------------
            # Confidence
            # ----------------------------------------------------------

            confidence = self._calculate_confidence(
                verification_score=verification_score,
                available_count=available_count,
                unresolved_count=len(unresolved),
            )

            processing_time_ms = int(
                round((time.perf_counter() - start_time) * 1000)
            )

            return {
                "agent": self.agent_name,
                "domain": self.domain,
                "confidence": round(confidence, 6),
                "risk_score": round(verification_score, 6),
                "decision": decision,
                "evidence": evidence,
                "contradictions": contradictions,
                "model_version": self.agent_version,
                "processing_time_ms": processing_time_ms,

                # AdversarialVerifier-specific fields.
                "verification_score": round(verification_score, 6),
                "adversarial_result": adversarial_result,
                "challenge_count": challenge_count,
                "challenge_results": challenge_results,
                "vulnerabilities": vulnerabilities,
                "evidence_chain_strength": evidence_chain_strength,
                "satellite_evidence_reliability": satellite_reliability,
                "image_evidence_reliability": image_reliability,
                "adversarial_narrative": adversarial_narrative,
                "unresolved_challenge_count": len(unresolved),

                # LLM audit information.
                "llm_provider": "groq",
                "llm_model": self.model,

                # Semantic clarification.
                "risk_score_meaning": "adversarial_challenge_score",
                "agent_version": AGENT_VERSION,
            }

        except Exception as exc:
            return self._error_result(
                str(exc),
                start_time,
            )

    # ------------------------------------------------------------------
    # Challenge context builder
    # ------------------------------------------------------------------

    def _build_challenge_context(
        self,
        image: Dict[str, Any],
        sensor: Dict[str, Any],
        text: Dict[str, Any],
        cross_modal: Dict[str, Any],
        investigation: Dict[str, Any],
        risk_engine: Dict[str, Any],
        satellite: Dict[str, Any],
    ) -> str:
        """Build full evidence chain context for adversarial challenge."""

        lines = []

        lines.append("=== FULL AGRICULTURE EVIDENCE CHAIN FOR ADVERSARIAL CHALLENGE ===")

        # Claim overview
        lines.append("\n--- CLAIM OVERVIEW ---")
        lines.append(f"Claimed crop: {cross_modal.get('claimed_crop', 'N/A')}")
        lines.append(f"Claimed event: {cross_modal.get('claimed_event', 'N/A')}")
        lines.append(f"Claimed loss: {cross_modal.get('claimed_loss_percent', 'N/A')}%")
        lines.append(f"Location: {cross_modal.get('location', 'N/A')}")
        lines.append(f"Event date: {cross_modal.get('event_date', 'N/A')}")

        # Text agent
        lines.append("\n--- TEXT AGENT ---")
        if text:
            lines.append(f"Decision: {text.get('decision', 'N/A')}")
            lines.append(f"Extracted crop: {text.get('extracted_crop', 'N/A')}")
            lines.append(f"Damage types: {text.get('damage_types', [])}")
            lines.append(f"Claimed loss: {text.get('claimed_loss_percent', 'N/A')}%")
            lines.append(f"Confidence: {text.get('confidence', 0):.3f}")
        else:
            lines.append("Not available.")

        # Image agent
        lines.append("\n--- IMAGE AGENT (Crop CNN) ---")
        if image and image.get("decision") not in (None, ""):
            lines.append(f"Decision: {image.get('decision', 'N/A')}")
            lines.append(f"Crop classification: {image.get('crop_classification', image.get('predicted_crop', 'N/A'))}")
            lines.append(f"Damage level: {image.get('damage_level', 'N/A')}")
            lines.append(f"Confidence: {image.get('confidence', 0):.3f}")
        else:
            lines.append("Not available or insufficient data.")

        # Satellite agent
        lines.append("\n--- SATELLITE AGENT (Sentinel-2 CropAgent v0.2) ---")
        if satellite and satellite.get("decision") not in (None, ""):
            lines.append(f"Decision: {satellite.get('decision', 'N/A')}")
            lines.append(f"Predicted crop: {satellite.get('predicted_crop', 'N/A')}")
            ndvi = satellite.get("ndvi") or satellite.get("ndvi_mean")
            lines.append(f"NDVI: {ndvi}")
            lines.append(f"Evidence decision: {satellite.get('evidence_decision', 'N/A')}")
            lines.append(f"Confidence: {satellite.get('confidence', 0):.3f}")
        else:
            lines.append("Not available or insufficient data.")

        # Sensor agent
        lines.append("\n--- SENSOR AGENT (Weather/Soil) ---")
        if sensor and sensor.get("decision") not in (None, ""):
            lines.append(f"Decision: {sensor.get('decision', 'N/A')}")
            lines.append(f"Detected events: {sensor.get('detected_events', [])}")
            lines.append(f"Evidence decision: {sensor.get('evidence_decision', 'N/A')}")
            lines.append(f"Confidence: {sensor.get('confidence', 0):.3f}")
        else:
            lines.append("Not available or insufficient data.")

        # CrossModal (LLM)
        lines.append("\n--- CROSS-MODAL AGENT (Groq LLM) ---")
        if cross_modal:
            lines.append(f"Decision: {cross_modal.get('decision', 'N/A')}")
            lines.append(f"Agreement level: {cross_modal.get('agreement_level', 'N/A')}")
            lines.append(f"Inconsistency score: {cross_modal.get('cross_modal_score', 'N/A')}")
            lines.append(f"Contradiction count: {cross_modal.get('contradiction_count', 0)}")
            contradictions = cross_modal.get("contradictions", [])
            if contradictions:
                for c in contradictions[:4]:
                    lines.append(f"  Contradiction: {c}")
            lines.append(f"LLM reasoning: {cross_modal.get('llm_reasoning', 'N/A')}")

        # Investigation (LLM)
        lines.append("\n--- INVESTIGATION AGENT (Groq LLM) ---")
        if investigation:
            lines.append(f"Decision: {investigation.get('decision', 'N/A')}")
            lines.append(f"Investigation score: {investigation.get('investigation_score', 'N/A')}")
            lines.append(f"Field visit priority: {investigation.get('field_visit_priority', 'N/A')}")
            fraud_indicators = investigation.get("fraud_indicators", [])
            if fraud_indicators:
                for f in fraud_indicators[:4]:
                    lines.append(f"  Fraud indicator: {f}")
            lines.append(f"Narrative: {investigation.get('investigation_narrative', 'N/A')}")

        # Risk engine
        lines.append("\n--- RISK ENGINE ---")
        if risk_engine:
            lines.append(f"Decision: {risk_engine.get('decision', 'N/A')}")
            lines.append(f"Consensus score: {risk_engine.get('consensus_score', risk_engine.get('risk_score', 'N/A'))}")
            lines.append(f"Risk level: {risk_engine.get('risk_level', 'N/A')}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # LLM adversarial challenge
    # ------------------------------------------------------------------

    def _llm_challenge(
        self,
        challenge_context: str,
    ) -> Dict[str, Any]:
        """
        Use Groq LLM for adversarial challenge reasoning.
        Falls back to heuristic analysis if LLM is unavailable.
        """

        if self.client is None:
            return self._heuristic_fallback(challenge_context)

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
                            "Adversarially challenge this agriculture claim "
                            "evidence chain:\n\n"
                            f"{challenge_context}"
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
                    "Groq returned an empty adversarial response."
                )

            parsed = json.loads(content)

            if not isinstance(parsed, dict):
                raise RuntimeError(
                    "Groq adversarial response must be a JSON object."
                )

            return parsed

        except Exception:
            return self._heuristic_fallback(challenge_context)

    def _heuristic_fallback(
        self,
        challenge_context: str,
    ) -> Dict[str, Any]:
        """Heuristic fallback when Groq LLM is unavailable."""

        suspicious = "SUSPICIOUS" in challenge_context or "FLAGGED" in challenge_context

        return {
            "verification_score": 0.6 if suspicious else 0.35,
            "adversarial_result": "FLAGGED" if suspicious else "NEEDS_REVIEW",
            "challenge_count": 1,
            "challenge_results": [
                {
                    "challenge": "LLM adversarial challenge unavailable.",
                    "target_agent": "All",
                    "severity": "MEDIUM",
                    "resolution": "UNRESOLVED",
                }
            ],
            "vulnerabilities": [
                "LLM adversarial verifier unavailable. Manual adversarial review required."
            ],
            "evidence_chain_strength": "MODERATE",
            "satellite_evidence_reliability": "UNAVAILABLE",
            "image_evidence_reliability": "UNAVAILABLE",
            "decision": "NEEDS_REVIEW",
            "adversarial_narrative": (
                "Groq LLM adversarial verifier not available. "
                "Heuristic fallback activated. "
                "Human review recommended before certification."
            ),
        }

    # ------------------------------------------------------------------
    # Confidence
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self,
        verification_score: float,
        available_count: int,
        unresolved_count: int,
    ) -> float:
        """Calculate adversarial verifier confidence."""

        if available_count == 0:
            return 0.0

        coverage_factor = min(available_count / 5.0, 1.0)
        challenge_penalty = min(0.30, unresolved_count * 0.08)

        confidence = (
            0.60 * coverage_factor
            + 0.30 * (1.0 - verification_score)
            - challenge_penalty
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

        processing_time_ms = int(
            round((time.perf_counter() - start_time) * 1000)
        )

        return {
            "agent": self.agent_name,
            "domain": self.domain,
            "confidence": 0.0,
            "risk_score": 1.0,
            "decision": "ERROR",
            "evidence": [],
            "contradictions": [message],
            "model_version": self.agent_version,
            "processing_time_ms": processing_time_ms,
            "verification_score": 1.0,
            "adversarial_result": "NEEDS_REVIEW",
            "challenge_count": 0,
            "challenge_results": [],
            "vulnerabilities": [message],
            "evidence_chain_strength": "INSUFFICIENT",
            "satellite_evidence_reliability": "UNAVAILABLE",
            "image_evidence_reliability": "UNAVAILABLE",
            "adversarial_narrative": f"Adversarial verification failed: {message}",
            "unresolved_challenge_count": 0,
            "llm_provider": "groq",
            "llm_model": self.model,
            "risk_score_meaning": "adversarial_challenge_score",
            "agent_version": AGENT_VERSION,
        }