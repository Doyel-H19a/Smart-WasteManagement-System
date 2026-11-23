"""Views for inspections."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from accounts.utils import date_param, int_param
from penalties.services import ISSUER_ROLES as PENALTY_ISSUER_ROLES
from waste_management.models import Ward

from . import services
from .forms import InspectionForm
from .models import Inspection
from .services import INSPECTOR_ROLES

# Staff who may see every inspection (a bulk generator sees only their own premises).
STAFF_ROLES = (
    User.Role.HEALTH_OFFICER,
    User.Role.MUNICIPAL_ADMIN,
    User.Role.EXECUTIVE_OFFICER,
    User.Role.SUPER_ADMIN,
)
VIEW_ROLES = STAFF_ROLES + (User.Role.BULK_GENERATOR,)


@role_required(*VIEW_ROLES)
def inspection_list(request):
    """Inspections with filters and summary cards, scoped by role."""
    user = request.user
    is_generator = user.role == User.Role.BULK_GENERATOR

    inspections = Inspection.objects.select_related("ward", "inspector", "bulk_generator")
    if is_generator:
        inspections = inspections.filter(bulk_generator=user)

    outcome = request.GET.get("outcome", "")
    if outcome in Inspection.Outcome.values:
        inspections = inspections.filter(outcome=outcome)
    else:
        outcome = ""

    category = request.GET.get("category", "")
    if category in Inspection.Category.values:
        inspections = inspections.filter(category=category)
    else:
        category = ""

    ward = int_param(request.GET.get("ward", ""))
    if ward is not None:
        inspections = inspections.filter(ward_id=ward)

    date_from = date_param(request.GET.get("from", ""))
    if date_from:
        inspections = inspections.filter(inspection_date__gte=date_from)
    date_to = date_param(request.GET.get("to", ""))
    if date_to:
        inspections = inspections.filter(inspection_date__lte=date_to)

    follow_up = request.GET.get("follow_up", "")
    if follow_up == "pending":
        inspections = inspections.filter(follow_up_required=True, follow_up_completed_at__isnull=True)
    else:
        follow_up = ""

    summary = services.summarise_inspections(inspections)
    page_obj = Paginator(inspections, 15).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)

    return render(
        request,
        "inspections/list.html",
        {
            "page_obj": page_obj,
            "summary": summary,
            "wards": Ward.objects.all(),
            "outcome_choices": Inspection.Outcome.choices,
            "category_choices": Inspection.Category.choices,
            "selected_outcome": outcome,
            "selected_category": category,
            "selected_ward": "" if ward is None else str(ward),
            "selected_follow_up": follow_up,
            "date_from": date_from.isoformat() if date_from else "",
            "date_to": date_to.isoformat() if date_to else "",
            "query_string": params.urlencode(),
            "is_generator": is_generator,
            "can_record": user.role in INSPECTOR_ROLES,
        },
    )


@role_required(*INSPECTOR_ROLES)
def inspection_create(request):
    """A Health Officer records an inspection."""
    if request.method == "POST":
        form = InspectionForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                inspection = services.record_inspection(form.save(commit=False), request.user)
                messages.success(request, f"Inspection {inspection.reference} recorded.")
                return redirect(inspection)
            except services.InspectionError as error:
                messages.error(request, str(error))
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = InspectionForm()
    return render(request, "inspections/form.html", {"form": form})


@login_required
def inspection_detail(request, pk):
    """One inspection. Staff see all; a generator only their own premises."""
    inspection = get_object_or_404(
        Inspection.objects.select_related(
            "ward", "inspector", "bulk_generator", "follow_up_completed_by"
        ),
        pk=pk,
    )
    user = request.user
    is_generator = user.role == User.Role.BULK_GENERATOR
    if is_generator:
        if inspection.bulk_generator_id != user.pk:
            raise PermissionDenied("You can only view inspections of your own premises.")
    elif user.role not in STAFF_ROLES:
        raise PermissionDenied("You do not have permission to view inspections.")

    penalties = inspection.penalties.select_related("issued_to")
    if is_generator:
        penalties = penalties.filter(issued_to=user)

    return render(
        request,
        "inspections/detail.html",
        {
            "inspection": inspection,
            "penalties": penalties,
            "can_issue_penalty": user.role in PENALTY_ISSUER_ROLES,
            "can_complete_follow_up": user.role in INSPECTOR_ROLES and inspection.follow_up_pending,
        },
    )


@role_required(*INSPECTOR_ROLES)
@require_POST
def follow_up_done(request, pk):
    """Mark the follow-up visit as completed."""
    inspection = get_object_or_404(Inspection, pk=pk)
    try:
        services.complete_follow_up(inspection, request.user)
        messages.success(request, f"Follow-up for {inspection.reference} marked as completed.")
    except services.InspectionError as error:
        messages.error(request, str(error))
    return redirect(inspection)