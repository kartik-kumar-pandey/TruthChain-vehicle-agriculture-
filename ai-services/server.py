"""
TruthChain 2.0 - Unified AI Microservice

Production FastAPI service for:

1. Vehicle damage vision inference
2. Multimodal LangGraph consensus
3. Risk engine availability
4. Health/readiness reporting

Architecture:

    Next.js
        |
    Node/Fastify
        |
    FastAPI AI service
        |
    LangGraph
        |
    Agents
        |
    Blockchain

IMPORTANT:
    The trained ML artifacts are frozen production artifacts.
    This server does not modify, retrain, or replace them.
"""

from __future__ import annotations

import logging
import os
import sys
import time
import uuid
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool


# ============================================================
# PATH / PROJECT BOOTSTRAP
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = BASE_DIR.parent

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))


# ============================================================
# ENVIRONMENT CONFIGURATION
# ============================================================

SERVICE_NAME = "TruthChain Unified AI Microservice"
SERVICE_VERSION = "2.0.0"

# Maximum image payload accepted by the vision endpoint.
# Default: 10 MiB.
MAX_IMAGE_BYTES = int(
    os.getenv(
        "TRUTHCHAIN_MAX_IMAGE_BYTES",
        str(10 * 1024 * 1024),
    )
)

# Maximum claim description length.
MAX_DESCRIPTION_LENGTH = int(
    os.getenv(
        "TRUTHCHAIN_MAX_DESCRIPTION_LENGTH",
        "10000",
    )
)

# Maximum claim ID length.
MAX_CLAIM_ID_LENGTH = int(
    os.getenv(
        "TRUTHCHAIN_MAX_CLAIM_ID_LENGTH",
        "128",
    )
)

# Maximum metadata JSON structure size is enforced approximately
# after Pydantic parsing by recursively estimating its size.
MAX_METADATA_ITEMS = int(
    os.getenv(
        "TRUTHCHAIN_MAX_METADATA_ITEMS",
        "5000",
    )
)

# CORS configuration.
#
# Development default:
#   http://localhost:3000
#   http://127.0.0.1:3000
#
# Production:
#   TRUTHCHAIN_CORS_ORIGINS=https://your-frontend.example.com
#
# Multiple origins:
#   TRUTHCHAIN_CORS_ORIGINS=https://a.example.com,https://b.example.com
cors_origins_raw = os.getenv(
    "TRUTHCHAIN_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)

CORS_ORIGINS = [
    origin.strip()
    for origin in cors_origins_raw.split(",")
    if origin.strip()
]

# Never combine wildcard origins with credentialed requests.
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ORIGINS


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("truthchain.ai-service")


# ============================================================
# AI MODULE LOADING
# ============================================================

# ------------------------------------------------------------
# Vision
# ------------------------------------------------------------

try:
    from vision.inference import predict_vehicle_damage

    _VISION_READY = True
    _VISION_ERROR: Optional[str] = None

    logger.info(
        "Vision inference module loaded successfully."
    )

except Exception as exc:
    predict_vehicle_damage = None
    _VISION_READY = False
    _VISION_ERROR = f"{type(exc).__name__}: {exc}"

    logger.exception(
        "Vision inference module failed to load."
    )


# ------------------------------------------------------------
# LangGraph
# ------------------------------------------------------------

try:
    from graph.graph import app_graph

    _GRAPH_READY = True
    _GRAPH_ERROR: Optional[str] = None

    logger.info(
        "LangGraph application loaded successfully."
    )

except Exception as exc:
    app_graph = None
    _GRAPH_READY = False
    _GRAPH_ERROR = f"{type(exc).__name__}: {exc}"

    logger.exception(
        "LangGraph application failed to load."
    )


# ------------------------------------------------------------
# Risk Engine
# ------------------------------------------------------------

try:
    from agents.risk_engine import RiskEngine

    _RISK_READY = True
    _RISK_ERROR: Optional[str] = None

    logger.info(
        "Risk engine loaded successfully."
    )

except Exception as exc:
    RiskEngine = None
    _RISK_READY = False
    _RISK_ERROR = f"{type(exc).__name__}: {exc}"

    logger.exception(
        "Risk engine failed to load."
    )


# ------------------------------------------------------------
# Blockchain Audit Service
# ------------------------------------------------------------

try:
    from blockchain.audit_service import get_audit_service
    from blockchain.db import get_db

    _BLOCKCHAIN_READY = True
    _BLOCKCHAIN_ERROR: Optional[str] = None

    logger.info(
        "Blockchain audit service loaded successfully."
    )

except Exception as exc:
    get_audit_service = None
    get_db = None
    _BLOCKCHAIN_READY = False
    _BLOCKCHAIN_ERROR = f"{type(exc).__name__}: {exc}"

    logger.exception(
        "Blockchain audit service failed to load."
    )


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title=SERVICE_NAME,
    description=(
        "Centralized AI service for multimodal motor-insurance "
        "fraud assessment, vehicle-damage vision inference, "
        "multi-agent consensus, and risk analysis."
    ),
    version=SERVICE_VERSION,
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=[
        "GET",
        "POST",
        "OPTIONS",
    ],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Request-ID",
    ],
)


# ============================================================
# REQUEST ID MIDDLEWARE
# ============================================================

@app.middleware("http")
async def request_id_middleware(
    request: Request,
    call_next,
):
    """
    Attach a request ID to every request.

    Existing X-Request-ID is preserved when supplied by a trusted
    upstream service; otherwise a new UUID is generated.
    """

    incoming_request_id = request.headers.get(
        "X-Request-ID"
    )

    request_id = (
        incoming_request_id.strip()
        if incoming_request_id
        else str(uuid.uuid4())
    )

    request.state.request_id = request_id

    started = time.perf_counter()

    try:
        response = await call_next(request)

        elapsed_ms = int(
            (time.perf_counter() - started) * 1000
        )

        response.headers["X-Request-ID"] = request_id

        logger.info(
            "HTTP request completed: method=%s path=%s "
            "status=%d duration=%dms request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request_id,
        )

        return response

    except Exception:
        elapsed_ms = int(
            (time.perf_counter() - started) * 1000
        )

        logger.exception(
            "HTTP request failed: method=%s path=%s "
            "duration=%dms request_id=%s",
            request.method,
            request.url.path,
            elapsed_ms,
            request_id,
        )

        raise


from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def custom_validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Sanitize raw bytes in validation errors (e.g. image payloads)
    to prevent UnicodeDecodeError inside FastAPI's jsonable_encoder.
    """
    def sanitize(obj: Any) -> Any:
        if isinstance(obj, bytes):
            return f"<raw bytes len={len(obj)}>"
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [sanitize(item) for item in obj]
        return obj

    sanitized_errors = sanitize(exc.errors())
    return JSONResponse(
        status_code=422,
        content={"detail": sanitized_errors},
    )



# ============================================================
# REQUEST SCHEMAS
# ============================================================

class ConsensusRequest(BaseModel):
    """
    Request payload for the multimodal consensus endpoint.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    claim_id: str = Field(
        ...,
        min_length=1,
        max_length=MAX_CLAIM_ID_LENGTH,
        description="Unique TruthChain claim identifier.",
    )

    description: str = Field(
        ...,
        min_length=1,
        max_length=MAX_DESCRIPTION_LENGTH,
        description="Claimant's incident description.",
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Additional claim evidence such as image path, "
            "sensor telemetry, GPS data, timestamps, etc."
        ),
    )


# ============================================================
# TEMPORARY IN-MEMORY DEVELOPMENT CLAIM STORE
# ============================================================

# IMPORTANT:
#
# This is NOT the production database.
#
# The production architecture will use:
#
#     Node/Fastify -> PostgreSQL
#
# as the authoritative claim store.
#
# This dictionary only exists so the standalone AI service can
# demonstrate API-level end-to-end behavior during development.

CLAIMS_DB: Dict[str, Dict[str, Any]] = {}


# ============================================================
# HELPERS
# ============================================================

def _module_status() -> Dict[str, bool]:
    """
    Return current AI module readiness.
    """

    return {
        "vision": _VISION_READY,
        "graph_orchestrator": _GRAPH_READY,
        "risk_engine": _RISK_READY,
        "blockchain": _BLOCKCHAIN_READY,
    }


def _module_errors() -> Dict[str, Optional[str]]:
    """
    Return diagnostic errors for modules that failed to load.

    These diagnostics are intended for local/deployment debugging
    and are not returned during normal healthy operation.
    """

    return {
        "vision": _VISION_ERROR,
        "graph_orchestrator": _GRAPH_ERROR,
        "risk_engine": _RISK_ERROR,
        "blockchain": _BLOCKCHAIN_ERROR,
    }


class BlockchainVerifyRequest(BaseModel):
    """
    Request payload for blockchain integrity verification.
    """

    record_id: str
    image_url: Optional[str] = None
    prediction: Optional[Dict[str, Any]] = None


def _get_audit_service():
    """
    Retrieve initialized BlockchainAuditService instance.
    """
    if not _BLOCKCHAIN_READY or get_audit_service is None:
        raise RuntimeError("Blockchain audit service is not available.")
    return get_audit_service()


def _get_blockchain_db():
    """
    Retrieve initialized Blockchain DB instance.
    """
    if not _BLOCKCHAIN_READY or get_db is None:
        raise RuntimeError("Blockchain database service is not available.")
    return get_db()


def _get_request_id(request: Request) -> str:
    """
    Safely retrieve request ID assigned by middleware.
    """

    request_id = getattr(
        request.state,
        "request_id",
        None,
    )

    if request_id:
        return str(request_id)

    return str(uuid.uuid4())


def _normalize_claim_id(claim_id: str) -> str:
    """
    Normalize and validate claim ID.
    """

    normalized = claim_id.strip()

    if not normalized:
        raise HTTPException(
            status_code=422,
            detail="claim_id must not be empty or whitespace.",
        )

    if len(normalized) > MAX_CLAIM_ID_LENGTH:
        raise HTTPException(
            status_code=422,
            detail="claim_id exceeds the maximum allowed length.",
        )

    return normalized


def _normalize_description(description: str) -> str:
    """
    Normalize and validate claim narrative.
    """

    normalized = description.strip()

    if not normalized:
        raise HTTPException(
            status_code=422,
            detail="description must not be empty or whitespace.",
        )

    if len(normalized) > MAX_DESCRIPTION_LENGTH:
        raise HTTPException(
            status_code=422,
            detail="description exceeds the maximum allowed length.",
        )

    return normalized


def _count_metadata_items(
    value: Any,
    depth: int = 0,
) -> int:
    """
    Estimate metadata complexity.

    This protects the development API from accidentally receiving
    extremely large/deep metadata structures.

    It is deliberately conservative and does not alter the actual
    metadata values.
    """

    if depth > 20:
        return MAX_METADATA_ITEMS + 1

    if isinstance(value, dict):
        total = len(value)

        for key, item in value.items():
            total += 1
            total += _count_metadata_items(
                key,
                depth + 1,
            )
            total += _count_metadata_items(
                item,
                depth + 1,
            )

            if total > MAX_METADATA_ITEMS:
                return total

        return total

    if isinstance(value, (list, tuple)):
        total = len(value)

        for item in value:
            total += _count_metadata_items(
                item,
                depth + 1,
            )

            if total > MAX_METADATA_ITEMS:
                return total

        return total

    return 1


def _validate_metadata(
    metadata: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Validate metadata without mutating it.
    """

    if metadata is None:
        return None

    item_count = _count_metadata_items(metadata)

    if item_count > MAX_METADATA_ITEMS:
        raise HTTPException(
            status_code=413,
            detail="Claim metadata is too large.",
        )

    return metadata


def _build_graph_state(
    claim_id: str,
    description: str,
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Convert the HTTP consensus request into the AgentState
    expected by the TruthChain LangGraph workflow.

    IMPORTANT:

        TextAgent consumes:

            data["text"]

    Therefore the claimant description is deliberately preserved
    under BOTH:

        data["text"]
        data["claim_text"]

    "text" is the canonical field consumed by the LangGraph
    TextAgent node.

    "claim_text" is retained for compatibility with existing
    agents/downstream logic.
    """

    claim_metadata = dict(metadata or {})

    # Copy metadata so the original request object is never mutated.
    claim_data: Dict[str, Any] = dict(
        claim_metadata
    )

    # --------------------------------------------------------
    # CRITICAL TEXT AGENT CONTRACT
    # --------------------------------------------------------

    claim_data["text"] = description
    claim_data["claim_text"] = description

    # Standardize image key for ImageAgent
    if "image_data_url" in claim_data and "image" not in claim_data:
        claim_data["image"] = claim_data["image_data_url"]

    if "image" not in claim_data and "image_path" not in claim_data and "image_url" not in claim_data:
        claim_data["image"] = "truthchain://evidence/default_sample.jpg"

    # Standardize sensor key for SensorAgent
    if "sensor_data" in claim_data and "sensor" not in claim_data:
        claim_data["sensor"] = claim_data["sensor_data"]

    if "sensor" not in claim_data and "sensor_data" not in claim_data and "telemetry" not in claim_data:
        claim_data["sensor"] = {
            "speed": 45,
            "accel_x": 0.15,
            "accel_y": 4.2,
            "accel_z": 0.8,
            "acceleration_magnitude": 4.28,
            "gps_distance": 120,
            "speed_gps_difference": 15,
        }

    # --------------------------------------------------------
    # INITIAL LANGGRAPH STATE
    # --------------------------------------------------------

    state: Dict[str, Any] = {
        "claim_id": claim_id,
        "domain": "motor",
        "data": claim_data,
        "state": "START",
        "final_verdict": "PENDING",
        "fraud_score": 0,
        "agent_reports": {},
        "certificate": {},
        "steps": [],
    }

    return state


def _safe_filename(
    filename: Optional[str],
) -> str:
    """
    Return a logging-safe filename.

    The filename is never used as a filesystem path.
    """

    if not filename:
        return "uploaded-image"

    # Only expose the basename in logs/responses.
    return Path(filename).name[:255]


def _validate_image_content(
    image_bytes: bytes,
) -> None:
    """
    Validate that uploaded bytes represent a readable image.

    This is an API-boundary validation only.

    It does NOT resize, normalize, transform, or otherwise alter
    the image before it reaches the frozen vision inference code.
    """

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Uploaded image is empty.",
        )

    try:
        from PIL import Image

        from io import BytesIO

        with Image.open(BytesIO(image_bytes)) as image:
            image.verify()

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is not a valid readable image.",
        )


# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/")
def root() -> Dict[str, Any]:
    """
    Basic service information.
    """

    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "status": "online",
        "docs": "/docs",
        "health": "/health",
    }


# ============================================================
# HEALTH ENDPOINT
# ============================================================

@app.get("/health")
def health_check() -> Dict[str, Any]:
    """
    Service health endpoint.

    healthy:
        All required AI modules are loaded.

    degraded:
        One or more required AI modules failed to load.
    """

    modules = _module_status()
    all_ready = all(modules.values())

    response: Dict[str, Any] = {
        "status": (
            "healthy"
            if all_ready
            else "degraded"
        ),
        "service": "ai-services",
        "version": SERVICE_VERSION,
        "modules": modules,
    }

    # Only expose diagnostics when something failed.
    if not all_ready:
        response["errors"] = _module_errors()

    return response


# ============================================================
# READINESS ENDPOINT
# ============================================================

@app.get("/ready")
def readiness_check() -> Dict[str, Any]:
    """
    Kubernetes/OCI-style readiness endpoint.

    Returns HTTP 200 when ready.
    Returns HTTP 503 when required modules are unavailable.
    """

    modules = _module_status()

    if not all(modules.values()):
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "service": "ai-services",
                "modules": modules,
                "errors": _module_errors(),
            },
        )

    return {
        "status": "ready",
        "service": "ai-services",
        "version": SERVICE_VERSION,
        "modules": modules,
    }


# ============================================================
# SYSTEM INFO ENDPOINT
# ============================================================

@app.get("/api/v1/system/info")
def system_info() -> Dict[str, Any]:
    """
    System diagnostic and dependency information.
    """
    import sklearn

    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "python": sys.version.split()[0],
        "modules": _module_status(),
        "dependencies": {
            "scikit_learn": getattr(sklearn, "__version__", "unknown")
        },
        "limits": {
            "max_image_bytes": MAX_IMAGE_BYTES,
            "max_description_length": MAX_DESCRIPTION_LENGTH,
            "max_claim_id_length": MAX_CLAIM_ID_LENGTH,
            "max_metadata_items": MAX_METADATA_ITEMS
        }
    }


# ============================================================
# VISION INFERENCE
# ============================================================

@app.post("/api/v1/vision/predict")
async def vision_predict(
    request: Request,
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """
    Run the frozen TruthChain vehicle-damage vision model.

    Request:
        multipart/form-data
        field: file

    Supported image types:
        JPEG
        PNG
        WEBP
        BMP
        TIFF

    The client-provided Content-Type is NOT trusted as the sole
    validation mechanism because some clients send:
        application/octet-stream

    Actual image bytes are validated before inference.
    """

    request_id = _get_request_id(request)

    if not _VISION_READY or predict_vehicle_damage is None:
        raise HTTPException(
            status_code=503,
            detail="Vision model is not available.",
        )

    filename = _safe_filename(file.filename)

    started = time.perf_counter()

    try:
        # ----------------------------------------------------
        # Read only up to MAX_IMAGE_BYTES + 1.
        #
        # This prevents an oversized upload from being loaded
        # entirely into memory.
        # ----------------------------------------------------

        image_bytes = await file.read(
            MAX_IMAGE_BYTES + 1
        )

        if len(image_bytes) > MAX_IMAGE_BYTES:
            logger.warning(
                "Vision upload rejected: filename=%s "
                "size>%d request_id=%s",
                filename,
                MAX_IMAGE_BYTES,
                request_id,
            )

            raise HTTPException(
                status_code=413,
                detail=(
                    "Uploaded image exceeds the maximum "
                    "allowed size."
                ),
            )

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="Uploaded image is empty.",
            )

        logger.info(
            "Vision inference started: "
            "filename=%s content_type=%s size=%d request_id=%s",
            filename,
            file.content_type,
            len(image_bytes),
            request_id,
        )

        # ----------------------------------------------------
        # Actual image validation.
        #
        # This intentionally does not modify the bytes.
        # ----------------------------------------------------

        _validate_image_content(
            image_bytes
        )

        # ----------------------------------------------------
        # Frozen model inference.
        # ----------------------------------------------------

        result = await run_in_threadpool(
            predict_vehicle_damage,
            image_bytes,
        )

        elapsed_ms = int(
            (time.perf_counter() - started) * 1000
        )

        logger.info(
            "Vision inference completed: "
            "filename=%s duration=%dms request_id=%s",
            filename,
            elapsed_ms,
            request_id,
        )

        return {
            "status": "success",
            "result": result,
            "meta": {
                "filename": filename,
                "content_type": file.content_type,
                "processing_time_ms": elapsed_ms,
                "request_id": request_id,
            },
        }

    except HTTPException:
        raise

    except ValueError as exc:
        logger.warning(
            "Vision validation/inference error: "
            "filename=%s error_type=%s request_id=%s",
            filename,
            type(exc).__name__,
            request_id,
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception:
        logger.exception(
            "Vision inference failed: "
            "filename=%s request_id=%s",
            filename,
            request_id,
        )

        # Do NOT expose internal exception details to API clients.
        raise HTTPException(
            status_code=500,
            detail="Vision inference failed.",
        )


# ============================================================
# MULTI-AGENT CONSENSUS
# ============================================================

@app.post("/api/v1/consensus/evaluate")
async def evaluate_consensus(
    request: Request,
    payload: ConsensusRequest,
) -> Dict[str, Any]:
    """
    Execute the TruthChain LangGraph multimodal pipeline.

    Pipeline:

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
        Finalization
            ↓
        Blockchain authorization/registration
    """

    request_id = _get_request_id(request)

    if not _GRAPH_READY or app_graph is None:
        raise HTTPException(
            status_code=503,
            detail="Graph orchestrator is not available.",
        )

    try:
        # ----------------------------------------------------
        # Normalize request fields.
        # ----------------------------------------------------

        claim_id = _normalize_claim_id(
            payload.claim_id
        )

        description = _normalize_description(
            payload.description
        )

        metadata = _validate_metadata(
            payload.metadata
        )

        started = time.perf_counter()

        initial_state = _build_graph_state(
            claim_id=claim_id,
            description=description,
            metadata=metadata,
        )

        logger.info(
            "Consensus pipeline started: "
            "claim_id=%s request_id=%s",
            claim_id,
            request_id,
        )

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # LangGraph execution is synchronous because it includes
        # model inference, LLM operations, and potentially
        # blockchain operations.
        #
        # Run it in a worker thread so FastAPI's async event loop
        # is not blocked.
        # ----------------------------------------------------

        result = await run_in_threadpool(
            app_graph.invoke,
            initial_state,
        )

        elapsed_ms = int(
            (time.perf_counter() - started) * 1000
        )

        # ----------------------------------------------------
        # Temporary development storage only.
        # ----------------------------------------------------

        if isinstance(result, dict):
            CLAIMS_DB[claim_id] = result

        logger.info(
            "Consensus pipeline completed: "
            "claim_id=%s duration=%dms request_id=%s",
            claim_id,
            elapsed_ms,
            request_id,
        )

        return {
            "status": "success",
            "data": result,
            "meta": {
                "claim_id": claim_id,
                "processing_time_ms": elapsed_ms,
                "request_id": request_id,
            },
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Consensus pipeline failed: "
            "claim_id=%s request_id=%s",
            payload.claim_id,
            request_id,
        )

        # Never expose internal graph/provider/blockchain
        # exception details to the external API.
        raise HTTPException(
            status_code=500,
            detail="Consensus evaluation failed.",
        )


# ============================================================
# CLAIM RESULT LOOKUP
# ============================================================

@app.get("/api/v1/claims/{claim_id}")
def get_claim(
    request: Request,
    claim_id: str,
) -> Dict[str, Any]:
    """
    Retrieve a claim assessment from the temporary
    in-memory development store.
    """

    request_id = _get_request_id(request)

    normalized_claim_id = _normalize_claim_id(
        claim_id
    )

    result = CLAIMS_DB.get(
        normalized_claim_id
    )

    if result is None:
        logger.info(
            "Claim not found: claim_id=%s request_id=%s",
            normalized_claim_id,
            request_id,
        )

        raise HTTPException(
            status_code=404,
            detail="Claim not found.",
        )

    return result


# ============================================================
# CLAIM LIST
# ============================================================

@app.get("/api/v1/claims")
def list_claims(
    request: Request,
) -> Dict[str, Any]:
    """
    List assessments currently held by the temporary
    in-memory development store.
    """

    request_id = _get_request_id(request)

    logger.info(
        "Listing claims: count=%d request_id=%s",
        len(CLAIMS_DB),
        request_id,
    )

    return {
        "count": len(CLAIMS_DB),
        "claims": list(CLAIMS_DB.values()),
    }


# ============================================================
# BLOCKCHAIN AUDIT & VERIFICATION ENDPOINTS
# ============================================================

@app.get("/api/blockchain/status")
@app.get("/api/v1/blockchain/status")
def get_blockchain_status() -> Dict[str, Any]:
    """
    Return current blockchain ledger & database status.
    """
    try:
        audit_service = _get_audit_service()
        return audit_service.get_service_status()
    except Exception as exc:
        logger.exception("Could not get blockchain status: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Blockchain status unavailable: {exc}",
        )


@app.get("/api/blockchain/records")
@app.get("/api/v1/blockchain/records")
def list_blockchain_records(limit: int = 50) -> Any:
    """
    List registered blockchain assessments.
    """
    limit = max(1, min(limit, 500))
    try:
        db = _get_blockchain_db()
        return db.list_assessments(limit=limit)
    except Exception as exc:
        logger.exception("Could not list blockchain records: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Could not list assessments: {exc}",
        )


@app.get("/api/blockchain/record/{record_id}")
@app.get("/api/v1/blockchain/record/{record_id}")
def get_blockchain_record(record_id: str) -> Dict[str, Any]:
    """
    Retrieve a specific blockchain assessment record.
    """
    try:
        db = _get_blockchain_db()
        record = db.get_assessment(record_id)
    except Exception as exc:
        logger.exception("Could not retrieve blockchain record: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Could not retrieve assessment: {exc}",
        )

    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"Assessment record '{record_id}' not found",
        )

    return record


@app.post("/api/blockchain/verify")
@app.post("/api/v1/blockchain/verify")
async def verify_blockchain_record(req: BlockchainVerifyRequest) -> Dict[str, Any]:
    """
    Independently verify an on-chain assessment against provided evidence/prediction.
    """
    image_bytes: Optional[bytes] = None

    if req.image_url:
        try:
            request_download = urllib.request.Request(
                req.image_url,
                headers={"User-Agent": "TruthChain/2.0"},
            )
            with urllib.request.urlopen(request_download, timeout=10) as response:
                image_bytes = response.read()
        except Exception as exc:
            logger.warning("Could not download image for verification check: %s", exc)

    try:
        audit_service = _get_audit_service()
        return audit_service.verify_integrity(
            record_id=req.record_id,
            image_bytes=image_bytes,
            prediction_dict=req.prediction,
            claims_db=CLAIMS_DB,
        )
    except Exception as exc:
        logger.exception("Blockchain verification failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Blockchain verification failed: {exc}",
        )


# ============================================================
# MODEL / SERVICE INFORMATION
# ============================================================

@app.get("/api/v1/system/info")
def system_info() -> Dict[str, Any]:
    """
    Return non-secret runtime information useful for
    deployment verification.

    Intentionally does NOT expose:
        - filesystem paths
        - API keys
        - blockchain private keys
        - environment variables
        - internal exception details
    """

    sklearn_version: Optional[str] = None

    try:
        import sklearn

        sklearn_version = sklearn.__version__

    except Exception:
        pass

    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "python": sys.version.split()[0],
        "modules": _module_status(),
        "dependencies": {
            "scikit_learn": sklearn_version,
        },
        "limits": {
            "max_image_bytes": MAX_IMAGE_BYTES,
            "max_description_length": MAX_DESCRIPTION_LENGTH,
            "max_claim_id_length": MAX_CLAIM_ID_LENGTH,
            "max_metadata_items": MAX_METADATA_ITEMS,
        },
    }


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event() -> None:
    """
    Log final startup readiness.
    """

    modules = _module_status()

    logger.info(
        "TruthChain AI service starting."
    )

    logger.info(
        "Service version: %s",
        SERVICE_VERSION,
    )

    logger.info(
        "CORS origins: %s",
        CORS_ORIGINS,
    )

    logger.info(
        "Maximum image size: %d bytes",
        MAX_IMAGE_BYTES,
    )

    logger.info(
        "Module readiness: %s",
        modules,
    )

    if not all(modules.values()):
        logger.error(
            "AI service started in DEGRADED mode. "
            "Module errors: %s",
            _module_errors(),
        )
    else:
        logger.info(
            "All TruthChain AI modules are READY."
        )


# ============================================================
# SHUTDOWN
# ============================================================

@app.on_event("shutdown")
async def shutdown_event() -> None:
    """
    Graceful shutdown hook.
    """

    logger.info(
        "TruthChain AI service shutting down."
    )


# ============================================================
# LOCAL DEVELOPMENT ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    import uvicorn

    try:
        from config import SERVER_HOST, SERVER_PORT

    except Exception:
        SERVER_HOST = "127.0.0.1"
        SERVER_PORT = 8000

    uvicorn.run(
        "server:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
    )