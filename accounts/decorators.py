"""Role-based access control decorators."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*allowed_roles):
    """Allow only logged-in users whose role is in allowed_roles (else HTTP 403)."""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if request.user.role not in allowed_roles:
                raise PermissionDenied("You do not have permission to view this page.")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator