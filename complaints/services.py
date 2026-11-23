"""Business logic for complaints (kept separate from the views)."""
from django.db import transaction
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from notifications.models import Notification
from notifications.services import notify, notify_many

from .models import Complaint, ComplaintStatusHistory

Status = Complaint.Status
COMPLAINT = Notification.Category.COMPLAINT
TASK = Notification.Category.TASK


class WorkflowError(Exception):
    """Raised when an action is not allowed in the complaint's current state."""


# --- Small internal helpers -------------------------------------------------
def _lock(complaint):
    """Re-read the complaint inside the transaction (row-locked on PostgreSQL)."""
    return Complaint.objects.select_for_update().get(pk=complaint.pk)


def _require_status(complaint, allowed, action):
    if complaint.status not in allowed:
        raise WorkflowError(
            f"Cannot {action}: the complaint is currently "
            f"'{complaint.get_status_display()}'."
        )


def _require_assigned_to(complaint, worker):
    if complaint.assigned_worker_id != worker.pk:
        raise WorkflowError("This task is not assigned to you.")


def _record(complaint, actor, note=""):
    """Add a timeline entry for the complaint's current status."""
    ComplaintStatusHistory.objects.create(
        complaint=complaint,
        status=complaint.status,
        changed_by=actor,
        note=note[:255],
    )


def _notify_citizen(complaint, title, message=""):
    notify(
        complaint.citizen,
        title=title,
        message=message,
        category=COMPLAINT,
        link=reverse("complaints:detail", args=[complaint.pk]),
    )


def _admin_link(complaint):
    return reverse("admin_dashboard:complaint_detail", args=[complaint.pk])


def _worker_link(complaint):
    return reverse("worker:task_detail", args=[complaint.pk])


# --- Citizen step -----------------------------------------------------------
@transaction.atomic
def submit_complaint(complaint):
    """Save a new complaint, record its first status entry and send notifications."""
    complaint.status = Status.SUBMITTED
    complaint.save()

    _record(complaint, complaint.citizen, "Complaint submitted by citizen.")

    _notify_citizen(
        complaint,
        f"Complaint {complaint.reference} submitted",
        "We have received your complaint. You will be notified as it progresses.",
    )

    admins = User.objects.filter(role=User.Role.MUNICIPAL_ADMIN, is_active=True)
    notify_many(
        admins,
        title=f"New complaint {complaint.reference}",
        message=f"{complaint.title} ({complaint.ward})",
        category=COMPLAINT,
        link=_admin_link(complaint),
    )
    return complaint


# --- Admin steps ------------------------------------------------------------
@transaction.atomic
def start_review(complaint, admin):
    """Submitted -> Under review."""
    complaint = _lock(complaint)
    _require_status(complaint, (Status.SUBMITTED,), "start a review")

    complaint.status = Status.UNDER_REVIEW
    complaint.save()
    _record(complaint, admin, "Complaint is being reviewed by the municipal office.")
    _notify_citizen(
        complaint,
        f"Complaint {complaint.reference} is under review",
        "A municipal officer has started reviewing your complaint.",
    )
    return complaint


@transaction.atomic
def reject_complaint(complaint, admin, reason):
    """Submitted or Under review -> Rejected (a reason is required)."""
    complaint = _lock(complaint)
    _require_status(complaint, (Status.SUBMITTED, Status.UNDER_REVIEW), "reject")
    if not reason:
        raise WorkflowError("A reason is required to reject a complaint.")

    complaint.status = Status.REJECTED
    complaint.save()
    _record(complaint, admin, f"Rejected: {reason}")
    _notify_citizen(
        complaint,
        f"Complaint {complaint.reference} was rejected",
        f"Reason: {reason}",
    )
    return complaint


@transaction.atomic
def assign_worker(complaint, admin, worker, priority, instructions=""):
    """Under review (or Assigned, for reassignment) -> Worker assigned."""
    complaint = _lock(complaint)
    _require_status(complaint, (Status.UNDER_REVIEW, Status.ASSIGNED), "assign a worker")
    if worker.role != User.Role.WORKER or not worker.is_active:
        raise WorkflowError("Only active waste workers can be assigned.")

    previous = complaint.assigned_worker  # may be None
    reassigned = previous is not None and previous.pk != worker.pk

    complaint.assigned_worker = worker
    complaint.assigned_by = admin
    complaint.assigned_at = timezone.now()
    complaint.priority = priority
    complaint.admin_note = instructions
    complaint.status = Status.ASSIGNED
    complaint.save()

    note = f"Assigned to {worker.display_name}" + (" (reassigned)" if reassigned else "") + "."
    _record(complaint, admin, note)

    notify(
        worker,
        title=f"New task {complaint.reference}",
        message=f"{complaint.title} – {complaint.address}",
        category=TASK,
        link=_worker_link(complaint),
    )
    if reassigned:
        notify(
            previous,
            title=f"Task {complaint.reference} was reassigned",
            message="This complaint has been given to another worker.",
            category=TASK,
            link=reverse("worker:task_list"),
        )
    _notify_citizen(
        complaint,
        f"A worker was assigned to {complaint.reference}",
        f"{worker.display_name} will handle your complaint.",
    )
    return complaint


@transaction.atomic
def verify_completion(complaint, admin, note=""):
    """Completed -> Resolved. The citizen and the worker are notified."""
    complaint = _lock(complaint)
    _require_status(complaint, (Status.COMPLETED,), "verify completion")

    complaint.status = Status.RESOLVED
    complaint.resolved_at = timezone.now()
    complaint.save()
    _record(complaint, admin, note or "Completion verified by the municipal office.")

    _notify_citizen(
        complaint,
        f"Complaint {complaint.reference} resolved",
        "Your complaint has been resolved and verified. Thank you for reporting it.",
    )
    if complaint.assigned_worker:
        notify(
            complaint.assigned_worker,
            title=f"Task {complaint.reference} verified",
            message="The municipal office verified your work.",
            category=TASK,
            link=_worker_link(complaint),
        )
    return complaint


@transaction.atomic
def request_rework(complaint, admin, reason):
    """Completed -> Accepted again: the admin is not satisfied with the proof."""
    complaint = _lock(complaint)
    _require_status(complaint, (Status.COMPLETED,), "send back for rework")
    if not reason:
        raise WorkflowError("A reason is required to send a task back.")

    complaint.status = Status.ACCEPTED
    complaint.completed_at = None
    complaint.save()
    _record(complaint, admin, f"Sent back for rework: {reason}")

    if complaint.assigned_worker:
        notify(
            complaint.assigned_worker,
            title=f"Task {complaint.reference} needs more work",
            message=f"Reason: {reason}",
            category=TASK,
            link=_worker_link(complaint),
        )
    return complaint


# --- Worker steps -----------------------------------------------------------
@transaction.atomic
def accept_assignment(complaint, worker):
    """Worker assigned -> Accepted by worker."""
    complaint = _lock(complaint)
    _require_assigned_to(complaint, worker)
    _require_status(complaint, (Status.ASSIGNED,), "accept this task")

    complaint.status = Status.ACCEPTED
    complaint.accepted_at = timezone.now()
    complaint.save()
    _record(complaint, worker, f"Accepted by {worker.display_name}.")

    _notify_citizen(
        complaint,
        f"Work started on {complaint.reference}",
        f"{worker.display_name} accepted the task.",
    )
    if complaint.assigned_by and complaint.assigned_by.is_active:
        notify(
            complaint.assigned_by,
            title=f"Task {complaint.reference} accepted",
            message=f"{worker.display_name} accepted the assignment.",
            category=TASK,
            link=_admin_link(complaint),
        )
    return complaint


@transaction.atomic
def complete_task(complaint, worker, note, proof_image):
    """Accepted -> Completed. A proof photo is required; the admin is asked to verify."""
    complaint = _lock(complaint)
    _require_assigned_to(complaint, worker)
    _require_status(complaint, (Status.ACCEPTED,), "complete this task")
    if not proof_image:
        raise WorkflowError("A proof photo is required to complete the task.")

    complaint.completion_note = note
    complaint.proof_image = proof_image
    complaint.completed_at = timezone.now()
    complaint.status = Status.COMPLETED
    complaint.save()
    _record(complaint, worker, f"Work completed by {worker.display_name}. Proof uploaded.")

    if complaint.assigned_by and complaint.assigned_by.is_active:
        recipients = [complaint.assigned_by]
    else:
        recipients = list(User.objects.filter(role=User.Role.MUNICIPAL_ADMIN, is_active=True))
    notify_many(
        recipients,
        title=f"Verify completion of {complaint.reference}",
        message=f"{worker.display_name} uploaded proof of completion.",
        category=TASK,
        link=_admin_link(complaint),
    )
    _notify_citizen(
        complaint,
        f"Work completed on {complaint.reference}",
        "The work is done and is now awaiting verification by the municipal office.",
    )
    return complaint


# --- Dashboard summaries ----------------------------------------------------
def get_citizen_summary(user):
    """Complaint counts and the five latest complaints for the citizen dashboard."""
    queryset = Complaint.objects.filter(citizen=user)
    counts = queryset.aggregate(
        total=Count("id"),
        open_count=Count("id", filter=Q(status__in=Complaint.OPEN_STATUSES)),
        resolved=Count("id", filter=Q(status=Status.RESOLVED)),
    )
    counts["recent"] = list(queryset.select_related("ward")[:5])
    return counts


def get_admin_summary():
    """City-wide complaint counts and the complaints that need an admin's action."""
    counts = Complaint.objects.aggregate(
        total=Count("id"),
        submitted=Count("id", filter=Q(status=Status.SUBMITTED)),
        under_review=Count("id", filter=Q(status=Status.UNDER_REVIEW)),
        in_progress=Count("id", filter=Q(status__in=(Status.ASSIGNED, Status.ACCEPTED))),
        awaiting_verification=Count("id", filter=Q(status=Status.COMPLETED)),
        resolved=Count("id", filter=Q(status=Status.RESOLVED)),
    )
    counts["needs_action"] = list(
        Complaint.objects.filter(
            status__in=(Status.SUBMITTED, Status.UNDER_REVIEW, Status.COMPLETED)
        )
        .select_related("ward", "citizen")
        .order_by("created_at")[:5]
    )
    return counts


def get_worker_summary(user):
    """Task counts and the five most recent active tasks for a worker."""
    queryset = Complaint.objects.filter(assigned_worker=user)
    counts = queryset.aggregate(
        to_accept=Count("id", filter=Q(status=Status.ASSIGNED)),
        in_progress=Count("id", filter=Q(status=Status.ACCEPTED)),
        awaiting_verification=Count("id", filter=Q(status=Status.COMPLETED)),
        verified=Count("id", filter=Q(status=Status.RESOLVED)),
    )
    counts["tasks"] = list(
        queryset.filter(status__in=(Status.ASSIGNED, Status.ACCEPTED))
        .select_related("ward")
        .order_by("-assigned_at")[:5]
    )
    return counts