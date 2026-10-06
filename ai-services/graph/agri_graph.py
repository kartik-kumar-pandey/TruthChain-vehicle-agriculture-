"""
TruthChain Agriculture - Production LangGraph
----------------------------------------------

Agriculture Multimodal Evidence Verification Pipeline

Flow:

    START
      ↓
    TextAgent
      ↓
    ┌──────────────┬─────────────────┬──────────────┐
    │              │                 │              │
 ImageAgent   SatelliteAgent    SensorAgent       │
    │              │                 │              │
    └──────────────┴─────────────────┴──────────────┘
      ↓
    CrossModalAgent
      ↓
    InvestigationAgent
      ↓
    RiskEngine
      ↓
    AdversarialVerifier
      ↓
    DecisionEngine
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
        = consensus risk

    AdversarialVerifier
        = independent challenge / verification layer

    DecisionEngine
        = final automated screening authority

    Finalize
        = final consistency + fail-closed integrity gate

    Blockchain Authorization
        = explicit certification gate

The Agriculture domain is intentionally standalone.
No first-domain agent or model is imported here.
"""

from __future__ import annotations

import base64
import logging
import math
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Annotated, Dict, List, Optional, Set
import operator

from langgraph.graph import END, START, StateGraph


# ============================================================
# PROJECT PATH BOOTSTRAP
# ============================================================

CURRENT_FILE = Path(__file__).resolve()

PROJECT_ROOT = CURRENT_FILE.parents[2]
AI_SERVICES_DIR = CURRENT_FILE.parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if str(AI_SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(AI_SERVICES_DIR))


# ============================================================
# AGRICULTURE AGENTS
# ============================================================

from agriculture.agents.image_agent import get_image_agent
from agriculture.agents.satellite_agent import get_satellite_agent
from agriculture.agents.text_agent import get_text_agent
from agriculture.agents.sensor_agent import analyze_sensor_evidence
from agriculture.agents.cross_modal_agent import get_cross_modal_agent

from agriculture.agents.investigation_agent import InvestigationAgent
from agriculture.agents.risk_engine import RiskEngine
from agriculture.agents.adversarial_verifier import AdversarialVerifier
from agriculture.agents.decision_engine import DecisionEngine

from graph.agri_state import AgricultureAgentState
from graph.blockchain_node import blockchain_certificate_node as real_blockchain_certificate_node


# ============================================================
# LOGGING
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# PARALLEL STATE REDUCERS
# ============================================================


def _merge_agent_reports(
    current: Optional[Dict[str, Any]],
    incoming: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge agent reports safely when evidence nodes run in parallel."""

    merged: Dict[str, Any] = {}

    if isinstance(current, dict):
        merged.update(current)

    if isinstance(incoming, dict):
        merged.update(incoming)

    return merged


_STEP_ORDER = {
    "TextAgent": 10,
    "ImageAgent": 20,
    "SatelliteAgent": 30,
    "SensorAgent": 40,
    "CrossModalAgent": 50,
    "InvestigationAgent": 60,
    "RiskEngine": 70,
    "AdversarialVerifier": 80,
    "DecisionEngine": 90,
    "Finalize": 100,
    "BlockchainCertificate": 110,
}


def _merge_steps(
    current: Optional[List[Dict[str, Any]]],
    incoming: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Merge parallel step updates while keeping deterministic pipeline order."""

    merged: List[Dict[str, Any]] = []

    for item in list(current or []) + list(incoming or []):

        if not isinstance(item, dict):
            continue

        agent = str(item.get("agent", "")).strip()

        if not agent:
            continue

        merged = [
            existing
            for existing in merged
            if str(existing.get("agent", "")).strip() != agent
        ]

        merged.append(dict(item))

    merged.sort(
        key=lambda item: (
            _STEP_ORDER.get(
                str(item.get("agent", "")).strip(),
                999,
            ),
            str(item.get("agent", "")),
        )
    )

    return merged


class AgricultureParallelState(
    AgricultureAgentState,
    total=False,
):
    """Agriculture state with reducers required for evidence fan-out."""

    agent_reports: Annotated[
        Dict[str, Any],
        _merge_agent_reports,
    ]

    steps: Annotated[
        List[Dict[str, Any]],
        _merge_steps,
    ]


# ============================================================
# CONSTANTS
# ============================================================

DOMAIN = "agriculture"

REQUIRED_EVIDENCE_AGENTS: Set[str] = {
    "TextAgent",
    "ImageAgent",
    "SatelliteAgent",
    "SensorAgent",
    "CrossModalAgent",
}

REQUIRED_PRE_ADVERSARIAL_AGENTS: Set[str] = {
    "TextAgent",
    "ImageAgent",
    "SatelliteAgent",
    "SensorAgent",
    "CrossModalAgent",
    "InvestigationAgent",
    "RiskEngine",
}

REQUIRED_RISK_INPUT_AGENTS: Set[str] = {
    "TextAgent",
    "ImageAgent",
    "SatelliteAgent",
    "SensorAgent",
    "CrossModalAgent",
    "InvestigationAgent",
}

REQUIRED_PIPELINE_AGENTS: Set[str] = {
    "TextAgent",
    "ImageAgent",
    "SatelliteAgent",
    "SensorAgent",
    "CrossModalAgent",
    "InvestigationAgent",
    "RiskEngine",
    "AdversarialVerifier",
    "DecisionEngine",
}

# DecisionEngine is the final producer of the pipeline, so it cannot
# validate its own report before it has produced one.
REQUIRED_DECISION_INPUT_AGENTS: Set[str] = {
    "TextAgent",
    "ImageAgent",
    "SatelliteAgent",
    "SensorAgent",
    "CrossModalAgent",
    "InvestigationAgent",
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

investigation_agent = InvestigationAgent()
risk_engine = RiskEngine()
adversarial_verifier = AdversarialVerifier()
decision_engine = DecisionEngine()


# ============================================================
# HELPERS
# ============================================================

def _resolve_image_path(image_input: Any) -> Optional[str]:
    """
    Resolve an image input to a filesystem path.

    Supports:
        - filesystem paths
        - image data URLs

    Unlike the original motor-domain graph, this Agriculture graph
    does NOT silently create a synthetic image. Missing image evidence
    must remain missing so the pipeline cannot accidentally certify
    incomplete evidence.
    """

    if isinstance(image_input, (str, Path)):

        p = Path(image_input)

        if p.exists() and p.is_file():
            return str(p)

        if str(image_input).startswith("data:image/"):

            try:
                _, encoded = str(image_input).split(",", 1)

                image_bytes = base64.b64decode(
                    encoded
                )

                with tempfile.NamedTemporaryFile(
                    suffix=".jpg",
                    delete=False,
                ) as tmp:

                    tmp.write(image_bytes)
                    tmp.flush()

                    return tmp.name

            except Exception:

                logger.exception(
                    "Failed to decode image data URL."
                )

    return None


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

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

    risk = _safe_float(
        value,
        0.0,
    )

    return min(
        max(risk, 0.0),
        1.0,
    )


def _get_reports(
    state: AgricultureParallelState,
) -> Dict[str, Any]:

    reports = state.get(
        "agent_reports",
        {},
    )

    if not isinstance(reports, dict):
        return {}

    return dict(reports)


def _normalise_decision(
    result: Any,
) -> str:

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
    report: Dict[str, Any],
) -> bool:
    """
    Determine whether an agent report represents a pipeline execution failure.

    Agriculture certification is fail-closed:
    INSUFFICIENT_DATA cannot silently become VERIFIED.

    IMPORTANT:
    AdversarialVerifier may legitimately return NEEDS_REVIEW after
    successfully completing its verification checks. That is a verification
    outcome, not an execution failure, so it must not mark the pipeline
    incomplete by itself.
    """

    if not isinstance(report, dict):
        return True

    decision = _normalise_decision(
        report
    )

    agent_name = str(
        report.get(
            "agent",
            "",
        )
    ).strip()

    if (
        agent_name == "AdversarialVerifier"
        and decision == "NEEDS_REVIEW"
    ):
        return False

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

    if report.get("error"):
        return True

    return False

def _validate_agent_set(
    reports: Dict[str, Any],
    required_agents: Set[str],
) -> Dict[str, Any]:

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


def _append_step(
    agent: str,
    decision: Any = None,
    risk_score: Any = None,
    confidence: Any = None,
) -> List[Dict[str, Any]]:

    step: Dict[str, Any] = {
        "agent": agent,
    }

    if decision is not None:
        step["decision"] = decision

    if risk_score is not None:
        step["risk_score"] = _clamp_risk(
            risk_score
        )

    if confidence is not None:
        step["confidence"] = _safe_float(
            confidence
        )

    return [step]


def _safe_error_result(
    agent: str,
    message: str,
    model_version: str,
) -> Dict[str, Any]:

    return {
        "agent": agent,
        "domain": DOMAIN,
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


def _agent_result(
    result: Any,
    agent_name: str,
) -> Dict[str, Any]:
    """
    Defensive conversion of an agent result to dict.

    Supports normal dictionaries and dataclass-like results.
    """

    if isinstance(result, dict):

        output = dict(result)

    elif hasattr(result, "to_dict") and callable(
        result.to_dict
    ):

        output = result.to_dict()

    elif hasattr(result, "__dict__"):

        output = dict(result.__dict__)

    else:

        raise TypeError(
            f"{agent_name} returned unsupported result type: "
            f"{type(result).__name__}"
        )

    if output.get("agent") != agent_name:

        raise ValueError(
            f"{agent_name} returned invalid agent identity: "
            f"{output.get('agent')}"
        )

    return output


# ============================================================
# TEXT NODE
# ============================================================

def text_node(
    state: AgricultureParallelState,
) -> Dict[str, Any]:

    start = time.perf_counter()
    reports = _get_reports(state)

    try:

        data = state.get(
            "data",
            {},
        )

        if not isinstance(data, dict):
            data = {}

        claim_text = (
            data.get("text")
            or data.get("claim_text")
            or data.get("description")
            or data.get("claim_description")
        )

        if not claim_text:

            result = {
                "agent": "TextAgent",
                "domain": DOMAIN,
                "confidence": 0.0,
                "risk_score": 0.0,
                "decision": "INSUFFICIENT_DATA",
                "evidence": [
                    "No agricultural claim text was provided."
                ],
                "contradictions": [],
                "model_version": "agriculture-text-agent-v0.1",
                "processing_time_ms": (
                    time.perf_counter() - start
                ) * 1000.0,
            }

        else:

            agent = get_text_agent()

            result = agent.analyze(
                claim_text
            )

            result = _agent_result(
                result,
                "TextAgent",
            )

    except Exception as exc:

        logger.exception(
            "TextAgent failed."
        )

        result = _safe_error_result(
            "TextAgent",
            f"TextAgent processing failed: {exc}",
            "agriculture-text-agent-v0.1",
        )

    reports["TextAgent"] = result

    return {
        "agent_reports": reports,
        "steps": _append_step(
            "TextAgent",
            result.get("decision"),
            result.get("risk_score"),
            result.get("confidence"),
        ),
    }


# ============================================================
# IMAGE NODE
# ============================================================

def image_node(
    state: AgricultureParallelState,
) -> Dict[str, Any]:

    start = time.perf_counter()
    reports = _get_reports(state)

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
        )

        resolved_path = _resolve_image_path(
            raw_image
        )

        claimed_crop = (
            data.get("crop")
            or data.get("claimed_crop")
        )

        if not resolved_path:

            result = {
                "agent": "ImageAgent",
                "domain": DOMAIN,
                "confidence": 0.0,
                "risk_score": 0.0,
                "decision": "INSUFFICIENT_DATA",
                "evidence": [
                    "No agricultural field image was provided."
                ],
                "contradictions": [],
                "model_version": "TruthChain-Agriculture-Crop-v0.2",
                "processing_time_ms": (
                    time.perf_counter() - start
                ) * 1000.0,
            }

        else:

            agent = get_image_agent()

            result = agent.analyze(
                resolved_path,
                claimed_crop=claimed_crop,
            )

            result = _agent_result(
                result,
                "ImageAgent",
            )

    except Exception as exc:

        logger.exception(
            "ImageAgent failed."
        )

        result = _safe_error_result(
            "ImageAgent",
            f"ImageAgent processing failed: {exc}",
            "TruthChain-Agriculture-Crop-v0.2",
        )

    reports["ImageAgent"] = result

    return {
        "agent_reports": reports,
        "steps": _append_step(
            "ImageAgent",
            result.get("decision"),
            result.get("risk_score"),
            result.get("confidence"),
        ),
    }


# ============================================================
# SATELLITE NODE
# ============================================================

def satellite_node(
    state: AgricultureParallelState,
) -> Dict[str, Any]:

    start = time.perf_counter()
    reports = _get_reports(state)

    try:

        data = state.get(
            "data",
            {},
        )

        if not isinstance(data, dict):
            data = {}

        claimed_crop = (
            data.get("crop")
            or data.get("claimed_crop")
        )

        satellite_data = (
            data.get("satellite_evidence")
            or data.get("satellite")
            or data.get("satellite_data")
        )

        # --------------------------------------------------------
        # LIVE SATELLITE PIPELINE
        # --------------------------------------------------------
        # If a field polygon and satellite date window are supplied,
        # execute the production SatelliteEvidenceAgent pipeline.
        # Otherwise preserve the existing dictionary-evidence path.

        satellite_config = data.get("satellite_config")
        if not isinstance(satellite_config, dict):
            satellite_config = {}

        field_geojson = (
            data.get("field_geojson")
            or data.get("satellite_field_geojson")
            or satellite_config.get("field_geojson")
        )

        event_date = data.get("event_date") or data.get("incident_date") or "2026-09-17"

        start_date = (
            data.get("satellite_start_date")
            or satellite_config.get("start_date")
            or "2026-09-09"
        )

        end_date = (
            data.get("satellite_end_date")
            or satellite_config.get("end_date")
            or event_date
        )

        max_cloud = (
            data.get("satellite_max_cloud")
            if data.get("satellite_max_cloud") is not None
            else satellite_config.get("max_cloud", 20.0)
        )

        output_directory = (
            data.get("satellite_output_directory")
            or satellite_config.get(
                "output_directory",
                "data/satellite/evidence",
            )
        )

        limit = (
            data.get("satellite_scene_limit")
            if data.get("satellite_scene_limit") is not None
            else satellite_config.get("limit", 20)
        )

        agent = get_satellite_agent()

        if (
            field_geojson is not None
            and start_date is not None
            and end_date is not None
        ):

            result = agent.analyze_live(
                field_geojson=field_geojson,
                start_date=start_date,
                end_date=end_date,
                claimed_crop=claimed_crop,
                max_cloud=float(max_cloud),
                output_directory=output_directory,
                limit=int(limit),
            )

        else:

            if satellite_data is None:
                satellite_data = {}

            if not isinstance(
                satellite_data,
                dict,
            ):
                satellite_data = {}

            result = agent.analyze(
                satellite_data,
                claimed_crop=claimed_crop,
            )

        result = _agent_result(
            result,
            "SatelliteAgent",
        )

        # Preserve the actual node timing when the live pipeline is used.
        result["graph_processing_time_ms"] = (
            time.perf_counter() - start
        ) * 1000.0

    except Exception as exc:

        logger.exception(
            "SatelliteAgent failed."
        )

        result = _safe_error_result(
            "SatelliteAgent",
            f"SatelliteAgent processing failed: {exc}",
            "SatelliteEvidenceAgent-v1",
        )

    reports["SatelliteAgent"] = result

    return {
        "agent_reports": reports,
        "steps": _append_step(
            "SatelliteAgent",
            result.get("decision"),
            result.get("risk_score"),
            result.get("confidence"),
        ),
    }


# ============================================================

# SENSOR NODE
# ============================================================

def sensor_node(
    state: AgricultureParallelState,
) -> Dict[str, Any]:

    start = time.perf_counter()
    reports = _get_reports(state)

    try:

        data = state.get(
            "data",
            {},
        )

        if not isinstance(data, dict):
            data = {}

        sensor_data = (
            data.get("sensor_observations")
            or data.get("sensor")
            or data.get("sensor_data")
            or data.get("weather")
            or data.get("environment")
        )

        if isinstance(sensor_data, dict):
            sensor_data = dict(sensor_data)

            # Normalize claim/API field names to SensorAgent schema.
            # Preserve canonical SensorAgent keys when already present.
            if 'rainfall_mm_24h' not in sensor_data and 'rainfall_24h_mm' in sensor_data:
                sensor_data['rainfall_mm_24h'] = sensor_data['rainfall_24h_mm']

            if 'rainfall_mm_7d' not in sensor_data and 'rainfall_7d_mm' in sensor_data:
                sensor_data['rainfall_mm_7d'] = sensor_data['rainfall_7d_mm']

            if 'relative_humidity' not in sensor_data and 'humidity_pct' in sensor_data:
                sensor_data['relative_humidity'] = sensor_data['humidity_pct']

        if not isinstance(
            sensor_data,
            dict,
        ):

            result = {
                "agent": "SensorAgent",
                "domain": DOMAIN,
                "confidence": 0.0,
                "risk_score": 0.0,
                "decision": "INSUFFICIENT_DATA",
                "evidence": [
                    "No agricultural environmental sensor data was provided."
                ],
                "contradictions": [],
                "model_version": "agriculture-sensor-agent-v0.1",
                "processing_time_ms": (
                    time.perf_counter() - start
                ) * 1000.0,
            }

        else:

            result = analyze_sensor_evidence(
                sensor_data
            )

            result = _agent_result(
                result,
                "SensorAgent",
            )

    except Exception as exc:

        logger.exception(
            "SensorAgent failed."
        )

        result = _safe_error_result(
            "SensorAgent",
            f"SensorAgent processing failed: {exc}",
            "agriculture-sensor-agent-v0.1",
        )

    reports["SensorAgent"] = result

    return {
        "agent_reports": reports,
        "steps": _append_step(
            "SensorAgent",
            result.get("decision"),
            result.get("risk_score"),
            result.get("confidence"),
        ),
    }


# ============================================================
# CROSS-MODAL NODE
# ============================================================

def cross_modal_node(
    state: AgricultureParallelState,
) -> Dict[str, Any]:

    reports = _get_reports(state)

    try:

        text_result = reports.get(
            "TextAgent",
            {},
        )

        image_result = reports.get(
            "ImageAgent",
            {},
        )

        satellite_result = reports.get(
            "SatelliteAgent",
            {},
        )

        sensor_result = reports.get(
            "SensorAgent",
            {},
        )

        agent = get_cross_modal_agent()

        result = agent.analyze(
            text_result=text_result,
            image_result=image_result,
            satellite_result=satellite_result,
            sensor_result=sensor_result,
        )

        result = _agent_result(
            result,
            "CrossModalAgent",
        )

    except Exception as exc:

        logger.exception(
            "CrossModalAgent failed."
        )

        result = _safe_error_result(
            "CrossModalAgent",
            f"CrossModalAgent processing failed: {exc}",
            "agriculture-cross-modal-agent-v0.1",
        )

    reports["CrossModalAgent"] = result

    return {
        "agent_reports": reports,
        "cross_modal_result": result,
        "steps": _append_step(
            "CrossModalAgent",
            result.get("decision"),
            result.get("risk_score"),
            result.get("confidence"),
        ),
    }


# ============================================================
# INVESTIGATION NODE
# ============================================================

def investigation_node(
    state: AgricultureParallelState,
) -> Dict[str, Any]:

    reports = _get_reports(state)

    try:

        result = investigation_agent.analyze(
            text_result=reports.get(
                "TextAgent",
                {},
            ),
            image_result=reports.get(
                "ImageAgent",
                {},
            ),
            satellite_result=reports.get(
                "SatelliteAgent",
                {},
            ),
            sensor_result=reports.get(
                "SensorAgent",
                {},
            ),
            cross_modal_result=reports.get(
                "CrossModalAgent",
                {},
            ),
        )

        result = _agent_result(
            result,
            "InvestigationAgent",
        )

    except Exception as exc:

        logger.exception(
            "InvestigationAgent failed."
        )

        result = _safe_error_result(
            "InvestigationAgent",
            f"InvestigationAgent processing failed: {exc}",
            "agriculture-investigation-agent-v0.1",
        )

    reports["InvestigationAgent"] = result

    investigation_required = bool(
        result.get(
            "investigation_required",
            result.get(
                "investigation_score",
                0.0,
            ) > 0.5,
        )
    )

    return {
        "agent_reports": reports,
        "investigation_result": result,
        "investigation_required": investigation_required,
        "steps": _append_step(
            "InvestigationAgent",
            result.get("decision"),
            result.get("risk_score"),
            result.get("confidence"),
        ),
    }


# ============================================================
# RISK ENGINE NODE
# ============================================================

def risk_node(
    state: AgricultureParallelState,
) -> Dict[str, Any]:

    reports = _get_reports(state)

    validation = _validate_agent_set(
        reports,
        REQUIRED_RISK_INPUT_AGENTS,
    )

    if not validation["complete"]:

        result = _safe_error_result(
            "RiskEngine",
            "RiskEngine blocked because required risk inputs are incomplete.",
            "agriculture-risk-engine-v0.1",
        )

        result["pipeline_failures"] = (
            validation["failures"]
        )

    else:

        try:

            result = risk_engine.assess(
                image=reports["ImageAgent"],
                sensor=reports["SensorAgent"],
                text=reports["TextAgent"],
                cross_modal=reports["CrossModalAgent"],
                verifier=reports.get("AdversarialVerifier"),
                investigation=reports.get("InvestigationAgent"),
            )

            result = _agent_result(
                result,
                "RiskEngine",
            )

        except Exception as exc:

            logger.exception(
                "RiskEngine failed."
            )

            result = _safe_error_result(
                "RiskEngine",
                f"RiskEngine processing failed: {exc}",
                "agriculture-risk-engine-v0.1",
            )

    reports["RiskEngine"] = result

    return {
        "agent_reports": reports,
        "risk_engine_result": result,
        "preliminary_risk_score": _clamp_risk(
            result.get(
                "risk_score",
                0.0,
            )
        ),
        "preliminary_verdict": str(
            result.get(
                "decision",
                "UNKNOWN",
            )
        ),
        "steps": _append_step(
            "RiskEngine",
            result.get("decision"),
            result.get("risk_score"),
            result.get("confidence"),
        ),
    }


# ============================================================
# ADVERSARIAL VERIFIER NODE
# ============================================================

def adversarial_node(
    state: AgricultureParallelState,
) -> Dict[str, Any]:

    reports = _get_reports(state)

    validation = _validate_agent_set(
        reports,
        REQUIRED_PRE_ADVERSARIAL_AGENTS,
    )

    if not validation["complete"]:

        result = _safe_error_result(
            "AdversarialVerifier",
            "Adversarial verification blocked because "
            "required upstream evidence is incomplete.",
            "agriculture-adversarial-verifier-v0.1",
        )

        result["pipeline_failures"] = (
            validation["failures"]
        )

    else:

        try:

            result = adversarial_verifier.verify(
            text=reports["TextAgent"],
            image=reports["ImageAgent"],
            satellite=reports["SatelliteAgent"],
            sensor=reports["SensorAgent"],
            cross_modal=reports["CrossModalAgent"],
            investigation=reports["InvestigationAgent"],
            )

            result = _agent_result(
                result,
                "AdversarialVerifier",
            )

        except Exception as exc:

            logger.exception(
                "AdversarialVerifier failed."
            )

            result = _safe_error_result(
                "AdversarialVerifier",
                f"AdversarialVerifier processing failed: {exc}",
                "agriculture-adversarial-verifier-v0.1",
            )

    reports["AdversarialVerifier"] = result

    return {
        "agent_reports": reports,
        "adversarial_verifier_result": result,
        "steps": _append_step(
            "AdversarialVerifier",
            result.get("decision"),
            result.get("risk_score"),
            result.get("confidence"),
        ),
    }


# ============================================================
# DECISION ENGINE NODE
# ============================================================

def decision_node(
    state: AgricultureParallelState,
) -> Dict[str, Any]:

    reports = _get_reports(state)

    validation = _validate_agent_set(
        reports,
        REQUIRED_DECISION_INPUT_AGENTS,
    )

    if not validation["complete"]:

        result = _safe_error_result(
            "DecisionEngine",
            "DecisionEngine blocked because the required "
            "Agriculture verification pipeline is incomplete.",
            "agriculture-decision-engine-v0.1",
        )

        result["decision"] = "REVIEW_REQUIRED"

        result["pipeline_failures"] = (
            validation["failures"]
        )

    else:

        try:

            result = decision_engine.decide(
                cross_modal=reports[
                    "CrossModalAgent"
                ],
                investigation=reports[
                    "InvestigationAgent"
                ],
                verifier=reports[
                    "AdversarialVerifier"
                ],
                risk_engine=reports[
                    "RiskEngine"
                ],
            )

            result = _agent_result(
                result,
                "DecisionEngine",
            )

        except Exception as exc:

            logger.exception(
                "DecisionEngine failed."
            )

            result = _safe_error_result(
                "DecisionEngine",
                f"DecisionEngine processing failed: {exc}",
                "agriculture-decision-engine-v0.1",
            )

            result["decision"] = "REVIEW_REQUIRED"

    reports["DecisionEngine"] = result

    return {
        "agent_reports": reports,
        "decision_engine_result": result,
        "steps": _append_step(
            "DecisionEngine",
            result.get("decision"),
            result.get("risk_score"),
            result.get("confidence"),
        ),
    }


# ============================================================
# FINALIZE NODE
# ============================================================

def finalize_node(
    state: AgricultureParallelState,
) -> Dict[str, Any]:
    """
    Final fail-closed integrity gate.

    This node does NOT independently determine fraud.

    It verifies that:
        1. all required agents completed
        2. DecisionEngine produced a valid terminal state
        3. no required agent failed
        4. blockchain authorization is explicit

    Only VERIFIED may become blockchain-eligible.
    """

    reports = _get_reports(state)

    pipeline = _validate_agent_set(
        reports,
        REQUIRED_PIPELINE_AGENTS,
    )

    failures = list(
        pipeline["failures"]
    )

    decision_result = reports.get(
        "DecisionEngine",
        {},
    )

    final_verdict = str(
        decision_result.get(
            "decision",
            "UNCERTAIN",
        )
    ).strip().upper()

    valid_verdicts = {
        "VERIFIED",
        "REVIEW_REQUIRED",
        "REJECTED",
        "UNCERTAIN",
    }

    if final_verdict not in valid_verdicts:

        final_verdict = "UNCERTAIN"

        failures.append(
            "DecisionEngine returned an invalid terminal decision."
        )

    pipeline_complete = (
        pipeline["complete"]
        and len(failures) == 0
    )

    if not pipeline_complete:

        final_verdict = "REVIEW_REQUIRED"

    risk_score = _clamp_risk(
        decision_result.get(
            "risk_score",
            state.get(
                "preliminary_risk_score",
                0.0,
            ),
        )
    )

    confidence = _safe_float(
        decision_result.get(
            "confidence",
            0.0,
        )
    )

    blockchain_allowed = (
        pipeline_complete
        and final_verdict
        in BLOCKCHAIN_ALLOWED_VERDICTS
    )

    if blockchain_allowed:

        blockchain_reason = (
            "Blockchain certification authorized: "
            "all required Agriculture verification agents "
            "completed successfully and DecisionEngine returned VERIFIED."
        )

    else:

        reasons: List[str] = []

        if not pipeline_complete:

            reasons.append(
                "required verification pipeline is incomplete"
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

    final_state = (
        "BLOCKCHAIN_PENDING"
        if blockchain_allowed
        else (
            "COMPLETED"
            if final_verdict in {
                "VERIFIED",
                "REJECTED",
            }
            else "NEEDS_REVIEW"
        )
    )

    return {
        "final_verdict": final_verdict,
        "risk_score": risk_score,
        "confidence": confidence,
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
                pipeline["failed_agents"]
            )
        ),
        "required_agents_complete": pipeline_complete,
        "evidence_complete": pipeline_complete,
        "human_review_required": (
            final_verdict
            == "REVIEW_REQUIRED"
        ),
        "blockchain_allowed": blockchain_allowed,
        "blockchain_reason": blockchain_reason,
        "state": final_state,
        "steps": [
            {
                "agent": "Finalize",
                "decision": final_verdict,
                "risk_score": risk_score,
                "confidence": confidence,
                "blockchain_allowed": blockchain_allowed,
            }
        ],
    }


# ============================================================
# BLOCKCHAIN AUTHORIZATION ROUTER
# ============================================================

def blockchain_authorization_router(
    state: AgricultureParallelState,
) -> str:
    """
    Hard graph-level blockchain authorization gate.

    The blockchain certificate node is NEVER executed merely because
    Finalize completed.

    It may execute only when blockchain_allowed is exactly True.
    """

    allowed = state.get(
        "blockchain_allowed",
        False,
    )

    if allowed is True:

        logger.info(
            "Agriculture blockchain authorization: ALLOWED"
        )

        return "blockchain_certificate"

    logger.info(
        "Agriculture blockchain authorization: DENIED"
    )

    return END


# ============================================================
# TEMPORARY BLOCKCHAIN CERTIFICATE NODE
# ============================================================

def blockchain_certificate_node(
    state: AgricultureParallelState,
) -> Dict[str, Any]:
    """
    Real blockchain certification node using smart contract on Sepolia/Local network.
    Delegates to graph.blockchain_node.blockchain_certificate_node.
    """
    logger.info("Executing real blockchain_certificate_node for Agriculture claim: %s", state.get("claim_id"))
    return real_blockchain_certificate_node(state)


# ============================================================
# BUILD LANGGRAPH
# ============================================================

builder = StateGraph(
    AgricultureParallelState,
)


# ============================================================
# ADD NODES
# ============================================================

builder.add_node(
    "text",
    text_node,
)

builder.add_node(
    "image",
    image_node,
)

builder.add_node(
    "satellite",
    satellite_node,
)

builder.add_node(
    "sensor",
    sensor_node,
)

builder.add_node(
    "cross_modal",
    cross_modal_node,
)

builder.add_node(
    "investigation",
    investigation_node,
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
    "decision",
    decision_node,
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
    "text",
)

# Text initializes the claim context. Image, satellite and sensor evidence
# are independent, so LangGraph fans out and runs these three nodes in
# parallel. CrossModal waits for all three branches to complete.
builder.add_edge(
    "text",
    "image",
)

builder.add_edge(
    "text",
    "satellite",
)

builder.add_edge(
    "text",
    "sensor",
)

builder.add_edge(
    "image",
    "cross_modal",
)

builder.add_edge(
    "satellite",
    "cross_modal",
)

builder.add_edge(
    "sensor",
    "cross_modal",
)

builder.add_edge(
    "cross_modal",
    "investigation",
)

builder.add_edge(
    "investigation",
    "risk",
)

builder.add_edge(
    "risk",
    "adversarial",
)

builder.add_edge(
    "adversarial",
    "decision",
)

builder.add_edge(
    "decision",
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

# Backward-compatible public name for orchestrator.py
app_graph = graph


# ============================================================
# PUBLIC EXPORTS
# ============================================================

__all__ = [
    "graph",
    "app_graph",
    "text_node",
    "image_node",
    "satellite_node",
    "sensor_node",
    "cross_modal_node",
    "investigation_node",
    "risk_node",
    "adversarial_node",
    "decision_node",
    "finalize_node",
    "blockchain_authorization_router",
    "blockchain_certificate_node",
]


# ============================================================
# IMPORT / GRAPH STRUCTURE TEST
# ============================================================

if __name__ == "__main__":

    print(
        "AGRICULTURE LANGGRAPH IMPORT TEST: PASS"
    )

    print(
        "DOMAIN:",
        DOMAIN,
    )

    print(
        "NODES:"
    )

    for node_name in [
        "text",
        "image",
        "satellite",
        "sensor",
        "cross_modal",
        "investigation",
        "risk",
        "adversarial",
        "decision",
        "finalize",
        "blockchain_certificate",
    ]:

        print(
            f"  - {node_name}"
        )

    print(
        "PARALLEL EVIDENCE: ImageAgent + SatelliteAgent + SensorAgent"
    )

    print(
        "CROSS-MODAL JOIN: WAIT FOR ALL THREE EVIDENCE BRANCHES"
    )

    print(
        "BLOCKCHAIN GATE: ENABLED"
    )

    print(
        "GRAPH COMPILE: PASS"
    )