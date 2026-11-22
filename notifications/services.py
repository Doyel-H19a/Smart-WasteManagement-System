"""Notification helpers used by other apps."""
from .models import Notification


def notify(recipient, title, message="", category=Notification.Category.SYSTEM, link=""):
    """Create one notification for one user."""
    return Notification.objects.create(
        recipient=recipient, title=title, message=message, category=category, link=link
    )


def notify_many(recipients, title, message="", category=Notification.Category.SYSTEM, link=""):
    """Create the same notification for many users in a single query."""
    notifications = [
        Notification(recipient=user, title=title, message=message, category=category, link=link)
        for user in recipients
    ]
    return Notification.objects.bulk_create(notifications)