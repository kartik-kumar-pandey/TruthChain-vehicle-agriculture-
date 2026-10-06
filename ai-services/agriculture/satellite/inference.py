"""
TruthChain Agriculture
Satellite Crop Evidence Inference
==================================

Production wrapper for the Agriculture satellite crop-evidence model.

Responsibilities:
    1. validate the 77-feature input
    2. load the trained XGBoost model
    3. run crop-class inference
    4. map model class indices to source crop IDs
    5. return a structured evidence result

This module does not make a fraud decision.
It only produces satellite crop-evidence inference.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import xgboost as xgb


DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parents[2]
    / "models"
    / "agriculture"
    / "satellite"
    / "satellite_cropagent_v0.2.json"
)


SOURCE_CLASS_IDS: tuple[int, ...] = (
    1,   # Wheat
    2,   # Mustard
    3,   # Lentil
    4,   # Fallow
    5,   # Green pea
    6,   # Sugarcane
    8,   # Garlic
    9,   # Maize
    13,  # Gram
    14,  # Coriander
    15,  # Potato
    16,  # Bersem
    36,  # Rice
)


SOURCE_CLASS_NAMES: dict[int, str] = {
    1: "Wheat",
    2: "Mustard",
    3: "Lentil",
    4: "Fallow",
    5: "Green pea",
    6: "Sugarcane",
    8: "Garlic",
    9: "Maize",
    13: "Gram",
    14: "Coriander",
    15: "Potato",
    16: "Bersem",
    36: "Rice",
}


@dataclass(frozen=True)
class SatelliteInferenceResult:
    """Structured satellite crop-evidence inference."""

    predicted_source_id: int
    predicted_crop: str
    top_probability: float
    claimed_source_id: int | None
    claimed_crop: str | None
    claimed_probability: float | None
    probabilities: dict[int, float]


class SatelliteCropInference:
    """
    Load and run the Agriculture satellite crop model.

    The model expects exactly 77 features in the order defined
    by agriculture.satellite.features.FEATURE_NAMES.
    """

    def __init__(
        self,
        model_path: str | Path = DEFAULT_MODEL_PATH,
    ) -> None:
        self.model_path = Path(model_path)

        if not self.model_path.exists():
            raise FileNotFoundError(
                "Satellite model not found: "
                f"{self.model_path}"
            )

        self.model = xgb.XGBClassifier()

        self.model.load_model(
            str(self.model_path)
        )

        feature_count = int(
            self.model.get_booster().num_features()
        )

        if feature_count != 77:
            raise RuntimeError(
                "Satellite model must contain "
                f"77 features; got {feature_count}."
            )

        class_count = len(
            self.model.classes_
        )

        if class_count != 13:
            raise RuntimeError(
                "Satellite model must contain "
                f"13 classes; got {class_count}."
            )

        if len(SOURCE_CLASS_IDS) != class_count:
            raise RuntimeError(
                "Source class mapping does not match "
                "the model class count."
            )

    def predict(
        self,
        feature_vector: np.ndarray,
        *,
        claimed_source_id: int | None = None,
    ) -> SatelliteInferenceResult:
        """
        Run inference on one 77-feature vector.

        Parameters
        ----------
        feature_vector:
            One-dimensional NumPy array containing exactly
            77 model features in the established order.

        claimed_source_id:
            Optional source crop ID from the farmer claim.
        """

        vector = np.asarray(
            feature_vector,
            dtype=np.float32,
        )

        if vector.shape != (77,):
            raise ValueError(
                "Satellite feature vector must have "
                f"shape (77,), got {vector.shape}."
            )

        if not np.isfinite(vector).all():
            raise ValueError(
                "Satellite feature vector contains "
                "NaN or Inf values."
            )

        if claimed_source_id is not None:
            if claimed_source_id not in SOURCE_CLASS_NAMES:
                raise ValueError(
                    "Unknown claimed source crop ID: "
                    f"{claimed_source_id}"
                )

        probabilities = self.model.predict_proba(
            vector.reshape(1, -1)
        )[0]

        if probabilities.shape != (13,):
            raise RuntimeError(
                "Satellite model returned an unexpected "
                f"probability shape: {probabilities.shape}"
            )

        if not np.isfinite(probabilities).all():
            raise RuntimeError(
                "Satellite model returned NaN or Inf "
                "probabilities."
            )

        probability_sum = float(
            probabilities.sum()
        )

        if not np.isclose(
            probability_sum,
            1.0,
            atol=1e-5,
        ):
            raise RuntimeError(
                "Satellite model probabilities do not "
                f"sum to 1.0: {probability_sum}"
            )

        predicted_model_index = int(
            np.argmax(probabilities)
        )

        predicted_source_id = SOURCE_CLASS_IDS[
            predicted_model_index
        ]

        predicted_crop = SOURCE_CLASS_NAMES[
            predicted_source_id
        ]

        top_probability = float(
            probabilities[
                predicted_model_index
            ]
        )

        claimed_probability: float | None = None
        claimed_crop: str | None = None

        if claimed_source_id is not None:
            claimed_model_index = (
                SOURCE_CLASS_IDS.index(
                    claimed_source_id
                )
            )

            claimed_probability = float(
                probabilities[
                    claimed_model_index
                ]
            )

            claimed_crop = SOURCE_CLASS_NAMES[
                claimed_source_id
            ]

        probability_map = {
            source_id: float(
                probabilities[index]
            )
            for index, source_id in enumerate(
                SOURCE_CLASS_IDS
            )
        }

        return SatelliteInferenceResult(
            predicted_source_id=predicted_source_id,
            predicted_crop=predicted_crop,
            top_probability=top_probability,
            claimed_source_id=claimed_source_id,
            claimed_crop=claimed_crop,
            claimed_probability=claimed_probability,
            probabilities=probability_map,
        )


__all__ = [
    "DEFAULT_MODEL_PATH",
    "SOURCE_CLASS_IDS",
    "SOURCE_CLASS_NAMES",
    "SatelliteInferenceResult",
    "SatelliteCropInference",
]