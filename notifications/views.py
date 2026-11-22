"""Views for the notifications app."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_list(request):
    """All notifications for the logged-in user, newest first."""
    paginator = Paginator(Notification.objects.filter(recipient=request.user), 15)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "notifications/list.html",
        {"page_obj": page_obj, "page_title": "Notifications"},
    )


@login_required
def notification_open(request, pk):
    """Mark one of the user's notifications as read, then go to its link."""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=["is_read"])

    target = notification.link
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(target)
    return redirect("notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    """Mark every unread notification of the user as read."""
    updated = Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, f"{updated} notification(s) marked as read.")
    return redirect("notifications:list")