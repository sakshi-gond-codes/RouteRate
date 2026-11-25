"""Role checks used by views. Access is always enforced on the server, never only in templates."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Allow the view only for users with one of the given roles (superusers always pass)."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(request, *args, **kwargs):
            user = request.user
            if user.is_superuser or user.role in roles:
                return view(request, *args, **kwargs)
            raise PermissionDenied("Your role does not allow this action.")

        return wrapped

    return decorator


def rate_manager_required(view):
    """Admin or Rate Analyst."""
    return role_required("admin", "analyst")(view)


def admin_required(view):
    return role_required("admin")(view)
