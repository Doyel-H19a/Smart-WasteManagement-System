"""Views for the Municipal Admin review console."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from complaints import services
from complaints.models import Complaint
from waste_management.models import Ward

from .forms import AssignWorkerForm, ReasonForm, VerifyForm

ADMIN_ROLES = (User.Role.MUNICIPAL_ADMIN, User.Role.SUPER_ADMIN)
DETAIL_TEMPLATE = "admin_dashboard/complaint_detail.html"


def _get_complaint(pk):
    return get_object_or_404(
        Complaint.objects.select_related("ward", "citizen", "assigned_worker", "assigned_by"),
        pk=pk,
    )


def _detail_context(complaint, **bound_forms):
    """Template context for the console; bound (invalid) forms replace the blank ones."""
    context = {
        "complaint": complaint,
        "history": complaint.history.select_related("changed_by"),
        "assign_form": AssignWorkerForm(
            prefix="assign",
            initial={
                "worker": complaint.assigned_worker_id,
                "priority": complaint.priority,
                "instructions": complaint.admin_note,
            },
        ),
        "reject_form": ReasonForm(prefix="reject"),
        "rework_form": ReasonForm(prefix="rework"),
        "verify_form": VerifyForm(prefix="verify"),
    }
    context.update(bound_forms)
    return context


@role_required(*ADMIN_ROLES)
def complaint_queue(request):
    """All complaints with status, ward and text filters."""
    complaints = Complaint.objects.select_related("ward", "citizen", "assigned_worker")

    status = request.GET.get("status", "")
    if status in Complaint.Status.values:
        complaints = complaints.filter(status=status)
    else:
        status = ""

    ward = request.GET.get("ward", "")
    if ward.isdigit() and len(ward) < 10:
        complaints = complaints.filter(ward_id=int(ward))
    else:
        ward = ""

    query = request.GET.get("q", "").strip()
    if query:
        complaints = complaints.filter(
            Q(title__icontains=query)
            | Q(address__icontains=query)
            | Q(citizen__username__icontains=query)
        )

    page_obj = Paginator(complaints, 10).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)

    return render(
        request,
        "admin_dashboard/queue.html",
        {
            "page_obj": page_obj,
            "status_choices": Complaint.Status.choices,
            "wards": Ward.objects.all(),
            "selected_status": status,
            "selected_ward": ward,
            "q": query,
            "query_string": params.urlencode(),
        },
    )


@role_required(*ADMIN_ROLES)
def complaint_detail(request, pk):
    """The review console for one complaint."""
    complaint = _get_complaint(pk)
    return render(request, DETAIL_TEMPLATE, _detail_context(complaint))


@role_required(*ADMIN_ROLES)
@require_POST
def complaint_start_review(request, pk):
    complaint = _get_complaint(pk)
    try:
        services.start_review(complaint, request.user)
        messages.success(request, f"{complaint.reference} is now under review.")
    except services.WorkflowError as error:
        messages.error(request, str(error))
    return redirect("admin_dashboard:complaint_detail", pk=pk)


@role_required(*ADMIN_ROLES)
@require_POST
def complaint_reject(request, pk):
    complaint = _get_complaint(pk)
    form = ReasonForm(request.POST, prefix="reject")
    if form.is_valid():
        try:
            services.reject_complaint(complaint, request.user, form.cleaned_data["reason"])
            messages.success(request, f"{complaint.reference} was rejected.")
        except services.WorkflowError as error:
            messages.error(request, str(error))
        return redirect("admin_dashboard:complaint_detail", pk=pk)
    messages.error(request, "Please correct the errors below.")
    return render(request, DETAIL_TEMPLATE, _detail_context(complaint, reject_form=form))


@role_required(*ADMIN_ROLES)
@require_POST
def complaint_assign(request, pk):
    complaint = _get_complaint(pk)
    form = AssignWorkerForm(request.POST, prefix="assign")
    if form.is_valid():
        data = form.cleaned_data
        try:
            services.assign_worker(
                complaint, request.user, data["worker"], data["priority"], data["instructions"]
            )
            messages.success(request, f"{data['worker'].display_name} was assigned to {complaint.reference}.")
        except services.WorkflowError as error:
            messages.error(request, str(error))
        return redirect("admin_dashboard:complaint_detail", pk=pk)
    messages.error(request, "Please correct the errors below.")
    return render(request, DETAIL_TEMPLATE, _detail_context(complaint, assign_form=form))


@role_required(*ADMIN_ROLES)
@require_POST
def complaint_verify(request, pk):
    complaint = _get_complaint(pk)
    form = VerifyForm(request.POST, prefix="verify")
    if form.is_valid():
        try:
            services.verify_completion(complaint, request.user, form.cleaned_data["note"])
            messages.success(request, f"{complaint.reference} is resolved. The citizen was notified.")
        except services.WorkflowError as error:
            messages.error(request, str(error))
        return redirect("admin_dashboard:complaint_detail", pk=pk)
    messages.error(request, "Please correct the errors below.")
    return render(request, DETAIL_TEMPLATE, _detail_context(complaint, verify_form=form))


@role_required(*ADMIN_ROLES)
@require_POST
def complaint_rework(request, pk):
    complaint = _get_complaint(pk)
    form = ReasonForm(request.POST, prefix="rework")
    if form.is_valid():
        try:
            services.request_rework(complaint, request.user, form.cleaned_data["reason"])
            messages.success(request, f"{complaint.reference} was sent back to the worker.")
        except services.WorkflowError as error:
            messages.error(request, str(error))
        return redirect("admin_dashboard:complaint_detail", pk=pk)
    messages.error(request, "Please correct the errors below.")
    return render(request, DETAIL_TEMPLATE, _detail_context(complaint, rework_form=form))


@role_required(*ADMIN_ROLES)
def worker_overview(request):
    """Every active worker with the number of tasks at each stage."""
    status = Complaint.Status
    workers = (
        User.objects.filter(role=User.Role.WORKER, is_active=True)
        .annotate(
            pending_accept=Count("assigned_complaints", filter=Q(assigned_complaints__status=status.ASSIGNED)),
            in_progress=Count("assigned_complaints", filter=Q(assigned_complaints__status=status.ACCEPTED)),
            awaiting_verification=Count("assigned_complaints", filter=Q(assigned_complaints__status=status.COMPLETED)),
            resolved=Count("assigned_complaints", filter=Q(assigned_complaints__status=status.RESOLVED)),
        )
        .order_by("first_name", "username")
    )
    return render(request, "admin_dashboard/workers.html", {"workers": workers})