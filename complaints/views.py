"""Views for the complaints app."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from accounts.models import User

from .forms import ComplaintForm
from .models import Complaint
from .services import submit_complaint

# Roles allowed to raise and list their own complaints.
COMPLAINT_REPORTER_ROLES = (User.Role.CITIZEN,)

# Roles allowed to view any complaint (read-only in Phase 2).
STAFF_VIEW_ROLES = (
    User.Role.MUNICIPAL_ADMIN,
    User.Role.HEALTH_OFFICER,
    User.Role.EXECUTIVE_OFFICER,
    User.Role.SUPER_ADMIN,
)


@role_required(*COMPLAINT_REPORTER_ROLES)
def complaint_create(request):
    """Submit a new complaint."""
    if request.method == "POST":
        form = ComplaintForm(request.POST, request.FILES)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.citizen = request.user
            submit_complaint(complaint)
            messages.success(request, f"Complaint {complaint.reference} submitted successfully.")
            return redirect(complaint)
        messages.error(request, "Please correct the errors below.")
    else:
        form = ComplaintForm()
    return render(request, "complaints/complaint_form.html", {"form": form})


@role_required(*COMPLAINT_REPORTER_ROLES)
def complaint_list(request):
    """The logged-in citizen's complaints, with a status filter and pagination."""
    complaints = Complaint.objects.filter(citizen=request.user).select_related("ward")

    selected_status = request.GET.get("status", "")
    if selected_status in Complaint.Status.values:
        complaints = complaints.filter(status=selected_status)
    else:
        selected_status = ""

    page_obj = Paginator(complaints, 10).get_page(request.GET.get("page"))

    params = request.GET.copy()
    params.pop("page", None)

    return render(
        request,
        "complaints/complaint_list.html",
        {
            "page_obj": page_obj,
            "status_choices": Complaint.Status.choices,
            "selected_status": selected_status,
            "query_string": params.urlencode(),
        },
    )


@login_required
def complaint_detail(request, pk):
    """Complaint details and timeline. Owner and staff roles only."""
    complaint = get_object_or_404(Complaint.objects.select_related("ward", "citizen"), pk=pk)
    user = request.user
    if complaint.citizen_id != user.pk and user.role not in STAFF_VIEW_ROLES:
        raise PermissionDenied("You can only view your own complaints.")

    return render(
        request,
        "complaints/complaint_detail.html",
        {
            "complaint": complaint,
            "history": complaint.history.select_related("changed_by"),
            "is_owner": complaint.citizen_id == user.pk,
        },
    )