"""
TruthChain Agriculture Domain
=============================

Standalone Agricultural Insurance / PMFBY verification domain.

This package contains the complete agriculture-specific AI pipeline:

    Claim
      ↓
    Evidence Validation
      ↓
    Satellite + Image + Sensor + Text
      ↓
    Cross-Modal Verification
      ↓
    Investigation
      ↓
    Risk / Consensus
      ↓
    Adversarial Verification
      ↓
    Evidence Certificate
      ↓
    Blockchain Proof
"""


# ============================================================
# Package metadata
# ============================================================

DOMAIN_NAME = "agriculture"

DOMAIN_VERSION = "1.0.0"

PROJECT_NAME = "TruthChain-Agri"


# ============================================================
# Supported verification domains
# ============================================================

SUPPORTED_DOMAIN = "agriculture"

INSURANCE_SCHEME = "PMFBY"


# ============================================================
# Public package information
# ============================================================

__all__ = [
    "DOMAIN_NAME",
    "DOMAIN_VERSION",
    "PROJECT_NAME",
    "SUPPORTED_DOMAIN",
    "INSURANCE_SCHEME",
]