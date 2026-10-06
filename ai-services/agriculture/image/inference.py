"""

TruthChain Agriculture

Image Crop Inference

\====================



Production inference wrapper for the trained

TruthChain Agriculture CropAgent RGB v0.2 model.



Checkpoint architecture:



    backbone:

        DINOv2 ViT-S/14



    classifier:

        LayerNorm(384)

        Dropout(0.20)

        Linear(384, 138)



The checkpoint state_dict uses:



    backbone.*

    classifier.0.*

    classifier.2.*

"""



from __future__ import annotations



from dataclasses import dataclass

from pathlib import Path



import numpy as np

import torch

import torch.nn as nn

from PIL import Image

from torchvision import transforms





DEFAULT_MODEL_PATH = (

    Path(__file__).resolve().parents[2]

    / "models"

    / "agriculture"

    / "crop"

    / "cropagent_rgb_dinov2_v0.2_best.pt"

)





MODEL_VERSION = "TruthChain-Agriculture-Crop-v0.2"

BACKBONE_NAME = "DINOv2 ViT-S/14"



NUM_CLASSES = 138

FEATURE_DIMENSION = 384

IMAGE_SIZE = 224

DROPOUT = 0.20



IMAGENET_MEAN = (

    0.485,

    0.456,

    0.406,

)



IMAGENET_STD = (

    0.229,

    0.224,

    0.225,

)





@dataclass(frozen=True)

class ImageCropInferenceResult:

    """Result produced by the CropAgent."""



    predicted_class_index: int

    predicted_crop: str

    confidence: float



    probabilities: dict[str, float]



    model_version: str

    backbone: str





class CropAgentError(RuntimeError):

    """Base error for CropAgent failures."""





class CropAgentModelError(CropAgentError):

    """Raised when the model cannot be loaded."""





class CropAgentInputError(CropAgentError):

    """Raised when the input image is invalid."""





class CropAgentNetworkError(CropAgentModelError):

    """Raised when the DINOv2 backbone cannot be obtained."""





class CropClassifier(nn.Module):

    """

    Exact classifier head used by the trained checkpoint.



    State-dict keys:



        classifier.0.weight

        classifier.0.bias

        classifier.2.weight

        classifier.2.bias

    """



    def __init__(

        self,

        feature_dimension: int = FEATURE_DIMENSION,

        num_classes: int = NUM_CLASSES,

    ) -> None:

        super().__init__()



        self.classifier = nn.Sequential(

            nn.LayerNorm(

                feature_dimension

            ),

            nn.Dropout(

                p=DROPOUT

            ),

            nn.Linear(

                feature_dimension,

                num_classes,

            ),

        )



    def forward(

        self,

        features: torch.Tensor,

    ) -> torch.Tensor:

        return self.classifier(

            features

        )





class CropAgentModel(nn.Module):

    """

    Complete trained CropAgent architecture.



    State-dict structure:



        backbone.*

        classifier.0.*

        classifier.2.*

    """



    def __init__(

        self,

        backbone: nn.Module,

        num_classes: int = NUM_CLASSES,

    ) -> None:

        super().__init__()



        self.backbone = backbone



        self.classifier = nn.Sequential(

            nn.LayerNorm(

                FEATURE_DIMENSION

            ),

            nn.Dropout(

                p=DROPOUT

            ),

            nn.Linear(

                FEATURE_DIMENSION,

                num_classes,

            ),

        )



    def forward(

        self,

        images: torch.Tensor,

    ) -> torch.Tensor:

        features = self.backbone(

            images

        )



        if isinstance(

            features,

            dict,

        ):

            if "x_norm_clstoken" in features:

                features = features[

                    "x_norm_clstoken"

                ]

            elif "x_prenorm_clstoken" in features:

                features = features[

                    "x_prenorm_clstoken"

                ]

            elif "x_norm_patchtokens" in features:

                features = features[

                    "x_norm_patchtokens"

                ][:, 0]

            else:

                raise CropAgentModelError(

                    "DINOv2 returned a dictionary "

                    "without a supported CLS-token key."

                )



        if features.ndim != 2:

            raise CropAgentModelError(

                "DINOv2 backbone returned unexpected "

                f"feature shape: {tuple(features.shape)}"

            )



        if features.shape[1] != FEATURE_DIMENSION:

            raise CropAgentModelError(

                "DINOv2 backbone returned "

                f"{features.shape[1]} features; "

                f"expected {FEATURE_DIMENSION}."

            )



        return self.classifier(

            features

        )





class CropAgent:

    """

    Production RGB crop classifier.



    Uses the exact trained checkpoint:



        TruthChain-Agriculture-Crop-v0.2



    with:



        DINOv2 ViT-S/14

        384-dimensional representation

        138 crop classes

    """



    def __init__(

        self,

        model_path: str | Path = DEFAULT_MODEL_PATH,

        device: str | None = None,

    ) -> None:

        self.model_path = Path(

            model_path

        )



        if not self.model_path.exists():

            raise CropAgentModelError(

                f"Checkpoint not found: "

                f"{self.model_path}"

            )



        self.device = self._resolve_device(

            device

        )



        self.checkpoint = (

            self._load_checkpoint()

        )



        self.class_to_idx = (

            self._validate_metadata()

        )



        self.idx_to_class = {

            int(index): str(name)

            for name, index

            in self.class_to_idx.items()

        }



        self.model = self._build_model()



        self.transform = transforms.Compose(

            [

                transforms.Resize(

                    (

                        IMAGE_SIZE,

                        IMAGE_SIZE,

                    )

                ),

                transforms.ToTensor(),

                transforms.Normalize(

                    mean=IMAGENET_MEAN,

                    std=IMAGENET_STD,

                ),

            ]

        )



        self.model.eval()



    @staticmethod

    def _resolve_device(

        device: str | None,

    ) -> torch.device:

        if device is not None:

            return torch.device(

                device

            )



        if torch.cuda.is_available():

            return torch.device(

                "cuda"

            )



        return torch.device(

            "cpu"

        )



    def _load_checkpoint(self) -> dict:

        try:

            checkpoint = torch.load(

                self.model_path,

                map_location="cpu",

                weights_only=False,

            )

        except Exception as exc:

            raise CropAgentModelError(

                "Failed to load CropAgent checkpoint."

            ) from exc



        if not isinstance(

            checkpoint,

            dict,

        ):

            raise CropAgentModelError(

                "CropAgent checkpoint must be a dictionary."

            )



        required_keys = {

            "model_state_dict",

            "num_classes",

            "class_to_idx",

            "model_version",

            "backbone",

        }



        missing = (

            required_keys

            - set(checkpoint.keys())

        )



        if missing:

            raise CropAgentModelError(

                "Checkpoint is missing required "

                f"keys: {sorted(missing)}"

            )



        return checkpoint



    def _validate_metadata(self) -> dict[str, int]:

        checkpoint = self.checkpoint



        checkpoint_num_classes = int(

            checkpoint["num_classes"]

        )



        if checkpoint_num_classes != NUM_CLASSES:

            raise CropAgentModelError(

                f"Checkpoint reports "

                f"{checkpoint_num_classes} classes; "

                f"expected {NUM_CLASSES}."

            )



        checkpoint_version = str(

            checkpoint["model_version"]

        )



        if checkpoint_version != MODEL_VERSION:

            raise CropAgentModelError(

                "Unexpected CropAgent model version: "

                f"{checkpoint_version}"

            )



        checkpoint_backbone = str(

            checkpoint["backbone"]

        )



        if checkpoint_backbone != BACKBONE_NAME:

            raise CropAgentModelError(

                "Unexpected CropAgent backbone: "

                f"{checkpoint_backbone}"

            )



        mapping = checkpoint[

            "class_to_idx"

        ]



        if not isinstance(

            mapping,

            dict,

        ):

            raise CropAgentModelError(

                "class_to_idx must be a dictionary."

            )



        normalized_mapping = {

            str(name): int(index)

            for name, index

            in mapping.items()

        }



        if len(

            normalized_mapping

        ) != NUM_CLASSES:

            raise CropAgentModelError(

                "Checkpoint class mapping contains "

                f"{len(normalized_mapping)} classes; "

                f"expected {NUM_CLASSES}."

            )



        indices = sorted(

            normalized_mapping.values()

        )



        expected_indices = list(

            range(NUM_CLASSES)

        )



        if indices != expected_indices:

            raise CropAgentModelError(

                "class_to_idx does not contain "

                f"the expected indices 0..{NUM_CLASSES - 1}."

            )



        return normalized_mapping



    @staticmethod

    @staticmethod
    def _load_dinov2_backbone() -> nn.Module:
        """
        Build the DINOv2 ViT-S/14 architecture without downloading
        pretrained weights.

        The CropAgent checkpoint contains the complete trained DINOv2
        backbone under ``backbone.*``. Therefore, separate pretrained
        DINOv2 weights are unnecessary and would introduce a network
        dependency.
        """
        try:
            hub_dir = Path(torch.hub.get_dir())
            local_repo = hub_dir / "facebookresearch_dinov2_main"

            if local_repo.exists():
                backbone = torch.hub.load(
                    str(local_repo),
                    "dinov2_vits14",
                    source="local",
                    pretrained=False,
                )
            else:
                backbone = torch.hub.load(
                    "facebookresearch/dinov2",
                    "dinov2_vits14",
                    pretrained=False,
                )
        except Exception as exc:
            raise CropAgentNetworkError(
                "Unable to construct DINOv2 ViT-S/14 architecture. "
                "The local DINOv2 source is unavailable and the "
                "remote repository could not be loaded."
            ) from exc

        return backbone

    def _build_model(self) -> CropAgentModel:

        backbone = (

            self._load_dinov2_backbone()

        )



        model = CropAgentModel(

            backbone=backbone,

            num_classes=NUM_CLASSES,

        )



        state_dict = self.checkpoint[

            "model_state_dict"

        ]



        if not isinstance(

            state_dict,

            dict,

        ):

            raise CropAgentModelError(

                "model_state_dict must be a dictionary."

            )



        state_keys = set(

            state_dict.keys()

        )



        if not any(

            key.startswith("backbone.")

            for key in state_keys

        ):

            raise CropAgentModelError(

                "Checkpoint does not contain "

                "backbone.* parameters."

            )



        if not any(

            key.startswith("classifier.")

            for key in state_keys

        ):

            raise CropAgentModelError(

                "Checkpoint does not contain "

                "classifier.* parameters."

            )



        try:

            model.load_state_dict(

                state_dict,

                strict=True,

            )

        except Exception as exc:

            raise CropAgentModelError(

                "CropAgent checkpoint weights do not "

                "match the reconstructed DINOv2 "

                "CropAgent architecture."

            ) from exc



        model.to(

            self.device

        )



        return model



    @staticmethod

    def _validate_image(

        image: Image.Image,

    ) -> None:

        if not isinstance(

            image,

            Image.Image,

        ):

            raise CropAgentInputError(

                "Input must be a PIL Image."

            )



        if image.width <= 0:

            raise CropAgentInputError(

                "Image width must be positive."

            )



        if image.height <= 0:

            raise CropAgentInputError(

                "Image height must be positive."

            )



    def predict(

        self,

        image: Image.Image,

    ) -> ImageCropInferenceResult:

        """

        Predict crop class from a PIL RGB image.

        """



        self._validate_image(

            image

        )



        image_rgb = image.convert(

            "RGB"

        )



        tensor = self.transform(

            image_rgb

        )



        tensor = tensor.unsqueeze(

            0

        ).to(

            self.device

        )



        with torch.inference_mode():

            logits = self.model(

                tensor

            )



            probabilities_tensor = torch.softmax(

                logits,

                dim=1,

            )



        probabilities_np = (

            probabilities_tensor[0]

            .detach()

            .cpu()

            .numpy()

            .astype(

                np.float64

            )

        )



        if probabilities_np.shape != (

            NUM_CLASSES,

        ):

            raise CropAgentModelError(

                "Model returned unexpected "

                f"probability shape: "

                f"{probabilities_np.shape}"

            )



        if not np.isfinite(

            probabilities_np

        ).all():

            raise CropAgentModelError(

                "Model probabilities contain "

                "NaN or Inf."

            )



        probability_sum = float(

            probabilities_np.sum()

        )



        if not np.isclose(

            probability_sum,

            1.0,

            atol=1e-5,

        ):

            raise CropAgentModelError(

                "Model probabilities do not sum "

                f"to approximately 1.0: "

                f"{probability_sum}"

            )



        predicted_index = int(

            np.argmax(

                probabilities_np

            )

        )



        if (

            predicted_index

            not in self.idx_to_class

        ):

            raise CropAgentModelError(

                "Predicted class index is not "

                "present in checkpoint mapping: "

                f"{predicted_index}"

            )



        predicted_crop = (

            self.idx_to_class[

                predicted_index

            ]

        )



        probabilities = {

            self.idx_to_class[index]: float(

                probabilities_np[index]

            )

            for index in range(

                NUM_CLASSES

            )

        }



        return ImageCropInferenceResult(

            predicted_class_index=predicted_index,

            predicted_crop=predicted_crop,

            confidence=float(

                probabilities_np[

                    predicted_index

                ]

            ),

            probabilities=probabilities,

            model_version=MODEL_VERSION,

            backbone=BACKBONE_NAME,

        )



    def predict_file(

        self,

        image_path: str | Path,

    ) -> ImageCropInferenceResult:

        """

        Load an image from disk and run prediction.

        """



        path = Path(

            image_path

        )



        if not path.exists():

            raise CropAgentInputError(

                f"Image file not found: {path}"

            )



        try:

            with Image.open(

                path

            ) as image:

                return self.predict(

                    image.copy()

                )

        except CropAgentInputError:

            raise

        except Exception as exc:

            raise CropAgentInputError(

                f"Unable to read image: {path}"

            ) from exc





__all__ = [

    "DEFAULT_MODEL_PATH",

    "MODEL_VERSION",

    "BACKBONE_NAME",

    "NUM_CLASSES",

    "FEATURE_DIMENSION",

    "ImageCropInferenceResult",

    "CropAgentError",

    "CropAgentModelError",

    "CropAgentInputError",

    "CropAgentNetworkError",

    "CropClassifier",

    "CropAgentModel",

    "CropAgent",

]