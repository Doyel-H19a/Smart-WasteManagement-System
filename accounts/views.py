"""Views for authentication, dashboard and profile."""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

from complaints.services import get_citizen_summary

from .forms import LoginForm, ProfileForm, RegistrationForm
from .models import User
from .navigation import ROLE_DESCRIPTIONS, ROLE_ICONS


class SwachhLoginView(LoginView):
    """Login page; logged-in users are sent straight to their dashboard."""

    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f"Welcome back, {form.get_user().display_name}!")
        return super().form_valid(form)


def register_view(request):
    """Public registration for Citizen, Green Champion and Bulk Waste Generator."""
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Your account has been created. Welcome to SwachhAI!")
            return redirect("accounts:dashboard")
        messages.error(request, "Please correct the errors below.")
    else:
        form = RegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
def dashboard_view(request):
    """Role-aware dashboard. Citizens also see their complaint statistics."""
    user = request.user
    context = {
        "page_title": f"{user.get_role_display()} Dashboard",
        "role_description": ROLE_DESCRIPTIONS.get(user.role, ""),
        "role_icon": ROLE_ICONS.get(user.role, "bi-person"),
    }
    if user.role == User.Role.CITIZEN:
        context["complaint_summary"] = get_citizen_summary(user)
    return render(request, "dashboard/role_dashboard.html", context)


@login_required
def profile_view(request):
    """Edit the logged-in user's profile."""
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile")
        messages.error(request, "Please correct the errors below.")
    else:
        form = ProfileForm(instance=request.user)

    return render(request, "accounts/profile.html", {"form": form, "page_title": "My Profile"})