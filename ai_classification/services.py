"""Database operations for classifications (kept apart from the classifier)."""
from .classifier import classify_image
from .models import WasteClassification


def classify_and_store(user, image_file):
    """Classify an uploaded image and save the result.

    Raises ClassifierUnavailable or InvalidImage; nothing is saved in that case.
    """
    result = classify_image(image_file)
    image_file.seek(0)
    return WasteClassification.objects.create(
        user=user,
        image=image_file,
        predicted_label=result.label,
        confidence=result.confidence,
        backend=result.backend,
        model_name=result.model_name,
        is_demo=result.is_demo,
    )