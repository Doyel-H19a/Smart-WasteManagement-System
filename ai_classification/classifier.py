"""Waste image classification service.

IMPORTANT: the default back-end is a DEMONSTRATION classifier. It does NOT
analyse the image content and its output is not a real prediction. It exists
only so the interface can be built and tested before a CNN is trained.

To use a real model later:
  1. Train a Keras CNN and save it as  ai_models/waste_cnn.keras
  2. Install TensorFlow (pip install tensorflow)
  3. Set AI_CLASSIFIER_BACKEND=keras in .env
  4. Make settings.AI_CLASS_NAMES match your model's output order.
"""
import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from PIL import Image

DEMO_NOTICE = (
    "This result is NOT produced by a trained CNN. It is a placeholder so the "
    "interface can be tested before a real model is added."
)

# key -> (display label, general disposal tip)
WASTE_CLASSES = {
    "organic": ("Organic / food waste", "Keep it in the wet-waste bin or compost it."),
    "plastic": ("Plastic", "Rinse and place in the dry-waste bin for recycling."),
    "paper": ("Paper / cardboard", "Keep it dry and place in the dry-waste bin."),
    "metal": ("Metal", "Place in the dry-waste bin or give it to a scrap collector."),
    "glass": ("Glass", "Wrap broken pieces safely and place in the dry-waste bin."),
    "e_waste": ("Electronic waste", "Hand over at an authorised e-waste collection point."),
    "hazardous": ("Hazardous waste", "Keep it separate and use a hazardous-waste pickup."),
    "construction": ("Construction debris", "Request a debris pickup. Do not leave it on footpaths."),
}


class ClassifierUnavailable(Exception):
    """The configured classifier cannot run (for example, no trained model yet)."""


class InvalidImage(Exception):
    """The uploaded file is not a readable image."""


@dataclass(frozen=True)
class ClassificationResult:
    label: str          # a key of WASTE_CLASSES
    confidence: float   # 0.0 - 1.0
    backend: str        # "demo" or "keras"
    is_demo: bool
    model_name: str


class DemoClassifier:
    """Placeholder. Picks a class from a hash of the file bytes (NOT image analysis)."""

    backend = "demo"
    is_demo = True
    model_name = "Demonstration classifier (not a trained model)"

    def classify(self, image_bytes):
        digest = hashlib.sha256(image_bytes).digest()
        keys = list(WASTE_CLASSES)
        label = keys[int.from_bytes(digest[:4], "big") % len(keys)]
        confidence = 0.55 + (int.from_bytes(digest[4:6], "big") % 4001) / 10000  # 0.55 - 0.95
        return ClassificationResult(
            label=label,
            confidence=round(confidence, 4),
            backend=self.backend,
            is_demo=True,
            model_name=self.model_name,
        )


class KerasClassifier:
    """Runs a trained Keras CNN. Not usable until a model file is provided."""

    backend = "keras"
    is_demo = False
    _model = None
    _loaded_path = None

    def _load_model(self):
        path = Path(settings.AI_MODEL_PATH)
        if not path.is_file():
            raise ClassifierUnavailable(
                f"No trained model found at {path}. Add a model file or set "
                "AI_CLASSIFIER_BACKEND=demo."
            )
        if KerasClassifier._model is None or KerasClassifier._loaded_path != path:
            try:
                import tensorflow as tf
            except ImportError as exc:
                raise ClassifierUnavailable(
                    "TensorFlow is not installed. Run: pip install tensorflow"
                ) from exc
            KerasClassifier._model = tf.keras.models.load_model(path)
            KerasClassifier._loaded_path = path
        return KerasClassifier._model

    def classify(self, image_bytes):
        model = self._load_model()
        import numpy as np

        height, width = model.input_shape[1:3]
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB").resize((width, height))
        # Scaling to 0-1 must match how the model was trained.
        array = np.asarray(image, dtype="float32") / 255.0
        probabilities = model.predict(np.expand_dims(array, 0), verbose=0)[0]

        class_names = list(settings.AI_CLASS_NAMES)
        if len(class_names) != len(probabilities):
            raise ClassifierUnavailable(
                "AI_CLASS_NAMES does not match the number of outputs of the model."
            )
        index = int(np.argmax(probabilities))
        label = class_names[index]
        if label not in WASTE_CLASSES:
            raise ClassifierUnavailable(f"Unknown class name '{label}' in AI_CLASS_NAMES.")
        return ClassificationResult(
            label=label,
            confidence=round(float(probabilities[index]), 4),
            backend=self.backend,
            is_demo=False,
            model_name=Path(settings.AI_MODEL_PATH).name,
        )


def get_classifier():
    """Return the back-end chosen in settings.AI_CLASSIFIER_BACKEND."""
    backend = getattr(settings, "AI_CLASSIFIER_BACKEND", "demo")
    if backend == "demo":
        return DemoClassifier()
    if backend == "keras":
        return KerasClassifier()
    raise ImproperlyConfigured("AI_CLASSIFIER_BACKEND must be 'demo' or 'keras'.")


def classify_image(image_file):
    """Validate an uploaded image and classify it with the configured back-end."""
    image_file.seek(0)
    data = image_file.read()
    image_file.seek(0)
    try:
        Image.open(io.BytesIO(data)).verify()
    except Exception as exc:
        raise InvalidImage("The file is not a valid image.") from exc
    return get_classifier().classify(data)