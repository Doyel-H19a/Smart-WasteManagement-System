"""Business logic for inspections (kept separate from the views)."""
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from notifications.models import Notification
from notifications.services import notify, notify_many

from .models import Inspection

SYSTEM = Notification.Category.SYSTEM

# Only Health Officers record inspections and complete follow-ups.
INSPECTOR_ROLES = (User.Role.HEALTH_OFFICER,)


class InspectionError(Exception):
    """Raised when an inspection action is not allowed."""


@transaction.atomic
def record_inspection(inspection, inspector):
    """Save a new inspection and notify the people who need to know."""
    if inspector.role not in INSPECTOR_ROLES or not inspector.is_active:
        raise InspectionError("Only health officers can record inspections.")

    inspection.inspector = inspector
    inspection.save()
    link = reverse("inspections:detail", args=[inspection.pk])

    generator = inspection.bulk_generator
    if generator is not None and generator.is_active:
        notify(
            generator,
            title=f"Inspection {inspection.reference} recorded",
            message=f"Your premises were inspected: {inspection.get_outcome_display()}.",
            category=SYSTEM,
            link=link,
        )

    if inspection.outcome == Inspection.Outcome.MAJOR:
        admins = User.objects.filter(role=User.Role.MUNICIPAL_ADMIN, is_active=True)
        notify_many(
            admins,
            title=f"Major violation found ({inspection.reference})",
            message=f"{inspection.premises_name} ({inspection.ward})",
            category=SYSTEM,
            link=link,
        )
    return inspection


@transaction.atomic
def complete_follow_up(inspection, user):
    """Mark a requested follow-up visit as done (once)."""
    inspection = Inspection.objects.select_for_update().get(pk=inspection.pk)
    if user.role not in INSPECTOR_ROLES or not user.is_active:
        raise InspectionError("Only health officers can complete a follow-up.")
    if not inspection.follow_up_required:
        raise InspectionError("No follow-up was requested for this inspection.")
    if inspection.follow_up_completed_at is not None:
        raise InspectionError("The follow-up has already been completed.")

    inspection.follow_up_completed_at = timezone.now()
    inspection.follow_up_completed_by = user
    inspection.save(update_fields=["follow_up_completed_at", "follow_up_completed_by"])
    return inspection


def summarise_inspections(queryset):
    """Counts by outcome and the number of pending and overdue follow-ups."""
    today = timezone.localdate()
    outcome = Inspection.Outcome
    pending = Q(follow_up_required=True, follow_up_completed_at__isnull=True)
    return queryset.aggregate(
        count=Count("id"),
        compliant=Count("id", filter=Q(outcome=outcome.COMPLIANT)),
        minor=Count("id", filter=Q(outcome=outcome.MINOR)),
        major=Count("id", filter=Q(outcome=outcome.MAJOR)),
        follow_ups_pending=Count("id", filter=pending),
        follow_ups_overdue=Count("id", filter=pending & Q(follow_up_date__lt=today)),
    )