"""
TruthChain Agriculture
Core Schemas
============

Pydantic schemas shared by the Agriculture / PMFBY verification
pipeline.

The schemas define:

- farmer claim input
- farm location / field geometry
- structured agent outputs
- consensus output
- evidence references
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from agriculture.core.constants import (
    AGENT_FAIL,
    AGENT_PASS,
    AGENT_SUSPICIOUS,
    MAX_CLAIMED_LOSS_PERCENT,
    MIN_CLAIMED_LOSS_PERCENT,
    FINAL_REJECTED,
    FINAL_REVIEW_REQUIRED,
    FINAL_UNCERTAIN,
    FINAL_VERIFIED,
)


# ============================================================
# Shared types
# ============================================================

AgentDecision = Literal[
    AGENT_PASS,
    AGENT_SUSPICIOUS,
    AGENT_FAIL,
]

FinalDecision = Literal[
    FINAL_VERIFIED,
    FINAL_REVIEW_REQUIRED,
    FINAL_REJECTED,
    FINAL_UNCERTAIN,
]


# ============================================================
# Geographic schemas
# ============================================================

class GeoPoint(BaseModel):
    """
    A geographic point expressed as latitude/longitude.
    """

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
    )

    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
    )


class FarmLocation(BaseModel):
    """
    Farm location supplied with an agricultural claim.

    A production claim may identify the farm using:
        - GPS coordinates
        - cadastral / field identifier
        - field polygon

    At least one location identifier must be supplied.
    """

    model_config = ConfigDict(extra="forbid")

    latitude: float | None = Field(
        default=None,
        ge=-90.0,
        le=90.0,
    )

    longitude: float | None = Field(
        default=None,
        ge=-180.0,
        le=180.0,
    )

    cadastral_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    field_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    boundary: list[GeoPoint] | None = None

    @field_validator("boundary")
    @classmethod
    def validate_boundary(
        cls,
        value: list[GeoPoint] | None,
    ) -> list[GeoPoint] | None:
        if value is not None and len(value) < 3:
            raise ValueError(
                "Field boundary must contain at least 3 points."
            )

        return value

    def has_location(self) -> bool:
        """
        Return True when the claim contains at least one usable
        field-location identifier.
        """

        has_coordinates = (
            self.latitude is not None
            and self.longitude is not None
        )

        return bool(
            has_coordinates
            or self.cadastral_id
            or self.field_id
            or self.boundary
        )


# ============================================================
# Claim schema
# ============================================================

class AgricultureClaim(BaseModel):
    """
    Agriculture / PMFBY claim submitted for verification.

    Sensitive farmer information remains an off-chain concern.
    Only hashes and verification metadata will later be prepared
    for blockchain anchoring.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    # --------------------------------------------------------
    # Identity / routing
    # --------------------------------------------------------

    claim_id: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )

    insurer_id: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )

    # Optional off-chain farmer reference.
    farmer_id: str | None = Field(
        default=None,
        max_length=200,
    )

    # --------------------------------------------------------
    # Farm information
    # --------------------------------------------------------

    farm: FarmLocation

    crop_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    sown_area: float = Field(
        ...,
        gt=0.0,
        description="Sown area in hectares.",
    )

    claimed_loss_pct: float = Field(
        ...,
        ge=MIN_CLAIMED_LOSS_PERCENT,
        le=MAX_CLAIMED_LOSS_PERCENT,
    )

    # --------------------------------------------------------
    # Claim timing
    # --------------------------------------------------------

    claim_date: date
    incident_date: date

    # --------------------------------------------------------
    # Claim description / evidence
    # --------------------------------------------------------

    description: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )

    image_path: str | None = Field(
        default=None,
        max_length=1000,
    )

    sensor_log_path: str | None = Field(
        default=None,
        max_length=1000,
    )

    weather_log_path: str | None = Field(
        default=None,
        max_length=1000,
    )

    # --------------------------------------------------------
    # Optional external references
    # --------------------------------------------------------

    satellite_reference: str | None = Field(
        default=None,
        max_length=1000,
    )

    policy_reference: str | None = Field(
        default=None,
        max_length=200,
    )

    @field_validator("crop_type")
    @classmethod
    def normalize_crop_type(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError(
                "Claim description cannot be empty."
            )

        return value


# ============================================================
# Evidence reference
# ============================================================

class EvidenceReference(BaseModel):
    """
    Reference to an evidence artifact used by an agent.

    Raw files remain off-chain. The hash provides deterministic
    identity for audit and later blockchain anchoring.
    """

    model_config = ConfigDict(extra="forbid")

    evidence_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    source: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )

    reference: str | None = Field(
        default=None,
        max_length=1000,
    )

    sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{64}$",
    )

    observed_at: datetime | None = None

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )


# ============================================================
# Structured Agent Result
# ============================================================

class AgentResult(BaseModel):
    """
    Common TruthChain agent contract.

    Every Agriculture agent must return this structure.

    The project documentation explicitly defines:
        agent
        domain
        confidence
        risk_score
        decision
        evidence
        contradictions
        model_version
        processing_time_ms
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    agent: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    domain: Literal["agriculture"] = "agriculture"

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )

    risk_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )

    decision: AgentDecision

    evidence: list[str] = Field(
        default_factory=list,
    )

    contradictions: list[str] = Field(
        default_factory=list,
    )

    model_version: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    processing_time_ms: float = Field(
        ...,
        ge=0.0,
    )

    evidence_refs: list[EvidenceReference] = Field(
        default_factory=list,
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict,
    )


# ============================================================
# Consensus result
# ============================================================

class ConsensusResult(BaseModel):
    """
    Result produced after combining the Agriculture agent risks.

    This is the preliminary decision before adversarial
    verification.
    """

    model_config = ConfigDict(extra="forbid")

    domain: Literal["agriculture"] = "agriculture"

    fraud_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )

    decision: FinalDecision

    agent_results: list[AgentResult] = Field(
        default_factory=list,
    )

    agent_flags: list[str] = Field(
        default_factory=list,
    )

    reasoning: list[str] = Field(
        default_factory=list,
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
    )


# ============================================================
# Adversarial verification result
# ============================================================

class AdversarialResult(BaseModel):
    """
    Result of the adversarial verification stage.

    The verifier attempts to challenge the preliminary
    consensus using independent evidence.
    """

    model_config = ConfigDict(extra="forbid")

    agent: Literal["AdversarialVerifier"] = (
        "AdversarialVerifier"
    )

    domain: Literal["agriculture"] = "agriculture"

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )

    challenged: bool

    verification_status: Literal[
        "CONFIRMED",
        "UNCERTAIN",
    ]

    contradictions: list[str] = Field(
        default_factory=list,
    )

    supporting_evidence: list[str] = Field(
        default_factory=list,
    )

    model_version: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    processing_time_ms: float = Field(
        ...,
        ge=0.0,
    )


# ============================================================
# Final verification result
# ============================================================

class VerificationResult(BaseModel):
    """
    Final agriculture verification result.

    This is the object that later feeds the evidence
    certificate and blockchain layer.
    """

    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(
        ...,
        min_length=1,
        max_length=200,
    )

    domain: Literal["agriculture"] = "agriculture"

    fraud_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )

    decision: FinalDecision

    agent_results: list[AgentResult] = Field(
        default_factory=list,
    )

    consensus: ConsensusResult | None = None

    adversarial_verification: AdversarialResult | None = None

    evidence_hash: str | None = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{64}$",
    )

    agent_hash: str | None = Field(
        default=None,
        pattern=r"^[0-9a-fA-F]{64}$",
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow,
    )


# ============================================================
# Public exports
# ============================================================

__all__ = [
    "AgentDecision",
    "FinalDecision",
    "GeoPoint",
    "FarmLocation",
    "AgricultureClaim",
    "EvidenceReference",
    "AgentResult",
    "ConsensusResult",
    "AdversarialResult",
    "VerificationResult",
]