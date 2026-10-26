from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def role_required(*roles):
    """Requires an authenticated, administrator-approved user holding one of `roles`.
    Administrators always pass."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            user = request.user
            if not user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if not (user.is_approved or user.is_superuser):
                return redirect("accounts:pending")
            if roles and not (user.is_admin_role or user.role in roles):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


approved_required = role_required()
