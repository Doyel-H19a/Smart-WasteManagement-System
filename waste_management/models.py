"""Models for wards, collection schedules and waste movement logs."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
    RegexValidator,
)
from django.db import models
from django.utils import timezone


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


class WasteType(models.TextChoices):
    """Kinds of waste handled by schedules and movements."""

    WET = "wet", "Wet / organic"
    DRY = "dry", "Dry / recyclable"
    MIXED = "mixed", "Mixed"
    HAZARDOUS = "hazardous", "Hazardous"
    E_WASTE = "e_waste", "Electronic"
    CONSTRUCTION = "construction", "Construction debris"


class Weekday(models.IntegerChoices):
    """Values match Python's date.weekday() (Monday = 0)."""

    MONDAY = 0, "Monday"
    TUESDAY = 1, "Tuesday"
    WEDNESDAY = 2, "Wednesday"
    THURSDAY = 3, "Thursday"
    FRIDAY = 4, "Friday"
    SATURDAY = 5, "Saturday"
    SUNDAY = 6, "Sunday"


vehicle_validator = RegexValidator(
    regex=r"^[A-Za-z0-9 \-]+$",
    message="Use letters, digits, spaces and hyphens only.",
)


class CollectionSchedule(models.Model):
    """A recurring weekly collection slot for one ward, route and waste type."""

    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="schedules")
    route_name = models.CharField(max_length=100, help_text="Street, area or route covered.")
    waste_type = models.CharField(max_length=20, choices=WasteType.choices, default=WasteType.WET)
    weekday = models.PositiveSmallIntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    assigned_worker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="collection_schedules", limit_choices_to={"role": "worker"},
    )
    vehicle_number = models.CharField(max_length=20, blank=True, validators=[vehicle_validator])
    notes = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(
        default=True, help_text="Inactive schedules are hidden from citizens and workers."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["weekday", "start_time", "ward__ward_number"]
        indexes = [models.Index(fields=["weekday", "is_active"])]
        constraints = [
            models.UniqueConstraint(
                fields=["ward", "route_name", "waste_type", "weekday", "start_time"],
                name="unique_collection_slot",
                violation_error_message=(
                    "A schedule for this ward, route, waste type, day and start time already exists."
                ),
            )
        ]

    def __str__(self):
        return f"{self.ward} – {self.route_name} ({self.get_weekday_display()} {self.time_window})"

    @property
    def time_window(self):
        return f"{self.start_time:%H:%M}–{self.end_time:%H:%M}"

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be later than start time."})


class WasteMovement(models.Model):
    """One logged movement of waste: a pickup, a transfer or a disposal."""

    class MovementType(models.TextChoices):
        PICKUP = "pickup", "Pickup"
        TRANSFER = "transfer", "Transfer"
        DISPOSAL = "disposal", "Disposal / processing"

    BADGES = {
        "pickup": "bg-primary",
        "transfer": "bg-warning text-dark",
        "disposal": "bg-success",
    }

    movement_type = models.CharField(max_length=20, choices=MovementType.choices, default=MovementType.PICKUP)
    waste_type = models.CharField(max_length=20, choices=WasteType.choices, default=WasteType.WET)
    quantity_kg = models.DecimalField(
        "quantity (kg)", max_digits=9, decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("50000"))],
    )
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="movements")
    schedule = models.ForeignKey(
        CollectionSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="movements"
    )
    from_location = models.CharField("from", max_length=150)
    to_location = models.CharField("to", max_length=150)
    vehicle_number = models.CharField(max_length=20, blank=True, validators=[vehicle_validator])
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    notes = models.CharField(max_length=255, blank=True)
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="waste_movements"
    )
    # Set automatically; workers cannot back-date entries.
    moved_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-moved_at", "-id"]
        indexes = [
            models.Index(fields=["movement_type", "-moved_at"]),
            models.Index(fields=["ward", "-moved_at"]),
            models.Index(fields=["logged_by", "-moved_at"]),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} {self.quantity_kg} kg ({self.get_waste_type_display()})"

    @property
    def badge_class(self):
        return self.BADGES.get(self.movement_type, "bg-secondary")