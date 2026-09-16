import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Model weights directory paths
MODELS_DIR = BASE_DIR / "ml" / "models"
VISION_MODEL_DIR = MODELS_DIR / "vision"
SENSOR_MODEL_DIR = MODELS_DIR / "sensor"

VISION_WEIGHTS_PATH = VISION_MODEL_DIR / "truthchain_vision_resnet50.pth"
if not VISION_WEIGHTS_PATH.exists():
    VISION_WEIGHTS_PATH = VISION_MODEL_DIR / "model.pth"

VISION_CLASSES_PATH = VISION_MODEL_DIR / "vision_classes.json"
if not VISION_CLASSES_PATH.exists():
    VISION_CLASSES_PATH = VISION_MODEL_DIR / "classes.json"

VISION_THRESHOLDS_PATH = VISION_MODEL_DIR / "vision_thresholds.json"
if not VISION_THRESHOLDS_PATH.exists():
    VISION_THRESHOLDS_PATH = VISION_MODEL_DIR / "thresholds.json"

# API & LLM Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

SERVER_HOST = os.getenv("AI_SERVICE_HOST", "0.0.0.0")
SERVER_PORT = int(os.getenv("AI_SERVICE_PORT", "8000"))
