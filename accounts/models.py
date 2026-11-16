"""Custom user model for SwachhAI."""
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models


class User(AbstractUser):
    """Application user. Every user has exactly one role."""

    class Role(models.TextChoices):
        CITIZEN = "citizen", "Citizen"
        WORKER = "worker", "Waste Worker"
        MUNICIPAL_ADMIN = "municipal_admin", "Municipal Admin"
        HEALTH_OFFICER = "health_officer", "Health Officer"
        EXECUTIVE_OFFICER = "executive_officer", "Executive Officer"
        SUPER_ADMIN = "super_admin", "Super Admin"
        GREEN_CHAMPION = "green_champion", "Green Champion"
        BULK_GENERATOR = "bulk_generator", "Bulk Waste Generator"

    phone_validator = RegexValidator(
        regex=r"^\+?[0-9]{10,15}$",
        message="Enter a valid phone number (10-15 digits, optional leading +).",
    )

    email = models.EmailField("email address", unique=True)
    role = models.CharField(max_length=30, choices=Role.choices, default=Role.CITIZEN)
    phone_number = models.CharField(max_length=16, blank=True, validators=[phone_validator])
    address = models.TextField(blank=True)
    profile_image = models.ImageField(upload_to="profiles/", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # createsuperuser will also ask for an email address.
    REQUIRED_FIELDS = ["email"]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.display_name} ({self.get_role_display()})"

    @property
    def display_name(self):
        """Full name if available, otherwise the username."""
        return self.get_full_name() or self.username

    def save(self, *args, **kwargs):
        # A Django superuser is always a Super Admin in SwachhAI.
        if self.is_superuser:
            self.role = self.Role.SUPER_ADMIN
        super().save(*args, **kwargs)