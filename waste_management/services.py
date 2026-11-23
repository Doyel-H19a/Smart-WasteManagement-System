"""Business logic for collection schedules and waste movements."""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.urls import reverse

from accounts.models import User
from notifications.models import Notification
from notifications.services import notify

from .models import WasteMovement

TASK = Notification.Category.TASK
ZERO = Decimal("0.00")


class MovementError(Exception):
    """Raised when a waste movement cannot be logged."""


def _schedule_link():
    return reverse("collection:schedule_list")


def _describe(schedule):
    return f"{schedule.get_weekday_display()} {schedule.time_window} · {schedule.ward} · {schedule.route_name}"


@transaction.atomic
def save_schedule(schedule, actor, previous_worker_id=None):
    """Save a new or edited schedule and notify workers whose assignment changed.

    previous_worker_id is the worker assigned before this edit (None for new schedules).
    """
    if schedule.pk is None:
        schedule.created_by = actor
    schedule.save()

    new_id = schedule.assigned_worker_id
    if new_id and new_id != previous_worker_id:
        notify(
            schedule.assigned_worker,
            title="New collection schedule",
            message=_describe(schedule),
            category=TASK,
            link=_schedule_link(),
        )
    if previous_worker_id and previous_worker_id != new_id:
        previous = User.objects.filter(pk=previous_worker_id, is_active=True).first()
        if previous:
            notify(
                previous,
                title="Collection schedule reassigned",
                message=f"You are no longer assigned to: {_describe(schedule)}",
                category=TASK,
                link=_schedule_link(),
            )
    return schedule


@transaction.atomic
def set_schedule_active(schedule, active):
    """Activate or deactivate a schedule (schedules are never deleted)."""
    if schedule.is_active == active:
        return schedule
    schedule.is_active = active
    schedule.save(update_fields=["is_active", "updated_at"])

    worker = schedule.assigned_worker
    if worker and worker.is_active:
        notify(
            worker,
            title="Collection schedule re-activated" if active else "Collection schedule cancelled",
            message=_describe(schedule),
            category=TASK,
            link=_schedule_link(),
        )
    return schedule


@transaction.atomic
def log_movement(movement, worker):
    """Save a waste movement logged by a worker (rules are checked again here)."""
    if worker.role != User.Role.WORKER:
        raise MovementError("Only waste workers can log waste movements.")

    schedule = movement.schedule
    if schedule is not None:
        if schedule.assigned_worker_id != worker.pk:
            raise MovementError("This schedule is not assigned to you.")
        if schedule.ward_id != movement.ward_id:
            raise MovementError("The ward must match the ward of the selected schedule.")

    movement.logged_by = worker
    movement.save()
    return movement


def summarise_movements(queryset):
    """Entry count and kilograms in total and per movement type."""
    types = WasteMovement.MovementType
    data = queryset.aggregate(
        count=Count("id"),
        total_kg=Sum("quantity_kg"),
        pickup_kg=Sum("quantity_kg", filter=Q(movement_type=types.PICKUP)),
        transfer_kg=Sum("quantity_kg", filter=Q(movement_type=types.TRANSFER)),
        disposal_kg=Sum("quantity_kg", filter=Q(movement_type=types.DISPOSAL)),
    )
    for key in ("total_kg", "pickup_kg", "transfer_kg", "disposal_kg"):
        data[key] = data[key] or ZERO
    return data