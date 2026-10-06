"""
TruthChain Agriculture - Risk / Consensus Engine

Combines Agriculture agent outputs into a deterministic consensus assessment.

IMPORTANT
---------
The resulting risk/consensus score is NOT a calibrated probability of fraud.

Current component meanings:
    ImageAgent          -> image evidence uncertainty
    SensorAgent         -> environmental evidence uncertainty
    TextAgent           -> extraction uncertainty
    CrossModalAgent     -> cross-modal inconsistency
    AdversarialVerifier -> unresolved adversarial challenge signal

InvestigationAgent is intentionally kept outside the weighted consensus.
It identifies additional verification work rather than being treated as
another fraud-risk signal.

Weights and thresholds are STARTING VALUES ONLY.
They must be validated against an appropriate agriculture-insurance
benchmark before operational use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional
import time


AGENT_NAME = "RiskEngine"
DOMAIN = "agriculture"
AGENT_VERSION = "agriculture-risk-engine-v0.1"


# Starting weights only.
STARTING_WEIGHTS = {
    "image": 0.25,
    "sensor": 0.25,
    "text": 0.15,
    "cross_modal": 0.25,
    "verifier": 0.10,
}


# Starting thresholds only.
LOW_RISK_THRESHOLD = 0.20
REVIEW_THRESHOLD = 0.50
HIGH_RISK_THRESHOLD = 0.75


FAILURE_DECISIONS = {
    "ERROR",
    "FAILED",
    "AGENT_ERROR",
    "PROCESSING_ERROR",
    "MODEL_ERROR",
}


INSUFFICIENT_DECISIONS = {
    "INSUFFICIENT_DATA",
    "NEEDS_REVIEW",
    "PENDING",
    "UNKNOWN",
}


@dataclass
class RiskConsensusResult:
    """Structured Risk/Consensus result."""

    agent: str
    domain: str
    confidence: float
    risk_score: float
    decision: str
    evidence: list[str]
    contradictions: list[str]
    model_version: str
    processing_time_ms: int

    consensus_score: float
    effective_weights: Dict[str, float]
    unavailable_components: list[str]

    component_scores: Dict[str, Optional[float]]
    component_decisions: Dict[str, Optional[str]]

    modality_count: int
    usable_modality_count: int

    recommendation: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""

        return {
            "agent": self.agent,
            "domain": self.domain,
            "confidence": self.confidence,
            "risk_score": self.risk_score,
            "decision": self.decision,
            "evidence": self.evidence,
            "contradictions": self.contradictions,
            "model_version": self.model_version,
            "processing_time_ms": self.processing_time_ms,
            "consensus_score": self.consensus_score,
            "effective_weights": self.effective_weights,
            "unavailable_components": self.unavailable_components,
            "component_scores": self.component_scores,
            "component_decisions": self.component_decisions,
            "modality_count": self.modality_count,
            "usable_modality_count": self.usable_modality_count,
            "recommendation": self.recommendation,
        }


class RiskEngine:
    """
    Deterministic Risk/Consensus Engine for Agriculture.

    Expected weighted components:

        ImageAgent
        SensorAgent
        TextAgent
        CrossModalAgent
        AdversarialVerifier

    InvestigationAgent is consumed only as supporting verification context.
    """

    def __init__(
        self,
        weights: Optional[Mapping[str, float]] = None,
        low_risk_threshold: float = LOW_RISK_THRESHOLD,
        review_threshold: float = REVIEW_THRESHOLD,
        high_risk_threshold: float = HIGH_RISK_THRESHOLD,
    ) -> None:

        self.weights = dict(
            weights or STARTING_WEIGHTS
        )

        self.low_risk_threshold = float(
            low_risk_threshold
        )

        self.review_threshold = float(
            review_threshold
        )

        self.high_risk_threshold = float(
            high_risk_threshold
        )

        self._validate_configuration()

    def _validate_configuration(self) -> None:
        """Validate configuration."""

        required = {
            "image",
            "sensor",
            "text",
            "cross_modal",
            "verifier",
        }

        if set(self.weights.keys()) != required:
            raise ValueError(
                "Risk weights must contain exactly: "
                "image, sensor, text, cross_modal, verifier"
            )

        for name, weight in self.weights.items():

            if weight < 0:
                raise ValueError(
                    f"Risk weight for '{name}' cannot be negative."
                )

        if sum(self.weights.values()) <= 0:

            raise ValueError(
                "At least one risk weight must be greater than zero."
            )

        if not (
            0.0
            <= self.low_risk_threshold
            < self.review_threshold
            < self.high_risk_threshold
            <= 1.0
        ):

            raise ValueError(
                "Thresholds must satisfy: "
                "0 <= low < review < high <= 1."
            )

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> Optional[float]:
        """Convert value to bounded float."""

        if value is None:
            return None

        try:
            value = float(value)
        except (
            TypeError,
            ValueError,
        ):
            return None

        if value != value:
            return None

        if value == float("inf"):
            return None

        if value == float("-inf"):
            return None

        return max(
            0.0,
            min(1.0, value),
        )

    @staticmethod
    def _extract_component(
        result: Optional[Mapping[str, Any]],
    ) -> tuple[
        Optional[float],
        Optional[str],
    ]:
        """Extract risk score and decision."""

        if not result:
            return None, None

        score = RiskEngine._safe_float(
            result.get("risk_score")
        )

        decision = result.get(
            "decision"
        )

        if decision is not None:
            decision = str(
                decision
            ).upper()

        return score, decision

    @staticmethod
    def _is_usable_component(
        score: Optional[float],
        decision: Optional[str],
    ) -> bool:
        """Determine whether component can participate in consensus."""

        if score is None:
            return False

        if decision in FAILURE_DECISIONS:
            return False

        if decision in INSUFFICIENT_DECISIONS:
            return False

        return True

    def _build_component_map(
        self,
        image: Optional[Mapping[str, Any]],
        sensor: Optional[Mapping[str, Any]],
        text: Optional[Mapping[str, Any]],
        cross_modal: Optional[Mapping[str, Any]],
        verifier: Optional[Mapping[str, Any]],
    ) -> Dict[
        str,
        Optional[Mapping[str, Any]],
    ]:
        """Build internal consensus component map."""

        return {
            "image": image,
            "sensor": sensor,
            "text": text,
            "cross_modal": cross_modal,
            "verifier": verifier,
        }

    def _calculate_consensus(
        self,
        component_results: Dict[
            str,
            Optional[Mapping[str, Any]],
        ],
    ) -> tuple[
        float,
        Dict[str, float],
        Dict[str, Optional[float]],
        Dict[str, Optional[str]],
        list[str],
    ]:
        """
        Calculate weighted consensus.

        Missing/unusable components are excluded and the remaining weights
        are renormalized.
        """

        component_scores: Dict[
            str,
            Optional[float],
        ] = {}

        component_decisions: Dict[
            str,
            Optional[str],
        ] = {}

        usable_components: Dict[
            str,
            float,
        ] = {}

        unavailable_components: list[str] = []

        for name, result in component_results.items():

            score, decision = (
                self._extract_component(
                    result
                )
            )

            component_scores[name] = score
            component_decisions[name] = decision

            if self._is_usable_component(
                score,
                decision,
            ):

                usable_components[name] = score

            else:

                unavailable_components.append(
                    name
                )

        if not usable_components:

            return (
                0.5,
                {},
                component_scores,
                component_decisions,
                unavailable_components,
            )

        total_weight = sum(
            self.weights[name]
            for name in usable_components
        )

        if total_weight <= 0:

            raise ValueError(
                "Usable risk components have zero total weight."
            )

        effective_weights = {
            name: self.weights[name] / total_weight
            for name in usable_components
        }

        consensus_score = sum(
            usable_components[name]
            * effective_weights[name]
            for name in usable_components
        )

        return (
            max(
                0.0,
                min(
                    1.0,
                    consensus_score,
                ),
            ),
            effective_weights,
            component_scores,
            component_decisions,
            unavailable_components,
        )

    def _determine_decision(
        self,
        consensus_score: float,
        unavailable_components: list[str],
        component_decisions: Dict[
            str,
            Optional[str],
        ],
    ) -> str:
        """
        Convert consensus into an initial screening decision.

        VERIFIED means the available signals are sufficiently low-risk and
        all weighted components are available.

        REVIEW_REQUIRED is used when evidence is incomplete or the
        consensus exceeds the review threshold.

        UNCERTAIN means no usable weighted evidence exists.
        """

        usable_count = len(
            [
                decision
                for decision in component_decisions.values()
                if (
                    decision is not None
                    and decision not in FAILURE_DECISIONS
                    and decision not in INSUFFICIENT_DECISIONS
                )
            ]
        )

        if usable_count == 0:
            return "UNCERTAIN"

        if consensus_score >= self.high_risk_threshold:
            return "REVIEW_REQUIRED"

        if consensus_score >= self.review_threshold:
            return "REVIEW_REQUIRED"

        if unavailable_components:
            return "REVIEW_REQUIRED"

        if consensus_score <= self.low_risk_threshold:
            return "VERIFIED"

        return "REVIEW_REQUIRED"

    def _build_recommendation(
        self,
        decision: str,
        consensus_score: float,
        unavailable_components: list[str],
    ) -> str:
        """Build human-readable recommendation."""

        if decision == "VERIFIED":

            return (
                "Available evidence is sufficiently consistent for an "
                "initial verification recommendation; continue with normal "
                "claim verification controls."
            )

        if decision == "UNCERTAIN":

            return (
                "Insufficient usable agent evidence is available to form "
                "a consensus assessment; additional evidence is required."
            )

        if unavailable_components:

            missing = ", ".join(
                unavailable_components
            )

            return (
                "Human review is recommended because the consensus requires "
                "additional evidence or unavailable components: "
                f"{missing}."
            )

        if consensus_score >= self.high_risk_threshold:

            return (
                "Multiple available risk signals require human review; "
                "do not treat this score as a fraud probability."
            )

        return (
            "The available evidence requires additional verification or "
            "human review before an insurance decision is made."
        )

    def assess(
        self,
        image: Optional[Mapping[str, Any]] = None,
        sensor: Optional[Mapping[str, Any]] = None,
        text: Optional[Mapping[str, Any]] = None,
        cross_modal: Optional[Mapping[str, Any]] = None,
        verifier: Optional[Mapping[str, Any]] = None,
        investigation: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run Risk/Consensus assessment."""

        start = time.perf_counter()

        component_results = (
            self._build_component_map(
                image=image,
                sensor=sensor,
                text=text,
                cross_modal=cross_modal,
                verifier=verifier,
            )
        )

        (
            consensus_score,
            effective_weights,
            component_scores,
            component_decisions,
            unavailable_components,
        ) = self._calculate_consensus(
            component_results
        )

        modality_count = len(
            component_results
        )

        usable_modality_count = len(
            [
                name
                for name, score
                in component_scores.items()
                if (
                    score is not None
                    and self._is_usable_component(
                        score,
                        component_decisions.get(
                            name
                        ),
                    )
                )
            ]
        )

        decision = self._determine_decision(
            consensus_score=consensus_score,
            unavailable_components=(
                unavailable_components
            ),
            component_decisions=(
                component_decisions
            ),
        )

        recommendation = self._build_recommendation(
            decision=decision,
            consensus_score=consensus_score,
            unavailable_components=(
                unavailable_components
            ),
        )

        evidence: list[str] = [
            (
                "Consensus score is a deterministic weighted aggregation "
                "of available Agriculture agent risk signals."
            ),
            (
                "Risk weights are starting values and are not calibrated "
                "insurance-fraud probabilities."
            ),
        ]

        if effective_weights:

            weight_text = ", ".join(
                f"{name}={weight:.3f}"
                for name, weight
                in effective_weights.items()
            )

            evidence.append(
                "Effective weights after availability normalization: "
                f"{weight_text}."
            )

        evidence.append(
            f"Usable weighted components: "
            f"{usable_modality_count}/{modality_count}."
        )

        if verifier is not None:

            verifier_score = self._safe_float(
                verifier.get(
                    "verification_score"
                )
            )

            if verifier_score is not None:

                evidence.append(
                    "AdversarialVerifier contributed a verification "
                    f"challenge score of {verifier_score:.3f}."
                )

        if investigation is not None:

            investigation_score = self._safe_float(
                investigation.get(
                    "investigation_score"
                )
            )

            if investigation_score is not None:

                evidence.append(
                    "InvestigationAgent reported an "
                    f"additional-verification score of "
                    f"{investigation_score:.3f}; this is kept outside "
                    "the weighted consensus."
                )

        contradictions: list[str] = []

        for (
            name,
            decision_value,
        ) in component_decisions.items():

            if decision_value in {
                "SUSPICIOUS",
                "FAIL",
            }:

                contradictions.append(
                    f"{name} reported {decision_value}."
                )

            elif (
                decision_value
                in FAILURE_DECISIONS
            ):

                contradictions.append(
                    f"{name} failed to produce a usable assessment."
                )

            elif (
                decision_value
                in INSUFFICIENT_DECISIONS
            ):

                contradictions.append(
                    f"{name} reported insufficient evidence."
                )

        if usable_modality_count == 0:

            confidence = 0.0

        else:

            coverage = (
                usable_modality_count
                / modality_count
            )

            contradiction_penalty = min(
                0.30,
                len(contradictions) * 0.05,
            )

            confidence = max(
                0.0,
                min(
                    1.0,
                    0.70 * coverage
                    + 0.30
                    * (
                        1.0
                        - contradiction_penalty
                    ),
                ),
            )

        processing_time_ms = int(
            round(
                (
                    time.perf_counter()
                    - start
                )
                * 1000
            )
        )

        result = RiskConsensusResult(
            agent=AGENT_NAME,
            domain=DOMAIN,
            confidence=round(
                confidence,
                6,
            ),
            risk_score=round(
                consensus_score,
                6,
            ),
            decision=decision,
            evidence=evidence,
            contradictions=contradictions,
            model_version=AGENT_VERSION,
            processing_time_ms=(
                processing_time_ms
            ),
            consensus_score=round(
                consensus_score,
                6,
            ),
            effective_weights={
                key: round(
                    value,
                    6,
                )
                for key, value
                in effective_weights.items()
            },
            unavailable_components=(
                unavailable_components
            ),
            component_scores={
                key: (
                    None
                    if value is None
                    else round(
                        value,
                        6,
                    )
                )
                for key, value
                in component_scores.items()
            },
            component_decisions=(
                component_decisions
            ),
            modality_count=(
                modality_count
            ),
            usable_modality_count=(
                usable_modality_count
            ),
            recommendation=(
                recommendation
            ),
        )

        return result.to_dict()

    def run(
        self,
        image: Optional[Mapping[str, Any]] = None,
        sensor: Optional[Mapping[str, Any]] = None,
        text: Optional[Mapping[str, Any]] = None,
        cross_modal: Optional[Mapping[str, Any]] = None,
        verifier: Optional[Mapping[str, Any]] = None,
        investigation: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Alias for assess()."""

        return self.assess(
            image=image,
            sensor=sensor,
            text=text,
            cross_modal=cross_modal,
            verifier=verifier,
            investigation=investigation,
        )


# ---------------------------------------------------------------------------
# Singleton + convenience API
# ---------------------------------------------------------------------------

_risk_engine: Optional[RiskEngine] = None


def get_risk_engine() -> RiskEngine:
    """Return shared RiskEngine instance."""

    global _risk_engine

    if _risk_engine is None:
        _risk_engine = RiskEngine()

    return _risk_engine


def assess_risk(
    image: Optional[Mapping[str, Any]] = None,
    sensor: Optional[Mapping[str, Any]] = None,
    text: Optional[Mapping[str, Any]] = None,
    cross_modal: Optional[Mapping[str, Any]] = None,
    verifier: Optional[Mapping[str, Any]] = None,
    investigation: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience wrapper."""

    return get_risk_engine().assess(
        image=image,
        sensor=sensor,
        text=text,
        cross_modal=cross_modal,
        verifier=verifier,
        investigation=investigation,
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _demo_agent_result(
    agent: str,
    risk_score: float,
    decision: str = "PASS",
) -> Dict[str, Any]:
    """Create deterministic mock agent result."""

    return {
        "agent": agent,
        "domain": DOMAIN,
        "confidence": 1.0 - risk_score,
        "risk_score": risk_score,
        "decision": decision,
        "evidence": [],
        "contradictions": [],
        "model_version": f"{agent}-test-v0.1",
        "processing_time_ms": 1,
    }


def self_test() -> bool:
    """
    Test the complete weighted consensus with AdversarialVerifier available.

    Expected weighted values:

        Image       = 0.10
        Sensor      = 0.00
        Text        = 0.00
        CrossModal  = 0.025
        Verifier    = 0.00

    Since all five components are available, the original weights are used
    directly:

        Image       = 0.25
        Sensor      = 0.25
        Text        = 0.15
        CrossModal  = 0.25
        Verifier    = 0.10
    """

    image = _demo_agent_result(
        "ImageAgent",
        risk_score=0.10,
    )

    sensor = _demo_agent_result(
        "SensorAgent",
        risk_score=0.00,
    )

    text = _demo_agent_result(
        "TextAgent",
        risk_score=0.00,
    )

    cross_modal = _demo_agent_result(
        "CrossModalAgent",
        risk_score=0.025,
    )

    verifier = _demo_agent_result(
        "AdversarialVerifier",
        risk_score=0.00,
        decision="PASS",
    )

    verifier["verification_score"] = 0.0
    verifier["passed_checks"] = 12
    verifier["failed_checks"] = 0
    verifier["challenge_count"] = 0

    investigation = {
        "agent": "InvestigationAgent",
        "domain": DOMAIN,
        "confidence": 0.887857,
        "risk_score": 0.071429,
        "decision": "PASS",
        "investigation_score": 0.071429,
        "verification_tasks": [
            {
                "task_id": "LOSS-002",
                "priority": "MEDIUM",
                "type": "loss_quantification",
            }
        ],
        "human_review_recommended": False,
    }

    result = assess_risk(
        image=image,
        sensor=sensor,
        text=text,
        cross_modal=cross_modal,
        verifier=verifier,
        investigation=investigation,
    )

    assert result["agent"] == "RiskEngine"
    assert result["domain"] == DOMAIN

    assert 0.0 <= result["consensus_score"] <= 1.0
    assert 0.0 <= result["risk_score"] <= 1.0
    assert 0.0 <= result["confidence"] <= 1.0

    assert result["decision"] in {
        "VERIFIED",
        "REVIEW_REQUIRED",
        "UNCERTAIN",
    }

    # All five weighted components must now be available.
    assert result["unavailable_components"] == []

    assert result["usable_modality_count"] == 5

    assert result["component_scores"]["image"] == 0.10
    assert result["component_scores"]["sensor"] == 0.0
    assert result["component_scores"]["text"] == 0.0
    assert result["component_scores"]["cross_modal"] == 0.025
    assert result["component_scores"]["verifier"] == 0.0

    # Effective weights should equal the configured starting weights
    # because every weighted component is available.
    assert abs(
        result["effective_weights"]["image"]
        - 0.25
    ) < 1e-6

    assert abs(
        result["effective_weights"]["sensor"]
        - 0.25
    ) < 1e-6

    assert abs(
        result["effective_weights"]["text"]
        - 0.15
    ) < 1e-6

    assert abs(
        result["effective_weights"]["cross_modal"]
        - 0.25
    ) < 1e-6

    assert abs(
        result["effective_weights"]["verifier"]
        - 0.10
    ) < 1e-6

    effective_weight_sum = sum(
        result["effective_weights"].values()
    )

    assert abs(
        effective_weight_sum - 1.0
    ) < 1e-5

    # Expected:
    #
    # 0.10 * 0.25  = 0.025
    # 0.00 * 0.25  = 0.000
    # 0.00 * 0.15  = 0.000
    # 0.025 * 0.25 = 0.00625
    # 0.00 * 0.10  = 0.000
    #
    # Total = 0.03125
    expected_consensus = 0.03125

    assert abs(
        result["consensus_score"]
        - expected_consensus
    ) < 1e-6

    assert abs(
        result["risk_score"]
        - expected_consensus
    ) < 1e-6

    assert any(
        "AdversarialVerifier contributed"
        in evidence
        for evidence in result["evidence"]
    )

    print("RISK ENGINE INTEGRATION TEST: PASS")
    print(
        f"CONSENSUS SCORE: "
        f"{result['consensus_score']}"
    )
    print(
        f"RISK SCORE: "
        f"{result['risk_score']}"
    )
    print(
        f"CONFIDENCE: "
        f"{result['confidence']}"
    )
    print(
        f"DECISION: "
        f"{result['decision']}"
    )
    print(
        f"USABLE COMPONENTS: "
        f"{result['usable_modality_count']}"
    )
    print(
        f"UNAVAILABLE: "
        f"{result['unavailable_components']}"
    )
    print(
        f"EFFECTIVE WEIGHTS: "
        f"{result['effective_weights']}"
    )

    return True


if __name__ == "__main__":
    self_test()