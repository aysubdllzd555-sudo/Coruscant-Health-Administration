from django.contrib import admin

from .models import Document, Message, Order, Patient, Reading, Report


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["full_name", "doctor", "is_emergency", "priority"]
    search_fields = ["full_name"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "patient", "uploaded_by", "created_at"]
    exclude = ["nonce", "encrypted_data"]  # never show encrypted bytes


admin.site.register([Reading, Report, Order, Message])
