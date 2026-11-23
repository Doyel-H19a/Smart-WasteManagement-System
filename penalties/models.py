"""Models for penalties issued for waste violations."""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from inspections.models import Inspection
from waste_management.models import Ward


class Penalty(models.Model):
    """A fine for a waste-related violation. Payments are recorded by the municipal office."""

    class Violation(models.TextChoices):
        ILLEGAL_DUMPING = "illegal_dumping", "Illegal dumping"
        NO_SEGREGATION = "no_segregation", "Failure to segregate waste"
        OPEN_BURNING = "open_burning", "Open burning of waste"
        BULK_NON_COMPLIANCE = "bulk_non_compliance", "Bulk generator non-compliance"
        DRAIN_BLOCKAGE = "drain_blockage", "Dumping that blocks drains"
        OTHER = "other", "Other violation"

    class Status(models.TextChoices):
        ISSUED = "issued", "Issued (payment due)"
        DISPUTED = "disputed", "Under dispute"
        PAID = "paid", "Paid"
        WAIVED = "waived", "Waived"
        CANCELLED = "cancelled", "Cancelled"

    # Statuses in which the penalty still needs a decision or a payment.
    OPEN_STATUSES = (Status.ISSUED, Status.DISPUTED)

    BADGES = {
        "issued": "bg-warning text-dark",
        "disputed": "bg-info text-dark",
        "paid": "bg-success",
        "waived": "bg-secondary",
        "cancelled": "bg-dark",
    }

    issued_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="penalties",
        limit_choices_to={"role__in": ["citizen", "bulk_generator"]},
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="penalties_issued"
    )
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="penalties")
    inspection = models.ForeignKey(
        Inspection, on_delete=models.SET_NULL, null=True, blank=True, related_name="penalties"
    )
    violation_type = models.CharField(max_length=30, choices=Violation.choices, default=Violation.OTHER)
    description = models.TextField()
    amount = models.DecimalField(
        "amount (₹)", max_digits=9, decimal_places=2,
        validators=[MinValueValidator(Decimal("1.00")), MaxValueValidator(Decimal("100000.00"))],
    )
    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ISSUED)

    # Payment (recorded by the municipal office)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField("receipt / reference no.", max_length=60, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    # Dispute and resolution
    dispute_reason = models.CharField(max_length=500, blank=True)
    disputed_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.CharField(max_length=255, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "penalties"
        indexes = [
            models.Index(fields=["status", "due_date"]),
            models.Index(fields=["issued_to", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.reference} – {self.get_violation_type_display()}"

    @property
    def reference(self):
        """Human-friendly number, for example PEN-00012."""
        return f"PEN-{self.pk:05d}" if self.pk else "PEN-NEW"

    @property
    def status_badge_class(self):
        return self.BADGES.get(self.status, "bg-secondary")

    @property
    def is_overdue(self):
        return self.status == self.Status.ISSUED and self.due_date < timezone.localdate()

    def get_absolute_url(self):
        return reverse("penalties:detail", args=[self.pk])


class PenaltyEvent(models.Model):
    """One entry per step; shown as the penalty timeline."""

    penalty = models.ForeignKey(Penalty, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=20, choices=Penalty.Status.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"{self.penalty.reference}: {self.get_status_display()}"