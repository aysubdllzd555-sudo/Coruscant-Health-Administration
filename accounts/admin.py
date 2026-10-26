from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CHAUserAdmin(UserAdmin):
    list_display = ("username", "display_name", "role", "is_approved", "department", "date_joined")
    list_filter = ("role", "is_approved", "rejected", "department")
    fieldsets = UserAdmin.fieldsets + (("CHA", {"fields": ("role", "is_approved", "rejected", "approved_at", "approved_by", "department", "phone")}),)
    actions = ["approve"]

    @admin.action(description="Approve selected registrations")
    def approve(self, request, queryset):
        for user in queryset:
            user.approve(request.user)
