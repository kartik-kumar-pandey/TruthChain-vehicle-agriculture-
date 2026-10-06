"""
TruthChain Agriculture - ImageAgent

Agricultural crop identification from farmer-provided
field/crop imagery.

This agent wraps the trained Agriculture CropAgent:

    DINOv2 ViT-S/14
    138 crop classes
    TruthChain-Agriculture-Crop-v0.2

IMPORTANT:

    ImageAgent provides image-based crop evidence.

    It does NOT determine whether an insurance claim
    is fraudulent.

    Final claim risk must be determined only after
    combining evidence from:

        - ImageAgent
        - SatelliteAgent
        - SensorAgent
        - TextAgent
        - CrossModalAgent
        - Investigation
        - Risk/Consensus
        - AdversarialVerifier
"""


from __future__ import annotations


import json
import time

from pathlib import Path
from typing import Any, Dict


from agriculture.image.inference import (
    CropAgent,
    CropAgentError,
)


# ============================================================
# CONSTANTS
# ============================================================


MODEL_VERSION = (
    "TruthChain-Agriculture-Crop-v0.2"
)

AGENT_VERSION = (
    "agriculture-image-agent-v0.1"
)

DOMAIN = "agriculture"


# ============================================================
# IMAGE AGENT
# ============================================================


class ImageAgent:
    """
    TruthChain Agriculture ImageAgent.

    Uses the already-trained Agriculture CropAgent to
    identify the crop visible in a farmer-provided image.

    The underlying CropAgent performs:

        image
          ↓
        RGB preprocessing
          ↓
        DINOv2 ViT-S/14
          ↓
        138-class classifier
          ↓
        crop + confidence

    This agent converts that model output into the
    standardized TruthChain agent response structure.

    IMPORTANT:

        This agent produces crop evidence only.

        A crop mismatch does NOT automatically mean
        fraud. Cross-modal verification and the later
        risk/consensus stages must evaluate the complete
        claim.
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        device: str | None = None,
    ) -> None:

        self.model_path = (
            Path(model_path)
            if model_path is not None
            else None
        )

        self.device = device

        self._crop_agent: CropAgent | None = None


    # ========================================================
    # MODEL
    # ========================================================


    def _get_crop_agent(self) -> CropAgent:
        """
        Lazily initialize the underlying CropAgent.

        The DINOv2 model is relatively expensive to load,
        therefore it should not be recreated for every
        image request.
        """

        if self._crop_agent is None:

            kwargs: Dict[str, Any] = {}

            if self.model_path is not None:
                kwargs["model_path"] = (
                    self.model_path
                )

            if self.device is not None:
                kwargs["device"] = (
                    self.device
                )

            self._crop_agent = CropAgent(
                **kwargs
            )

        return self._crop_agent


    # ========================================================
    # IMAGE ANALYSIS
    # ========================================================


    def analyze(
        self,
        image_path: str | Path,
        claimed_crop: str | None = None,
    ) -> Dict[str, Any]:
        """
        Analyze a farmer-provided agricultural image.

        Parameters
        ----------
        image_path:
            Path to the farmer-provided image.

        claimed_crop:
            Optional crop stated in the insurance claim.

            This is preserved as context only.

            The ImageAgent itself does NOT make a fraud
            decision from the claim comparison.

        Returns
        -------
        Dict[str, Any]
            Standardized TruthChain Agriculture agent result.
        """

        start_time = time.perf_counter()


        try:

            # ------------------------------------------------
            # INPUT VALIDATION
            # ------------------------------------------------

            image_path = Path(
                image_path
            )

            if not image_path.exists():

                raise FileNotFoundError(
                    f"Image file not found: "
                    f"{image_path}"
                )

            if not image_path.is_file():

                raise ValueError(
                    f"Image path is not a file: "
                    f"{image_path}"
                )


            # ------------------------------------------------
            # MODEL INFERENCE
            # ------------------------------------------------

            crop_agent = (
                self._get_crop_agent()
            )

            result = (
                crop_agent.predict_file(
                    image_path
                )
            )


            # ------------------------------------------------
            # EXTRACT MODEL RESULT
            # ------------------------------------------------

            predicted_crop = (
                result.predicted_crop
            )

            predicted_class_index = (
                result.predicted_class_index
            )

            confidence = float(
                result.confidence
            )

            probabilities = (
                result.probabilities
            )


            # ------------------------------------------------
            # IMAGE EVIDENCE UNCERTAINTY
            # ------------------------------------------------

            # This is NOT final insurance fraud risk.
            #
            # It represents uncertainty in the image
            # modality itself.

            evidence_uncertainty = (
                max(
                    0.0,
                    min(
                        1.0,
                        1.0 - confidence,
                    ),
                )
            )


            # ------------------------------------------------
            # OPTIONAL CLAIM CONTEXT
            # ------------------------------------------------

            claim_match = None

            if claimed_crop:

                claim_match = (
                    self._basic_crop_match(
                        claimed_crop,
                        predicted_crop,
                    )
                )


            # ------------------------------------------------
            # EVIDENCE
            # ------------------------------------------------

            evidence = [
                (
                    "Image model predicted crop "
                    f"'{predicted_crop}' with "
                    f"{confidence:.4f} confidence."
                )
            ]


            if claimed_crop:

                if claim_match:

                    evidence.append(
                        (
                            "The image prediction is "
                            "compatible with the claimed "
                            f"crop '{claimed_crop}'."
                        )
                    )

                else:

                    evidence.append(
                        (
                            "The image prediction differs "
                            "from the raw claimed crop "
                            f"label '{claimed_crop}'. "
                            "This requires cross-modal "
                            "verification."
                        )
                    )


            # ------------------------------------------------
            # PROCESSING TIME
            # ------------------------------------------------

            processing_time_ms = int(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000
            )


            # ------------------------------------------------
            # STANDARD TRUTHCHAIN RESPONSE
            # ------------------------------------------------

            return {

                "agent": "ImageAgent",

                "domain": DOMAIN,

                # Image-model confidence.
                #
                # NOT fraud confidence.
                "confidence": round(
                    confidence,
                    4,
                ),

                # Image evidence uncertainty.
                #
                # NOT final fraud risk.
                "risk_score": round(
                    evidence_uncertainty,
                    4,
                ),

                # Successful image evidence extraction.
                #
                # This does NOT mean that the insurance
                # claim itself is genuine.
                "decision": "PASS",

                "evidence": evidence,

                "contradictions": [],

                "model_version": (
                    MODEL_VERSION
                ),

                "processing_time_ms": (
                    processing_time_ms
                ),

                # ------------------------------------------------
                # Agriculture-specific evidence
                # ------------------------------------------------

                "predicted_crop": (
                    predicted_crop
                ),

                "predicted_class_index": (
                    predicted_class_index
                ),

                "image_confidence": round(
                    confidence,
                    6,
                ),

                "evidence_uncertainty": round(
                    evidence_uncertainty,
                    6,
                ),

                "claimed_crop": (
                    claimed_crop
                ),

                "claim_crop_match": (
                    claim_match
                ),

                "probabilities": {
                    crop: round(
                        float(probability),
                        6,
                    )
                    for crop, probability
                    in probabilities.items()
                },

                "input_image": str(
                    image_path
                ),

                "agent_version": (
                    AGENT_VERSION
                ),
            }


        except (
            FileNotFoundError,
            ValueError,
            CropAgentError,
        ) as exc:

            processing_time_ms = int(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000
            )


            return {

                "agent": "ImageAgent",

                "domain": DOMAIN,

                "confidence": 0.0,

                "risk_score": 0.0,

                "decision": "ERROR",

                "evidence": [
                    (
                        "Agriculture image analysis "
                        f"failed: {str(exc)}"
                    )
                ],

                "contradictions": [],

                "model_version": (
                    MODEL_VERSION
                ),

                "processing_time_ms": (
                    processing_time_ms
                ),

                "predicted_crop": None,

                "predicted_class_index": None,

                "image_confidence": 0.0,

                "evidence_uncertainty": 1.0,

                "claimed_crop": (
                    claimed_crop
                ),

                "claim_crop_match": None,

                "probabilities": {},

                "input_image": str(
                    image_path
                ),

                "agent_version": (
                    AGENT_VERSION
                ),

                "error_type": (
                    type(exc).__name__
                ),

                "error": str(exc),
            }


        except Exception as exc:

            processing_time_ms = int(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000
            )


            return {

                "agent": "ImageAgent",

                "domain": DOMAIN,

                "confidence": 0.0,

                "risk_score": 0.0,

                "decision": "ERROR",

                "evidence": [
                    (
                        "Unexpected Agriculture "
                        "image-agent error: "
                        f"{str(exc)}"
                    )
                ],

                "contradictions": [],

                "model_version": (
                    MODEL_VERSION
                ),

                "processing_time_ms": (
                    processing_time_ms
                ),

                "predicted_crop": None,

                "predicted_class_index": None,

                "image_confidence": 0.0,

                "evidence_uncertainty": 1.0,

                "claimed_crop": (
                    claimed_crop
                ),

                "claim_crop_match": None,

                "probabilities": {},

                "input_image": str(
                    image_path
                ),

                "agent_version": (
                    AGENT_VERSION
                ),

                "error_type": (
                    type(exc).__name__
                ),

                "error": str(exc),
            }


    # ========================================================
    # BASIC CROP MATCH
    # ========================================================


    @staticmethod
    def _basic_crop_match(
        claimed_crop: str,
        predicted_crop: str,
    ) -> bool:
        """
        Perform a conservative raw-label comparison.

        IMPORTANT:

            This is intentionally NOT the final crop
            normalization logic.

        The full Agriculture CrossModalAgent will later
        handle equivalences such as:

            Mustard
            Rapeseed
            Rapeseed (Canola) plant

        mapping to the same canonical crop group.
        """

        claimed = (
            str(
                claimed_crop
            )
            .strip()
            .lower()
        )

        predicted = (
            str(
                predicted_crop
            )
            .strip()
            .lower()
        )

        if not claimed or not predicted:
            return False

        if claimed == predicted:
            return True

        # Simple known Agriculture equivalences.
        #
        # Full normalization belongs to CrossModal.

        mustard_group = {
            "mustard",
            "rapeseed",
            "canola",
            "rapeseed plant",
            "rapeseed (canola) plant",
        }

        sugarcane_group = {
            "sugarcane",
            "sugar cane",
            "sugar cane plant",
        }

        if (
            claimed in mustard_group
            and predicted in mustard_group
        ):
            return True

        if (
            claimed in sugarcane_group
            and predicted in sugarcane_group
        ):
            return True

        return False


# ============================================================
# SINGLETON
# ============================================================


_image_agent: ImageAgent | None = None


def get_image_agent() -> ImageAgent:
    """
    Lazily initialize the Agriculture ImageAgent.

    This prevents the DINOv2 CropAgent from being loaded
    repeatedly by the API.
    """

    global _image_agent

    if _image_agent is None:

        _image_agent = ImageAgent()

    return _image_agent


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================


def analyze_image(
    image_path: str | Path,
    claimed_crop: str | None = None,
) -> Dict[str, Any]:
    """
    Convenience function for API and graph nodes.
    """

    agent = get_image_agent()

    return agent.analyze(
        image_path=image_path,
        claimed_crop=claimed_crop,
    )


# ============================================================
# LOCAL TEST
# ============================================================


if __name__ == "__main__":

    import sys


    print("=" * 70)
    print("TRUTHCHAIN AGRICULTURE IMAGE AGENT TEST")
    print("=" * 70)


    if len(sys.argv) < 2:

        print()

        print("Usage:")

        print(
            'python -m agents.image_agent '
            '"path/to/field_image.webp"'
        )

        print()

        print("Optional claimed crop:")

        print(
            'python -m agents.image_agent '
            '"path/to/field_image.webp" '
            '"Mustard"'
        )

        print()

        sys.exit(1)


    image_path = sys.argv[1]

    claimed_crop = (
        sys.argv[2]
        if len(sys.argv) >= 3
        else None
    )


    print(
        f"Image: {image_path}"
    )

    if claimed_crop:

        print(
            f"Claimed crop: {claimed_crop}"
        )


    print()

    agent = get_image_agent()

    print(
        f"Device: {agent._get_crop_agent().device}"
    )

    print(
        f"Model version: {MODEL_VERSION}"
    )

    print(
        f"Agent version: {AGENT_VERSION}"
    )

    print()


    result = agent.analyze(
        image_path=image_path,
        claimed_crop=claimed_crop,
    )


    print("=" * 70)
    print("AGRICULTURE IMAGE AGENT RESULT")
    print("=" * 70)


    print(
        json.dumps(
            result,
            indent=2,
        )
    )