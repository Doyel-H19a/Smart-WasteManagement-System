"""Django admin configuration for classifications."""
from django.contrib import admin

from .models import WasteClassification


@admin.register(WasteClassification)
class WasteClassificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "predicted_label", "confidence", "is_demo", "backend", "created_at")
    list_filter = ("is_demo", "backend", "predicted_label")
    search_fields = ("user__username",)