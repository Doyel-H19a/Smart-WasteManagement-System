"""Template context for the notification bell in the top bar."""
from .models import Notification


def notification_summary(request):
    """Unread count and the five most recent notifications for the logged-in user."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    queryset = Notification.objects.filter(recipient=user)
    return {
        "unread_notification_count": queryset.filter(is_read=False).count(),
        "recent_notifications": list(queryset[:5]),
    }