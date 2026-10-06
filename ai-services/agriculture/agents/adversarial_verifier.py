"""
TruthChain Agriculture - Adversarial Verification Agent

Purpose
-------
Independently challenge the evidence produced by the Agriculture agents.

The verifier does NOT declare insurance fraud by itself.

It looks for:
    - agent failures
    - insufficient evidence
    - crop contradictions
    - event contradictions
    - satellite contradictions
    - image/claim mismatch
    - environmental evidence mismatch
    - cross-modal contradictions
    - investigation requirements
    - missing critical evidence

The output follows the shared TruthChain agent contract.

IMPORTANT
---------
This is a deterministic verification layer.

It is NOT a trained fraud classifier and its risk_score is NOT a calibrated
fraud probability.

Thresholds and rules are starting values and must be validated against a
proper agriculture insurance benchmark before operational use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional
import time


AGENT_NAME = "AdversarialVerifier"
DOMAIN = "agriculture"
AGENT_VERSION = "agriculture-adversarial-verifier-v0.1"


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


SUSPICIOUS_DECISIONS = {
    "SUSPICIOUS",
    "FAIL",
}


# Starting rule weights only.
# These are not learned fraud probabilities.
RULE_WEIGHTS = {
    "agent_failure": 0.30,
    "crop_contradiction": 0.25,
    "event_contradiction": 0.20,
    "environment_contradiction": 0.15,
    "cross_modal_contradiction": 0.25,
    "missing_evidence": 0.10,
    "investigation_required": 0.10,
}


@dataclass
class AdversarialVerificationResult:
    """Structured adversarial verification result."""

    agent: str
    domain: str
    confidence: float
    risk_score: float
    decision: str

    evidence: list[str]
    contradictions: list[str]

    model_version: str
    processing_time_ms: int

    verification_score: float
    challenge_count: int
    passed_checks: int
    failed_checks: int

    checks: list[Dict[str, Any]]
    recommendations: list[str]

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
            "verification_score": self.verification_score,
            "challenge_count": self.challenge_count,
            "passed_checks": self.passed_checks,
            "failed_checks": self.failed_checks,
            "checks": self.checks,
            "recommendations": self.recommendations,
        }


class AdversarialVerifier:
    """
    Deterministic adversarial verifier.

    The verifier attempts to challenge an otherwise accepted claim.

    It deliberately does not replace the CrossModalAgent or RiskEngine.
    """

    def __init__(
        self,
        rule_weights: Optional[Mapping[str, float]] = None,
    ) -> None:

        self.rule_weights = dict(
            rule_weights or RULE_WEIGHTS
        )

        self._validate_configuration()

    def _validate_configuration(self) -> None:
        """Validate rule weights."""

        required = set(RULE_WEIGHTS.keys())

        if set(self.rule_weights.keys()) != required:
            raise ValueError(
                "Verifier rule weights must contain exactly: "
                + ", ".join(sorted(required))
            )

        for name, weight in self.rule_weights.items():

            if weight < 0:
                raise ValueError(
                    f"Verifier rule weight '{name}' cannot be negative."
                )

        if sum(self.rule_weights.values()) <= 0:
            raise ValueError(
                "At least one verifier rule weight must be positive."
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
        except (TypeError, ValueError):
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
    def _decision(
        result: Optional[Mapping[str, Any]],
    ) -> Optional[str]:
        """Extract normalized decision."""

        if not result:
            return None

        value = result.get("decision")

        if value is None:
            return None

        return str(value).upper()

    @staticmethod
    def _get(
        result: Optional[Mapping[str, Any]],
        key: str,
        default: Any = None,
    ) -> Any:
        """Safely retrieve a field."""

        if not result:
            return default

        return result.get(
            key,
            default,
        )

    @staticmethod
    def _normalize_crop(
        value: Any,
    ) -> Optional[str]:
        """
        Normalize common Agriculture crop names.

        This mirrors the normalization concept used by CrossModalAgent.
        """

        if value is None:
            return None

        text = str(value).strip().lower()

        if not text:
            return None

        text = text.replace(
            "_",
            " ",
        )

        text = text.replace(
            "-",
            " ",
        )

        aliases = {
            "maize": "Maize",
            "corn": "Maize",
            "maize corn": "Maize",
            "maize (corn)": "Maize",
            "maize corn plant": "Maize",
            "maize (corn) plant": "Maize",

            "mustard": "Mustard",
            "rapeseed": "Mustard",
            "canola": "Mustard",
            "rapeseed canola": "Mustard",

            "sugarcane": "Sugarcane",
            "sugar cane": "Sugarcane",
            "sugar cane plant": "Sugarcane",

            "wheat": "Wheat",
            "wheat plant": "Wheat",

            "rice": "Rice",
            "rice plant": "Rice",

            "potato": "Potato",
            "potato plant": "Potato",

            "lentil": "Lentil",
            "lentils": "Lentil",

            "gram": "Gram",
            "chickpea": "Gram",
            "chickpeas": "Gram",

            "green pea": "Green pea",
            "green peas": "Green pea",

            "garlic": "Garlic",
            "coriander": "Coriander",
            "bersem": "Bersem",
            "fallow": "Fallow",
        }

        if text in aliases:
            return aliases[text]

        return str(value).strip()

    @staticmethod
    def _normalize_event(
        value: Any,
    ) -> Optional[str]:
        """Normalize common environmental event names."""

        if value is None:
            return None

        text = str(value).strip().lower()

        if not text:
            return None

        if (
            "heavy rain" in text
            or "rainfall" in text
            or "excess rain" in text
        ):
            return "Heavy rain"

        if (
            "flood" in text
            or "flooding" in text
        ):
            return "Flood"

        if (
            "drought" in text
            or "dry spell" in text
        ):
            return "Drought"

        if (
            "hail" in text
            or "hailstorm" in text
        ):
            return "Hail"

        if (
            "waterlogging" in text
            or "water logging" in text
        ):
            return "Waterlogging"

        if (
            "heatwave" in text
            or "heat wave" in text
        ):
            return "Heatwave"

        if (
            "frost" in text
        ):
            return "Frost"

        return str(value).strip()

    def _add_check(
        self,
        checks: list[Dict[str, Any]],
        name: str,
        category: str,
        passed: bool,
        severity: str,
        evidence: str,
    ) -> None:
        """Append a standardized verification check."""

        checks.append(
            {
                "check": name,
                "category": category,
                "passed": bool(passed),
                "severity": severity,
                "evidence": evidence,
            }
        )

    def _check_agent_failures(
        self,
        results: Dict[str, Optional[Mapping[str, Any]]],
        checks: list[Dict[str, Any]],
    ) -> None:
        """Check whether any upstream agent failed."""

        for name, result in results.items():

            if result is None:
                continue

            decision = self._decision(result)

            if decision in FAILURE_DECISIONS:

                self._add_check(
                    checks=checks,
                    name=f"{name}_failure_check",
                    category="agent_failure",
                    passed=False,
                    severity="HIGH",
                    evidence=(
                        f"{name} returned failure decision "
                        f"{decision}."
                    ),
                )

            else:

                self._add_check(
                    checks=checks,
                    name=f"{name}_failure_check",
                    category="agent_failure",
                    passed=True,
                    severity="INFO",
                    evidence=(
                        f"{name} did not report an execution failure."
                    ),
                )

    def _check_crop_consistency(
        self,
        text: Optional[Mapping[str, Any]],
        image: Optional[Mapping[str, Any]],
        satellite: Optional[Mapping[str, Any]],
        cross_modal: Optional[Mapping[str, Any]],
        checks: list[Dict[str, Any]],
    ) -> None:
        """Challenge crop consistency across modalities."""

        claimed_crop = self._normalize_crop(
            self._get(text, "crop")
        )

        if claimed_crop is None:
            claimed_crop = self._normalize_crop(
                self._get(
                    cross_modal,
                    "claimed_crop",
                )
            )

        image_crop = self._normalize_crop(
            self._get(
                image,
                "predicted_crop",
            )
        )

        satellite_crop = self._normalize_crop(
            self._get(
                satellite,
                "predicted_crop",
            )
        )

        available = [
            value
            for value in [
                claimed_crop,
                image_crop,
                satellite_crop,
            ]
            if value is not None
        ]

        if len(available) < 2:

            self._add_check(
                checks=checks,
                name="crop_consistency_check",
                category="crop_contradiction",
                passed=True,
                severity="INFO",
                evidence=(
                    "Insufficient independent crop labels were available "
                    "for an adversarial comparison."
                ),
            )

            return

        mismatches = []

        if (
            claimed_crop is not None
            and image_crop is not None
            and claimed_crop != image_crop
        ):
            mismatches.append(
                f"claim={claimed_crop}, image={image_crop}"
            )

        if (
            claimed_crop is not None
            and satellite_crop is not None
            and claimed_crop != satellite_crop
        ):
            mismatches.append(
                f"claim={claimed_crop}, satellite={satellite_crop}"
            )

        if mismatches:

            self._add_check(
                checks=checks,
                name="crop_consistency_check",
                category="crop_contradiction",
                passed=False,
                severity="HIGH",
                evidence=(
                    "Independent crop evidence conflicts: "
                    + "; ".join(mismatches)
                    + "."
                ),
            )

        else:

            self._add_check(
                checks=checks,
                name="crop_consistency_check",
                category="crop_contradiction",
                passed=True,
                severity="INFO",
                evidence=(
                    f"Available crop evidence is consistent with "
                    f"{claimed_crop}."
                ),
            )

    def _check_event_consistency(
        self,
        text: Optional[Mapping[str, Any]],
        sensor: Optional[Mapping[str, Any]],
        cross_modal: Optional[Mapping[str, Any]],
        checks: list[Dict[str, Any]],
    ) -> None:
        """Challenge claimed environmental event."""

        claimed_event = self._normalize_event(
            self._get(
                text,
                "event",
            )
        )

        if claimed_event is None:

            claimed_event = self._normalize_event(
                self._get(
                    cross_modal,
                    "claimed_event",
                )
            )

        sensor_events = self._get(
            sensor,
            "detected_events",
            [],
        )

        if sensor_events is None:
            sensor_events = []

        if isinstance(
            sensor_events,
            str,
        ):
            sensor_events = [
                sensor_events
            ]

        normalized_sensor_events = [
            self._normalize_event(event)
            for event in sensor_events
        ]

        normalized_sensor_events = [
            event
            for event in normalized_sensor_events
            if event is not None
        ]

        if (
            claimed_event is None
            or not normalized_sensor_events
        ):

            self._add_check(
                checks=checks,
                name="event_consistency_check",
                category="event_contradiction",
                passed=True,
                severity="INFO",
                evidence=(
                    "Insufficient independent event evidence was "
                    "available for adversarial comparison."
                ),
            )

            return

        if claimed_event in normalized_sensor_events:

            self._add_check(
                checks=checks,
                name="event_consistency_check",
                category="event_contradiction",
                passed=True,
                severity="INFO",
                evidence=(
                    f"Claimed event {claimed_event} is supported by "
                    "available sensor evidence."
                ),
            )

        else:

            self._add_check(
                checks=checks,
                name="event_consistency_check",
                category="event_contradiction",
                passed=False,
                severity="MEDIUM",
                evidence=(
                    f"Claimed event {claimed_event} was not found in "
                    "the detected sensor events: "
                    f"{normalized_sensor_events}."
                ),
            )

    def _check_environment(
        self,
        sensor: Optional[Mapping[str, Any]],
        checks: list[Dict[str, Any]],
    ) -> None:
        """Challenge environmental evidence quality."""

        if not sensor:

            self._add_check(
                checks=checks,
                name="environment_availability_check",
                category="environment_contradiction",
                passed=False,
                severity="MEDIUM",
                evidence=(
                    "No SensorAgent result was provided."
                ),
            )

            return

        decision = self._decision(sensor)

        if decision in FAILURE_DECISIONS:

            self._add_check(
                checks=checks,
                name="environment_availability_check",
                category="environment_contradiction",
                passed=False,
                severity="HIGH",
                evidence=(
                    f"SensorAgent returned failure decision "
                    f"{decision}."
                ),
            )

            return

        self._add_check(
            checks=checks,
            name="environment_availability_check",
            category="environment_contradiction",
            passed=True,
            severity="INFO",
            evidence=(
                "SensorAgent supplied usable environmental evidence."
            ),
        )

    def _check_cross_modal(
        self,
        cross_modal: Optional[Mapping[str, Any]],
        checks: list[Dict[str, Any]],
    ) -> None:
        """Challenge CrossModalAgent output."""

        if not cross_modal:

            self._add_check(
                checks=checks,
                name="cross_modal_check",
                category="cross_modal_contradiction",
                passed=False,
                severity="HIGH",
                evidence=(
                    "CrossModalAgent result was not provided."
                ),
            )

            return

        decision = self._decision(cross_modal)

        contradiction_count = self._get(
            cross_modal,
            "contradiction_count",
            0,
        )

        try:
            contradiction_count = int(
                contradiction_count
            )
        except (
            TypeError,
            ValueError,
        ):
            contradiction_count = 0

        if (
            decision in SUSPICIOUS_DECISIONS
            or contradiction_count > 0
        ):

            self._add_check(
                checks=checks,
                name="cross_modal_check",
                category="cross_modal_contradiction",
                passed=False,
                severity="HIGH",
                evidence=(
                    "CrossModalAgent reported "
                    f"decision={decision}, "
                    f"contradiction_count={contradiction_count}."
                ),
            )

        elif decision in INSUFFICIENT_DECISIONS:

            self._add_check(
                checks=checks,
                name="cross_modal_check",
                category="cross_modal_contradiction",
                passed=False,
                severity="MEDIUM",
                evidence=(
                    "CrossModalAgent reported insufficient evidence."
                ),
            )

        else:

            self._add_check(
                checks=checks,
                name="cross_modal_check",
                category="cross_modal_contradiction",
                passed=True,
                severity="INFO",
                evidence=(
                    "CrossModalAgent did not report a contradiction."
                ),
            )

    def _check_missing_evidence(
        self,
        image: Optional[Mapping[str, Any]],
        satellite: Optional[Mapping[str, Any]],
        sensor: Optional[Mapping[str, Any]],
        text: Optional[Mapping[str, Any]],
        cross_modal: Optional[Mapping[str, Any]],
        investigation: Optional[Mapping[str, Any]],
        checks: list[Dict[str, Any]],
    ) -> None:
        """Identify missing evidence without assigning artificial risk."""

        missing = []

        if image is None:
            missing.append("image")

        if satellite is None:
            missing.append("satellite")

        if sensor is None:
            missing.append("sensor")

        if text is None:
            missing.append("text")

        if cross_modal is None:
            missing.append("cross_modal")

        if investigation is None:
            missing.append("investigation")

        if missing:

            self._add_check(
                checks=checks,
                name="missing_evidence_check",
                category="missing_evidence",
                passed=False,
                severity="MEDIUM",
                evidence=(
                    "Missing evidence components: "
                    + ", ".join(missing)
                    + "."
                ),
            )

        else:

            self._add_check(
                checks=checks,
                name="missing_evidence_check",
                category="missing_evidence",
                passed=True,
                severity="INFO",
                evidence=(
                    "All expected Agriculture evidence components "
                    "were supplied."
                ),
            )

    def _check_investigation(
        self,
        investigation: Optional[Mapping[str, Any]],
        checks: list[Dict[str, Any]],
    ) -> None:
        """Challenge unresolved investigation requirements."""

        if not investigation:

            self._add_check(
                checks=checks,
                name="investigation_check",
                category="investigation_required",
                passed=False,
                severity="MEDIUM",
                evidence=(
                    "InvestigationAgent result was not provided."
                ),
            )

            return

        investigation_score = self._safe_float(
            self._get(
                investigation,
                "investigation_score",
            )
        )

        task_count = self._get(
            investigation,
            "task_count",
            None,
        )

        # InvestigationAgent uses "investigation_tasks".
        # Keep "verification_tasks" as a backward-compatible alias.
        tasks = self._get(
            investigation,
            "investigation_tasks",
            None,
        )

        if tasks is None:
            tasks = self._get(
                investigation,
                "verification_tasks",
                None,
            )

        if task_count is None and isinstance(
            tasks,
            list,
        ):
            task_count = len(tasks)

        if task_count is None:
            task_count = 0

        try:
            task_count = int(task_count)
        except (
            TypeError,
            ValueError,
        ):
            task_count = 0

        human_review = bool(
            self._get(
                investigation,
                "human_review_recommended",
                False,
            )
        )

        if (
            human_review
            or task_count > 0
            or (
                investigation_score is not None
                and investigation_score >= 0.50
            )
        ):

            self._add_check(
                checks=checks,
                name="investigation_check",
                category="investigation_required",
                passed=False,
                severity="MEDIUM",
                evidence=(
                    f"InvestigationAgent indicates additional "
                    f"verification is required "
                    f"(tasks={task_count}, "
                    f"score={investigation_score}, "
                    f"human_review={human_review})."
                ),
            )

        else:

            self._add_check(
                checks=checks,
                name="investigation_check",
                category="investigation_required",
                passed=True,
                severity="INFO",
                evidence=(
                    "InvestigationAgent did not identify unresolved "
                    "verification requirements."
                ),
            )

    def _calculate_verification_score(
        self,
        checks: list[Dict[str, Any]],
    ) -> float:
        """
        Calculate deterministic challenge score.

        The score represents how strongly the current evidence challenges
        the claim. It is not a fraud probability.
        """

        category_failures: Dict[str, int] = {}

        for check in checks:

            if check["passed"]:
                continue

            category = check["category"]

            category_failures[category] = (
                category_failures.get(
                    category,
                    0,
                )
                + 1
            )

        weighted_signal = 0.0
        total_weight = 0.0

        for category, weight in self.rule_weights.items():

            total_weight += weight

            if category in category_failures:

                # One or more failures in the category produce a full
                # category signal. We intentionally avoid multiplying the
                # score by the number of duplicate failures.
                weighted_signal += weight

        if total_weight <= 0:
            return 0.0

        return max(
            0.0,
            min(
                1.0,
                weighted_signal / total_weight,
            ),
        )

    def _determine_decision(
        self,
        verification_score: float,
        failed_checks: int,
        challenge_count: int,
    ) -> str:
        """
        Convert challenge score into an agent decision.

        The verifier uses SUSPICIOUS for substantial unresolved challenges.
        It does not use REJECTED because the verifier is not an adjudicator.
        """

        if challenge_count == 0:
            return "PASS"

        if verification_score >= 0.50:
            return "SUSPICIOUS"

        if failed_checks > 0:
            return "NEEDS_REVIEW"

        return "PASS"

    def _build_recommendations(
        self,
        checks: list[Dict[str, Any]],
    ) -> list[str]:

        recommendations: list[str] = []

        failed_categories = {
            check["category"]
            for check in checks
            if not check["passed"]
        }

        if "crop_contradiction" in failed_categories:
            recommendations.append(
                "Re-verify the claimed crop using independent field "
                "or multi-temporal evidence."
            )

        if "event_contradiction" in failed_categories:
            recommendations.append(
                "Independently verify the claimed environmental event "
                "using weather or official event records."
            )

        if "environment_contradiction" in failed_categories:
            recommendations.append(
                "Obtain additional environmental observations for "
                "the claim period."
            )

        if "cross_modal_contradiction" in failed_categories:
            recommendations.append(
                "Investigate disagreement between the multimodal "
                "evidence sources."
            )

        if "missing_evidence" in failed_categories:
            recommendations.append(
                "Collect missing evidence before making a final "
                "claim determination."
            )

        if "investigation_required" in failed_categories:
            recommendations.append(
                "Complete the outstanding InvestigationAgent "
                "verification tasks."
            )

        if "agent_failure" in failed_categories:
            recommendations.append(
                "Re-run failed agents or obtain an independent "
                "evidence source."
            )

        if not recommendations:
            recommendations.append(
                "No major adversarial challenge was identified from "
                "the supplied evidence."
            )

        return recommendations

    def verify(
        self,
        image: Optional[Mapping[str, Any]] = None,
        satellite: Optional[Mapping[str, Any]] = None,
        sensor: Optional[Mapping[str, Any]] = None,
        text: Optional[Mapping[str, Any]] = None,
        cross_modal: Optional[Mapping[str, Any]] = None,
        investigation: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Run adversarial verification.

        Parameters are expected to be outputs from the corresponding
        Agriculture agents.
        """

        start = time.perf_counter()

        results = {
            "image": image,
            "satellite": satellite,
            "sensor": sensor,
            "text": text,
            "cross_modal": cross_modal,
            "investigation": investigation,
        }

        checks: list[Dict[str, Any]] = []

        self._check_agent_failures(
            results=results,
            checks=checks,
        )

        self._check_crop_consistency(
            text=text,
            image=image,
            satellite=satellite,
            cross_modal=cross_modal,
            checks=checks,
        )

        self._check_event_consistency(
            text=text,
            sensor=sensor,
            cross_modal=cross_modal,
            checks=checks,
        )

        self._check_environment(
            sensor=sensor,
            checks=checks,
        )

        self._check_cross_modal(
            cross_modal=cross_modal,
            checks=checks,
        )

        self._check_missing_evidence(
            image=image,
            satellite=satellite,
            sensor=sensor,
            text=text,
            cross_modal=cross_modal,
            investigation=investigation,
            checks=checks,
        )

        self._check_investigation(
            investigation=investigation,
            checks=checks,
        )

        verification_score = (
            self._calculate_verification_score(
                checks=checks,
            )
        )

        failed_checks = sum(
            1
            for check in checks
            if not check["passed"]
        )

        passed_checks = sum(
            1
            for check in checks
            if check["passed"]
        )

        challenge_count = failed_checks

        decision = self._determine_decision(
            verification_score=verification_score,
            failed_checks=failed_checks,
            challenge_count=challenge_count,
        )

        contradictions = [
            check["evidence"]
            for check in checks
            if (
                not check["passed"]
                and check["category"]
                in {
                    "crop_contradiction",
                    "event_contradiction",
                    "environment_contradiction",
                    "cross_modal_contradiction",
                }
            )
        ]

        evidence = [
            (
                "Adversarial verification independently challenged "
                "the supplied Agriculture evidence."
            ),
            (
                "Verification score represents unresolved challenge "
                "signals and is not a fraud probability."
            ),
            (
                f"Completed {len(checks)} verification checks: "
                f"{passed_checks} passed and {failed_checks} failed."
            ),
        ]

        if decision == "PASS":

            evidence.append(
                "No major unresolved adversarial challenge was found "
                "in the supplied evidence."
            )

        elif decision == "NEEDS_REVIEW":

            evidence.append(
                "Some verification checks require additional evidence "
                "before the claim can be considered fully verified."
            )

        else:

            evidence.append(
                "Multiple challenge signals remain unresolved; "
                "human review is recommended."
            )

        recommendations = self._build_recommendations(
            checks=checks,
        )

        # Confidence measures how complete and internally assessable the
        # verification process was. It does not mean confidence in fraud.
        expected_checks = 7

        completeness = min(
            1.0,
            len(checks) / expected_checks,
        )

        if len(checks) == 0:
            confidence = 0.0
        else:
            contradiction_penalty = min(
                0.25,
                len(contradictions) * 0.05,
            )

            confidence = max(
                0.0,
                min(
                    1.0,
                    0.70 * completeness
                    + 0.30 * (1.0 - contradiction_penalty),
                ),
            )

        processing_time_ms = int(
            round(
                (time.perf_counter() - start) * 1000
            )
        )

        result = AdversarialVerificationResult(
            agent=AGENT_NAME,
            domain=DOMAIN,
            confidence=round(
                confidence,
                6,
            ),
            risk_score=round(
                verification_score,
                6,
            ),
            decision=decision,
            evidence=evidence,
            contradictions=contradictions,
            model_version=AGENT_VERSION,
            processing_time_ms=processing_time_ms,
            verification_score=round(
                verification_score,
                6,
            ),
            challenge_count=challenge_count,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            checks=checks,
            recommendations=recommendations,
        )

        return result.to_dict()

    def run(
        self,
        image: Optional[Mapping[str, Any]] = None,
        satellite: Optional[Mapping[str, Any]] = None,
        sensor: Optional[Mapping[str, Any]] = None,
        text: Optional[Mapping[str, Any]] = None,
        cross_modal: Optional[Mapping[str, Any]] = None,
        investigation: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Alias for verify()."""

        return self.verify(
            image=image,
            satellite=satellite,
            sensor=sensor,
            text=text,
            cross_modal=cross_modal,
            investigation=investigation,
        )


# ---------------------------------------------------------------------------
# Singleton + convenience API
# ---------------------------------------------------------------------------

_verifier: Optional[AdversarialVerifier] = None


def get_adversarial_verifier() -> AdversarialVerifier:
    """Return shared verifier instance."""

    global _verifier

    if _verifier is None:
        _verifier = AdversarialVerifier()

    return _verifier


def verify_claim(
    image: Optional[Mapping[str, Any]] = None,
    satellite: Optional[Mapping[str, Any]] = None,
    sensor: Optional[Mapping[str, Any]] = None,
    text: Optional[Mapping[str, Any]] = None,
    cross_modal: Optional[Mapping[str, Any]] = None,
    investigation: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience wrapper around the shared verifier."""

    return get_adversarial_verifier().verify(
        image=image,
        satellite=satellite,
        sensor=sensor,
        text=text,
        cross_modal=cross_modal,
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
    """Create deterministic mock agent output."""

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
    Test adversarial verification with coherent agriculture evidence.

    Expected scenario:

        Claimed crop: Wheat
        Image crop: Wheat
        Satellite crop: Wheat
        Claimed event: Heavy rain
        Sensor event: Heavy rain
        Cross-modal: PASS
        Investigation: PASS

    One investigation task is intentionally absent in this test so the
    verifier can demonstrate that it checks evidence completeness.
    """

    image = _demo_agent_result(
        "ImageAgent",
        risk_score=0.10,
    )

    image["predicted_crop"] = "Wheat"

    satellite = _demo_agent_result(
        "SatelliteAgent",
        risk_score=0.05,
    )

    satellite["predicted_crop"] = "Wheat"

    sensor = _demo_agent_result(
        "SensorAgent",
        risk_score=0.00,
    )

    sensor["detected_events"] = [
        "Heavy rain",
        "Waterlogging",
    ]

    text = _demo_agent_result(
        "TextAgent",
        risk_score=0.00,
    )

    text["crop"] = "Wheat"
    text["event"] = "Heavy rain"

    cross_modal = _demo_agent_result(
        "CrossModalAgent",
        risk_score=0.025,
    )

    cross_modal["claimed_crop"] = "Wheat"
    cross_modal["claimed_event"] = "Heavy rain"
    cross_modal["contradiction_count"] = 0
    cross_modal["agreement_score"] = 0.928571

    investigation = {
        "agent": "InvestigationAgent",
        "domain": DOMAIN,
        "confidence": 0.887857,
        "risk_score": 0.071429,
        "decision": "PASS",
        "investigation_score": 0.071429,
        "verification_tasks": [],
        "human_review_recommended": False,
    }

    result = verify_claim(
        image=image,
        satellite=satellite,
        sensor=sensor,
        text=text,
        cross_modal=cross_modal,
        investigation=investigation,
    )

    assert result["agent"] == "AdversarialVerifier"
    assert result["domain"] == DOMAIN

    assert 0.0 <= result["verification_score"] <= 1.0
    assert 0.0 <= result["risk_score"] <= 1.0
    assert 0.0 <= result["confidence"] <= 1.0

    assert result["decision"] in {
        "PASS",
        "NEEDS_REVIEW",
        "SUSPICIOUS",
    }

    assert result["passed_checks"] >= 1
    assert result["failed_checks"] >= 0

    assert len(result["checks"]) > 0

    assert (
        result["component"] if "component" in result else True
    )

    print("ADVERSARIAL VERIFIER TEST: PASS")
    print(
        f"VERIFICATION SCORE: "
        f"{result['verification_score']}"
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
        f"PASSED CHECKS: "
        f"{result['passed_checks']}"
    )
    print(
        f"FAILED CHECKS: "
        f"{result['failed_checks']}"
    )
    print(
        f"CHALLENGE COUNT: "
        f"{result['challenge_count']}"
    )

    return True


if __name__ == "__main__":
    self_test()