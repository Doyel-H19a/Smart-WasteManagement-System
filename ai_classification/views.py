"""Views for the waste classification interface."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User

from .classifier import DEMO_NOTICE, ClassifierUnavailable, InvalidImage
from .forms import ClassifyForm
from .models import WasteClassification
from .services import classify_and_store

# Besides the owner, these roles may open any stored result.
REVIEW_ROLES = (User.Role.MUNICIPAL_ADMIN, User.Role.SUPER_ADMIN)


def _is_demo_mode():
    return getattr(settings, "AI_CLASSIFIER_BACKEND", "demo") == "demo"


@login_required
def classify_view(request):
    """Upload form plus the user's recent results."""
    if request.method == "POST":
        form = ClassifyForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                record = classify_and_store(request.user, form.cleaned_data["image"])
                return redirect("ai_classification:result", pk=record.pk)
            except (ClassifierUnavailable, InvalidImage) as error:
                messages.error(request, str(error))
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ClassifyForm()

    return render(
        request,
        "ai_classification/classify.html",
        {
            "form": form,
            "recent": WasteClassification.objects.filter(user=request.user)[:10],
            "is_demo": _is_demo_mode(),
            "demo_notice": DEMO_NOTICE,
        },
    )


@login_required
def result_view(request, pk):
    """One classification result (owner, or Municipal/Super Admin)."""
    record = get_object_or_404(WasteClassification, pk=pk)
    if record.user_id != request.user.pk and request.user.role not in REVIEW_ROLES:
        raise PermissionDenied("You can only view your own classification results.")
    return render(
        request,
        "ai_classification/result.html",
        {"record": record, "is_demo": record.is_demo, "demo_notice": DEMO_NOTICE},
    )