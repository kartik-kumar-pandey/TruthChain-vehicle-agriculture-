"""
TruthChain Agriculture
Core Exceptions
================

Custom exceptions used by the agriculture verification
pipeline.

The goal is to distinguish expected pipeline failures
from programming errors. API and orchestration layers
can catch these exceptions and return structured error
responses without hiding the underlying cause.
"""

from __future__ import annotations


# ============================================================
# Base exception
# ============================================================

class AgricultureError(Exception):
    """
    Base exception for all expected Agriculture-domain errors.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "AGRICULTURE_ERROR",
    ) -> None:
        super().__init__(message)

        self.message = message
        self.code = code

    def to_dict(self) -> dict[str, str]:
        """
        Convert the exception into a safe structured response.
        """
        return {
            "code": self.code,
            "message": self.message,
        }


# ============================================================
# Claim validation
# ============================================================

class ClaimValidationError(AgricultureError):
    """
    Raised when an agriculture claim is malformed or invalid.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="CLAIM_VALIDATION_ERROR",
        )


class InvalidFieldGeometryError(AgricultureError):
    """
    Raised when the submitted field polygon is invalid.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="INVALID_FIELD_GEOMETRY",
        )


class FarmerOutsideFieldError(AgricultureError):
    """
    Raised when farmer GPS coordinates do not fall inside
    the submitted field polygon.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="FARMER_OUTSIDE_FIELD",
        )


# ============================================================
# Evidence errors
# ============================================================

class EvidenceError(AgricultureError):
    """
    Base class for evidence acquisition or validation errors.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="EVIDENCE_ERROR",
        )


class SatelliteEvidenceError(EvidenceError):
    """
    Raised when satellite evidence cannot be obtained,
    processed, or validated.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)

        self.code = "SATELLITE_EVIDENCE_ERROR"


class NoSatelliteSceneError(SatelliteEvidenceError):
    """
    Raised when no suitable Sentinel-2 observation is found.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)

        self.code = "NO_SATELLITE_SCENE"


class SatelliteAuthenticationError(SatelliteEvidenceError):
    """
    Raised when Copernicus authentication fails.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)

        self.code = "SATELLITE_AUTHENTICATION_ERROR"


class SatelliteQualityError(SatelliteEvidenceError):
    """
    Raised when the returned satellite evidence does not
    contain enough usable pixels.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)

        self.code = "SATELLITE_QUALITY_ERROR"


class WeatherEvidenceError(EvidenceError):
    """
    Raised when environmental/weather evidence cannot be
    obtained or interpreted.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)

        self.code = "WEATHER_EVIDENCE_ERROR"


class ImageEvidenceError(EvidenceError):
    """
    Raised when uploaded crop images cannot be processed.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)

        self.code = "IMAGE_EVIDENCE_ERROR"


# ============================================================
# Model errors
# ============================================================

class ModelError(AgricultureError):
    """
    Base class for machine-learning model failures.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="MODEL_ERROR",
        )


class ModelNotFoundError(ModelError):
    """
    Raised when a required trained model artifact is missing.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)

        self.code = "MODEL_NOT_FOUND"


class ModelLoadError(ModelError):
    """
    Raised when a model artifact exists but cannot be loaded.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)

        self.code = "MODEL_LOAD_ERROR"


class FeatureSchemaError(ModelError):
    """
    Raised when model input features do not match the expected
    schema.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)

        self.code = "FEATURE_SCHEMA_ERROR"


# ============================================================
# Agent errors
# ============================================================

class AgentExecutionError(AgricultureError):
    """
    Raised when an Agriculture agent cannot complete its task.
    """

    def __init__(
        self,
        agent: str,
        message: str,
    ) -> None:
        super().__init__(
            message,
            code="AGENT_EXECUTION_ERROR",
        )

        self.agent = agent

    def to_dict(self) -> dict[str, str]:
        """
        Return the standard error representation including
        the responsible agent.
        """
        return {
            "code": self.code,
            "agent": self.agent,
            "message": self.message,
        }


# ============================================================
# Consensus / verification errors
# ============================================================

class ConsensusError(AgricultureError):
    """
    Raised when risk/consensus computation cannot be completed.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="CONSENSUS_ERROR",
        )


class AdversarialVerificationError(AgricultureError):
    """
    Raised when the adversarial verification stage fails.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="ADVERSARIAL_VERIFICATION_ERROR",
        )


# ============================================================
# Proof / blockchain errors
# ============================================================

class EvidenceCertificateError(AgricultureError):
    """
    Raised when an evidence certificate cannot be constructed.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="EVIDENCE_CERTIFICATE_ERROR",
        )


class BlockchainError(AgricultureError):
    """
    Base exception for blockchain interaction errors.
    """

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            code="BLOCKCHAIN_ERROR",
        )


class BlockchainConnectionError(BlockchainError):
    """
    Raised when the blockchain RPC endpoint cannot be reached.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)

        self.code = "BLOCKCHAIN_CONNECTION_ERROR"


class BlockchainTransactionError(BlockchainError):
    """
    Raised when an evidence transaction fails.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)

        self.code = "BLOCKCHAIN_TRANSACTION_ERROR"


# ============================================================
# Utility
# ============================================================

def is_agriculture_error(error: BaseException) -> bool:
    """
    Return True when the exception belongs to the expected
    Agriculture-domain exception hierarchy.
    """
    return isinstance(error, AgricultureError)


__all__ = [
    "AgricultureError",
    "ClaimValidationError",
    "InvalidFieldGeometryError",
    "FarmerOutsideFieldError",
    "EvidenceError",
    "SatelliteEvidenceError",
    "NoSatelliteSceneError",
    "SatelliteAuthenticationError",
    "SatelliteQualityError",
    "WeatherEvidenceError",
    "ImageEvidenceError",
    "ModelError",
    "ModelNotFoundError",
    "ModelLoadError",
    "FeatureSchemaError",
    "AgentExecutionError",
    "ConsensusError",
    "AdversarialVerificationError",
    "EvidenceCertificateError",
    "BlockchainError",
    "BlockchainConnectionError",
    "BlockchainTransactionError",
    "is_agriculture_error",
]