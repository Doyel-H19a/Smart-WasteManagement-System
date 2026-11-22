"""Django admin configuration for wards."""
from django.contrib import admin

from .models import Ward


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ("ward_number", "name", "zone", "population", "is_active")
    list_filter = ("is_active", "zone")
    search_fields = ("name", "zone")