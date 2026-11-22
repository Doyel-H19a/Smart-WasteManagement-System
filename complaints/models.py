"""Models for citizen waste complaints."""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse

from waste_management.models import Ward

# Bootstrap badge classes for each status.
STATUS_BADGES = {
    "submitted": "bg-secondary",
    "under_review": "bg-info text-dark",
    "assigned": "bg-primary",
    "accepted": "bg-primary",
    "completed": "bg-warning text-dark",
    "resolved": "bg-success",
    "rejected": "bg-danger",
}


class Complaint(models.Model):
    """A waste-related complaint raised by a citizen."""

    class Category(models.TextChoices):
        ILLEGAL_DUMPING = "illegal_dumping", "Illegal dumping"
        OVERFLOWING_BIN = "overflowing_bin", "Overflowing bin"
        MISSED_COLLECTION = "missed_collection", "Missed collection"
        DEAD_ANIMAL = "dead_animal", "Dead animal"
        CONSTRUCTION_DEBRIS = "construction_debris", "Construction debris"
        HAZARDOUS_WASTE = "hazardous_waste", "Hazardous waste"
        DRAIN_BLOCKAGE = "drain_blockage", "Drain blockage"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        ASSIGNED = "assigned", "Worker assigned"
        ACCEPTED = "accepted", "Accepted by worker"
        COMPLETED = "completed", "Work completed (awaiting verification)"
        RESOLVED = "resolved", "Resolved"
        REJECTED = "rejected", "Rejected"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    # Statuses in which the complaint is still being handled.
    OPEN_STATUSES = (
        Status.SUBMITTED,
        Status.UNDER_REVIEW,
        Status.ASSIGNED,
        Status.ACCEPTED,
        Status.COMPLETED,
    )

    citizen = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="complaints"
    )
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="complaints")
    title = models.CharField(max_length=150)
    category = models.CharField(max_length=30, choices=Category.choices, default=Category.OTHER)
    description = models.TextField()
    address = models.CharField("location / address", max_length=255)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    image = models.ImageField("photo", upload_to="complaints/%Y/%m/", blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["citizen", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.reference} – {self.title}"

    @property
    def reference(self):
        """Human-friendly complaint number, for example SWA-00012."""
        return f"SWA-{self.pk:05d}" if self.pk else "SWA-NEW"

    @property
    def status_badge_class(self):
        return STATUS_BADGES.get(self.status, "bg-secondary")

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    def get_absolute_url(self):
        return reverse("complaints:detail", args=[self.pk])


class ComplaintStatusHistory(models.Model):
    """One entry per status change; shown as the complaint timeline."""

    complaint = models.ForeignKey(Complaint, on_delete=models.CASCADE, related_name="history")
    status = models.CharField(max_length=20, choices=Complaint.Status.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name_plural = "complaint status history"

    def __str__(self):
        return f"{self.complaint.reference}: {self.get_status_display()}"