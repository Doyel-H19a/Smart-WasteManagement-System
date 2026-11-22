"""Business logic for complaints (kept separate from the views)."""
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse

from accounts.models import User
from notifications.models import Notification
from notifications.services import notify, notify_many

from .models import Complaint, ComplaintStatusHistory


@transaction.atomic
def submit_complaint(complaint):
    """Save a new complaint, record its first status entry and send notifications."""
    complaint.status = Complaint.Status.SUBMITTED
    complaint.save()

    ComplaintStatusHistory.objects.create(
        complaint=complaint,
        status=complaint.status,
        changed_by=complaint.citizen,
        note="Complaint submitted by citizen.",
    )

    link = reverse("complaints:detail", args=[complaint.pk])

    notify(
        recipient=complaint.citizen,
        title=f"Complaint {complaint.reference} submitted",
        message="We have received your complaint. You will be notified as it progresses.",
        category=Notification.Category.COMPLAINT,
        link=link,
    )

    admins = User.objects.filter(role=User.Role.MUNICIPAL_ADMIN, is_active=True)
    notify_many(
        admins,
        title=f"New complaint {complaint.reference}",
        message=f"{complaint.title} ({complaint.ward})",
        category=Notification.Category.COMPLAINT,
        link=link,
    )
    return complaint


def get_citizen_summary(user):
    """Complaint counts and the five latest complaints for the citizen dashboard."""
    queryset = Complaint.objects.filter(citizen=user)
    counts = queryset.aggregate(
        total=Count("id"),
        open_count=Count("id", filter=Q(status__in=Complaint.OPEN_STATUSES)),
        resolved=Count("id", filter=Q(status=Complaint.Status.RESOLVED)),
    )
    counts["recent"] = list(queryset.select_related("ward")[:5])
    return counts