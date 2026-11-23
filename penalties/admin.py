"""Django admin configuration for penalties."""
from django.contrib import admin

from .models import Penalty, PenaltyEvent


class PenaltyEventInline(admin.TabularInline):
    model = PenaltyEvent
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Penalty)
class PenaltyAdmin(admin.ModelAdmin):
    list_display = ("id", "issued_to", "violation_type", "amount", "due_date", "status", "issued_by")
    list_filter = ("status", "violation_type", "ward")
    search_fields = ("description", "issued_to__username", "payment_reference")
    inlines = [PenaltyEventInline]