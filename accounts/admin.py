from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ["username", "first_name", "last_name", "role", "is_approved"]
    list_filter = ["role", "is_approved"]
    fieldsets = UserAdmin.fieldsets + (
        ("Hospital", {"fields": ["role", "is_approved", "phone", "specialty", "license_number", "department"]}),
    )
