"""Views for ward management."""
from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from accounts.models import User

from .forms import WardForm
from .models import Ward

WARD_MANAGER_ROLES = (User.Role.MUNICIPAL_ADMIN, User.Role.SUPER_ADMIN)


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