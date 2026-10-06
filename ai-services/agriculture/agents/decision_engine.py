"""
TruthChain Agriculture - Final Decision Engine

Purpose
-------
Converts the outputs of the Agriculture verification stack into a final
screening state.

Pipeline:

    CrossModalAgent
          +
    InvestigationAgent
          +
    AdversarialVerifier
          +
    RiskEngine
          |
          v
    DecisionEngine
          |
          +--> VERIFIED
          +--> REVIEW_REQUIRED
          +--> REJECTED
          +--> UNCERTAIN

IMPORTANT
---------
This is a deterministic screening/decision layer.

It is NOT an insurance adjudicator and does not establish fraud by itself.

The decision rules and thresholds are STARTING VALUES ONLY and must be
validated against appropriate agriculture-insurance data before operational
use.

The engine intentionally prefers REVIEW_REQUIRED over REJECTED when the
evidence is contradictory or incomplete.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional
import time


AGENT_NAME = "DecisionEngine"
DOMAIN = "agriculture"
AGENT_VERSION = "agriculture-decision-engine-v0.1"


# ---------------------------------------------------------------------------
# Decision constants
# ---------------------------------------------------------------------------

VERIFIED = "VERIFIED"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
REJECTED = "REJECTED"
UNCERTAIN = "UNCERTAIN"


VALID_DECISIONS = {
    VERIFIED,
    REVIEW_REQUIRED,
    REJECTED,
    UNCERTAIN,
}


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


# ---------------------------------------------------------------------------
# Starting thresholds
# ---------------------------------------------------------------------------

# These are screening thresholds only.

REVIEW_RISK_THRESHOLD = 0.50
HIGH_RISK_THRESHOLD = 0.75

# A verifier challenge score at or above this value means the claim has
# substantial unresolved adversarial challenges.
VERIFIER_REVIEW_THRESHOLD = 0.50

# Cross-modal inconsistency threshold.
CROSS_MODAL_REVIEW_THRESHOLD = 0.25


@dataclass
class FinalDecisionResult:
    """Structured final decision result."""

    agent: str
    domain: str
    confidence: float
    risk_score: float
    decision: str

    evidence: list[str]
    contradictions: list[str]

    model_version: str
    processing_time_ms: int

    consensus_score: Optional[float]
    verification_score: Optional[float]
    investigation_score: Optional[float]
    cross_modal_score: Optional[float]

    decision_reasons: list[str]
    human_review_required: bool
    human_review_reason: Optional[str]

    evidence_completeness: float
    verification_status: str

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
            "verification_score": self.verification_score,
            "investigation_score": self.investigation_score,
            "cross_modal_score": self.cross_modal_score,
            "decision_reasons": self.decision_reasons,
            "human_review_required": self.human_review_required,
            "human_review_reason": self.human_review_reason,
            "evidence_completeness": self.evidence_completeness,
            "verification_status": self.verification_status,
        }


class DecisionEngine:
    """
    Deterministic final screening decision layer.

    Inputs:

        cross_modal
        investigation
        verifier
        risk_engine

    The engine does not independently classify the crop, satellite scene,
    sensor data, or claim text.
    """

    def __init__(
        self,
        review_risk_threshold: float = REVIEW_RISK_THRESHOLD,
        high_risk_threshold: float = HIGH_RISK_THRESHOLD,
        verifier_review_threshold: float = (
            VERIFIER_REVIEW_THRESHOLD
        ),
        cross_modal_review_threshold: float = (
            CROSS_MODAL_REVIEW_THRESHOLD
        ),
    ) -> None:

        self.review_risk_threshold = float(
            review_risk_threshold
        )

        self.high_risk_threshold = float(
            high_risk_threshold
        )

        self.verifier_review_threshold = float(
            verifier_review_threshold
        )

        self.cross_modal_review_threshold = float(
            cross_modal_review_threshold
        )

        self._validate_configuration()

    def _validate_configuration(self) -> None:
        """Validate thresholds."""

        if not (
            0.0
            <= self.review_risk_threshold
            < self.high_risk_threshold
            <= 1.0
        ):
            raise ValueError(
                "Risk thresholds must satisfy "
                "0 <= review < high <= 1."
            )

        if not (
            0.0
            <= self.verifier_review_threshold
            <= 1.0
        ):
            raise ValueError(
                "Verifier review threshold must be between 0 and 1."
            )

        if not (
            0.0
            <= self.cross_modal_review_threshold
            <= 1.0
        ):
            raise ValueError(
                "Cross-modal review threshold must be between 0 and 1."
            )

    @staticmethod
    def _safe_float(
        value: Any,
    ) -> Optional[float]:
        """Convert a value into a bounded float."""

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
            min(
                1.0,
                value,
            ),
        )

    @staticmethod
    def _decision(
        result: Optional[Mapping[str, Any]],
    ) -> Optional[str]:
        """Extract normalized decision."""

        if not result:
            return None

        value = result.get(
            "decision"
        )

        if value is None:
            return None

        return str(
            value
        ).upper()

    @staticmethod
    def _get(
        result: Optional[Mapping[str, Any]],
        key: str,
        default: Any = None,
    ) -> Any:
        """Safely retrieve a result field."""

        if not result:
            return default

        return result.get(
            key,
            default,
        )

    def _extract_scores(
        self,
        cross_modal: Optional[Mapping[str, Any]],
        investigation: Optional[Mapping[str, Any]],
        verifier: Optional[Mapping[str, Any]],
        risk_engine: Optional[Mapping[str, Any]],
    ) -> Dict[str, Optional[float]]:
        """Extract relevant scores."""

        return {
            "consensus_score": self._safe_float(
                self._get(
                    risk_engine,
                    "consensus_score",
                )
            ),
            "verification_score": self._safe_float(
                self._get(
                    verifier,
                    "verification_score",
                )
            ),
            "investigation_score": self._safe_float(
                self._get(
                    investigation,
                    "investigation_score",
                )
            ),
            "cross_modal_score": self._safe_float(
                self._get(
                    cross_modal,
                    "risk_score",
                )
            ),
        }

    def _calculate_completeness(
        self,
        cross_modal: Optional[Mapping[str, Any]],
        investigation: Optional[Mapping[str, Any]],
        verifier: Optional[Mapping[str, Any]],
        risk_engine: Optional[Mapping[str, Any]],
    ) -> float:
        """
        Calculate evidence-processing completeness.

        This measures whether the decision layer received the expected
        verification components. It is not confidence that a claim is true.
        """

        components = [
            cross_modal,
            investigation,
            verifier,
            risk_engine,
        ]

        available = sum(
            1
            for component in components
            if component is not None
        )

        return available / len(
            components
        )

    def _collect_component_failures(
        self,
        cross_modal: Optional[Mapping[str, Any]],
        investigation: Optional[Mapping[str, Any]],
        verifier: Optional[Mapping[str, Any]],
        risk_engine: Optional[Mapping[str, Any]],
    ) -> list[str]:
        """Collect failed or insufficient component states."""

        failures: list[str] = []

        components = {
            "CrossModalAgent": cross_modal,
            "InvestigationAgent": investigation,
            "AdversarialVerifier": verifier,
            "RiskEngine": risk_engine,
        }

        for name, result in components.items():

            if result is None:
                failures.append(
                    f"{name} result is missing."
                )
                continue

            decision = self._decision(
                result
            )

            if decision in FAILURE_DECISIONS:

                failures.append(
                    f"{name} returned failure decision "
                    f"{decision}."
                )

            elif decision in INSUFFICIENT_DECISIONS:

                failures.append(
                    f"{name} returned insufficient evidence "
                    f"decision {decision}."
                )

        return failures

    def _collect_contradictions(
        self,
        cross_modal: Optional[Mapping[str, Any]],
        investigation: Optional[Mapping[str, Any]],
        verifier: Optional[Mapping[str, Any]],
        risk_engine: Optional[Mapping[str, Any]],
    ) -> list[str]:
        """Collect explicit contradictions from upstream components."""

        contradictions: list[str] = []

        components = {
            "CrossModalAgent": cross_modal,
            "InvestigationAgent": investigation,
            "AdversarialVerifier": verifier,
            "RiskEngine": risk_engine,
        }

        for name, result in components.items():

            if not result:
                continue

            values = result.get(
                "contradictions"
            )

            if not isinstance(
                values,
                list,
            ):
                continue

            for value in values:

                if value is None:
                    continue

                text = str(
                    value
                ).strip()

                if not text:
                    continue

                contradictions.append(
                    f"{name}: {text}"
                )

        return contradictions

    def _determine_decision(
        self,
        scores: Dict[str, Optional[float]],
        cross_modal_decision: Optional[str],
        investigation_decision: Optional[str],
        verifier_decision: Optional[str],
        risk_decision: Optional[str],
        failures: list[str],
        contradictions: list[str],
        completeness: float,
    ) -> tuple[str, list[str]]:
        """
        Determine final screening decision.

        Decision priority:

            1. Missing/failing core verification -> UNCERTAIN
            2. Strong unresolved adversarial challenge -> REVIEW_REQUIRED
            3. Strong cross-modal inconsistency -> REVIEW_REQUIRED
            4. High consensus risk -> REVIEW_REQUIRED
            5. Moderate consensus risk -> REVIEW_REQUIRED
            6. Complete low-risk coherent evidence -> VERIFIED

        REJECTED is deliberately conservative and is reserved for a future
        policy/adjudication layer rather than being inferred from one agent.
        """

        reasons: list[str] = []

        if failures:

            reasons.append(
                "One or more required verification components "
                "were unavailable or failed."
            )

            return (
                UNCERTAIN,
                reasons,
            )

        if completeness < 1.0:

            reasons.append(
                "The verification stack is incomplete."
            )

            return (
                UNCERTAIN,
                reasons,
            )

        verifier_score = scores.get(
            "verification_score"
        )

        if (
            verifier_score is not None
            and verifier_score
            >= self.verifier_review_threshold
        ):

            reasons.append(
                "Adversarial verification found substantial "
                "unresolved challenge signals."
            )

            return (
                REVIEW_REQUIRED,
                reasons,
            )

        if verifier_decision in {
            "SUSPICIOUS",
        }:

            reasons.append(
                "AdversarialVerifier reported SUSPICIOUS."
            )

            return (
                REVIEW_REQUIRED,
                reasons,
            )

        cross_modal_score = scores.get(
            "cross_modal_score"
        )

        if (
            cross_modal_score is not None
            and cross_modal_score
            >= self.cross_modal_review_threshold
        ):

            reasons.append(
                "Cross-modal inconsistency exceeds the starting "
                "review threshold."
            )

            return (
                REVIEW_REQUIRED,
                reasons,
            )

        if cross_modal_decision in {
            "SUSPICIOUS",
            "FAIL",
        }:

            reasons.append(
                "CrossModalAgent reported unresolved disagreement."
            )

            return (
                REVIEW_REQUIRED,
                reasons,
            )

        consensus_score = scores.get(
            "consensus_score"
        )

        if consensus_score is None:

            reasons.append(
                "RiskEngine did not provide a usable consensus score."
            )

            return (
                UNCERTAIN,
                reasons,
            )

        if consensus_score >= self.high_risk_threshold:

            reasons.append(
                "Consensus risk signal exceeds the starting "
                "high-risk threshold."
            )

            return (
                REVIEW_REQUIRED,
                reasons,
            )

        if consensus_score >= self.review_risk_threshold:

            reasons.append(
                "Consensus risk signal exceeds the starting "
                "review threshold."
            )

            return (
                REVIEW_REQUIRED,
                reasons,
            )

        if investigation_decision in {
            "NEEDS_REVIEW",
            "SUSPICIOUS",
        }:

            reasons.append(
                "InvestigationAgent identified unresolved "
                "verification requirements."
            )

            return (
                REVIEW_REQUIRED,
                reasons,
            )

        if contradictions:

            reasons.append(
                "Upstream components contain explicit contradictions."
            )

            return (
                REVIEW_REQUIRED,
                reasons,
            )

        if risk_decision == REVIEW_REQUIRED:

            reasons.append(
                "RiskEngine itself recommends additional review."
            )

            return (
                REVIEW_REQUIRED,
                reasons,
            )

        reasons.append(
            "All required verification components are available and "
            "the supplied evidence does not exceed the starting "
            "review thresholds."
        )

        return (
            VERIFIED,
            reasons,
        )

    def _build_human_review_reason(
        self,
        decision: str,
        reasons: list[str],
    ) -> Optional[str]:
        """Build human-review routing reason."""

        if decision == VERIFIED:
            return None

        if decision == UNCERTAIN:

            return (
                "The verification stack is incomplete or unavailable. "
                "Additional evidence is required before a final claim "
                "decision."
            )

        if decision == REVIEW_REQUIRED:

            return (
                "The claim requires human review because: "
                + " ".join(reasons)
            )

        if decision == REJECTED:

            return (
                "The current decision indicates rejection by an "
                "explicit adjudication rule."
            )

        return (
            "Human review is required."
        )

    def _build_evidence(
        self,
        decision: str,
        scores: Dict[str, Optional[float]],
        completeness: float,
    ) -> list[str]:
        """Build factual decision evidence."""

        evidence = [
            (
                "DecisionEngine combines previously generated "
                "verification outputs and does not rerun the "
                "underlying models."
            ),
            (
                "The final decision is a deterministic screening "
                "state, not a calibrated fraud probability."
            ),
            (
                f"Verification stack completeness: "
                f"{completeness:.3f}."
            ),
        ]

        if scores["consensus_score"] is not None:

            evidence.append(
                "RiskEngine consensus score: "
                f"{scores['consensus_score']:.6f}."
            )

        if scores["verification_score"] is not None:

            evidence.append(
                "Adversarial verification score: "
                f"{scores['verification_score']:.6f}."
            )

        if scores["investigation_score"] is not None:

            evidence.append(
                "Investigation score: "
                f"{scores['investigation_score']:.6f}."
            )

        if scores["cross_modal_score"] is not None:

            evidence.append(
                "Cross-modal risk/inconsistency score: "
                f"{scores['cross_modal_score']:.6f}."
            )

        evidence.append(
            f"Final screening state: {decision}."
        )

        return evidence

    def decide(
        self,
        cross_modal: Optional[Mapping[str, Any]] = None,
        investigation: Optional[Mapping[str, Any]] = None,
        verifier: Optional[Mapping[str, Any]] = None,
        risk_engine: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Produce the final screening decision.
        """

        start = time.perf_counter()

        scores = self._extract_scores(
            cross_modal=cross_modal,
            investigation=investigation,
            verifier=verifier,
            risk_engine=risk_engine,
        )

        completeness = self._calculate_completeness(
            cross_modal=cross_modal,
            investigation=investigation,
            verifier=verifier,
            risk_engine=risk_engine,
        )

        failures = self._collect_component_failures(
            cross_modal=cross_modal,
            investigation=investigation,
            verifier=verifier,
            risk_engine=risk_engine,
        )

        contradictions = self._collect_contradictions(
            cross_modal=cross_modal,
            investigation=investigation,
            verifier=verifier,
            risk_engine=risk_engine,
        )

        cross_modal_decision = self._decision(
            cross_modal
        )

        investigation_decision = self._decision(
            investigation
        )

        verifier_decision = self._decision(
            verifier
        )

        risk_decision = self._decision(
            risk_engine
        )

        (
            decision,
            reasons,
        ) = self._determine_decision(
            scores=scores,
            cross_modal_decision=cross_modal_decision,
            investigation_decision=investigation_decision,
            verifier_decision=verifier_decision,
            risk_decision=risk_decision,
            failures=failures,
            contradictions=contradictions,
            completeness=completeness,
        )

        human_review_required = decision in {
            REVIEW_REQUIRED,
            UNCERTAIN,
        }

        human_review_reason = (
            self._build_human_review_reason(
                decision=decision,
                reasons=reasons,
            )
        )

        evidence = self._build_evidence(
            decision=decision,
            scores=scores,
            completeness=completeness,
        )

        # Risk score is inherited from the consensus layer when available.
        # It remains a consensus signal rather than a fraud probability.
        risk_score = (
            scores["consensus_score"]
            if scores["consensus_score"] is not None
            else 0.5
        )

        # Confidence reflects completeness and agreement of the decision
        # process, not confidence that fraud occurred or did not occur.
        base_confidence = completeness

        if decision == VERIFIED:

            confidence = min(
                1.0,
                base_confidence,
            )

        elif decision == REVIEW_REQUIRED:

            confidence = min(
                1.0,
                0.75 * base_confidence,
            )

        elif decision == UNCERTAIN:

            confidence = min(
                1.0,
                0.50 * base_confidence,
            )

        else:

            confidence = min(
                1.0,
                0.75 * base_confidence,
            )

        if contradictions:

            confidence = max(
                0.0,
                confidence
                - min(
                    0.20,
                    len(contradictions) * 0.03,
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

        verification_status = (
            "COMPLETE"
            if completeness == 1.0
            else "INCOMPLETE"
        )

        result = FinalDecisionResult(
            agent=AGENT_NAME,
            domain=DOMAIN,
            confidence=round(
                confidence,
                6,
            ),
            risk_score=round(
                risk_score,
                6,
            ),
            decision=decision,
            evidence=evidence,
            contradictions=contradictions,
            model_version=AGENT_VERSION,
            processing_time_ms=(
                processing_time_ms
            ),
            consensus_score=scores[
                "consensus_score"
            ],
            verification_score=scores[
                "verification_score"
            ],
            investigation_score=scores[
                "investigation_score"
            ],
            cross_modal_score=scores[
                "cross_modal_score"
            ],
            decision_reasons=reasons,
            human_review_required=(
                human_review_required
            ),
            human_review_reason=(
                human_review_reason
            ),
            evidence_completeness=round(
                completeness,
                6,
            ),
            verification_status=(
                verification_status
            ),
        )

        return result.to_dict()

    def run(
        self,
        cross_modal: Optional[Mapping[str, Any]] = None,
        investigation: Optional[Mapping[str, Any]] = None,
        verifier: Optional[Mapping[str, Any]] = None,
        risk_engine: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Alias for decide()."""

        return self.decide(
            cross_modal=cross_modal,
            investigation=investigation,
            verifier=verifier,
            risk_engine=risk_engine,
        )


# ---------------------------------------------------------------------------
# Singleton + convenience API
# ---------------------------------------------------------------------------

_decision_engine: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    """Return shared DecisionEngine instance."""

    global _decision_engine

    if _decision_engine is None:
        _decision_engine = DecisionEngine()

    return _decision_engine


def make_decision(
    cross_modal: Optional[Mapping[str, Any]] = None,
    investigation: Optional[Mapping[str, Any]] = None,
    verifier: Optional[Mapping[str, Any]] = None,
    risk_engine: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience wrapper."""

    return get_decision_engine().decide(
        cross_modal=cross_modal,
        investigation=investigation,
        verifier=verifier,
        risk_engine=risk_engine,
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

def _agent_result(
    agent: str,
    risk_score: float,
    decision: str = "PASS",
) -> Dict[str, Any]:
    """Create deterministic test result."""

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
    Test the final decision layer using the complete coherent pipeline.

    Expected result:

        VERIFIED
        human_review_required = False
        verification_status = COMPLETE
    """

    cross_modal = _agent_result(
        "CrossModalAgent",
        risk_score=0.025,
        decision="PASS",
    )

    cross_modal["agreement_score"] = 0.928571
    cross_modal["contradiction_count"] = 0

    investigation = _agent_result(
        "InvestigationAgent",
        risk_score=0.071429,
        decision="PASS",
    )

    investigation["investigation_score"] = 0.071429
    investigation["verification_tasks"] = []
    investigation["human_review_recommended"] = False

    verifier = _agent_result(
        "AdversarialVerifier",
        risk_score=0.0,
        decision="PASS",
    )

    verifier["verification_score"] = 0.0
    verifier["passed_checks"] = 12
    verifier["failed_checks"] = 0
    verifier["challenge_count"] = 0

    risk_engine = _agent_result(
        "RiskEngine",
        risk_score=0.03125,
        decision="VERIFIED",
    )

    risk_engine["consensus_score"] = 0.03125
    risk_engine["effective_weights"] = {
        "image": 0.25,
        "sensor": 0.25,
        "text": 0.15,
        "cross_modal": 0.25,
        "verifier": 0.10,
    }

    result = make_decision(
        cross_modal=cross_modal,
        investigation=investigation,
        verifier=verifier,
        risk_engine=risk_engine,
    )

    assert result["agent"] == "DecisionEngine"
    assert result["domain"] == DOMAIN

    assert result["decision"] == VERIFIED

    assert result["human_review_required"] is False

    assert result["verification_status"] == "COMPLETE"

    assert result["evidence_completeness"] == 1.0

    assert result["consensus_score"] == 0.03125

    assert result["verification_score"] == 0.0

    assert result["investigation_score"] == 0.071429

    assert result["cross_modal_score"] == 0.025

    assert result["risk_score"] == 0.03125

    assert 0.0 <= result["confidence"] <= 1.0

    assert len(result["decision_reasons"]) >= 1

    assert result["human_review_reason"] is None

    print("DECISION ENGINE TEST: PASS")
    print(
        f"DECISION: "
        f"{result['decision']}"
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
        f"EVIDENCE COMPLETENESS: "
        f"{result['evidence_completeness']}"
    )
    print(
        f"VERIFICATION STATUS: "
        f"{result['verification_status']}"
    )
    print(
        f"HUMAN REVIEW REQUIRED: "
        f"{result['human_review_required']}"
    )
    print(
        f"REASON: "
        f"{result['decision_reasons']}"
    )

    return True


if __name__ == "__main__":
    self_test()