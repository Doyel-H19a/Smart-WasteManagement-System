"""Django admin configuration for inspections."""
from django.contrib import admin

from .models import Inspection


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = ("id", "premises_name", "ward", "category", "outcome", "inspector", "inspection_date")
    list_filter = ("outcome", "category", "ward")
    search_fields = ("premises_name", "address", "findings", "inspector__username")
    readonly_fields = ("created_at",)