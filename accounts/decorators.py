from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def role_required(*roles):
    """Allows the view only for approved users with one of the given roles.
    Administrators can open every page."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            user = request.user
            if not user.is_approved:
                return redirect("pending")
            if user.role != "admin" and user.role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
