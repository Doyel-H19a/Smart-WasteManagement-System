"""Views for ward management and the complaint map."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.decorators import role_required
from accounts.models import User
from complaints.models import Complaint

from .forms import WardForm
from .models import Ward

WARD_MANAGER_ROLES = (User.Role.MUNICIPAL_ADMIN, User.Role.SUPER_ADMIN)

# Roles that see every complaint and all ward areas on the map.
MAP_OVERVIEW_ROLES = (
    User.Role.MUNICIPAL_ADMIN,
    User.Role.HEALTH_OFFICER,
    User.Role.EXECUTIVE_OFFICER,
    User.Role.SUPER_ADMIN,
)

# One colour per status; also used for the legend.
STATUS_COLORS = {
    "submitted": "#6c757d",
    "under_review": "#0dcaf0",
    "assigned": "#0d6efd",
    "accepted": "#6610f2",
    "completed": "#ffc107",
    "resolved": "#198754",
    "rejected": "#dc3545",
}

MAX_MAP_COMPLAINTS = 500


@role_required(*WARD_MANAGER_ROLES)
def ward_list(request):
    """List all wards with the number of complaints raised in each."""
    wards = Ward.objects.annotate(complaint_count=Count("complaints"))
    return render(
        request,
        "waste_management/ward_list.html",
        {"wards": wards, "page_title": "Ward Management"},
    )


@role_required(*WARD_MANAGER_ROLES)
def ward_create(request):
    """Add a new ward."""
    if request.method == "POST":
        form = WardForm(request.POST)
        if form.is_valid():
            ward = form.save()
            messages.success(request, f"{ward} was created.")
            return redirect("waste_management:ward_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = WardForm(initial={"is_active": True})
    return render(
        request,
        "waste_management/ward_form.html",
        {"form": form, "page_title": "Add Ward", "is_edit": False},
    )


@role_required(*WARD_MANAGER_ROLES)
def ward_update(request, pk):
    """Edit an existing ward."""
    ward = get_object_or_404(Ward, pk=pk)
    if request.method == "POST":
        form = WardForm(request.POST, instance=ward)
        if form.is_valid():
            form.save()
            messages.success(request, f"{ward} was updated.")
            return redirect("waste_management:ward_list")
        messages.error(request, "Please correct the errors below.")
    else:
        form = WardForm(instance=ward)
    return render(
        request,
        "waste_management/ward_form.html",
        {"form": form, "page_title": f"Edit {ward}", "is_edit": True},
    )


def _complaint_url(user, complaint):
    """The detail page that is right for this role."""
    if user.role in WARD_MANAGER_ROLES:
        return reverse("admin_dashboard:complaint_detail", args=[complaint.pk])
    if user.role == User.Role.WORKER:
        return reverse("worker:task_detail", args=[complaint.pk])
    return complaint.get_absolute_url()


@login_required
def complaint_map(request):
    """Leaflet map of complaints (and ward areas for staff), scoped by role."""
    user = request.user
    base = Complaint.objects.select_related("ward")
    overview = user.role in MAP_OVERVIEW_ROLES

    if overview:
        pass  # sees everything
    elif user.role == User.Role.WORKER:
        base = base.filter(assigned_worker=user)
    elif user.role == User.Role.CITIZEN:
        base = base.filter(citizen=user)
    else:
        raise PermissionDenied("The map is not available for your role.")

    located = base.filter(latitude__isnull=False, longitude__isnull=False)
    missing_count = base.count() - located.count()

    complaints = [
        {
            "id": c.pk,
            "ref": c.reference,
            "title": c.title,
            "status": c.status,
            "status_label": c.get_status_display(),
            "ward": str(c.ward),
            "lat": float(c.latitude),
            "lng": float(c.longitude),
            "url": _complaint_url(user, c),
        }
        for c in located.order_by("-created_at")[:MAX_MAP_COMPLAINTS]
    ]

    wards = []
    if overview:
        ward_qs = Ward.objects.filter(latitude__isnull=False, longitude__isnull=False).annotate(
            open_count=Count("complaints", filter=Q(complaints__status__in=Complaint.OPEN_STATUSES)),
            total_count=Count("complaints"),
        )
        wards = [
            {
                "number": w.ward_number,
                "name": w.name,
                "zone": w.zone,
                "lat": float(w.latitude),
                "lng": float(w.longitude),
                "open": w.open_count,
                "total": w.total_count,
            }
            for w in ward_qs
        ]

    legend = [
        {"label": label, "color": STATUS_COLORS[value]} for value, label in Complaint.Status.choices
    ]

    return render(
        request,
        "waste_management/map.html",
        {
            "map_data": {"complaints": complaints, "wards": wards, "colors": STATUS_COLORS},
            "status_choices": Complaint.Status.choices,
            "legend": legend,
            "missing_count": missing_count,
            "shown_count": len(complaints),
            "show_wards": overview,
        },
    )