"""Django admin configuration for the custom user model."""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .forms import AdminUserChangeForm, AdminUserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = AdminUserCreationForm
    form = AdminUserChangeForm

    list_display = ("username", "email", "role", "is_active", "is_staff", "created_at")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name", "phone_number")

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("SwachhAI Profile", {"fields": ("role", "phone_number", "address", "profile_image")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("SwachhAI Profile", {"fields": ("email", "role", "phone_number")}),
    )