"""Views for collection schedules and waste movement monitoring."""
from datetime import time

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from . import services
from .forms import CollectionScheduleForm, WasteMovementForm
from .models import CollectionSchedule, Ward, WasteMovement, WasteType, Weekday

# Who may create, edit and switch schedules on or off.
SCHEDULE_MANAGER_ROLES = (User.Role.MUNICIPAL_ADMIN, User.Role.SUPER_ADMIN)

# Who may open the movement list and map (a worker only sees their own entries).
MOVEMENT_VIEW_ROLES = (
    User.Role.WORKER,
    User.Role.MUNICIPAL_ADMIN,
    User.Role.HEALTH_OFFICER,
    User.Role.EXECUTIVE_OFFICER,
    User.Role.SUPER_ADMIN,
)

WORKER_ROLES = (User.Role.WORKER,)

MOVEMENT_COLORS = {"pickup": "#0d6efd", "transfer": "#fd7e14", "disposal": "#198754"}
MAX_MAP_MOVEMENTS = 300


def _int_param(raw, maximum=None):
    """A safe integer from a query-string value, or None."""
    if raw.isdecimal() and len(raw) < 10:
        number = int(raw)
        if maximum is None or number <= maximum:
            return number
    return None


def _date_param(raw):
    """A date from a query-string value (YYYY-MM-DD), or None."""
    try:
        return parse_date(raw)
    except ValueError:
        return None


def _scoped_movements(user):
    """Movements the user may see: a worker only their own, monitors everything."""
    movements = WasteMovement.objects.select_related("ward", "logged_by", "schedule")
    if user.role == User.Role.WORKER:
        movements = movements.filter(logged_by=user)
    return movements


# --- Schedules --------------------------------------------------------------
@login_required
def schedule_list(request):
    """Weekly collection schedule, scoped by role."""
    user = request.user
    can_manage = user.role in SCHEDULE_MANAGER_ROLES

    schedules = (
        CollectionSchedule.objects.select_related("ward", "assigned_worker")
        .annotate(
            last_pickup=Max(
                "movements__moved_at",
                filter=Q(movements__movement_type=WasteMovement.MovementType.PICKUP),
            )
        )
        .order_by("weekday", "start_time", "ward__ward_number")
    )
    if user.role == User.Role.WORKER:
        schedules = schedules.filter(assigned_worker=user, is_active=True)
    elif not can_manage:
        schedules = schedules.filter(is_active=True)

    ward = _int_param(request.GET.get("ward", ""))
    if ward is not None:
        schedules = schedules.filter(ward_id=ward)
    day = _int_param(request.GET.get("day", ""), maximum=6)
    if day is not None:
        schedules = schedules.filter(weekday=day)
    waste_type = request.GET.get("waste_type", "")
    if waste_type in WasteType.values:
        schedules = schedules.filter(waste_type=waste_type)
    else:
        waste_type = ""

    page_obj = Paginator(schedules, 15).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)

    today = timezone.localdate().weekday()
    return render(
        request,
        "waste_management/schedule_list.html",
        {
            "page_obj": page_obj,
            "wards": Ward.objects.all(),
            "weekday_choices": Weekday.choices,
            "waste_choices": WasteType.choices,
            "selected_ward": "" if ward is None else str(ward),
            "selected_day": "" if day is None else str(day),
            "selected_waste": waste_type,
            "query_string": params.urlencode(),
            "can_manage": can_manage,
            "is_worker": user.role == User.Role.WORKER,
            "show_ops": user.role in MOVEMENT_VIEW_ROLES,
            "today_weekday": today,
            "today_label": Weekday(today).label,
        },
    )


@role_required(*SCHEDULE_MANAGER_ROLES)
def schedule_create(request):
    """Add a schedule."""
    if request.method == "POST":
        form = CollectionScheduleForm(request.POST)
        if form.is_valid():
            schedule = services.save_schedule(form.save(commit=False), request.user)
            messages.success(request, f"Schedule created: {schedule}.")
            return redirect("collection:schedule_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = CollectionScheduleForm(
            initial={"is_active": True, "start_time": time(6, 0), "end_time": time(9, 0)}
        )
    return render(
        request,
        "waste_management/schedule_form.html",
        {"form": form, "page_title": "Add Collection Schedule", "is_edit": False},
    )


@role_required(*SCHEDULE_MANAGER_ROLES)
def schedule_update(request, pk):
    """Edit a schedule; workers whose assignment changes are notified."""
    schedule = get_object_or_404(CollectionSchedule, pk=pk)
    previous_worker_id = schedule.assigned_worker_id  # read before the form changes the object
    if request.method == "POST":
        form = CollectionScheduleForm(request.POST, instance=schedule)
        if form.is_valid():
            services.save_schedule(form.save(commit=False), request.user, previous_worker_id)
            messages.success(request, "Schedule updated.")
            return redirect("collection:schedule_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = CollectionScheduleForm(instance=schedule)
    return render(
        request,
        "waste_management/schedule_form.html",
        {"form": form, "page_title": "Edit Collection Schedule", "is_edit": True},
    )


@role_required(*SCHEDULE_MANAGER_ROLES)
@require_POST
def schedule_toggle(request, pk):
    """Switch a schedule on or off."""
    schedule = get_object_or_404(CollectionSchedule.objects.select_related("assigned_worker"), pk=pk)
    services.set_schedule_active(schedule, not schedule.is_active)
    state = "activated" if schedule.is_active else "deactivated"
    messages.success(request, f"Schedule {state}.")
    return redirect("collection:schedule_list")


# --- Waste movements --------------------------------------------------------
@role_required(*MOVEMENT_VIEW_ROLES)
def movement_list(request):
    """Waste movement log with filters and totals."""
    user = request.user
    movements = _scoped_movements(user)

    movement_type = request.GET.get("type", "")
    if movement_type in WasteMovement.MovementType.values:
        movements = movements.filter(movement_type=movement_type)
    else:
        movement_type = ""

    waste_type = request.GET.get("waste_type", "")
    if waste_type in WasteType.values:
        movements = movements.filter(waste_type=waste_type)
    else:
        waste_type = ""

    ward = _int_param(request.GET.get("ward", ""))
    if ward is not None:
        movements = movements.filter(ward_id=ward)

    date_from = _date_param(request.GET.get("from", ""))
    if date_from:
        movements = movements.filter(moved_at__date__gte=date_from)
    date_to = _date_param(request.GET.get("to", ""))
    if date_to:
        movements = movements.filter(moved_at__date__lte=date_to)

    summary = services.summarise_movements(movements)
    page_obj = Paginator(movements, 15).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)

    return render(
        request,
        "waste_management/movement_list.html",
        {
            "page_obj": page_obj,
            "summary": summary,
            "wards": Ward.objects.all(),
            "type_choices": WasteMovement.MovementType.choices,
            "waste_choices": WasteType.choices,
            "selected_type": movement_type,
            "selected_waste": waste_type,
            "selected_ward": "" if ward is None else str(ward),
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
            "query_string": params.urlencode(),
            "is_worker": user.role == User.Role.WORKER,
        },
    )


def _initial_from_schedule(request):
    """Pre-fill the log form from ?schedule=<id> (only the worker's own active schedules)."""
    schedule_id = _int_param(request.GET.get("schedule", ""))
    if schedule_id is None:
        return {}
    schedule = CollectionSchedule.objects.filter(
        pk=schedule_id, assigned_worker=request.user, is_active=True
    ).first()
    if schedule is None:
        return {}
    return {
        "schedule": schedule.pk,
        "ward": schedule.ward_id,
        "waste_type": schedule.waste_type,
        "vehicle_number": schedule.vehicle_number,
        "movement_type": WasteMovement.MovementType.PICKUP,
        "from_location": schedule.route_name,
    }


@role_required(*WORKER_ROLES)
def movement_create(request):
    """A worker logs a pickup, transfer or disposal."""
    if request.method == "POST":
        form = WasteMovementForm(request.POST, worker=request.user)
        if form.is_valid():
            try:
                movement = services.log_movement(form.save(commit=False), request.user)
                messages.success(
                    request,
                    f"Logged: {movement.get_movement_type_display()}, {movement.quantity_kg} kg.",
                )
                return redirect("collection:movement_list")
            except services.MovementError as error:
                messages.error(request, str(error))
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = WasteMovementForm(worker=request.user, initial=_initial_from_schedule(request))
    return render(request, "waste_management/movement_form.html", {"form": form})


@role_required(*MOVEMENT_VIEW_ROLES)
def movement_map(request):
    """Leaflet map of located waste movements, scoped by role."""
    movements = _scoped_movements(request.user)
    located = movements.filter(latitude__isnull=False, longitude__isnull=False)
    missing_count = movements.count() - located.count()

    data = [
        {
            "type": m.movement_type,
            "type_label": m.get_movement_type_display(),
            "waste": m.get_waste_type_display(),
            "kg": str(m.quantity_kg),
            "ward": str(m.ward),
            "from": m.from_location,
            "to": m.to_location,
            "when": timezone.localtime(m.moved_at).strftime("%d %b %Y, %H:%M"),
            "by": m.logged_by.display_name,
            "lat": float(m.latitude),
            "lng": float(m.longitude),
        }
        for m in located[:MAX_MAP_MOVEMENTS]
    ]
    legend = [
        {"label": label, "color": MOVEMENT_COLORS[value]}
        for value, label in WasteMovement.MovementType.choices
    ]
    return render(
        request,
        "waste_management/movement_map.html",
        {
            "map_data": {"movements": data, "colors": MOVEMENT_COLORS},
            "type_choices": WasteMovement.MovementType.choices,
            "legend": legend,
            "shown_count": len(data),
            "missing_count": missing_count,
        },
    )