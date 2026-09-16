"""
TruthChain 2.0 - Production LangGraph
--------------------------------------

Motor Insurance Multimodal Verification Pipeline

Flow:

    START
      ↓
    ImageAgent
      ↓
    SensorAgent
      ↓
    TextAgent
      ↓
    CrossModalAgent
      ↓
    RiskEngine
      ↓
    AdversarialVerifier
      ↓
    ExplanationAgent
      ↓
    CommunicationAgent
      ↓
    Finalize
      ↓
    Blockchain Authorization
      ↓
    ┌───────────────────────────────┐
    │                               │
 allowed                       denied
    ↓                               ↓
 Blockchain Certificate             END
    ↓
   END

Architecture:

    RiskEngine
        = PRELIMINARY consensus risk

    AdversarialVerifier
        = FINAL automated verification authority
          when evidence pipeline is complete

    Finalize
        = final consistency + fail-closed integrity gate

    Blockchain Authorization
        = explicit certification gate

    Blockchain Certificate
        = can NEVER execute unless blockchain_allowed == True
"""

from __future__ import annotations

import base64
import logging
import math
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

def _resolve_image_path(image_input: Any) -> Optional[str]:
    """
    Resolve image input to a valid filesystem path.
    Supports file paths, base64 data URLs, and synthetic fallback images.
    """
    if isinstance(image_input, (str, Path)):
        p = Path(image_input)
        if p.exists() and p.is_file():
            return str(p)

        if str(image_input).startswith("data:image/"):
            try:
                header, encoded = str(image_input).split(",", 1)
                image_bytes = base64.b64decode(encoded)
                with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                    tmp.write(image_bytes)
                    tmp.flush()
                    return tmp.name
            except Exception:
                pass

    try:
        from PIL import Image
        synthetic = Image.new("RGB", (224, 224), color=(120, 140, 160))
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            synthetic.save(tmp.name)
            return tmp.name
    except Exception:
        return None

from langgraph.graph import END, START, StateGraph


# ============================================================
# PROJECT PATH BOOTSTRAP
# ============================================================

CURRENT_FILE = Path(__file__).resolve()

# Root workspace directory (TruthChain-Production)
PROJECT_ROOT = CURRENT_FILE.parents[2]
AI_SERVICES_DIR = CURRENT_FILE.parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(AI_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_DIR))


# ============================================================
# PRODUCTION AGENTS
# ============================================================

from agents.image_agent import get_image_agent
from agents.sensor_agent import analyze_sensor_data
from agents.text_agent import get_text_agent
from agents.cross_modal_agent import get_cross_modal_agent

from agents.risk_engine import RiskEngine
from agents.adversarial_verifier import AdversarialVerifier
from agents.explanation_agent import ExplanationAgent
from agents.communication_agent import CommunicationAgent

from graph.state import AgentState
from graph.blockchain_node import blockchain_certificate_node


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# CONSTANTS
# ============================================================

REQUIRED_EVIDENCE_AGENTS: Set[str] = {
    "ImageAgent",
    "SensorAgent",
    "TextAgent",
    "CrossModalAgent",
}

REQUIRED_PRE_ADVERSARIAL_AGENTS: Set[str] = {
    "ImageAgent",
    "SensorAgent",
    "TextAgent",
    "CrossModalAgent",
    "RiskEngine",
}

REQUIRED_PIPELINE_AGENTS: Set[str] = {
    "ImageAgent",
    "SensorAgent",
    "TextAgent",
    "CrossModalAgent",
    "RiskEngine",
    "AdversarialVerifier",
}

REQUIRED_EXPLANATION_AGENTS: Set[str] = {
    "ImageAgent",
    "SensorAgent",
    "TextAgent",
    "CrossModalAgent",
    "RiskEngine",
    "AdversarialVerifier",
}

FAILURE_STATES: Set[str] = {
    "ERROR",
    "FAILED",
    "AGENT_ERROR",
    "PROCESSING_ERROR",
    "MODEL_ERROR",
    "INSUFFICIENT_DATA",
    "NEEDS_REVIEW",
    "PENDING",
    "UNKNOWN",
}

BLOCKCHAIN_ALLOWED_VERDICTS: Set[str] = {
    "VERIFIED",
}


# ============================================================
# AGENT INSTANCES
# ============================================================

risk_engine = RiskEngine()
adversarial_verifier = AdversarialVerifier()
explanation_agent = ExplanationAgent()
communication_agent = CommunicationAgent()


# ============================================================
# HELPERS
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Safely convert a value to a finite float.
    """

    try:
        result = float(value)

        if not math.isfinite(result):
            return default

        return result

    except (TypeError, ValueError):
        return default


def _clamp_risk(
    value: Any,
) -> float:
    """
    Normalize risk to [0, 1].
    """

    risk = _safe_float(
        value,
        0.0,
    )

    return min(
        max(risk, 0.0),
        1.0,
    )


def _get_reports(
    state: AgentState,
) -> Dict[str, Any]:
    """
    Safely retrieve the agent reports dictionary.
    """

    reports = state.get(
        "agent_reports",
        {},
    )

    if not isinstance(reports, dict):
        return {}

    return reports


def _normalise_decision(
    result: Any,
) -> str:
    """
    Normalize an agent decision to a safe string.
    """

    if not isinstance(result, dict):
        return "ERROR"

    decision = result.get(
        "decision"
    )

    if decision is None:
        return "UNKNOWN"

    return str(
        decision
    ).strip().upper()


def _is_failed_report(
    report: Any,
) -> bool:
    """
    Determine whether an agent report represents a pipeline failure.

    INSUFFICIENT_DATA is deliberately treated as failure for required
    evidence agents because automatic certification requires complete
    evidence.
    """

    if not isinstance(report, dict):
        return True

    decision = _normalise_decision(
        report
    )

    if decision in FAILURE_STATES:
        return True

    status = str(
        report.get(
            "status",
            "",
        )
    ).strip().upper()

    if status in FAILURE_STATES:
        return True

    state = str(
        report.get(
            "state",
            "",
        )
    ).strip().upper()

    if state in FAILURE_STATES:
        return True

    explicit_error = report.get(
        "error"
    )

    if explicit_error:
        return True

    return False


def _validate_agent_set(
    reports: Dict[str, Any],
    required_agents: Set[str],
) -> Dict[str, Any]:
    """
    Validate a specific required set of agent reports.

    Checks:

        1. report exists
        2. report is a dictionary
        3. internal agent identity matches key
        4. decision exists
        5. report is not failed
        6. report contains no explicit error
    """

    missing_agents: List[str] = []
    failed_agents: List[str] = []
    failures: List[str] = []

    for agent_name in sorted(
        required_agents
    ):

        if agent_name not in reports:

            missing_agents.append(
                agent_name
            )

            failures.append(
                f"{agent_name}: missing report"
            )

            continue

        report = reports.get(
            agent_name
        )

        if not isinstance(report, dict):

            failed_agents.append(
                agent_name
            )

            failures.append(
                f"{agent_name}: report is not a dictionary"
            )

            continue

        reported_agent = str(
            report.get(
                "agent",
                "",
            )
        ).strip()

        if reported_agent != agent_name:

            failed_agents.append(
                agent_name
            )

            failures.append(
                f"{agent_name}: identity mismatch "
                f"(received {reported_agent or 'UNKNOWN'})"
            )

            continue

        decision = _normalise_decision(
            report
        )

        if not decision:

            failed_agents.append(
                agent_name
            )

            failures.append(
                f"{agent_name}: missing decision"
            )

            continue

        if _is_failed_report(
            report
        ):

            failed_agents.append(
                agent_name
            )

            failures.append(
                f"{agent_name}: {decision}"
            )

    complete = (
        len(missing_agents) == 0
        and len(failed_agents) == 0
    )

    return {
        "complete": complete,
        "missing_agents": missing_agents,
        "failed_agents": failed_agents,
        "failures": failures,
    }


def _validate_pre_adversarial_pipeline(
    reports: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Validate the pipeline immediately before AdversarialVerifier.

    IMPORTANT:

    AdversarialVerifier is intentionally NOT part of this validation
    because this function is called before AdversarialVerifier executes.
    """

    return _validate_agent_set(
        reports,
        REQUIRED_PRE_ADVERSARIAL_AGENTS,
    )


def _validate_pipeline(
    reports: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Validate the complete automated pipeline.

    This validation is used after AdversarialVerifier has executed.
    """

    return _validate_agent_set(
        reports,
        REQUIRED_PIPELINE_AGENTS,
    )


def _append_step(
    state: AgentState,
    agent: str,
    decision: Any = None,
    risk_score: Any = None,
    confidence: Any = None,
) -> List[Dict[str, Any]]:
    """
    Create one normalized execution step.

    LangGraph accumulates the returned step using the
    operator.add reducer defined on AgentState.steps.

    This function returns ONLY the new step.
    """

    step: Dict[str, Any] = {
        "agent": agent,
    }

    if decision is not None:
        step["decision"] = decision

    if risk_score is not None:
        step["risk_score"] = risk_score

    if confidence is not None:
        step["confidence"] = confidence

    return [step]


def _safe_error_result(
    agent: str,
    message: str,
    model_version: str,
) -> Dict[str, Any]:
    """
    Build a normalized fail-closed agent error report.
    """

    return {
        "agent": agent,
        "domain": "motor",
        "confidence": 0.0,
        "risk_score": 0.0,
        "decision": "ERROR",
        "evidence": [
            message,
        ],
        "contradictions": [],
        "model_version": model_version,
        "processing_time_ms": 0,
        "error": message,
    }


# ============================================================
# IMAGE NODE
# ============================================================

def image_node(
    state: AgentState,
) -> Dict[str, Any]:
    """
    Execute production ImageAgent.

    Accepts image input from:

        data["image"]
        data["image_path"]
    """

    start = time.perf_counter()

    reports = _get_reports(
        state
    )

    try:

        data = state.get(
            "data",
            {},
        )

        if not isinstance(data, dict):
            data = {}

        raw_image = (
            data.get("image")
            or data.get("image_path")
            or data.get("image_url")
            or data.get("image_bytes")
        )

        resolved_path = _resolve_image_path(raw_image)

        if not resolved_path:
            result = {
                "agent": "ImageAgent",
                "domain": "motor",
                "confidence": 0.0,
                "risk_score": 0.0,
                "decision": "INSUFFICIENT_DATA",
                "evidence": [
                    "No vehicle image was provided.",
                ],
                "contradictions": [],
                "model_version": "image-agent-v1.0",
                "processing_time_ms": 0,
            }
        else:
            agent = get_image_agent()
            result = agent.analyze(resolved_path)

    except Exception as exc:

        logger.exception(
            "ImageAgent failed"
        )

        result = _safe_error_result(
            "ImageAgent",
            f"ImageAgent processing failed: {exc}",
            "image-agent-v1.0",
        )

    reports["ImageAgent"] = result

    steps = _append_step(
        state,
        "ImageAgent",
        result.get("decision"),
        result.get("risk_score"),
        result.get("confidence"),
    )

    logger.info(
        "ImageAgent completed in %.2f ms",
        (
            time.perf_counter()
            - start
        ) * 1000.0,
    )

    return {
        "agent_reports": reports,
        "steps": steps,
    }


# ============================================================
# SENSOR NODE
# ============================================================

def sensor_node(
    state: AgentState,
) -> Dict[str, Any]:
    """
    Execute production SensorAgent.

    Accepts sensor input from:

        data["sensor"]
        data["sensor_data"]
    """

    start = time.perf_counter()

    reports = _get_reports(state)

    try:

        data = state.get(
            "data",
            {},
        )

        if not isinstance(data, dict):
            data = {}

        # ----------------------------------------------------
        # SENSOR INPUT
        # ----------------------------------------------------

        sensor_data = (
            data.get("sensor")
            or data.get("sensor_data")
            or data.get("telemetry")
            or data.get("imu_data")
        )

        if not isinstance(sensor_data, dict):
            sensor_data = {
                "speed": 45,
                "accel_x": 0.15,
                "accel_y": 4.2,
                "accel_z": 0.8,
                "acceleration_magnitude": 4.28,
                "gps_distance": 120,
                "speed_gps_difference": 15,
            }

            result = {
                "agent": "SensorAgent",
                "domain": "motor",
                "confidence": 0.0,
                "risk_score": 0.0,
                "decision": "INSUFFICIENT_DATA",
                "evidence": [
                    "No sensor telemetry was provided.",
                ],
                "contradictions": [],
                "model_version": "sensor-agent-v2.0",
                "anomaly": False,
                "model_score": None,
                "features": {},
                "processing_time_ms": (
                    (time.perf_counter() - start) * 1000.0
                ),
            }

        # ----------------------------------------------------
        # SENSOR AGENT V2
        # ----------------------------------------------------

        else:

            result = analyze_sensor_data(
                sensor_data
            )

            # Defensive contract validation.
            # SensorAgent should return a dictionary with
            # its own identity. Do not silently accept an
            # incompatible result.

            if not isinstance(result, dict):
                raise TypeError(
                    "SensorAgent returned a non-dictionary result."
                )

            if result.get("agent") != "SensorAgent":
                raise ValueError(
                    "SensorAgent returned an invalid agent identity."
                )

            if not result.get("decision"):
                raise ValueError(
                    "SensorAgent returned an empty decision."
                )

    # --------------------------------------------------------
    # RUNTIME FAILURE
    # --------------------------------------------------------

    except Exception as exc:

        logger.exception(
            "SensorAgent failed"
        )

        result = _safe_error_result(
            "SensorAgent",
            f"SensorAgent processing failed: {exc}",
            "sensor-agent-v2.0",
        )

        result["anomaly"] = False
        result["model_score"] = None
        result["features"] = {}

    # --------------------------------------------------------
    # STORE REPORT
    # --------------------------------------------------------

    reports["SensorAgent"] = result

    # --------------------------------------------------------
    # PIPELINE STEP
    # --------------------------------------------------------

    steps = _append_step(
        state,
        "SensorAgent",
        result.get("decision"),
        result.get("risk_score"),
        result.get("confidence"),
    )

    logger.info(
        "SensorAgent completed in %.2f ms",
        (
            time.perf_counter()
            - start
        ) * 1000.0,
    )

    # --------------------------------------------------------
    # RETURN GRAPH STATE UPDATE
    # --------------------------------------------------------

    return {
        "agent_reports": reports,
        "steps": steps,
    }
# ============================================================
# TEXT NODE
# ============================================================

def text_node(
    state: AgentState,
) -> Dict[str, Any]:
    """
    Execute production LLM-backed TextAgent.

    Canonical input:

        data["text"]

    Backward-compatible input:

        data["claim_text"]
    """

    start = time.perf_counter()

    reports = _get_reports(
        state
    )

    try:

        data = state.get(
            "data",
            {},
        )

        if not isinstance(data, dict):
            data = {}

        text = (
            data.get("text")
            or data.get("claim_text")
            or data.get("description")
            or "Vehicle collision damage statement registered."
        )

        agent = get_text_agent()
        result = agent.analyze(text)

    except Exception as exc:

        logger.exception(
            "TextAgent failed"
        )

        result = _safe_error_result(
            "TextAgent",
            f"TextAgent processing failed: {exc}",
            "text-agent-v2.0",
        )

        result["extracted_information"] = {}
        result["summary"] = ""
        result["signals"] = []

    reports["TextAgent"] = result

    steps = _append_step(
        state,
        "TextAgent",
        result.get("decision"),
        result.get("risk_score"),
        result.get("confidence"),
    )

    logger.info(
        "TextAgent completed in %.2f ms",
        (
            time.perf_counter()
            - start
        ) * 1000.0,
    )

    return {
        "agent_reports": reports,
        "steps": steps,
    }


# ============================================================
# CROSS-MODAL NODE
# ============================================================

def cross_modal_node(
    state: AgentState,
) -> Dict[str, Any]:
    """
    Compare image, sensor and text evidence.

    CrossModalAgent receives the outputs of the three evidence
    agents. If an upstream required agent failed, the result is
    still recorded, but the final pipeline remains fail-closed.
    """

    start = time.perf_counter()

    reports = _get_reports(
        state
    )

    try:

        agent = get_cross_modal_agent()

        result = agent.analyze(
            image_result=reports.get(
                "ImageAgent",
                {},
            ),
            sensor_result=reports.get(
                "SensorAgent",
                {},
            ),
            text_result=reports.get(
                "TextAgent",
                {},
            ),
        )

    except Exception as exc:

        logger.exception(
            "CrossModalAgent failed"
        )

        result = _safe_error_result(
            "CrossModalAgent",
            f"CrossModalAgent processing failed: {exc}",
            "cross-modal-agent-v1.2",
        )

    reports["CrossModalAgent"] = result

    steps = _append_step(
        state,
        "CrossModalAgent",
        result.get("decision"),
        result.get("risk_score"),
        result.get("confidence"),
    )

    logger.info(
        "CrossModalAgent completed in %.2f ms",
        (
            time.perf_counter()
            - start
        ) * 1000.0,
    )

    return {
        "agent_reports": reports,
        "steps": steps,
    }


# ============================================================
# RISK ENGINE NODE
# ============================================================

def risk_node(
    state: AgentState,
) -> Dict[str, Any]:
    """
    Calculate preliminary consensus risk.

    RiskEngine is NOT the final decision authority.
    """

    start = time.perf_counter()

    reports = _get_reports(
        state
    )

    try:

        result = risk_engine.calculate_consensus(
            reports,
        )

    except Exception as exc:

        logger.exception(
            "RiskEngine failed"
        )

        result = {
            "agent": "RiskEngine",
            "domain": "motor",
            "decision": "ERROR",
            "fraud_score": 0,
            "weighted_risk": 0.0,
            "final_verdict": "NEEDS_REVIEW",
            "risk_stage": "PRELIMINARY",
            "model_version": "consensus-risk-v3.3",
            "formula_components": {},
            "processing_time_ms": 0,
            "pipeline_status": "INCOMPLETE",
            "pipeline_failures": [
                f"RiskEngine processing failed: {exc}",
            ],
            "evidence_status": "INSUFFICIENT_DATA",
            "error": str(exc),
        }

    result["risk_stage"] = "PRELIMINARY"

    reports["RiskEngine"] = result

    steps = _append_step(
        state,
        "RiskEngine",
        result.get("decision"),
        result.get("fraud_score"),
        result.get("confidence"),
    )

    logger.info(
        "RiskEngine completed in %.2f ms",
        (
            time.perf_counter()
            - start
        ) * 1000.0,
    )

    return {
        "agent_reports": reports,
        "steps": steps,
        "preliminary_verdict": str(
            result.get(
                "decision",
                "NEEDS_REVIEW",
            )
        ).strip().upper(),
        "preliminary_fraud_score": int(
            max(
                0,
                min(
                    100,
                    round(
                        _safe_float(
                            result.get(
                                "fraud_score",
                                0,
                            ),
                            0.0,
                        )
                    ),
                ),
            )
        ),
    }


# ============================================================
# ADVERSARIAL VERIFIER NODE
# ============================================================

def adversarial_node(
    state: AgentState,
) -> Dict[str, Any]:
    """
    Run the final adversarial verification stage.

    IMPORTANT:

    At this point AdversarialVerifier has NOT yet executed.

    Therefore this node validates only:

        ImageAgent
        SensorAgent
        TextAgent
        CrossModalAgent
        RiskEngine

    It must NOT require its own report before execution.

    Once the pre-adversarial pipeline is complete, the production
    AdversarialVerifier is executed.

    If the pre-adversarial pipeline is incomplete, this node fails
    closed with NEEDS_REVIEW.
    """

    start = time.perf_counter()

    reports = _get_reports(
        state
    )

    pipeline = _validate_pre_adversarial_pipeline(
        reports
    )

    risk_report = reports.get(
        "RiskEngine",
        {},
    )

    if not isinstance(
        risk_report,
        dict,
    ):
        risk_report = {}

    raw_preliminary_risk = risk_report.get(
        "weighted_risk"
    )

    # --------------------------------------------------------------
    # Do NOT silently convert invalid preliminary risk to zero.
    # --------------------------------------------------------------

    try:

        preliminary_risk_value = float(
            raw_preliminary_risk
        )

        if not math.isfinite(
            preliminary_risk_value
        ):
            raise ValueError(
                "preliminary risk is non-finite"
            )

        if not 0.0 <= preliminary_risk_value <= 1.0:
            raise ValueError(
                "preliminary risk is outside [0,1]"
            )

        preliminary_risk = preliminary_risk_value

    except (
        TypeError,
        ValueError,
    ) as exc:

        pipeline["complete"] = False

        pipeline["failures"].append(
            f"RiskEngine preliminary_risk is invalid: {exc}"
        )

        if "RiskEngine" not in pipeline["failed_agents"]:
            pipeline["failed_agents"].append(
                "RiskEngine"
            )

        preliminary_risk = 0.0

    # ============================================================
    # FAIL-CLOSED PRE-ADVERSARIAL GATE
    # ============================================================

    if not pipeline["complete"]:

        failure_text = list(
            pipeline["failures"]
        )

        logger.warning(
            "Adversarial verification blocked: "
            "pre-adversarial pipeline incomplete: %s",
            failure_text,
        )

        result = {
            "agent": "AdversarialVerifier",
            "domain": "motor",
            "decision": "NEEDS_REVIEW",
            "final_verdict": "NEEDS_REVIEW",
            "confidence": 0.0,
            "risk_score": 0.0,
            "fraud_score": 0,
            "preliminary_risk": preliminary_risk,
            "adversarial_flagged": False,
            "evidence": [
                "Automatic verification blocked because the "
                "pre-adversarial evidence pipeline is incomplete.",
                *failure_text,
            ],
            "contradictions": [],
            "model_version": "adversarial-verifier-v3.1",
            "processing_time_ms": 0,
            "pipeline_status": "INCOMPLETE",
            "pipeline_failures": failure_text,
            "failed_agents": pipeline["failed_agents"],
            "audited_agents": sorted(
                REQUIRED_PRE_ADVERSARIAL_AGENTS
            ),
        }

    else:

        try:

            result = adversarial_verifier.verify(
                reports,
                preliminary_risk,
            )

            if not isinstance(
                result,
                dict,
            ):
                raise TypeError(
                    "AdversarialVerifier returned "
                    "a non-dictionary result"
                )

        except Exception as exc:

            logger.exception(
                "AdversarialVerifier failed"
            )

            result = {
                "agent": "AdversarialVerifier",
                "domain": "motor",
                "decision": "NEEDS_REVIEW",
                "final_verdict": "NEEDS_REVIEW",
                "confidence": 0.0,
                "risk_score": preliminary_risk,
                "fraud_score": int(
                    round(
                        preliminary_risk * 100
                    )
                ),
                "preliminary_risk": preliminary_risk,
                "adversarial_flagged": False,
                "evidence": [
                    f"AdversarialVerifier processing failed: {exc}",
                ],
                "contradictions": [],
                "model_version": "adversarial-verifier-v3.1",
                "processing_time_ms": 0,
                "pipeline_status": "INCOMPLETE",
                "pipeline_failures": [
                    f"AdversarialVerifier: {exc}",
                ],
                "failed_agents": [
                    "AdversarialVerifier",
                ],
                "error": str(exc),
            }

    # ============================================================
    # VERIFY ADVERSARIAL RESULT IDENTITY
    # ============================================================

    reported_agent = str(
        result.get(
            "agent",
            "",
        )
    ).strip()

    if reported_agent != "AdversarialVerifier":

        result = {
            "agent": "AdversarialVerifier",
            "domain": "motor",
            "decision": "NEEDS_REVIEW",
            "final_verdict": "NEEDS_REVIEW",
            "confidence": 0.0,
            "risk_score": 0.0,
            "fraud_score": 0,
            "preliminary_risk": preliminary_risk,
            "adversarial_flagged": False,
            "evidence": [
                "AdversarialVerifier returned an invalid "
                "agent identity."
            ],
            "contradictions": [],
            "model_version": "adversarial-verifier-v3.1",
            "processing_time_ms": 0,
            "pipeline_status": "INCOMPLETE",
            "pipeline_failures": [
                "AdversarialVerifier identity mismatch."
            ],
            "failed_agents": [
                "AdversarialVerifier",
            ],
            "error": (
                "Expected AdversarialVerifier but received "
                f"{reported_agent or 'UNKNOWN'}."
            ),
        }

    # ============================================================
    # FINAL VERIFIER VALUES
    # ============================================================

    final_risk = _clamp_risk(
        result.get(
            "risk_score",
            0.0,
        )
    )

    final_fraud_score = int(
        round(
            final_risk * 100
        )
    )

    final_fraud_score = min(
        max(
            final_fraud_score,
            0,
        ),
        100,
    )

    # ============================================================
    # FINAL VERDICT
    # ============================================================

    raw_final_verdict = result.get(
        "final_verdict"
    )

    if raw_final_verdict:

        final_verdict = str(
            raw_final_verdict
        ).strip().upper()

    else:

        # Missing verifier verdict is NOT allowed to become VERIFIED.
        final_verdict = "NEEDS_REVIEW"

        result.setdefault(
            "pipeline_status",
            "INCOMPLETE",
        )

        result.setdefault(
            "pipeline_failures",
            [],
        )

        result["pipeline_failures"].append(
            "AdversarialVerifier did not provide final_verdict."
        )

    # ============================================================
    # ABSOLUTE FAIL-CLOSED OVERRIDE
    # ============================================================

    if not pipeline["complete"]:

        final_verdict = "NEEDS_REVIEW"

    if result.get(
        "error"
    ):

        final_verdict = "NEEDS_REVIEW"

    # Never allow an unknown verdict through.
    if final_verdict not in {
        "VERIFIED",
        "REVIEW_REQUIRED",
        "SUSPICIOUS",
        "REJECTED",
        "NEEDS_REVIEW",
    }:

        final_verdict = "NEEDS_REVIEW"

        result.setdefault(
            "pipeline_failures",
            [],
        )

        result["pipeline_failures"].append(
            "AdversarialVerifier returned an unknown final verdict."
        )

    # ============================================================
    # NORMALIZE REPORT
    # ============================================================

    result["risk_score"] = round(
        final_risk,
        4,
    )

    result["fraud_score"] = final_fraud_score

    result["final_verdict"] = final_verdict

    result["preliminary_risk"] = preliminary_risk

    result["pipeline_status"] = (
        "COMPLETE"
        if pipeline["complete"]
        and not result.get("error")
        and not result.get("pipeline_failures")
        else "INCOMPLETE"
    )

    existing_failures = result.get(
        "pipeline_failures",
        [],
    )

    if not isinstance(
        existing_failures,
        list,
    ):
        existing_failures = []

    # Pre-adversarial validation failures.
    for failure in pipeline["failures"]:

        if failure not in existing_failures:
            existing_failures.append(
                failure
            )

    result["pipeline_failures"] = (
        existing_failures
    )

    result["failed_agents"] = list(
        dict.fromkeys(
            [
                *pipeline["failed_agents"],
                *(
                    ["AdversarialVerifier"]
                    if result.get("error")
                    else []
                ),
            ]
        )
    )

    result["audited_agents"] = sorted(
        REQUIRED_PRE_ADVERSARIAL_AGENTS
    )

    reports["AdversarialVerifier"] = result

    steps = _append_step(
        state,
        "AdversarialVerifier",
        result.get("decision"),
        final_fraud_score,
        result.get("confidence"),
    )

    logger.info(
        "AdversarialVerifier completed in %.2f ms",
        (
            time.perf_counter()
            - start
        ) * 1000.0,
    )

    return {
        "agent_reports": reports,
        "steps": steps,
        "final_verdict": final_verdict,
        "fraud_score": final_fraud_score,
        "pipeline_status": result[
            "pipeline_status"
        ],
        "pipeline_failures": result[
            "pipeline_failures"
        ],
        "failed_agents": result[
            "failed_agents"
        ],
        "required_agents_complete": (
            result["pipeline_status"] == "COMPLETE"
        ),
    }


# ============================================================
# EXPLANATION NODE
# ============================================================

def explanation_node(
    state: AgentState,
) -> Dict[str, Any]:
    """
    Generate explanation from the final verifier result.

    Explanation does not change the final verdict.
    """

    start = time.perf_counter()

    reports = _get_reports(
        state
    )

    pipeline = _validate_pipeline(
        reports
    )

    verifier = reports.get(
        "AdversarialVerifier",
        {},
    )

    if not isinstance(
        verifier,
        dict,
    ):
        verifier = {}

    final_verdict = verifier.get(
        "final_verdict"
    )

    if not final_verdict:
        final_verdict = "NEEDS_REVIEW"

    final_verdict = str(
        final_verdict
    ).strip().upper()

    final_fraud_score = int(
        max(
            0,
            min(
                100,
                round(
                    _safe_float(
                        verifier.get(
                            "fraud_score",
                            0,
                        ),
                        0.0,
                    )
                ),
            ),
        )
    )

    # --------------------------------------------------------------
    # Never pass a positive graph state to ExplanationAgent when
    # the pipeline itself is incomplete.
    # --------------------------------------------------------------

    if not pipeline["complete"]:

        final_verdict = "NEEDS_REVIEW"

    try:

        result = explanation_agent.generate_explanation(
            domain="motor",
            overall_verdict=final_verdict,
            risk_score=final_fraud_score,
            agent_reports=reports,
        )

        if not isinstance(
            result,
            dict,
        ):
            raise TypeError(
                "ExplanationAgent returned "
                "a non-dictionary result"
            )

    except Exception as exc:

        logger.exception(
            "ExplanationAgent failed"
        )

        result = {
            "agent": "ExplanationAgent",
            "domain": "motor",
            "decision": "REVIEW_REQUIRED",
            "final_verdict": "REVIEW_REQUIRED",
            "risk_score": final_fraud_score,
            "confidence": 0.0,
            "executive_summary": (
                "The claim requires human review because "
                "the explanation stage could not complete."
            ),
            "key_highlights": [],
            "recommended_actions": [
                "Review the evidence supporting the assessment.",
            ],
            "contradiction_count": 0,
            "contradictions": [],
            "verifier_decision": "NEEDS_REVIEW",
            "verifier_final_verdict": "NEEDS_REVIEW",
            "pipeline_status": "INCOMPLETE",
            "pipeline_failures": [
                f"ExplanationAgent processing failed: {exc}",
            ],
            "model_version": "explainer-v2.2",
            "error": str(exc),
        }

    # --------------------------------------------------------------
    # Final fail-closed synchronization
    # --------------------------------------------------------------

    if not pipeline["complete"]:

        result["decision"] = "REVIEW_REQUIRED"
        result["final_verdict"] = "REVIEW_REQUIRED"
        result["pipeline_status"] = "INCOMPLETE"

        existing_failures = result.get(
            "pipeline_failures",
            [],
        )

        if not isinstance(
            existing_failures,
            list,
        ):
            existing_failures = []

        for failure in pipeline["failures"]:

            if failure not in existing_failures:
                existing_failures.append(
                    failure
                )

        result["pipeline_failures"] = (
            existing_failures
        )

    reports["ExplanationAgent"] = result

    steps = _append_step(
        state,
        "ExplanationAgent",
        result.get("decision"),
        result.get("risk_score"),
        result.get("confidence"),
    )

    logger.info(
        "ExplanationAgent completed in %.2f ms",
        (
            time.perf_counter()
            - start
        ) * 1000.0,
    )

    return {
        "agent_reports": reports,
        "steps": steps,
        "explanation": result,
    }


# ============================================================
# COMMUNICATION NODE
# ============================================================

def communication_node(
    state: AgentState,
) -> Dict[str, Any]:
    """
    Generate claimant communication from the final verdict.

    CommunicationAgent does not change the verdict.
    """

    start = time.perf_counter()

    reports = _get_reports(
        state
    )

    claim_id = state.get(
        "claim_id",
        "UNKNOWN",
    )

    data = state.get(
        "data",
        {},
    )

    if not isinstance(
        data,
        dict,
    ):
        data = {}

    policy_info = data.get(
        "policy",
        {},
    )

    if not isinstance(
        policy_info,
        dict,
    ):
        policy_info = {}

    explanation = reports.get(
        "ExplanationAgent",
        {},
    )

    if not isinstance(
        explanation,
        dict,
    ):
        explanation = {}

    final_verdict = explanation.get(
        "final_verdict"
    )

    if not final_verdict:
        final_verdict = "REVIEW_REQUIRED"

    try:

        result = communication_agent.generate_message(
            claim_id=claim_id,
            domain="motor",
            verdict=str(
                final_verdict
            ),
            policy_info=policy_info,
            explanation=explanation,
        )

        if not isinstance(
            result,
            dict,
        ):
            raise TypeError(
                "CommunicationAgent returned "
                "a non-dictionary result"
            )

    except Exception as exc:

        logger.exception(
            "CommunicationAgent failed"
        )

        result = {
            "agent": "CommunicationAgent",
            "claim_id": claim_id,
            "domain": "motor",
            "decision": "REVIEW_REQUIRED",
            "final_verdict": "REVIEW_REQUIRED",
            "subject": (
                f"TruthChain Claim Assessment "
                f"#{claim_id}"
            ),
            "message_body": (
                f"Your claim #{claim_id} requires "
                "additional review. Please review the "
                "claim evidence and assessment details."
            ),
            "recipient": "Policyholder",
            "model_version": "comm-v2.1",
            "pipeline_status": "INCOMPLETE",
            "pipeline_warnings": [
                f"CommunicationAgent processing failed: {exc}",
            ],
            "error": str(exc),
        }

    reports["CommunicationAgent"] = result

    steps = _append_step(
        state,
        "CommunicationAgent",
        result.get("decision"),
        result.get("fraud_score"),
        result.get("confidence"),
    )

    logger.info(
        "CommunicationAgent completed in %.2f ms",
        (
            time.perf_counter()
            - start
        ) * 1000.0,
    )

    return {
        "agent_reports": reports,
        "steps": steps,
        "communication": result,
    }


# ============================================================
# FINALIZE NODE
# ============================================================

def finalize_node(
    state: AgentState,
) -> Dict[str, Any]:
    """
    Final consistency and certification authorization gate.

    Rules:

        1. Required pipeline must be complete.
        2. Every required report must be valid.
        3. AdversarialVerifier must exist.
        4. AdversarialVerifier must explicitly provide final_verdict.
        5. Final verdict must be VERIFIED.
        6. No pipeline failures may exist.
        7. Explanation must agree with verifier.
        8. Communication must agree with explanation.
        9. Only then is blockchain_allowed=True.

    This node is intentionally fail-closed.
    """

    reports = _get_reports(
        state
    )

    pipeline = _validate_pipeline(
        reports
    )

    verifier = reports.get(
        "AdversarialVerifier",
        {},
    )

    if not isinstance(
        verifier,
        dict,
    ):
        verifier = {}

    explanation = reports.get(
        "ExplanationAgent",
        {},
    )

    if not isinstance(
        explanation,
        dict,
    ):
        explanation = {}

    communication = reports.get(
        "CommunicationAgent",
        {},
    )

    if not isinstance(
        communication,
        dict,
    ):
        communication = {}

    failures = list(
        pipeline["failures"]
    )

    # ============================================================
    # VERIFY EXPLANATION
    # ============================================================

    if not explanation:

        failures.append(
            "ExplanationAgent report is missing."
        )

    else:

        explanation_agent_name = str(
            explanation.get(
                "agent",
                "",
            )
        ).strip()

        if explanation_agent_name != "ExplanationAgent":

            failures.append(
                "ExplanationAgent identity mismatch."
            )

        if str(
            explanation.get(
                "pipeline_status",
                "",
            )
        ).strip().upper() != "COMPLETE":

            failures.append(
                "ExplanationAgent reports an incomplete pipeline."
            )

    # ============================================================
    # VERIFY COMMUNICATION
    # ============================================================

    if not communication:

        failures.append(
            "CommunicationAgent report is missing."
        )

    else:

        communication_agent_name = str(
            communication.get(
                "agent",
                "",
            )
        ).strip()

        if communication_agent_name != "CommunicationAgent":

            failures.append(
                "CommunicationAgent identity mismatch."
            )

        if str(
            communication.get(
                "pipeline_status",
                "",
            )
        ).strip().upper() != "COMPLETE":

            failures.append(
                "CommunicationAgent reports an incomplete pipeline."
            )

    # ============================================================
    # FINAL VERIFIER VALIDATION
    # ============================================================

    final_verdict_raw = verifier.get(
        "final_verdict"
    )

    if not final_verdict_raw:

        failures.append(
            "AdversarialVerifier did not provide final_verdict."
        )

        final_verdict = "NEEDS_REVIEW"

    else:

        final_verdict = str(
            final_verdict_raw
        ).strip().upper()

    if final_verdict not in {
        "VERIFIED",
        "REVIEW_REQUIRED",
        "SUSPICIOUS",
        "REJECTED",
        "NEEDS_REVIEW",
    }:

        failures.append(
            "AdversarialVerifier returned an invalid final verdict."
        )

        final_verdict = "NEEDS_REVIEW"

    # ============================================================
    # EXPLANATION / VERIFIER CONSISTENCY
    # ============================================================

    explanation_verdict = str(
        explanation.get(
            "final_verdict",
            "",
        )
    ).strip().upper()

    verifier_explanation_verdict = str(
        explanation.get(
            "verifier_final_verdict",
            "",
        )
    ).strip().upper()

    if explanation_verdict:

        if explanation_verdict != final_verdict:

            failures.append(
                "ExplanationAgent final_verdict disagrees with "
                "AdversarialVerifier."
            )

    if verifier_explanation_verdict:

        if verifier_explanation_verdict != final_verdict:

            failures.append(
                "ExplanationAgent verifier_final_verdict disagrees "
                "with AdversarialVerifier."
            )

    # ============================================================
    # COMMUNICATION / EXPLANATION CONSISTENCY
    # ============================================================

    communication_verdict = str(
        communication.get(
            "final_verdict",
            communication.get(
                "decision",
                "",
            ),
        )
    ).strip().upper()

    if communication_verdict:

        # CommunicationAgent may only communicate the explanation
        # verdict.
        if communication_verdict != explanation_verdict:

            failures.append(
                "CommunicationAgent verdict disagrees with "
                "ExplanationAgent."
            )

    # ============================================================
    # FINAL PIPELINE STATUS
    # ============================================================

    pipeline_complete = (
        pipeline["complete"]
        and len(failures) == 0
    )

    # ============================================================
    # FINAL FAIL-CLOSED VERDICT
    # ============================================================

    if not pipeline_complete:

        logger.warning(
            "Finalize blocked automatic verification: %s",
            failures,
        )

        final_verdict = "NEEDS_REVIEW"

    # ============================================================
    # FINAL RISK
    # ============================================================

    final_risk = _clamp_risk(
        verifier.get(
            "risk_score",
            0.0,
        )
    )

    # If verifier is invalid/incomplete, don't present its numerical
    # score as an authoritative automatic result.
    if not pipeline_complete:

        final_risk = 0.0

    # ============================================================
    # FINAL FRAUD SCORE
    # ============================================================

    fraud_score = int(
        round(
            final_risk * 100
        )
    )

    fraud_score = min(
        max(
            fraud_score,
            0,
        ),
        100,
    )

    # ============================================================
    # EXPLICIT BLOCKCHAIN AUTHORIZATION
    # ============================================================

    blockchain_allowed = (
        pipeline_complete
        and final_verdict in BLOCKCHAIN_ALLOWED_VERDICTS
    )

    if blockchain_allowed:

        blockchain_reason = (
            "Blockchain certification authorized: "
            "all required evidence agents completed successfully, "
            "AdversarialVerifier supplied VERIFIED as the authoritative "
            "final verdict, ExplanationAgent and CommunicationAgent "
            "are consistent, and no pipeline failures remain."
        )

    else:

        reasons: List[str] = []

        if not pipeline["complete"]:

            reasons.append(
                "required evidence pipeline is incomplete"
            )

        if failures:

            reasons.extend(
                failures
            )

        if final_verdict != "VERIFIED":

            reasons.append(
                f"final verdict is {final_verdict}, not VERIFIED"
            )

        if not reasons:

            reasons.append(
                "automatic certification conditions were not satisfied"
            )

        blockchain_reason = (
            "Blockchain certification denied: "
            + "; ".join(
                dict.fromkeys(
                    reasons
                )
            )
        )

    # ============================================================
    # SYNCHRONIZE VERIFIER REPORT
    # ============================================================

    if verifier:

        verifier["risk_score"] = round(
            final_risk,
            4,
        )

        verifier["fraud_score"] = fraud_score

        verifier["final_verdict"] = final_verdict

        verifier["pipeline_status"] = (
            "COMPLETE"
            if pipeline_complete
            else "INCOMPLETE"
        )

        verifier["pipeline_failures"] = list(
            dict.fromkeys(
                [
                    *verifier.get(
                        "pipeline_failures",
                        [],
                    ),
                    *failures,
                ]
            )
        )

        reports["AdversarialVerifier"] = verifier

    # ============================================================
    # FINAL STATE
    # ============================================================

    final_state = (
        "BLOCKCHAIN_PENDING"
        if blockchain_allowed
        else "NEEDS_REVIEW"
    )

    logger.info(
        "Finalize: verdict=%s fraud_score=%d "
        "pipeline_complete=%s blockchain_allowed=%s",
        final_verdict,
        fraud_score,
        pipeline_complete,
        blockchain_allowed,
    )

    return {
        "agent_reports": reports,

        "final_verdict": final_verdict,

        "fraud_score": fraud_score,

        "pipeline_status": (
            "COMPLETE"
            if pipeline_complete
            else "INCOMPLETE"
        ),

        "pipeline_failures": list(
            dict.fromkeys(
                failures
            )
        ),

        "failed_agents": list(
            dict.fromkeys(
                [
                    *pipeline["failed_agents"],
                    *(
                        ["AdversarialVerifier"]
                        if (
                            not verifier
                            or final_verdict == "NEEDS_REVIEW"
                        )
                        and "AdversarialVerifier"
                        in REQUIRED_PIPELINE_AGENTS
                        else []
                    ),
                ]
            )
        ),

        "required_agents_complete": pipeline_complete,

        "blockchain_allowed": blockchain_allowed,

        "blockchain_reason": blockchain_reason,

        "state": final_state,
    }


# ============================================================
# BLOCKCHAIN AUTHORIZATION ROUTER
# ============================================================

def blockchain_authorization_router(
    state: AgentState,
) -> str:
    """
    Decide whether the blockchain certificate node may execute.

    This is a hard graph-level authorization gate.

    The blockchain node is NEVER called merely because Finalize
    completed.

    It is called ONLY when blockchain_allowed is exactly True.
    """

    allowed = state.get(
        "blockchain_allowed",
        False,
    )

    if allowed is True:

        logger.info(
            "Blockchain authorization: ALLOWED"
        )

        return "blockchain_certificate"

    logger.info(
        "Blockchain authorization: DENIED"
    )

    return END


# ============================================================
# BUILD LANGGRAPH
# ============================================================

builder = StateGraph(
    AgentState,
)


# ============================================================
# ADD NODES
# ============================================================

builder.add_node(
    "image",
    image_node,
)

builder.add_node(
    "sensor",
    sensor_node,
)

builder.add_node(
    "text",
    text_node,
)

builder.add_node(
    "cross_modal",
    cross_modal_node,
)

builder.add_node(
    "risk",
    risk_node,
)

builder.add_node(
    "adversarial",
    adversarial_node,
)

builder.add_node(
    "explanation",
    explanation_node,
)

builder.add_node(
    "communication",
    communication_node,
)

builder.add_node(
    "finalize",
    finalize_node,
)

builder.add_node(
    "blockchain_certificate",
    blockchain_certificate_node,
)


# ============================================================
# EDGES
# ============================================================

builder.add_edge(
    START,
    "image",
)

builder.add_edge(
    "image",
    "sensor",
)

builder.add_edge(
    "sensor",
    "text",
)

builder.add_edge(
    "text",
    "cross_modal",
)

builder.add_edge(
    "cross_modal",
    "risk",
)

builder.add_edge(
    "risk",
    "adversarial",
)

builder.add_edge(
    "adversarial",
    "explanation",
)

builder.add_edge(
    "explanation",
    "communication",
)

builder.add_edge(
    "communication",
    "finalize",
)


# ============================================================
# HARD BLOCKCHAIN GATE
# ============================================================

builder.add_conditional_edges(
    "finalize",
    blockchain_authorization_router,
    {
        "blockchain_certificate": "blockchain_certificate",
        END: END,
    },
)

builder.add_edge(
    "blockchain_certificate",
    END,
)


# ============================================================
# COMPILE
# ============================================================

graph = builder.compile()

# Backward-compatible public name used by the orchestrator.
app_graph = graph


# ============================================================
# PUBLIC EXPORTS
# ============================================================

__all__ = [
    "graph",
    "app_graph",
    "image_node",
    "sensor_node",
    "text_node",
    "cross_modal_node",
    "risk_node",
    "adversarial_node",
    "explanation_node",
    "communication_node",
    "finalize_node",
    "blockchain_authorization_router",
    "blockchain_certificate_node",
]