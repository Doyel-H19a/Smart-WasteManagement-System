"""Django admin configuration for wards, schedules and waste movements."""
from django.contrib import admin

from .models import CollectionSchedule, Ward, WasteMovement


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ("ward_number", "name", "zone", "population", "is_active")
    list_filter = ("is_active", "zone")
    search_fields = ("name", "zone")


@admin.register(CollectionSchedule)
class CollectionScheduleAdmin(admin.ModelAdmin):
    list_display = ("ward", "route_name", "waste_type", "weekday", "start_time", "end_time",
                    "assigned_worker", "is_active")
    list_filter = ("is_active", "weekday", "waste_type", "ward")
    search_fields = ("route_name", "vehicle_number", "assigned_worker__username")


@admin.register(WasteMovement)
class WasteMovementAdmin(admin.ModelAdmin):
    list_display = ("moved_at", "movement_type", "waste_type", "quantity_kg", "ward", "logged_by")
    list_filter = ("movement_type", "waste_type", "ward")
    search_fields = ("from_location", "to_location", "vehicle_number", "logged_by__username")
    readonly_fields = ("moved_at",)