"""Template context processors for the accounts app."""
from django.urls import reverse

from .navigation import get_menu_for_role


def sidebar_menu(request):
    """Build the role-specific sidebar for the logged-in user."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    items = []
    for label, icon, url_name in get_menu_for_role(user.role):
        url = reverse(url_name) if url_name else None
        items.append(
            {
                "label": label,
                "icon": icon,
                "url": url,
                "active": url is not None and request.path == url,
            }
        )
    return {"sidebar_menu": items, "role_label": user.get_role_display()}