"""Models for sanitation and waste-compliance inspections."""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from waste_management.models import Ward

RATING_VALIDATORS = [MinValueValidator(1), MaxValueValidator(5)]


class Inspection(models.Model):
    """One inspection of a place by a Health Officer. Not editable after saving."""

    class Category(models.TextChoices):
        PUBLIC_AREA = "public_area", "Public area / street"
        COLLECTION_POINT = "collection_point", "Collection point / community bin"
        BULK_PREMISES = "bulk_premises", "Bulk waste generator premises"
        FACILITY = "facility", "Transfer station / processing facility"

    class Outcome(models.TextChoices):
        COMPLIANT = "compliant", "Compliant"
        MINOR = "minor_issues", "Minor issues"
        MAJOR = "major_violation", "Major violation"

    BADGES = {
        "compliant": "bg-success",
        "minor_issues": "bg-warning text-dark",
        "major_violation": "bg-danger",
    }

    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="inspections"
    )
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="inspections")
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.PUBLIC_AREA)
    premises_name = models.CharField("place inspected", max_length=150)
    address = models.CharField(max_length=255)
    bulk_generator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="inspections_received", limit_choices_to={"role": "bulk_generator"},
        verbose_name="registered generator",
    )
    inspection_date = models.DateField(default=timezone.localdate)

    segregation_rating = models.PositiveSmallIntegerField(
        "waste segregation (1-5)", validators=RATING_VALIDATORS
    )
    cleanliness_rating = models.PositiveSmallIntegerField(
        "area cleanliness (1-5)", validators=RATING_VALIDATORS
    )
    bin_condition_rating = models.PositiveSmallIntegerField(
        "bin and equipment condition (1-5)", validators=RATING_VALIDATORS
    )
    outcome = models.CharField(max_length=20, choices=Outcome.choices, default=Outcome.MINOR)
    findings = models.TextField()
    recommendations = models.TextField(blank=True)

    follow_up_required = models.BooleanField("follow-up visit needed", default=False)
    follow_up_date = models.DateField(null=True, blank=True)
    follow_up_completed_at = models.DateTimeField(null=True, blank=True)
    follow_up_completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    photo = models.ImageField(upload_to="inspections/%Y/%m/", blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-inspection_date", "-id"]
        indexes = [
            models.Index(fields=["outcome", "-inspection_date"]),
            models.Index(fields=["ward", "-inspection_date"]),
        ]

    def __str__(self):
        return f"{self.reference} – {self.premises_name}"

    @property
    def reference(self):
        """Human-friendly number, for example INS-00012."""
        return f"INS-{self.pk:05d}" if self.pk else "INS-NEW"

    @property
    def outcome_badge_class(self):
        return self.BADGES.get(self.outcome, "bg-secondary")

    @property
    def overall_rating(self):
        """Average of the three ratings, to one decimal place."""
        total = self.segregation_rating + self.cleanliness_rating + self.bin_condition_rating
        return round(total / 3, 1)

    @property
    def follow_up_pending(self):
        return self.follow_up_required and self.follow_up_completed_at is None

    @property
    def follow_up_overdue(self):
        return (
            self.follow_up_pending
            and self.follow_up_date is not None
            and self.follow_up_date < timezone.localdate()
        )

    def get_absolute_url(self):
        return reverse("inspections:detail", args=[self.pk])