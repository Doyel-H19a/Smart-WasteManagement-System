"""Views for penalties."""
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from accounts.utils import int_param
from inspections.models import Inspection
from waste_management.models import Ward

from . import services
from .forms import DisputeForm, IssuePenaltyForm, PaymentForm, ReasonForm, RejectDisputeForm
from .models import Penalty
from .services import ISSUER_ROLES, RECIPIENT_ROLES, RESOLVER_ROLES

# Staff who may view every penalty (read-only unless they are issuers or resolvers).
STAFF_VIEW_ROLES = (
    User.Role.HEALTH_OFFICER,
    User.Role.MUNICIPAL_ADMIN,
    User.Role.EXECUTIVE_OFFICER,
    User.Role.SUPER_ADMIN,
)
LIST_ROLES = STAFF_VIEW_ROLES + RECIPIENT_ROLES
DETAIL_TEMPLATE = "penalties/detail.html"
PENALTY_RELATED = ("issued_to", "issued_by", "ward", "inspection", "resolved_by", "recorded_by")


def _detail_context(user, penalty, **bound_forms):
    """Template context for the detail page; bound (invalid) forms replace the blank ones."""
    is_open = penalty.status in Penalty.OPEN_STATUSES
    is_recipient = penalty.issued_to_id == user.pk
    is_resolver = user.role in RESOLVER_ROLES
    is_issuer = penalty.issued_by_id == user.pk

    context = {
        "penalty": penalty,
        "events": penalty.events.select_related("actor"),
        "is_recipient": is_recipient,
        "can_dispute": (
            is_recipient and penalty.status == Penalty.Status.ISSUED and penalty.disputed_at is None
        ),
        "can_record_payment": is_resolver and penalty.status == Penalty.Status.ISSUED,
        "can_decide": is_resolver and is_open and not is_issuer,
        "blocked_by_conflict": is_resolver and is_open and is_issuer,
        "dispute_form": DisputeForm(prefix="dispute"),
        "pay_form": PaymentForm(prefix="pay"),
        "reject_form": RejectDisputeForm(
            prefix="reject", initial={"new_due_date": timezone.localdate() + timedelta(days=14)}
        ),
        "waive_form": ReasonForm(prefix="waive"),
        "cancel_form": ReasonForm(prefix="cancel"),
    }
    context.update(bound_forms)
    return context


def _get_penalty(pk):
    return get_object_or_404(Penalty.objects.select_related(*PENALTY_RELATED), pk=pk)


@role_required(*LIST_ROLES)
def penalty_list(request):
    """Penalties with filters and totals. A recipient sees only their own."""
    user = request.user
    is_recipient = user.role in RECIPIENT_ROLES

    penalties = Penalty.objects.select_related("issued_to", "ward", "issued_by")
    if is_recipient:
        penalties = penalties.filter(issued_to=user)

    status = request.GET.get("status", "")
    if status in Penalty.Status.values:
        penalties = penalties.filter(status=status)
    else:
        status = ""

    ward = int_param(request.GET.get("ward", ""))
    if ward is not None:
        penalties = penalties.filter(ward_id=ward)

    query = request.GET.get("q", "").strip()
    if query and not is_recipient:
        penalties = penalties.filter(
            Q(issued_to__username__icontains=query)
            | Q(issued_to__first_name__icontains=query)
            | Q(issued_to__last_name__icontains=query)
            | Q(description__icontains=query)
        )

    overdue = request.GET.get("overdue") == "1"
    if overdue:
        penalties = penalties.filter(
            status=Penalty.Status.ISSUED, due_date__lt=timezone.localdate()
        )

    summary = services.summarise_penalties(penalties)
    page_obj = Paginator(penalties, 15).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)

    return render(
        request,
        "penalties/list.html",
        {
            "page_obj": page_obj,
            "summary": summary,
            "wards": Ward.objects.all(),
            "status_choices": Penalty.Status.choices,
            "selected_status": status,
            "selected_ward": "" if ward is None else str(ward),
            "q": query,
            "overdue": overdue,
            "query_string": params.urlencode(),
            "is_recipient": is_recipient,
            "can_issue": user.role in ISSUER_ROLES,
        },
    )


def _initial_from_inspection(request):
    """Pre-fill the issue form from ?inspection=<id>."""
    initial = {"due_date": timezone.localdate() + timedelta(days=14)}
    inspection_id = int_param(request.GET.get("inspection", ""))
    if inspection_id is None:
        return initial
    inspection = Inspection.objects.filter(pk=inspection_id).first()
    if inspection is None:
        return initial
    initial.update({"inspection": inspection.pk, "ward": inspection.ward_id})
    if inspection.bulk_generator_id:
        initial["issued_to"] = inspection.bulk_generator_id
        initial["violation_type"] = Penalty.Violation.BULK_NON_COMPLIANCE
    return initial


@role_required(*ISSUER_ROLES)
def penalty_create(request):
    """Issue a penalty."""
    if request.method == "POST":
        form = IssuePenaltyForm(request.POST)
        if form.is_valid():
            try:
                penalty = services.issue_penalty(form.save(commit=False), request.user)
                messages.success(
                    request, f"Penalty {penalty.reference} issued to {penalty.issued_to.display_name}."
                )
                return redirect(penalty)
            except services.PenaltyError as error:
                messages.error(request, str(error))
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = IssuePenaltyForm(initial=_initial_from_inspection(request))
    return render(request, "penalties/form.html", {"form": form})


@login_required
def penalty_detail(request, pk):
    """One penalty. The person penalised and staff roles only."""
    penalty = _get_penalty(pk)
    user = request.user
    if penalty.issued_to_id != user.pk and user.role not in STAFF_VIEW_ROLES:
        raise PermissionDenied("You can only view penalties issued to you.")
    return render(request, DETAIL_TEMPLATE, _detail_context(user, penalty))


@role_required(*RECIPIENT_ROLES)
@require_POST
def penalty_dispute(request, pk):
    """The person penalised disputes it (once)."""
    penalty = get_object_or_404(Penalty.objects.select_related(*PENALTY_RELATED), pk=pk, issued_to=request.user)
    form = DisputeForm(request.POST, prefix="dispute")
    if form.is_valid():
        try:
            services.dispute_penalty(penalty, request.user, form.cleaned_data["reason"])
            messages.success(request, "Your dispute was sent to the municipal office.")
        except services.PenaltyError as error:
            messages.error(request, str(error))
        return redirect("penalties:detail", pk=pk)
    messages.error(request, "Please correct the errors below.")
    return render(request, DETAIL_TEMPLATE, _detail_context(request.user, penalty, dispute_form=form))


@role_required(*RESOLVER_ROLES)
@require_POST
def penalty_pay(request, pk):
    """Record a payment received by the municipal office."""
    penalty = _get_penalty(pk)
    form = PaymentForm(request.POST, prefix="pay")
    if form.is_valid():
        try:
            services.record_payment(penalty, request.user, form.cleaned_data["reference"])
            messages.success(request, f"Payment recorded for {penalty.reference}.")
        except services.PenaltyError as error:
            messages.error(request, str(error))
        return redirect("penalties:detail", pk=pk)
    messages.error(request, "Please correct the errors below.")
    return render(request, DETAIL_TEMPLATE, _detail_context(request.user, penalty, pay_form=form))


@role_required(*RESOLVER_ROLES)
@require_POST
def penalty_reject_dispute(request, pk):
    """Reject a dispute: the penalty stands with a new due date."""
    penalty = _get_penalty(pk)
    form = RejectDisputeForm(request.POST, prefix="reject")
    if form.is_valid():
        try:
            services.reject_dispute(
                penalty, request.user, form.cleaned_data["note"], form.cleaned_data["new_due_date"]
            )
            messages.success(request, f"Dispute rejected. {penalty.reference} stands.")
        except services.PenaltyError as error:
            messages.error(request, str(error))
        return redirect("penalties:detail", pk=pk)
    messages.error(request, "Please correct the errors below.")
    return render(request, DETAIL_TEMPLATE, _detail_context(request.user, penalty, reject_form=form))


@role_required(*RESOLVER_ROLES)
@require_POST
def penalty_waive(request, pk):
    penalty = _get_penalty(pk)
    form = ReasonForm(request.POST, prefix="waive")
    if form.is_valid():
        try:
            services.waive_penalty(penalty, request.user, form.cleaned_data["reason"])
            messages.success(request, f"{penalty.reference} was waived.")
        except services.PenaltyError as error:
            messages.error(request, str(error))
        return redirect("penalties:detail", pk=pk)
    messages.error(request, "Please correct the errors below.")
    return render(request, DETAIL_TEMPLATE, _detail_context(request.user, penalty, waive_form=form))


@role_required(*RESOLVER_ROLES)
@require_POST
def penalty_cancel(request, pk):
    penalty = _get_penalty(pk)
    form = ReasonForm(request.POST, prefix="cancel")
    if form.is_valid():
        try:
            services.cancel_penalty(penalty, request.user, form.cleaned_data["reason"])
            messages.success(request, f"{penalty.reference} was cancelled.")
        except services.PenaltyError as error:
            messages.error(request, str(error))
        return redirect("penalties:detail", pk=pk)
    messages.error(request, "Please correct the errors below.")
    return render(request, DETAIL_TEMPLATE, _detail_context(request.user, penalty, cancel_form=form))