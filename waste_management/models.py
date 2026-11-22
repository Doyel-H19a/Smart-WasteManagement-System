"""Models for wards (the geographic units of the city)."""
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Ward(models.Model):
    """A municipal ward. Complaints, schedules and inspections link to it."""

    ward_number = models.PositiveIntegerField(unique=True, validators=[MinValueValidator(1)])
    name = models.CharField(max_length=100)
    zone = models.CharField(max_length=100, blank=True)
    population = models.PositiveIntegerField(null=True, blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
        help_text="Centre point, used for maps later (optional).",
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    is_active = models.BooleanField(default=True, help_text="Inactive wards cannot be chosen in new complaints.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ward_number"]

    def __str__(self):
        return f"Ward {self.ward_number} – {self.name}"