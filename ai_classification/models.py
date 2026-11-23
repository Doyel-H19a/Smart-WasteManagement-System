"""Models for stored waste classifications."""
from django.conf import settings
from django.db import models

from .classifier import WASTE_CLASSES


class WasteClassification(models.Model):
    """One classified image. `is_demo` records whether the result was a placeholder."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="classifications"
    )
    image = models.ImageField(upload_to="classifications/%Y/%m/")
    predicted_label = models.CharField(max_length=30)
    confidence = models.FloatField()
    backend = models.CharField(max_length=20)
    model_name = models.CharField(max_length=120)
    is_demo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        mode = "DEMO" if self.is_demo else self.backend
        return f"{self.predicted_label} ({mode})"

    @property
    def label_display(self):
        return WASTE_CLASSES.get(self.predicted_label, (self.predicted_label, ""))[0]

    @property
    def disposal_tip(self):
        return WASTE_CLASSES.get(self.predicted_label, ("", ""))[1]

    @property
    def confidence_percent(self):
        return round(self.confidence * 100)