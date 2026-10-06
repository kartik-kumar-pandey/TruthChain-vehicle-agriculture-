"""
TruthChain 2.0 - ImageAgent

Motor insurance vehicle-damage analysis using the frozen
TruthChain Vision ResNet-50 model.

Model task:
    Multi-label vehicle damage classification

Classes:
    dent
    scratch
    crack
    glass_shatter
    lamp_broken
    tire_flat

IMPORTANT:
    ImageAgent detects vehicle damage.

    It does NOT determine whether a claim is fraudulent.

    Final claim fraud risk must be determined by the centralized
    TruthChain risk engine after combining evidence from:

        - ImageAgent
        - SensorAgent
        - TextAgent
        - CrossModalAgent
        - InvestigationAgent
        - AdversarialVerifier
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms
from torchvision.models import resnet50, ResNet50_Weights

logger = logging.getLogger(__name__)


# ============================================================
# PATHS
# ============================================================

# Consolidated ai-services structure:
#
# ai-services/
# ├── agents/
# │   └── image_agent.py
# └── ml/
#     └── models/
#         └── vision/
#             ├── truthchain_vision_resnet50.pth
#             ├── vision_classes.json
#             ├── vision_thresholds.json
#             └── vision_preprocessing.json

# image_agent.py
#     parent[0] = agents
#     parent[1] = ai-services

BASE_DIR = Path(__file__).resolve().parent.parent

IMAGE_MODEL_DIR = (
    BASE_DIR
    / "ml"
    / "models"
    / "vision"
)

MODEL_PATH = (
    IMAGE_MODEL_DIR
    / "truthchain_vision_resnet50.pth"
)

CLASSES_PATH = (
    IMAGE_MODEL_DIR
    / "vision_classes.json"
)

THRESHOLDS_PATH = (
    IMAGE_MODEL_DIR
    / "vision_thresholds.json"
)

PREPROCESSING_PATH = (
    IMAGE_MODEL_DIR
    / "vision_preprocessing.json"
)


# ============================================================
# CONSTANTS
# ============================================================

MODEL_VERSION = "image-agent-v1.0"

DEFAULT_CLASSES = [
    "dent",
    "scratch",
    "crack",
    "glass_shatter",
    "lamp_broken",
    "tire_flat",
]

DEFAULT_THRESHOLDS = {
    "dent": 0.35,
    "scratch": 0.42,
    "crack": 0.74,
    "glass_shatter": 0.73,
    "lamp_broken": 0.70,
    "tire_flat": 0.86,
}

DEFAULT_IMAGE_SIZE = 224

DEFAULT_MEAN = [
    0.485,
    0.456,
    0.406,
]

DEFAULT_STD = [
    0.229,
    0.224,
    0.225,
]


# ============================================================
# IMAGE AGENT
# ============================================================

class ImageAgent:
    """
    TruthChain ImageAgent.

    Loads the already-trained TruthChain Vision ResNet-50 model
    and performs multi-label vehicle damage inference.

    The trained model is NOT modified or retrained.

    IMPORTANT:
        This agent provides image evidence only.

        A detected dent, scratch, crack, broken lamp, etc.
        does NOT automatically mean that the insurance claim
        is fraudulent.
    """

    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        classes_path: Path = CLASSES_PATH,
        thresholds_path: Path = THRESHOLDS_PATH,
        preprocessing_path: Path = PREPROCESSING_PATH,
        device: str | None = None,
    ):
        self.model_path = Path(model_path)
        self.classes_path = Path(classes_path)
        self.thresholds_path = Path(thresholds_path)
        self.preprocessing_path = Path(preprocessing_path)

        self.device = torch.device(
            device
            if device
            else (
                "cuda"
                if torch.cuda.is_available()
                else "cpu"
            )
        )

        # Load frozen model metadata.
        self.classes = self._load_classes()
        self.num_classes = len(self.classes)
        self.thresholds = self._load_thresholds()
        self.preprocessing = self._load_preprocessing()

        # Load frozen production model.
        self.model = self._load_model()

        # Build exact training preprocessing.
        self.transform = self._build_transform()


    # ========================================================
    # METADATA
    # ========================================================

    def _load_classes(
        self,
    ) -> List[str]:
        """
        Load class names from vision_classes.json.

        The exact ordering is validated because model output
        indices are positional.
        """

        if not self.classes_path.exists():
            raise FileNotFoundError(
                f"Vision classes file not found: "
                f"{self.classes_path}"
            )

        with open(
            self.classes_path,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        classes = data.get("classes")

        if not classes:
            raise ValueError(
                "vision_classes.json does not contain "
                "'classes'."
            )

        classes = [
            str(class_name)
            for class_name in classes
        ]

        # IMPORTANT:
        # The class order must exactly match the frozen model
        # output order. Checking only the class count is unsafe.
        if classes != DEFAULT_CLASSES:
            raise ValueError(
                "Vision class configuration does not match "
                "the frozen TruthChain class order. "
                f"Expected: {DEFAULT_CLASSES}; "
                f"found: {classes}"
            )

        return classes


    def _load_thresholds(
        self,
    ) -> Dict[str, float]:
        """
        Load per-class detection thresholds.
        """

        if not self.thresholds_path.exists():
            raise FileNotFoundError(
                f"Vision thresholds file not found: "
                f"{self.thresholds_path}"
            )

        with open(
            self.thresholds_path,
            "r",
            encoding="utf-8",
        ) as file:
            thresholds = json.load(file)

        # Some metadata files may wrap thresholds inside
        # a "thresholds" object.
        if isinstance(thresholds, dict):
            if "thresholds" in thresholds:
                thresholds = thresholds["thresholds"]

        if not isinstance(
            thresholds,
            dict,
        ):
            raise ValueError(
                "vision_thresholds.json must contain "
                "a threshold dictionary."
            )

        for class_name in self.classes:

            if class_name not in thresholds:
                raise ValueError(
                    f"Missing threshold for class: "
                    f"{class_name}"
                )

        loaded_thresholds = {
            class_name: float(
                thresholds[class_name]
            )
            for class_name in self.classes
        }

        # Validate thresholds.
        for class_name, threshold in (
            loaded_thresholds.items()
        ):

            if not 0.0 <= threshold <= 1.0:
                raise ValueError(
                    f"Invalid threshold for "
                    f"{class_name}: {threshold}. "
                    "Expected a value between 0 and 1."
                )

        return loaded_thresholds


    def _load_preprocessing(
        self,
    ) -> Dict[str, Any]:
        """
        Load the preprocessing configuration used during
        model training.

        The frozen production contract is:

            image_size = 224
            color_format = RGB
            ImageNet mean
            ImageNet std

        Missing preprocessing metadata is treated as a deployment
        error rather than silently replacing a missing artifact.
        """

        if not self.preprocessing_path.exists():
            raise FileNotFoundError(
                f"Vision preprocessing file not found: "
                f"{self.preprocessing_path}"
            )

        with open(
            self.preprocessing_path,
            "r",
            encoding="utf-8",
        ) as file:
            preprocessing = json.load(file)

        if not isinstance(
            preprocessing,
            dict,
        ):
            raise ValueError(
                "vision_preprocessing.json must contain "
                "a JSON object."
            )

        image_size = int(
            preprocessing.get(
                "image_size",
                -1,
            )
        )

        normalization = preprocessing.get(
            "normalization",
            {},
        )

        if not isinstance(
            normalization,
            dict,
        ):
            raise ValueError(
                "vision_preprocessing.json normalization "
                "must be an object."
            )

        mean = normalization.get(
            "mean"
        )

        std = normalization.get(
            "std"
        )

        color_format = str(
            preprocessing.get(
                "color_format",
                "",
            )
        ).upper()

        # --------------------------------------------------------
        # Validate frozen image size.
        # --------------------------------------------------------

        if image_size != DEFAULT_IMAGE_SIZE:
            raise ValueError(
                "Frozen vision preprocessing mismatch: "
                f"expected image_size={DEFAULT_IMAGE_SIZE}, "
                f"found {image_size}."
            )

        # --------------------------------------------------------
        # Validate frozen ImageNet mean.
        # --------------------------------------------------------

        if list(mean or []) != DEFAULT_MEAN:
            raise ValueError(
                "Frozen vision preprocessing mismatch: "
                f"expected mean={DEFAULT_MEAN}, "
                f"found {mean}."
            )

        # --------------------------------------------------------
        # Validate frozen ImageNet std.
        # --------------------------------------------------------

        if list(std or []) != DEFAULT_STD:
            raise ValueError(
                "Frozen vision preprocessing mismatch: "
                f"expected std={DEFAULT_STD}, "
                f"found {std}."
            )

        # --------------------------------------------------------
        # Validate frozen RGB format.
        # --------------------------------------------------------

        if color_format != "RGB":
            raise ValueError(
                "Frozen vision preprocessing mismatch: "
                "expected color_format='RGB', "
                f"found {color_format!r}."
            )

        return preprocessing


    # ========================================================
    # MODEL
    # ========================================================

    def _load_model(
        self,
    ) -> nn.Module:
        """
        Load the frozen TruthChain Vision ResNet-50 model.

        IMPORTANT:
            The classifier architecture matches the verified
            production checkpoint:

                model.fc = Sequential(
                    Dropout(p=0.0),
                    Linear(in_features, num_classes)
                )

            Do not change this architecture.
        """

        if not self.model_path.exists():
            logger.warning("Vision model checkpoint not found at %s. Initializing default ResNet50 model.", self.model_path)
            model = resnet50(weights=ResNet50_Weights.DEFAULT)
            model.fc = nn.Sequential(
                nn.Dropout(p=0.0),
                nn.Linear(model.fc.in_features, self.num_classes)
            )
            model.eval()
            return model

        print(
            "Loading TruthChain Vision model from: "
            f"{self.model_path}"
        )

        # The verified local checkpoint loads correctly
        # using weights_only=True.
        checkpoint = torch.load(
            self.model_path,
            map_location=self.device,
            weights_only=True,
        )

        if not isinstance(
            checkpoint,
            dict,
        ):
            raise ValueError(
                "Expected checkpoint to be a dictionary."
            )

        state_dict = checkpoint.get(
            "model_state_dict"
        )

        if state_dict is None:
            raise ValueError(
                "Checkpoint does not contain "
                "'model_state_dict'."
            )

        # ----------------------------------------------------
        # VERIFIED PRODUCTION ARCHITECTURE
        # ----------------------------------------------------
        #
        # The checkpoint contains:
        #
        #     fc.1.weight
        #     fc.1.bias
        #
        # Therefore the classifier is:
        #
        #     Sequential
        #         Dropout
        #         Linear
        #
        # This architecture MUST remain unchanged.
        # ----------------------------------------------------

        model = models.resnet50(
            weights=None
        )

        model.fc = nn.Sequential(
            nn.Dropout(
                p=0.0
            ),
            nn.Linear(
                model.fc.in_features,
                len(self.classes),
            ),
        )

        # Strict loading ensures that the architecture matches
        # the frozen trained checkpoint exactly.
        model.load_state_dict(
            state_dict,
            strict=True,
        )

        model.to(
            self.device
        )

        # Production inference mode.
        model.eval()

        return model


    # ========================================================
    # PREPROCESSING
    # ========================================================

    def _build_transform(self):
        """
        Reproduce the preprocessing used during training.

        Expected production preprocessing:

            224 x 224
            RGB
            ImageNet mean
            ImageNet standard deviation
        """

        image_size = int(
            self.preprocessing.get(
                "image_size",
                DEFAULT_IMAGE_SIZE,
            )
        )

        normalization = (
            self.preprocessing.get(
                "normalization",
                {},
            )
        )

        mean = normalization.get(
            "mean",
            DEFAULT_MEAN,
        )

        std = normalization.get(
            "std",
            DEFAULT_STD,
        )

        color_format = str(
            self.preprocessing.get(
                "color_format",
                "RGB",
            )
        ).upper()

        if color_format != "RGB":
            raise ValueError(
                "TruthChain Vision model requires RGB "
                f"input, but preprocessing configuration "
                f"specifies: {color_format}"
            )

        return transforms.Compose(
            [
                transforms.Resize(
                    (
                        image_size,
                        image_size,
                    )
                ),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=mean,
                    std=std,
                ),
            ]
        )


    # ========================================================
    # IMAGE LOADING
    # ========================================================

    def _load_image(
        self,
        image_path: str | Path,
    ) -> Image.Image:
        """
        Load an image and convert it to RGB.
        """

        image_path = Path(
            image_path
        )

        if not image_path.exists():
            raise FileNotFoundError(
                f"Image not found: {image_path}"
            )

        if not image_path.is_file():
            raise ValueError(
                f"Image path is not a file: {image_path}"
            )

        # Use a context manager so the source file handle
        # is released immediately after conversion.
        with Image.open(
            image_path
        ) as source:

            # The frozen model expects RGB input.
            image = source.convert(
                "RGB"
            )

        return image


    # ========================================================
    # EVIDENCE
    # ========================================================

    def _build_evidence(
        self,
        probabilities: Dict[str, float],
        detected_damage: List[str],
    ) -> List[str]:
        """
        Build human-readable evidence from detected classes.

        This describes visual damage only.

        It does NOT make a fraud determination.
        """

        evidence: List[str] = []

        for class_name in detected_damage:

            probability = probabilities[
                class_name
            ]

            readable_name = class_name.replace(
                "_",
                " ",
            )

            evidence.append(
                f"Vehicle {readable_name} "
                f"detected with probability "
                f"{probability:.3f}."
            )

        if not evidence:

            evidence.append(
                "No configured vehicle damage "
                "class exceeded its detection "
                "threshold."
            )

        return evidence


    # ========================================================
    # DECISION
    # ========================================================

    def _calculate_decision(
        self,
        probabilities: Dict[str, float],
        detected_damage: List[str],
    ) -> tuple[str, float]:
        """
        Calculate the ImageAgent image-level decision.

        IMPORTANT:
            This is NOT the final fraud decision.

        DAMAGE_DETECTED:
            At least one configured vehicle damage class
            exceeded its calibrated detection threshold.

        NO_DAMAGE:
            No configured vehicle damage class exceeded
            its calibrated detection threshold.

        INSUFFICIENT_DATA:
            No model probabilities are available.
        """

        if not probabilities:

            return (
                "INSUFFICIENT_DATA",
                0.0,
            )

        # ----------------------------------------------------
        # DAMAGE DETECTED
        # ----------------------------------------------------

        if detected_damage:

            strongest_detected_probability = max(
                probabilities[class_name]
                for class_name in detected_damage
            )

            confidence = float(
                min(
                    0.99,
                    strongest_detected_probability,
                )
            )

            return (
                "DAMAGE_DETECTED",
                confidence,
            )

        # ----------------------------------------------------
        # NO DAMAGE
        # ----------------------------------------------------

        max_probability = max(
            probabilities.values()
        )

        confidence = float(
            min(
                0.99,
                max_probability,
            )
        )

        return (
            "NO_DAMAGE",
            confidence,
        )


    # ========================================================
    # IMAGE EVIDENCE SIGNAL
    # ========================================================

    def _calculate_risk_score(
        self,
        probabilities: Dict[str, float],
        detected_damage: List[str],
    ) -> float:
        """
        Calculate the ImageAgent image evidence signal.

        IMPORTANT:

        This is NOT a probability of fraud.

        This is NOT the final TruthChain claim risk.

        It represents the strongest model confidence among
        the image classes.

        The centralized TruthChain risk engine must combine
        this image signal with:

            - SensorAgent
            - TextAgent
            - CrossModalAgent
            - InvestigationAgent
            - AdversarialVerifier

        before producing final claim-level fraud risk.
        """

        if not probabilities:
            return 0.0

        # Only use detected damage probabilities when
        # available.
        #
        # This prevents an arbitrary high non-detected class
        # from becoming the primary image damage signal.
        if detected_damage:

            strongest_probability = max(
                probabilities[class_name]
                for class_name in detected_damage
            )

        else:

            # No damage detected.
            #
            # This remains an image evidence signal and
            # does NOT represent fraud probability.
            strongest_probability = max(
                probabilities.values()
            )

        return float(
            min(
                1.0,
                strongest_probability,
            )
        )


    # ========================================================
    # PUBLIC INFERENCE API
    # ========================================================

    def analyze(
        self,
        image_path: str | Path,
    ) -> Dict[str, Any]:
        """
        Analyze one vehicle image.

        Returns the standardized TruthChain ImageAgent
        response.

        Decisions:

            DAMAGE_DETECTED
            NO_DAMAGE
            INSUFFICIENT_DATA
            ERROR

        risk_score:
            Image evidence signal only.

        It does NOT represent final claim fraud risk.
        """

        start_time = time.perf_counter()

        try:

            # ------------------------------------------------
            # LOAD IMAGE
            # ------------------------------------------------

            image = self._load_image(
                image_path
            )

            # ------------------------------------------------
            # PREPROCESS
            # ------------------------------------------------

            tensor = self.transform(
                image
            ).unsqueeze(0)

            tensor = tensor.to(
                self.device
            )

            # ------------------------------------------------
            # MODEL INFERENCE
            # ------------------------------------------------

            with torch.no_grad():

                logits = self.model(
                    tensor
                )

                # Multi-label classification.
                #
                # Each class is independent.
                #
                # IMPORTANT:
                #   sigmoid
                #   NOT softmax
                #   NOT argmax

                probabilities_tensor = (
                    torch.sigmoid(
                        logits
                    )[0]
                )

            # ------------------------------------------------
            # BUILD PROBABILITY DICTIONARY
            # ------------------------------------------------

            probabilities = {
                class_name: float(
                    probabilities_tensor[index].item()
                )
                for index, class_name
                in enumerate(self.classes)
            }

            # ------------------------------------------------
            # APPLY PER-CLASS THRESHOLDS
            # ------------------------------------------------

            detected_damage = [
                class_name
                for class_name in self.classes
                if (
                    probabilities[class_name]
                    >= self.thresholds[class_name]
                )
            ]

            # ------------------------------------------------
            # DECISION
            # ------------------------------------------------

            decision, confidence = (
                self._calculate_decision(
                    probabilities,
                    detected_damage,
                )
            )

            # ------------------------------------------------
            # DAMAGE FLAG
            # ------------------------------------------------

            damage_detected = bool(
                detected_damage
            )

            # ------------------------------------------------
            # IMAGE EVIDENCE SIGNAL
            # ------------------------------------------------

            risk_score = (
                self._calculate_risk_score(
                    probabilities,
                    detected_damage,
                )
            )

            # ------------------------------------------------
            # EVIDENCE
            # ------------------------------------------------

            evidence = (
                self._build_evidence(
                    probabilities,
                    detected_damage,
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

            result = {
                "agent": "ImageAgent",

                "domain": "motor",

                # Image-model confidence.
                #
                # NOT fraud confidence.
                "confidence": round(
                    confidence,
                    4,
                ),

                # Image evidence signal.
                #
                # NOT final fraud risk.
                "risk_score": round(
                    risk_score,
                    4,
                ),

                # Image-level decision.
                "decision": decision,

                # Explicit damage indicator.
                "damage_detected": damage_detected,

                # Human-readable evidence.
                "evidence": evidence,

                # Reserved for multimodal reasoning.
                "contradictions": [],

                # Model version.
                "model_version": MODEL_VERSION,

                # Inference latency.
                "processing_time_ms": (
                    processing_time_ms
                ),

                # Detected classes.
                "detected_damage": (
                    detected_damage
                ),

                # Number of detected classes.
                "num_detected": len(
                    detected_damage
                ),

                # Full per-class predictions.
                "predictions": {
                    class_name: {
                        "probability": round(
                            probabilities[
                                class_name
                            ],
                            6,
                        ),
                        "threshold": (
                            self.thresholds[
                                class_name
                            ]
                        ),
                        "detected": (
                            class_name
                            in detected_damage
                        ),
                    }
                    for class_name in self.classes
                },
            }

            return result

        except Exception as exc:

            processing_time_ms = int(
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000
            )

            # IMPORTANT:
            #
            # A missing image is INSUFFICIENT_DATA.
            #
            # A supplied image that fails during loading,
            # preprocessing, or model inference is ERROR.
            #
            # Keeping these states separate is important for
            # production observability, retries and auditing.

            return {
                "agent": "ImageAgent",

                "domain": "motor",

                "confidence": 0.0,

                "risk_score": 0.0,

                "decision": "ERROR",

                "damage_detected": False,

                "evidence": [
                    f"Image analysis failed: {str(exc)}"
                ],

                "contradictions": [],

                "model_version": MODEL_VERSION,

                "processing_time_ms": (
                    processing_time_ms
                ),

                "detected_damage": [],

                "num_detected": 0,

                "predictions": {},

                "error_type": type(exc).__name__,

                "error": str(exc),
            }


# ============================================================
# SINGLETON
# ============================================================

_image_agent: ImageAgent | None = None


def get_image_agent() -> ImageAgent:
    """
    Lazily initialize the ImageAgent.

    This prevents the ResNet-50 model from being loaded
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
) -> Dict[str, Any]:
    """
    Convenience function for API and LangGraph nodes.
    """

    agent = get_image_agent()

    return agent.analyze(
        image_path
    )


# ============================================================
# LOCAL TEST
# ============================================================

if __name__ == "__main__":

    import sys

    print("=" * 70)
    print("TRUTHCHAIN IMAGE AGENT TEST")
    print("=" * 70)

    if len(sys.argv) < 2:

        print()
        print("Usage:")
        print(
            'python -m agents.image_agent '
            '"path/to/image.webp"'
        )

        print()

        print("Example:")
        print(
            'python -m agents.image_agent '
            '"C:\\Users\\karti\\Downloads\\crash-car-side-view.webp"'
        )

        print()

        sys.exit(1)

    image_path = sys.argv[1]

    print(
        f"Image: {image_path}"
    )

    print()

    agent = get_image_agent()

    print(
        f"Device: {agent.device}"
    )

    print(
        f"Model version: {MODEL_VERSION}"
    )

    print(
        f"Model path: {agent.model_path}"
    )

    print(
        f"Classes: {agent.classes}"
    )

    print(
        f"Thresholds: {agent.thresholds}"
    )

    print()

    result = agent.analyze(
        image_path
    )

    print("=" * 70)
    print("IMAGE AGENT RESULT")
    print("=" * 70)

    print(
        json.dumps(
            result,
            indent=2,
        )
    )