
"""
TruthChain Vision — Inference Module
=====================================
Loads the pre-trained ResNet-50 multi-label vehicle damage classification
model and exposes a single clean inference function.

DO NOT modify the model architecture or weights.
DO NOT use argmax or a global 0.5 threshold.
This is a MULTI-LABEL model; each class is thresholded independently.

Usage
-----
    from vision.inference import predict_vehicle_damage

    result = predict_vehicle_damage("/path/to/car.jpg")
    # or: predict_vehicle_damage(pil_image)
    # or: predict_vehicle_damage(numpy_array)
"""

from __future__ import annotations

import io
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import numpy as np
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image, UnidentifiedImageError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths — model artifacts live in models/vision/ relative to project root.
# This file is at  <project_root>/src/vision/inference.py
# ---------------------------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()
_PROJECT_ROOT = _THIS_FILE.parent.parent.parent          # src/vision/../../  → project root

# Flexible path resolution for local dev & cloud container deployments
_ENV_MODELS = os.getenv("MODELS_DIR")
if _ENV_MODELS and Path(_ENV_MODELS).exists():
    _MODELS_DIR = Path(_ENV_MODELS)
elif (_PROJECT_ROOT / "models" / "vision").exists():
    _MODELS_DIR = _PROJECT_ROOT / "models" / "vision"
elif (Path.cwd() / "models" / "vision").exists():
    _MODELS_DIR = Path.cwd() / "models" / "vision"
else:
    _MODELS_DIR = _PROJECT_ROOT / "models" / "vision"

_WEIGHTS_PATH    = _MODELS_DIR / "truthchain_vision_resnet50.pth"
_CLASSES_PATH    = _MODELS_DIR / "vision_classes.json"
_THRESHOLDS_PATH = _MODELS_DIR / "vision_thresholds.json"
_PREPROC_PATH    = _MODELS_DIR / "vision_preprocessing.json"
_MANIFEST_PATH   = _MODELS_DIR / "MANIFEST.json"



# ---------------------------------------------------------------------------
# VisionModel
# ---------------------------------------------------------------------------

class VisionModel:
    """
    Wraps the trained TruthChain ResNet-50 multi-label classifier.

    - Loads architecture + weights exactly once at construction time.
    - Never trains during inference (model.eval() is set and maintained).
    - Uses per-class thresholds from vision_thresholds.json (NOT 0.5).
    - Supports CUDA (preferred) and CPU.
    """

    def __init__(self) -> None:
        # ── 1. Load config files ────────────────────────────────────────────
        with open(_CLASSES_PATH) as f:
            classes_cfg = json.load(f)
        with open(_THRESHOLDS_PATH) as f:
            thresholds_cfg = json.load(f)
        with open(_PREPROC_PATH) as f:
            preproc_cfg = json.load(f)

        self.classes: List[str] = list(classes_cfg["classes"])        # exact order from ZIP
        self.num_classes: int = int(classes_cfg["num_classes"])       # 6
        self.thresholds: Dict[str, float] = dict(thresholds_cfg)      # per-class thresholds

        # ── 2. Preprocessing parameters (from vision_preprocessing.json) ────
        image_size: int = preproc_cfg["image_size"]              # 224
        mean: list[float] = preproc_cfg["normalization"]["mean"] # [0.485, 0.456, 0.406]
        std: list[float]  = preproc_cfg["normalization"]["std"]  # [0.229, 0.224, 0.225]
        # color_format is RGB — PIL default; ensured in predict()

        # Deterministic inference transform — exactly matches training preprocessing.
        # Training used: Resize(256) → CenterCrop(224) → ToTensor → Normalize(ImageNet)
        self._transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(image_size),
            transforms.ToTensor(),
            transforms.Normalize(mean=mean, std=std),
        ])

        # ── 3. Device ────────────────────────────────────────────────────────
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("TruthChain Vision: using device=%s", self.device)

        # ── 4. Load checkpoint to discover architecture before building ──────
        #   The checkpoint is a training dict containing 'model_state_dict'.
        #   We inspect the fc keys to reconstruct the head identically.
        if not _WEIGHTS_PATH.exists():
            raise FileNotFoundError(
                f"Vision model weights not found at: {_WEIGHTS_PATH}\n"
                "Ensure the ZIP has been extracted to models/vision/."
            )

        checkpoint = torch.load(_WEIGHTS_PATH, map_location=self.device, weights_only=True)

        # Extract the actual state_dict — checkpoint is a training wrapper dict.
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
        elif isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
        else:
            # Raw state_dict saved directly
            state_dict = checkpoint

        # ── 5. Build architecture to match the saved state_dict ──────────
        #   Inspect fc keys to determine the exact head used during training.
        #   fc.1.weight / fc.1.bias  →  fc = Sequential(Dropout, Linear)
        #   fc.weight   / fc.bias    →  fc = Linear
        fc_keys = [k for k in state_dict.keys() if k.startswith("fc")]
        has_sequential_fc = any(k.startswith("fc.1.") for k in fc_keys)

        self._model = models.resnet50(weights=None)              # no pretrained ImageNet weights
        in_features: int = getattr(self._model.fc, "in_features", 2048)

        if has_sequential_fc:
            # Training used: nn.Sequential(nn.Dropout(p), nn.Linear(2048, num_classes))
            # fc.0 = Dropout (no params), fc.1 = Linear
            self._model.fc = nn.Sequential(
                nn.Dropout(p=0.5),
                nn.Linear(in_features, self.num_classes),
            )
        else:
            # Training used a bare nn.Linear
            self._model.fc = nn.Linear(in_features, self.num_classes)

        self._model.load_state_dict(state_dict)
        self._model.to(self.device)

        # ── 6. Set eval mode — NEVER train during inference ──────────────
        self._model.eval()
        logger.info(
            "TruthChain Vision model loaded. classes=%s thresholds=%s",
            self.classes, self.thresholds,
        )

    # -----------------------------------------------------------------------
    # Public predict method
    # -----------------------------------------------------------------------

    def predict(
        self,
        image: Union[str, Path, Image.Image, np.ndarray, bytes],
    ) -> Dict[str, Any]:
        """
        Run multi-label damage classification on a single vehicle image.

        Parameters
        ----------
        image : str | Path | PIL.Image.Image | np.ndarray | bytes
            Accepts a file path, PIL Image, NumPy array (H×W×C, uint8 RGB),
            or raw image bytes.

        Returns
        -------
        dict with keys:
            probabilities     – {class_name: float} all six sigmoid outputs
            thresholds        – {class_name: float} per-class thresholds
            detected_damages  – list of {type, probability, threshold}
                                only for classes where prob >= threshold
            model_version     – str
            device            – str ("cuda" or "cpu")

        Raises
        ------
        ValueError  – if image cannot be decoded / is not a valid image
        """
        pil_image = self._load_to_pil(image)

        # Preprocess → tensor
        tensor = self._transform(pil_image)          # shape: [3, 224, 224]
        tensor = tensor.unsqueeze(0).to(self.device)  # shape: [1, 3, 224, 224]

        # Forward pass — no gradients, no training
        with torch.no_grad():
            logits = self._model(tensor)             # shape: [1, 6]

        # sigmoid → probabilities (multi-label, NOT softmax)
        probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()  # shape: [6,]

        # Validate output shape
        assert probs.shape == (self.num_classes,), (
            f"Unexpected output shape: {probs.shape}. Expected ({self.num_classes},)."
        )

        # Build probability dict preserving class order from ZIP
        probabilities: Dict[str, float] = {
            cls: float(probs[i]) for i, cls in enumerate(self.classes)
        }

        # Apply per-class thresholds independently (multi-label)
        detected_damages: List[Dict[str, Any]] = []
        for cls in self.classes:
            prob = probabilities[cls]
            thr  = self.thresholds[cls]
            if prob >= thr:                          # NOT >= 0.5 globally
                detected_damages.append({
                    "type": cls,
                    "probability": round(prob, 6),
                    "threshold": thr,
                })

        return {
            "probabilities": {k: round(v, 6) for k, v in probabilities.items()},
            "thresholds": dict(self.thresholds),
            "detected_damages": detected_damages,
            "model_version": "TruthChain Vision ResNet-50",
            "device": str(self.device),
        }

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _load_to_pil(
        self,
        image: Union[str, Path, Image.Image, np.ndarray, bytes],
    ) -> Image.Image:
        """Convert any supported input type to a PIL RGB image."""
        if isinstance(image, Image.Image):
            return image.convert("RGB")

        if isinstance(image, np.ndarray):
            if image.size == 0 or 0 in image.shape:
                raise ValueError(
                    f"NumPy array has zero-sized dimension: shape={image.shape}. "
                    "Provide a non-empty image array."
                )
            if image.ndim == 2:
                # Grayscale → RGB
                image = np.stack([image] * 3, axis=-1)
            elif image.ndim == 3 and image.shape[2] == 4:
                # RGBA → RGB
                image = image[:, :, :3]
            if image.dtype != np.uint8:
                image = np.clip(image, 0, 255).astype(np.uint8)
            return Image.fromarray(image, mode="RGB")

        if isinstance(image, bytes):
            try:
                return Image.open(io.BytesIO(image)).convert("RGB")
            except UnidentifiedImageError as e:
                raise ValueError(f"Cannot decode image bytes: {e}") from e

        if isinstance(image, (str, Path)):
            path = Path(image)
            if path.exists():
                try:
                    return Image.open(path).convert("RGB")
                except UnidentifiedImageError as e:
                    raise ValueError(f"Cannot open image at {path}: {e}") from e
            # Treat as URL
            return self._load_from_url(str(image))

        raise ValueError(
            f"Unsupported image type: {type(image)}. "
            "Pass a file path, URL string, PIL.Image, np.ndarray, or bytes."
        )

    @staticmethod
    def _load_from_url(url: str) -> Image.Image:
        """Fetch image from URL and return as PIL RGB."""
        try:
            import requests
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            raw = resp.content
        except ImportError:
            # Fallback to urllib if requests is not available
            import urllib.request
            with urllib.request.urlopen(url, timeout=15) as resp:  # type: ignore
                raw = resp.read()
        except Exception as e:
            raise ValueError(f"Failed to fetch image from URL '{url}': {e}") from e

        try:
            return Image.open(io.BytesIO(raw)).convert("RGB")
        except UnidentifiedImageError as e:
            raise ValueError(f"URL did not return a valid image '{url}': {e}") from e


# ---------------------------------------------------------------------------
# Module-level singleton — loaded once, reused on every request
# ---------------------------------------------------------------------------

_vision_model: Optional[VisionModel] = None


def _get_model() -> VisionModel:
    """Return the module-level singleton, initializing it on first call."""
    global _vision_model
    if _vision_model is None:
        logger.info("Initializing TruthChain Vision model singleton...")
        _vision_model = VisionModel()
    return _vision_model


def predict_vehicle_damage(
    image: Union[str, Path, Image.Image, np.ndarray, bytes],
) -> Dict[str, Any]:
    """
    Classify vehicle damage in a single image.

    This is the ONLY function the rest of the application needs to call.
    All PyTorch internals, preprocessing, sigmoid, and threshold logic
    are encapsulated here.
    """
    return _get_model().predict(image)

