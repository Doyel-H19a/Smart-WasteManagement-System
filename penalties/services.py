"""Business logic for penalties (kept separate from the views)."""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from notifications.models import Notification
from notifications.services import notify, notify_many

from .models import Penalty, PenaltyEvent

Status = Penalty.Status
SYSTEM = Notification.Category.SYSTEM
ZERO = Decimal("0.00")

ISSUER_ROLES = (User.Role.HEALTH_OFFICER, User.Role.MUNICIPAL_ADMIN)
RESOLVER_ROLES = (User.Role.MUNICIPAL_ADMIN, User.Role.SUPER_ADMIN)
RECIPIENT_ROLES = (User.Role.CITIZEN, User.Role.BULK_GENERATOR)


class PenaltyError(Exception):
    """Raised when a penalty action is not allowed."""


# --- Small internal helpers -------------------------------------------------
def _lock(penalty):
    """Re-read the penalty inside the transaction (row-locked on PostgreSQL)."""
    return Penalty.objects.select_for_update().get(pk=penalty.pk)


def _require_status(penalty, allowed, action):
    if penalty.status not in allowed:
        raise PenaltyError(
            f"Cannot {action}: the penalty is currently '{penalty.get_status_display()}'."
        )


def _require_resolver(actor):
    if actor.role not in RESOLVER_ROLES or not actor.is_active:
        raise PenaltyError("Only municipal admins and super admins can do this.")


def _require_not_issuer(penalty, actor):
    """Nobody may decide on a penalty they issued themselves."""
    if penalty.issued_by_id == actor.pk:
        raise PenaltyError("You issued this penalty, so another officer must decide on it.")


def _require_text(value, message):
    value = (value or "").strip()
    if not value:
        raise PenaltyError(message)
    return value


def _record(penalty, actor, note=""):
    PenaltyEvent.objects.create(
        penalty=penalty, status=penalty.status, actor=actor, note=note[:255]
    )


def _link(penalty):
    return reverse("penalties:detail", args=[penalty.pk])


def _money(amount):
    return f"₹{amount:.2f}"


def _notify_recipient(penalty, title, message):
    notify(penalty.issued_to, title=title, message=message, category=SYSTEM, link=_link(penalty))


def _notify_issuer(penalty, actor, title, message):
    issuer = penalty.issued_by
    if issuer.is_active and issuer.pk != actor.pk:
        notify(issuer, title=title, message=message, category=SYSTEM, link=_link(penalty))


def _alert_staff(penalty, exclude_pk, title, message):
    """Notify active municipal admins and the issuer (except the person acting)."""
    people = {u.pk: u for u in User.objects.filter(role=User.Role.MUNICIPAL_ADMIN, is_active=True)}
    issuer = penalty.issued_by
    if issuer.is_active:
        people[issuer.pk] = issuer
    people.pop(exclude_pk, None)
    notify_many(list(people.values()), title=title, message=message, category=SYSTEM, link=_link(penalty))


# --- Issuing ----------------------------------------------------------------
@transaction.atomic
def issue_penalty(penalty, actor):
    """Save a new penalty as 'Issued' and notify the person penalised."""
    if actor.role not in ISSUER_ROLES or not actor.is_active:
        raise PenaltyError("Only health officers and municipal admins can issue penalties.")

    recipient = penalty.issued_to
    if recipient.role not in RECIPIENT_ROLES or not recipient.is_active:
        raise PenaltyError("Penalties can only be issued to active citizens and bulk waste generators.")
    if penalty.amount is None or penalty.amount <= 0:
        raise PenaltyError("The penalty amount must be greater than zero.")

    inspection = penalty.inspection
    if inspection is not None:
        if inspection.ward_id != penalty.ward_id:
            raise PenaltyError("The ward must match the ward of the linked inspection.")
        if inspection.bulk_generator_id and inspection.bulk_generator_id != recipient.pk:
            raise PenaltyError("This inspection was of another generator's premises.")

    penalty.issued_by = actor
    penalty.status = Status.ISSUED
    penalty.save()
    _record(
        penalty, actor,
        f"Penalty of {_money(penalty.amount)} issued. Due {penalty.due_date:%d %b %Y}.",
    )
    _notify_recipient(
        penalty,
        f"Penalty {penalty.reference} issued",
        f"{_money(penalty.amount)} – {penalty.get_violation_type_display()}. "
        f"Due by {penalty.due_date:%d %b %Y}. You can dispute it from the penalty page.",
    )
    return penalty


# --- The person penalised ---------------------------------------------------
@transaction.atomic
def dispute_penalty(penalty, user, reason):
    """Issued -> Under dispute. Only the recipient, and only once."""
    penalty = _lock(penalty)
    if penalty.issued_to_id != user.pk:
        raise PenaltyError("Only the person who was penalised can dispute it.")
    _require_status(penalty, (Status.ISSUED,), "dispute this penalty")
    if penalty.disputed_at is not None:
        raise PenaltyError("This penalty was already disputed once and cannot be disputed again.")
    reason = _require_text(reason, "Please explain why you are disputing this penalty.")

    penalty.status = Status.DISPUTED
    penalty.dispute_reason = reason
    penalty.disputed_at = timezone.now()
    penalty.save()
    _record(penalty, user, f"Disputed: {reason}")
    _alert_staff(
        penalty, user.pk,
        f"Penalty {penalty.reference} disputed",
        f"{user.display_name} disputed a penalty of {_money(penalty.amount)}.",
    )
    return penalty


# --- The municipal office ---------------------------------------------------
@transaction.atomic
def record_payment(penalty, actor, reference):
    """Issued -> Paid, with a receipt reference. Payments are never processed online."""
    penalty = _lock(penalty)
    _require_resolver(actor)
    _require_status(penalty, (Status.ISSUED,), "record a payment")
    reference = _require_text(reference, "A receipt or reference number is required.")

    penalty.status = Status.PAID
    penalty.paid_at = timezone.now()
    penalty.payment_reference = reference
    penalty.recorded_by = actor
    penalty.save()
    _record(penalty, actor, f"Payment of {_money(penalty.amount)} recorded. Reference: {reference}.")
    _notify_recipient(
        penalty,
        f"Payment recorded for {penalty.reference}",
        f"We recorded your payment of {_money(penalty.amount)}. Reference: {reference}.",
    )
    _notify_issuer(
        penalty, actor,
        f"Penalty {penalty.reference} paid",
        f"Payment of {_money(penalty.amount)} was recorded.",
    )
    return penalty


@transaction.atomic
def reject_dispute(penalty, actor, note, new_due_date):
    """Under dispute -> Issued again (the penalty stands), with a new due date."""
    penalty = _lock(penalty)
    _require_resolver(actor)
    _require_not_issuer(penalty, actor)
    _require_status(penalty, (Status.DISPUTED,), "reject a dispute")
    note = _require_text(note, "A reason is required to reject a dispute.")
    if new_due_date is None or new_due_date < timezone.localdate():
        raise PenaltyError("Choose a new due date that is today or later.")

    penalty.status = Status.ISSUED
    penalty.due_date = new_due_date
    penalty.resolution_note = note[:255]
    penalty.resolved_by = actor
    penalty.resolved_at = timezone.now()
    penalty.save()
    _record(penalty, actor, f"Dispute rejected: {note} New due date {new_due_date:%d %b %Y}.")
    _notify_recipient(
        penalty,
        f"Dispute rejected for {penalty.reference}",
        f"The penalty stands. Reason: {note}. New due date: {new_due_date:%d %b %Y}.",
    )
    _notify_issuer(
        penalty, actor,
        f"Dispute rejected for {penalty.reference}",
        f"The penalty stands. Reason: {note}",
    )
    return penalty


def _resolve(penalty, actor, new_status, reason, action, past_tense):
    """Shared by waive and cancel: Issued or Under dispute -> a final status."""
    penalty = _lock(penalty)
    _require_resolver(actor)
    _require_not_issuer(penalty, actor)
    _require_status(penalty, Penalty.OPEN_STATUSES, action)
    reason = _require_text(reason, f"A reason is required to {action}.")

    penalty.status = new_status
    penalty.resolution_note = reason[:255]
    penalty.resolved_by = actor
    penalty.resolved_at = timezone.now()
    penalty.save()
    _record(penalty, actor, f"{past_tense.capitalize()}: {reason}")
    _notify_recipient(
        penalty, f"Penalty {penalty.reference} {past_tense}", f"Reason: {reason}"
    )
    _notify_issuer(
        penalty, actor, f"Penalty {penalty.reference} {past_tense}", f"Reason: {reason}"
    )
    return penalty


@transaction.atomic
def waive_penalty(penalty, actor, reason):
    """Issued or Under dispute -> Waived (the amount is no longer owed)."""
    return _resolve(penalty, actor, Status.WAIVED, reason, "waive this penalty", "waived")


@transaction.atomic
def cancel_penalty(penalty, actor, reason):
    """Issued or Under dispute -> Cancelled (for example, issued in error)."""
    return _resolve(penalty, actor, Status.CANCELLED, reason, "cancel this penalty", "cancelled")


# --- Summaries --------------------------------------------------------------
def summarise_penalties(queryset):
    """Counts and rupee totals for a set of penalties."""
    today = timezone.localdate()
    data = queryset.aggregate(
        count=Count("id"),
        issued_count=Count("id", filter=Q(status=Status.ISSUED)),
        disputed_count=Count("id", filter=Q(status=Status.DISPUTED)),
        paid_count=Count("id", filter=Q(status=Status.PAID)),
        overdue_count=Count("id", filter=Q(status=Status.ISSUED, due_date__lt=today)),
        outstanding=Sum("amount", filter=Q(status=Status.ISSUED)),
        disputed_amount=Sum("amount", filter=Q(status=Status.DISPUTED)),
        collected=Sum("amount", filter=Q(status=Status.PAID)),
    )
    for key in ("outstanding", "disputed_amount", "collected"):
        data[key] = data[key] or ZERO
    return data