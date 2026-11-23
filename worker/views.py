"""Views for waste workers (task list, accept, complete with proof)."""
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from complaints import services
from complaints.models import Complaint

from .forms import CompleteTaskForm

WORKER_ROLES = (User.Role.WORKER,)
Status = Complaint.Status

ACTIVE_STATUSES = (Status.ASSIGNED, Status.ACCEPTED)
DONE_STATUSES = (Status.COMPLETED, Status.RESOLVED)
DETAIL_TEMPLATE = "worker/task_detail.html"


def _get_task(request, pk):
    """A worker can only open complaints that are assigned to them (else 404)."""
    return get_object_or_404(
        Complaint.objects.select_related("ward", "citizen"),
        pk=pk,
        assigned_worker=request.user,
    )


def _detail_context(complaint, form=None):
    return {
        "complaint": complaint,
        "history": complaint.history.select_related("changed_by"),
        "complete_form": form or CompleteTaskForm(),
    }


@role_required(*WORKER_ROLES)
def task_list(request):
    """The worker's tasks, split into Active and Done tabs."""
    tab = request.GET.get("tab", "active")
    if tab not in ("active", "done"):
        tab = "active"

    mine = Complaint.objects.filter(assigned_worker=request.user)
    statuses = ACTIVE_STATUSES if tab == "active" else DONE_STATUSES
    tasks = mine.filter(status__in=statuses).select_related("ward").order_by("-assigned_at", "-created_at")

    page_obj = Paginator(tasks, 10).get_page(request.GET.get("page"))
    return render(
        request,
        "worker/task_list.html",
        {
            "page_obj": page_obj,
            "tab": tab,
            "query_string": f"tab={tab}",
            "active_count": mine.filter(status__in=ACTIVE_STATUSES).count(),
            "done_count": mine.filter(status__in=DONE_STATUSES).count(),
        },
    )


@role_required(*WORKER_ROLES)
def task_detail(request, pk):
    complaint = _get_task(request, pk)
    return render(request, DETAIL_TEMPLATE, _detail_context(complaint))


@role_required(*WORKER_ROLES)
@require_POST
def task_accept(request, pk):
    complaint = _get_task(request, pk)
    try:
        services.accept_assignment(complaint, request.user)
        messages.success(request, f"You accepted task {complaint.reference}.")
    except services.WorkflowError as error:
        messages.error(request, str(error))
    return redirect("worker:task_detail", pk=pk)


@role_required(*WORKER_ROLES)
@require_POST
def task_complete(request, pk):
    complaint = _get_task(request, pk)
    form = CompleteTaskForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            services.complete_task(
                complaint,
                request.user,
                form.cleaned_data["completion_note"],
                form.cleaned_data["proof_image"],
            )
            messages.success(request, "Task completed. The municipal office will verify your proof.")
        except services.WorkflowError as error:
            messages.error(request, str(error))
        return redirect("worker:task_detail", pk=pk)
    messages.error(request, "Please correct the errors below.")
    return render(request, DETAIL_TEMPLATE, _detail_context(complaint, form))