"""Django admin configuration for complaints."""
from django.contrib import admin

from .models import Complaint, ComplaintStatusHistory


class ComplaintStatusHistoryInline(admin.TabularInline):
    model = ComplaintStatusHistory
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "citizen", "ward", "category", "status", "priority", "created_at")
    list_filter = ("status", "priority", "category", "ward")
    search_fields = ("title", "description", "address", "citizen__username")
    inlines = [ComplaintStatusHistoryInline]