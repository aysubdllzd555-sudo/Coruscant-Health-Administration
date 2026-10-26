from django.contrib import admin

from .models import AuditEvent, Department, Device, DoctorProfile, Document, Message, Order, Patient, Reading, Report, ServiceType


class ServiceInline(admin.TabularInline):
    model = ServiceType
    extra = 0


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "kind", "location")
    inlines = [ServiceInline]


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("mrn", "display_name", "age", "district", "primary_doctor", "ed_status", "acuity", "source")
    list_filter = ("ed_status", "source", "district", "acuity")
    search_fields = ("mrn", "first_name", "last_name")


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ("patient", "recorded_at", "heart_rate", "spo2", "temperature_c", "systolic", "resp_rate", "source")
    list_filter = ("source",)
    date_hierarchy = "recorded_at"


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """Ciphertext and wrapped keys are never displayed or editable."""

    list_display = ("title", "patient", "category", "size", "key_id", "uploaded_by", "created_at")
    exclude = ("wrapped_key", "nonce", "ciphertext")
    readonly_fields = ("uid", "sha256", "key_id", "size", "content_type", "original_name")


@admin.register(AuditEvent)
class AuditAdmin(admin.ModelAdmin):
    list_display = ("at", "actor", "action", "target", "patient", "ip")
    list_filter = ("action",)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register([DoctorProfile, Device, Report, Order, Message])
